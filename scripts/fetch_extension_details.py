#!/usr/bin/env python3
"""Fetch metadata and GitHub star counts for every community extension.

For each community extension seen in the download statistics, read its
description.yml from the duckdb/community-extensions repository and the star
count of its GitHub repository.

Outputs:

    data/extension_details/extension_details.parquet   current snapshot, rewritten only when something changed
    data/star_history/date=YYYY-MM-DD/stars.parquet    one file per day, so star growth can be charted

The snapshot is written uncompressed and without a timestamp column so that git can
store it as a small delta from day to day instead of a fresh 700 KB blob.

Requires GITHUB_TOKEN in the environment for the GitHub API.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests
import yaml
from markdown import markdown
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DESCRIPTION_URL = "https://raw.githubusercontent.com/duckdb/community-extensions/main/extensions/{name}/description.yml"
GITHUB_API = "https://api.github.com"
USER_AGENT = (
    "duckdb-community-extension-analysis/1.0 "
    "(+https://github.com/dtenwolde/duckdb-community-extension-analysis)"
)
REQUEST_TIMEOUT = 30
# Refuse to overwrite the snapshot when more than this share of extensions failed,
# so a GitHub outage cannot wipe the details table.
MAX_FAILURE_RATIO = 0.2

COLUMNS = [
    ("extension", "VARCHAR"),
    ("repo_url", "VARCHAR"),
    ("star_count", "INTEGER"),
    ("extended_description", "VARCHAR"),
    ("extended_description_html", "VARCHAR"),
    ("hello_world", "VARCHAR"),
    ("hello_world_html", "VARCHAR"),
    ("version", "VARCHAR"),
    ("description", "VARCHAR"),
    ("build", "VARCHAR"),
    ("language", "VARCHAR"),
    ("license", "VARCHAR"),
    ("maintainers", "VARCHAR"),
    ("excluded_platforms", "VARCHAR"),
    ("excluded_platforms_html", "VARCHAR"),
    ("requires_toolchains", "VARCHAR"),
    ("ref", "VARCHAR"),
    ("fetched_at", "TIMESTAMPTZ"),
]

log = logging.getLogger("fetch_extension_details")


def make_session(token: str | None) -> requests.Session:
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
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def community_extensions(conn: duckdb.DuckDBPyConnection, downloads_dir: Path) -> list[str]:
    pattern = str(downloads_dir / "**" / "*.parquet")
    rows = conn.execute(
        "SELECT DISTINCT extension FROM read_parquet(?) WHERE type = 'Community' ORDER BY extension", [pattern]
    ).fetchall()
    return [r[0] for r in rows]


def fetch_description(session: requests.Session, name: str) -> dict | None:
    response = session.get(DESCRIPTION_URL.format(name=name), timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None  # extension removed from the registry
    response.raise_for_status()
    data = yaml.safe_load(response.text)
    return data if isinstance(data, dict) else None


def fetch_stars(session: requests.Session, repo: str) -> int | None:
    response = session.get(f"{GITHUB_API}/repos/{repo}", timeout=REQUEST_TIMEOUT)
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining is not None and int(remaining) < 50:
        log.warning("GitHub API rate limit nearly exhausted: %s requests remaining", remaining)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("stargazers_count")


def markdown_or_none(text: str | None) -> str | None:
    return markdown(text) if text else None


def as_dict(value) -> dict:
    """description.yml sections are sometimes a bare string instead of a mapping."""
    return value if isinstance(value, dict) else {}


def build_row(name: str, desc: dict, star_count: int | None, fetched_at: datetime) -> tuple:
    ext = as_dict(desc.get("extension"))
    repo = as_dict(desc.get("repo"))
    docs = as_dict(desc.get("docs"))

    maintainers = ext.get("maintainers") or []
    if isinstance(maintainers, str):
        maintainers = [maintainers]

    excluded_raw = ext.get("excluded_platforms") or ""
    excluded_md = (
        "\n".join(f"- {p.strip()}" for p in str(excluded_raw).split(";") if p.strip()) if excluded_raw else "- None"
    )

    return (
        name,
        repo.get("github"),
        star_count,
        docs.get("extended_description"),
        markdown_or_none(docs.get("extended_description")),
        docs.get("hello_world"),
        markdown_or_none(docs.get("hello_world")),
        str(ext["version"]) if ext.get("version") is not None else None,
        ext.get("description"),
        ext.get("build"),
        ext.get("language"),
        ext.get("license"),
        ", ".join(maintainers),
        excluded_md,
        markdown(excluded_md),
        str(ext.get("requires_toolchains") or ""),
        str(repo.get("ref") or ""),
        fetched_at,
    )


def write_parquet(conn: duckdb.DuckDBPyConnection, query: str, target: Path, compression: str = "ZSTD") -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".parquet.tmp")
    os.close(fd)
    try:
        conn.execute(f"COPY ({query}) TO ? (FORMAT PARQUET, COMPRESSION {compression})", [tmp_name])
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def snapshot_unchanged(conn: duckdb.DuckDBPyConnection, query: str, existing: Path) -> bool:
    """True when the new rows are identical to the rows already on disk."""
    try:
        diff = conn.execute(
            f"SELECT count(*) FROM (({query}) EXCEPT ALL (SELECT * FROM read_parquet(?)))"
            f" UNION ALL SELECT count(*) FROM ((SELECT * FROM read_parquet(?)) EXCEPT ALL ({query}))",
            [str(existing), str(existing)],
        ).fetchall()
    except duckdb.Error as exc:  # e.g. schema changed between versions of this script
        log.debug("Could not compare with existing snapshot: %s", exc)
        return False
    return all(row[0] == 0 for row in diff)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        log.error("GITHUB_TOKEN is not set; the GitHub API allows only 60 anonymous requests per hour")
        return 2

    session = make_session(token)
    conn = duckdb.connect()
    fetched_at = datetime.now(timezone.utc)

    names = community_extensions(conn, args.data_dir / "downloads")
    log.info("Fetching details for %d community extensions", len(names))

    rows: list[tuple] = []
    failures: list[str] = []
    removed: list[str] = []
    for name in names:
        try:
            desc = fetch_description(session, name)
            if desc is None:
                removed.append(name)
                continue
            repo = as_dict(desc.get("repo")).get("github")
            stars = fetch_stars(session, repo) if repo else None
            rows.append(build_row(name, desc, stars, fetched_at))
            log.debug("%s: %s stars", name, stars)
        except (requests.RequestException, yaml.YAMLError) as exc:
            log.error("%s: %s", name, exc)
            failures.append(name)

    log.info("%d processed, %d no longer in registry, %d failed", len(rows), len(removed), len(failures))
    if removed:
        log.info("Not in registry: %s", ", ".join(removed))
    if names and len(failures) / len(names) > MAX_FAILURE_RATIO:
        log.error("Too many failures (%d of %d); keeping the existing snapshot", len(failures), len(names))
        return 1

    schema = ", ".join(f"{col} {typ}" for col, typ in COLUMNS)
    conn.execute(f"CREATE TEMP TABLE details ({schema})")
    conn.executemany(f"INSERT INTO details VALUES ({', '.join('?' for _ in COLUMNS)})", rows)

    snapshot = args.data_dir / "extension_details" / "extension_details.parquet"
    snapshot_query = "SELECT * EXCLUDE (fetched_at) FROM details ORDER BY extension"
    if snapshot.exists() and snapshot_unchanged(conn, snapshot_query, snapshot):
        log.info("extension_details.parquet unchanged")
    else:
        write_parquet(conn, snapshot_query, snapshot, compression="UNCOMPRESSED")
        log.info("Wrote %s", snapshot)

    write_parquet(
        conn,
        "SELECT extension, repo_url, star_count, fetched_at FROM details ORDER BY extension",
        args.data_dir / "star_history" / f"date={fetched_at:%Y-%m-%d}" / "stars.parquet",
    )
    log.info("Wrote star_history/date=%s", f"{fetched_at:%Y-%m-%d}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
