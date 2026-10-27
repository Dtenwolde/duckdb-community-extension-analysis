#!/usr/bin/env python3
"""Fetch DuckDB client-library download statistics from public package registries.

Two datasets are produced under data/:

1. client_downloads/channel=NAME/year=YYYY/month=MM/client_downloads.parquet
   Daily download counts with history (backfilled from each registry's API):
     pypi    duckdb                      total, by operating system, by Python minor version
     npm     @duckdb/node-api, @duckdb/duckdb-wasm   (legacy `duckdb` package: snapshot totals only)
     cran    duckdb
     crates  duckdb                      total, by crate version (registry keeps 90 days)
   Months within the refresh window are rewritten every run because registries publish
   counts with a delay of several days; older months are only written when missing.
   History depth per registry: PyPI ~180 days, npm 365 days, crates.io 90 days, CRAN full.

2. client_snapshots/date=YYYY-MM-DD/client_snapshots.parquet
   Running totals that registries expose without history, captured once per run:
   NuGet, conda-forge, Homebrew, Docker Hub, GitHub repository metrics, GitHub release
   asset download counts, crates.io lifetime totals and PyPI recent windows.

Requires GITHUB_TOKEN for the GitHub API.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "duckdb-community-extension-analysis/1.0 "
    "(+https://github.com/dtenwolde/duckdb-community-extension-analysis)"
)
REQUEST_TIMEOUT = 60
REFRESH_DAYS = 45  # npm and PyPI publish counts a few days late and revise recent days
HISTORY_START = date(2019, 1, 1)

NPM_PACKAGES = ["@duckdb/node-api", "@duckdb/duckdb-wasm"]
# The legacy unscoped package has years of history and its daily endpoint answers 502;
# only its point totals work, so it is tracked as a snapshot.
NPM_SNAPSHOT_PACKAGES = ["duckdb", "@duckdb/node-api", "@duckdb/duckdb-wasm"]
NUGET_PACKAGES = ["DuckDB.NET.Data.Full", "DuckDB.NET.Data", "DuckDB.NET.Bindings.Full", "DuckDB.NET.Bindings"]
CONDA_PACKAGES = ["python-duckdb", "duckdb", "libduckdb", "duckdb-cli", "r-duckdb"]

log = logging.getLogger("fetch_client_stats")


class FetchError(Exception):
    pass


def make_session(github_token: str | None) -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=2.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.github_headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    return session


def get_json(session: requests.Session, url: str, **kwargs):
    response = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    if response.status_code != 200:
        raise FetchError(f"{url} returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise FetchError(f"{url} is not valid JSON: {exc}") from exc


# ----------------------------------------------------------------------------- daily history
# Row shape: (channel, package, date, dimension, dimension_value, downloads)

def fetch_pypi(session) -> list[tuple]:
    rows = []
    overall = get_json(session, "https://pypistats.org/api/packages/duckdb/overall?mirrors=false")["data"]
    for r in overall:
        rows.append(("pypi", "duckdb", date.fromisoformat(r["date"]), "total", None, int(r["downloads"])))
    for dimension, endpoint in (("os", "system"), ("python_minor", "python_minor")):
        data = get_json(session, f"https://pypistats.org/api/packages/duckdb/{endpoint}")["data"]
        for r in data:
            value = None if r["category"] in (None, "null") else str(r["category"])
            rows.append(("pypi", "duckdb", date.fromisoformat(r["date"]), dimension, value or "unknown", int(r["downloads"])))
    return rows


def fetch_npm(session, start: date, end: date) -> list[tuple]:
    """npm's download API only answers reliably for its named ranges, so history is limited to
    the last 365 days per request; the nightly runs accumulate the rest over time."""
    rows = []
    for package in NPM_PACKAGES:
        data = get_json(session, f"https://api.npmjs.org/downloads/range/last-year/{package}")
        for r in data.get("downloads", []):
            day = date.fromisoformat(r["day"])
            # npm returns 0 for days it has not processed yet (sometimes a week back); skip
            # them so they are not stored as real zeros. They arrive in a later refresh.
            if start <= day <= end and int(r["downloads"]) > 0:
                rows.append(("npm", package, day, "total", None, int(r["downloads"])))
    return rows


def fetch_cran(session, start: date, end: date) -> list[tuple]:
    data = get_json(session, f"https://cranlogs.r-pkg.org/downloads/daily/{start}:{end}/duckdb")
    rows = []
    for entry in data:
        for r in entry.get("downloads", []):
            rows.append(("cran", "duckdb", date.fromisoformat(r["day"]), "total", None, int(r["downloads"])))
    return rows


def fetch_crates(session) -> tuple[list[tuple], dict]:
    crate = get_json(session, "https://crates.io/api/v1/crates/duckdb")
    version_num = {v["id"]: v["num"] for v in crate.get("versions", [])}
    data = get_json(session, "https://crates.io/api/v1/crates/duckdb/downloads")
    per_day: dict[date, int] = defaultdict(int)
    rows = []
    for r in data["version_downloads"]:
        day = date.fromisoformat(r["date"])
        rows.append(("crates", "duckdb", day, "version", version_num.get(r["version"], str(r["version"])), int(r["downloads"])))
        per_day[day] += int(r["downloads"])
    for r in data.get("meta", {}).get("extra_downloads", []):  # downloads not attributed to a version
        per_day[date.fromisoformat(r["date"])] += int(r["downloads"])
    for day, n in per_day.items():
        rows.append(("crates", "duckdb", day, "total", None, n))
    return rows, crate["crate"]


# ----------------------------------------------------------------------------- snapshots
# Row shape: (channel, package, metric, item, sub_item, value)

def snapshot_nuget(session) -> list[tuple]:
    rows = []
    for package in NUGET_PACKAGES:
        data = get_json(session, f"https://azuresearch-usnc.nuget.org/query?q=packageid:{package}&prerelease=true")
        for p in data.get("data", []):
            if p["id"].lower() == package.lower():
                rows.append(("nuget", p["id"], "total_downloads", None, None, int(p["totalDownloads"])))
    return rows


def snapshot_conda(session) -> list[tuple]:
    rows = []
    for package in CONDA_PACKAGES:
        data = get_json(session, f"https://api.anaconda.org/package/conda-forge/{package}")
        files = data.get("files", [])
        rows.append(("conda-forge", package, "total_downloads", None, None, sum(int(f.get("ndownloads", 0)) for f in files)))
        rows.append(("conda-forge", package, "files", None, None, len(files)))
    return rows


def snapshot_homebrew(session) -> list[tuple]:
    data = get_json(session, "https://formulae.brew.sh/api/formula/duckdb.json")
    rows = []
    for metric, windows in data.get("analytics", {}).items():
        if metric == "build_error":
            continue
        for window, counts in windows.items():
            rows.append(("homebrew", "duckdb", f"{metric}_{window}", None, None, int(counts.get("duckdb", 0))))
    return rows


def snapshot_docker(session) -> list[tuple]:
    data = get_json(session, "https://hub.docker.com/v2/repositories/duckdb/duckdb/")
    return [
        ("docker", "duckdb/duckdb", "pull_count", None, None, int(data["pull_count"])),
        ("docker", "duckdb/duckdb", "star_count", None, None, int(data.get("star_count", 0))),
    ]


def snapshot_github(session) -> list[tuple]:
    headers = session.github_headers
    repo = get_json(session, "https://api.github.com/repos/duckdb/duckdb", headers=headers)
    rows = [
        ("github", "duckdb/duckdb", "stars", None, None, int(repo["stargazers_count"])),
        ("github", "duckdb/duckdb", "forks", None, None, int(repo["forks_count"])),
        ("github", "duckdb/duckdb", "open_issues", None, None, int(repo["open_issues_count"])),
        ("github", "duckdb/duckdb", "subscribers", None, None, int(repo["subscribers_count"])),
    ]
    page = 1
    while True:
        releases = get_json(session, f"https://api.github.com/repos/duckdb/duckdb/releases?per_page=100&page={page}", headers=headers)
        if not releases:
            break
        for rel in releases:
            tag = rel["tag_name"]
            published = (rel.get("published_at") or "")[:10]
            for asset in rel.get("assets", []):
                rows.append(("github_releases", "duckdb/duckdb", "asset_downloads", tag, asset["name"], int(asset["download_count"])))
            rows.append(("github_releases", "duckdb/duckdb", "release_downloads", tag, published, sum(int(a["download_count"]) for a in rel.get("assets", []))))
        page += 1
    return rows


def snapshot_npm_points(session) -> list[tuple]:
    """npm's API answers 5xx intermittently; keep whatever succeeds and only fail when nothing did."""
    rows = []
    errors = []
    for package in NPM_SNAPSHOT_PACKAGES:
        for window in ("last-week", "last-month", "last-year"):
            try:
                data = get_json(session, f"https://api.npmjs.org/downloads/point/{window}/{package}")
                rows.append(("npm", package, f"downloads_{window.replace('-', '_')}", None, None, int(data["downloads"])))
            except (FetchError, requests.RequestException, KeyError, ValueError) as exc:
                errors.append(f"{package} {window}: {exc}")
    for err in errors:
        log.warning("npm totals: %s", err)
    if errors and not rows:
        raise FetchError("all npm point requests failed")
    return rows


