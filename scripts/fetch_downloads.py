#!/usr/bin/env python3
"""Fetch weekly DuckDB extension download statistics into hive-partitioned Parquet.

Upstream publishes one JSON file per ISO week for core ("Regular") extensions and
one for community extensions.  The file for the current week is rewritten every
night until the week ends, so recent weeks are always re-fetched while older
weeks are only fetched when they are missing locally.

Output layout (one file per ISO week, both registries in the same file):

    data/downloads/year=2026/week=43/downloads.parquet

Columns: extension, type, downloads_last_week, week_start, source_last_update, fetched_at
The partition columns (year, week) live in the directory names only.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ENDPOINTS = {
    "Regular": "https://extensions.duckdb.org/download-stats-weekly",
    "Community": "https://community-extensions.duckdb.org/download-stats-weekly",
}
FIRST_WEEK = (2024, 40)  # first week with published community statistics
USER_AGENT = (
    "duckdb-community-extension-analysis/1.0 "
    "(+https://github.com/dtenwolde/duckdb-community-extension-analysis)"
)
REQUEST_TIMEOUT = 30  # seconds
SPIKE_RATIO = 3.0  # warn when a week's total differs this much from the previous week

log = logging.getLogger("fetch_downloads")


class WeekFetchError(Exception):
    """Raised when a week cannot be fetched for a reason other than 'not published'."""


def make_session() -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def iter_weeks(first: tuple[int, int], last: tuple[int, int]):
    """Yield (iso_year, iso_week) from first to last inclusive."""
    current = date.fromisocalendar(first[0], first[1], 1)
    end = date.fromisocalendar(last[0], last[1], 1)
    while current <= end:
        year, week, _ = current.isocalendar()
        yield year, week
        current += timedelta(weeks=1)


def parse_timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        log.warning("Unparseable _last_update %r", value)
        return None


def fetch_week_type(session: requests.Session, type_: str, year: int, week: int) -> list[tuple] | None:
    """Return rows for one registry and week, or None when upstream has no file."""
    url = f"{ENDPOINTS[type_]}/{year}/{week:02d}.json"
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise WeekFetchError(f"{url} returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise WeekFetchError(f"{url} is not valid JSON: {exc}") from exc

    source_last_update = parse_timestamp(payload.get("_last_update"))
    week_start = date.fromisocalendar(year, week, 1)
    fetched_at = datetime.now(timezone.utc)
    rows = []
    for extension, count in payload.items():
        if extension == "_last_update":
            continue
        if not isinstance(count, int):
            log.warning("Skipping %s/%s: non-integer count %r", type_, extension, count)
            continue
        rows.append((extension, type_, count, week_start, source_last_update, fetched_at))
    return rows


def write_parquet(conn: duckdb.DuckDBPyConnection, rows: list[tuple], target: Path) -> None:
    """Write rows to target atomically (write to a temp file in the same directory, then rename)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    conn.execute("CREATE OR REPLACE TEMP TABLE week_rows AS SELECT * FROM downloads_schema LIMIT 0")
    conn.executemany("INSERT INTO week_rows VALUES (?, ?, ?, ?, ?, ?)", rows)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".parquet.tmp")
    os.close(fd)
    try:
        conn.execute(
            "COPY (SELECT * FROM week_rows ORDER BY type, extension) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [tmp_name],
        )
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def week_total(conn: duckdb.DuckDBPyConnection, path: Path) -> int | None:
    if not path.exists():
        return None
    return conn.execute("SELECT sum(downloads_last_week) FROM read_parquet(?)", [str(path)]).fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data/downloads", type=Path, help="output directory")
    parser.add_argument("--refresh-weeks", default=3, type=int, help="always re-fetch this many most recent weeks")
    parser.add_argument("--all", action="store_true", help="re-fetch every week, not only missing and recent ones")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    today = datetime.now(timezone.utc).date()
    current_week = today.isocalendar()[:2]
    refresh_from = (today - timedelta(weeks=args.refresh_weeks - 1)).isocalendar()[:2]

    session = make_session()
    conn = duckdb.connect()
    conn.execute(
        """
        CREATE TEMP TABLE downloads_schema (
            extension VARCHAR,
            type VARCHAR,
            downloads_last_week BIGINT,
            week_start DATE,
            source_last_update TIMESTAMPTZ,
            fetched_at TIMESTAMPTZ
        )
        """
    )

    failures: list[str] = []
    written = skipped = unpublished = 0
    previous_total: int | None = None

    for year, week in iter_weeks(FIRST_WEEK, current_week):
        target = args.data_dir / f"year={year}" / f"week={week:02d}" / "downloads.parquet"
        is_recent = (year, week) >= refresh_from
        if target.exists() and not is_recent and not args.all:
            skipped += 1
            previous_total = week_total(conn, target)
            continue

        rows: list[tuple] = []
        try:
            for type_ in ENDPOINTS:
                type_rows = fetch_week_type(session, type_, year, week)
                if type_rows is None:
                    log.debug("%d-W%02d %s: not published", year, week, type_)
                else:
                    rows.extend(type_rows)
        except (WeekFetchError, requests.RequestException) as exc:
            # Never overwrite an existing week with partial data.
            log.error("%d-W%02d: %s", year, week, exc)
            failures.append(f"{year}-W{week:02d}")
            previous_total = week_total(conn, target)
            continue

        if not rows:
            unpublished += 1
            log.info("%d-W%02d: nothing published upstream", year, week)
            continue

        write_parquet(conn, rows, target)
        written += 1
        total = sum(r[2] for r in rows)
        log.info("%d-W%02d: wrote %d rows, %d downloads -> %s", year, week, len(rows), total, target)
        if previous_total and total and max(total / previous_total, previous_total / total) > SPIKE_RATIO:
            log.warning(
                "%d-W%02d: total downloads %d differ more than %.0fx from previous week (%d); check upstream",
                year, week, total, SPIKE_RATIO, previous_total,
            )
        previous_total = total

    log.info("Done: %d weeks written, %d unchanged, %d unpublished, %d failed", written, skipped, unpublished, len(failures))
    if failures:
        log.error("Failed weeks: %s", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