def snapshot_pypi_recent(session) -> list[tuple]:
    data = get_json(session, "https://pypistats.org/api/packages/duckdb/recent")["data"]
    return [("pypi", "duckdb", f"recent_{k}", None, None, int(v)) for k, v in data.items()]


def snapshot_crates(crate: dict) -> list[tuple]:
    return [
        ("crates", "duckdb", "total_downloads", None, None, int(crate["downloads"])),
        ("crates", "duckdb", "recent_downloads_90d", None, None, int(crate["recent_downloads"])),
    ]


# ----------------------------------------------------------------------------- writing

def write_parquet(conn, query: str, target: Path, params: list | None = None) -> bool:
    """Write query result to target; returns False when the existing file already had identical bytes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".parquet.tmp")
    os.close(fd)
    try:
        conn.execute(f"COPY ({query}) TO '{tmp_name}' (FORMAT PARQUET, COMPRESSION ZSTD)", params or [])
        if target.exists() and target.read_bytes() == Path(tmp_name).read_bytes():
            return False
        os.replace(tmp_name, target)
        return True
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def write_daily(conn, rows: list[tuple], data_dir: Path, refresh_from: date) -> None:
    """One file per channel and month. Channels are separate files so that a registry that
    fails tonight leaves every other registry's history untouched."""
    conn.execute("CREATE OR REPLACE TEMP TABLE daily (channel VARCHAR, package VARCHAR, date DATE, dimension VARCHAR, dimension_value VARCHAR, downloads BIGINT)")
    conn.executemany("INSERT INTO daily VALUES (?, ?, ?, ?, ?, ?)", rows)
    parts = conn.execute("SELECT DISTINCT channel, date_trunc('month', date)::DATE FROM daily ORDER BY 1, 2").fetchall()
    written = skipped = unchanged = 0
    for channel, month in parts:
        target = data_dir / "client_downloads" / f"channel={channel}" / f"year={month.year}" / f"month={month.month:02d}" / "client_downloads.parquet"
        month_end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        if target.exists() and month_end < refresh_from:
            skipped += 1
            continue
        changed = write_parquet(
            conn,
            "SELECT package, date, dimension, dimension_value, downloads FROM daily "
            "WHERE channel = ? AND date_trunc('month', date) = ? ORDER BY package, dimension, dimension_value, date",
            target,
            [channel, month],
        )
        written += changed
        unchanged += not changed
    log.info("Daily history: %d channel-months written, %d unchanged, %d outside refresh window", written, unchanged, skipped)


def write_snapshot(conn, rows: list[tuple], data_dir: Path, fetched_at: datetime) -> None:
    conn.execute("CREATE OR REPLACE TEMP TABLE snap (channel VARCHAR, package VARCHAR, metric VARCHAR, item VARCHAR, sub_item VARCHAR, value BIGINT, fetched_at TIMESTAMPTZ)")
    conn.executemany("INSERT INTO snap VALUES (?, ?, ?, ?, ?, ?, ?)", [r + (fetched_at,) for r in rows])
    target = data_dir / "client_snapshots" / f"date={fetched_at:%Y-%m-%d}" / "client_snapshots.parquet"
    write_parquet(conn, "SELECT * FROM snap ORDER BY channel, package, metric, item, sub_item", target)
    log.info("Snapshot: %d rows -> %s", len(rows), target)


# ----------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--refresh-days", default=REFRESH_DAYS, type=int)
    parser.add_argument("--all", action="store_true", help="rewrite every month, not only the refresh window")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        log.warning("GITHUB_TOKEN is not set; GitHub metrics will use the anonymous rate limit")

    session = make_session(token)
    conn = duckdb.connect()
    now = datetime.now(timezone.utc)
    today = now.date()
    refresh_from = HISTORY_START if args.all else today - timedelta(days=args.refresh_days)

    daily: list[tuple] = []
    snapshots: list[tuple] = []
    failures: list[str] = []
    daily_failures: list[str] = []

    def run(name, fn, *fn_args):
        try:
            return fn(*fn_args)
        except (FetchError, requests.RequestException, KeyError, ValueError) as exc:
            log.error("%s: %s", name, exc)
            failures.append(name)
            return None

    for name, fn, fn_args in (
        ("pypi daily", fetch_pypi, (session,)),
        ("npm daily", fetch_npm, (session, HISTORY_START, today)),
        ("cran daily", fetch_cran, (session, HISTORY_START, today)),
    ):
        if (r := run(name, fn, *fn_args)) is not None:
            daily += r
        else:
            daily_failures.append(name)
    if (r := run("crates daily", fetch_crates, session)) is not None:
        rows, crate = r
        daily += rows
        snapshots += snapshot_crates(crate)
    else:
        daily_failures.append("crates daily")

    for name, fn in (
        ("nuget", snapshot_nuget),
        ("conda-forge", snapshot_conda),
        ("homebrew", snapshot_homebrew),
        ("docker", snapshot_docker),
        ("github", snapshot_github),
        ("npm totals", snapshot_npm_points),
        ("pypi recent", snapshot_pypi_recent),
    ):
        if (r := run(name, fn, session)) is not None:
            snapshots += r

    for channel in ("pypi", "npm", "cran", "crates"):
        n = sum(1 for row in daily if row[0] == channel)
        log.info("%-7s %6d daily rows", channel, n)
    if daily_failures:
        log.error("Daily history not updated for: %s (other channels are written)", ", ".join(daily_failures))
    if daily:
        write_daily(conn, daily, args.data_dir, refresh_from)
    if snapshots:
        write_snapshot(conn, snapshots, args.data_dir, now)

    if failures:
        log.error("Failed sources: %s", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
