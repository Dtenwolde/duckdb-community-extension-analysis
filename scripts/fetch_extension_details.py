#!/usr/bin/env python3
"""Fetch metadata and GitHub star counts for every community extension.

For each community extension seen in the download statistics, read its
description.yml from the duckdb/community-extensions repository and the star
count of its GitHub repository.

The number of HTTP requests does not grow with the number of extensions: all
description.yml files come from one tarball of the registry, and star counts are
fetched through the GraphQL API in batches of STARS_BATCH_SIZE repositories.

Outputs:

    data/extension_details/extension_details.parquet   current snapshot, rewritten only when something changed
    data/star_history/date=YYYY-MM-DD/stars.parquet    one file per day, so star growth can be charted

The snapshot is written uncompressed and without a timestamp column so that git can
store it as a small delta from day to day instead of a fresh 700 KB blob.

Requires GITHUB_TOKEN in the environment for the GitHub API.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests
import yaml
from markdown import markdown
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REGISTRY_TARBALL_URL = "https://codeload.github.com/duckdb/community-extensions/tar.gz/refs/heads/main"
GITHUB_API = "https://api.github.com"
# Repositories per GraphQL request. One request costs a single rate-limit point at this size.
STARS_BATCH_SIZE = 100
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
        allowed_methods=("GET", "POST"),  # the only POST is the read-only GraphQL query
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


_DESCRIPTION_PATH = re.compile(r"^[^/]+/extensions/([^/]+)/description\.yml$")


def fetch_descriptions(session: requests.Session) -> dict[str, str]:
    """Return the raw description.yml text of every extension in the registry, keyed by name.

    The archive is read in memory and nothing is extracted to disk.
    """
    response = session.get(REGISTRY_TARBALL_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    descriptions: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        for member in archive:
            match = _DESCRIPTION_PATH.match(member.name)
            if not match or not member.isfile():
                continue
            descriptions[match.group(1)] = archive.extractfile(member).read().decode("utf-8", errors="replace")
    return descriptions


def fetch_stars(session: requests.Session, repo: str) -> int | None:
    response = session.get(f"{GITHUB_API}/repos/{repo}", timeout=REQUEST_TIMEOUT)
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining is not None and int(remaining) < 50:
        log.warning("GitHub API rate limit nearly exhausted: %s requests remaining", remaining)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("stargazers_count")


_REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def fetch_stars_batch(session: requests.Session, repos: list[str]) -> dict[str, int | None]:
    """Star counts for one batch of repositories in a single GraphQL request.

    A repository that does not exist maps to None. Repositories whose result could not
    be determined are left out of the returned mapping. Raises on a failed request.
    """
    fields = []
    for i, repo in enumerate(repos):
        owner, name = repo.split("/", 1)
        fields.append(f"r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ stargazerCount }}")
    query = "query { rateLimit { remaining } " + " ".join(fields) + " }"
    response = session.post(f"{GITHUB_API}/graphql", json={"query": query}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise requests.RequestException(f"GraphQL query returned no data: {payload.get('errors') or payload}")

    remaining = (data.get("rateLimit") or {}).get("remaining")
    if remaining is not None and remaining < 50:
        log.warning("GitHub GraphQL rate limit nearly exhausted: %s points remaining", remaining)

    not_found = {
        error["path"][0]
        for error in payload.get("errors") or []
        if error.get("type") == "NOT_FOUND" and error.get("path")
    }
    stars: dict[str, int | None] = {}
    for i, repo in enumerate(repos):
        alias = f"r{i}"
        if data.get(alias) is not None:
            stars[repo] = data[alias]["stargazerCount"]
        elif alias in not_found:
            stars[repo] = None
    return stars


def fetch_all_stars(session: requests.Session, repos: list[str]) -> tuple[dict[str, int | None], set[str]]:
    """Star counts for all repositories, plus the set of repositories whose lookup failed.

    Anything the batched GraphQL query cannot answer is retried one repository at a
    time through the REST API, so a single bad batch does not fail 100 extensions.
    """
    stars: dict[str, int | None] = {}
    failed: set[str] = set()
    valid = []
    for repo in repos:
        if _REPO_SLUG.match(repo):
            valid.append(repo)
        else:
            log.warning("Not an owner/name repository, no star count: %r", repo)
            stars[repo] = None

    for start in range(0, len(valid), STARS_BATCH_SIZE):
        batch = valid[start : start + STARS_BATCH_SIZE]
        try:
            stars.update(fetch_stars_batch(session, batch))
        except (requests.RequestException, ValueError) as exc:
            log.warning("GraphQL star query failed, falling back to one request per repository: %s", exc)
        for repo in batch:
            if repo in stars:
                continue
            try:
                stars[repo] = fetch_stars(session, repo)
            except requests.RequestException as exc:
                log.error("%s: %s", repo, exc)
                failed.add(repo)
    return stars, failed


_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")


def normalise_markdown(text: str) -> str:
    """Make GitHub-flavoured habits parse with Python-Markdown.

    Python-Markdown only recognises a list when a blank line precedes it; description.yml
    authors usually write lists straight after a paragraph. Insert the blank line.
    """
    lines = text.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        prev = lines[i - 1] if i else ""
        if _LIST_ITEM.match(line) and prev.strip() and not _LIST_ITEM.match(prev) and not prev.startswith(("    ", "\t")):
            out.append("")
        out.append(line)
    return "\n".join(out)


# Evidence's stylesheet styles markdown elements through a `markdown` class on each tag
# (p.markdown, ul.markdown, code.markdown, ...). Tag the generated HTML the same way so the
# site's own typography applies. Fenced code blocks are left untouched and styled by the page.
_TAGGABLE = re.compile(r"<(p|ul|ol|li|h[1-6]|code|blockquote|table|thead|tbody|tr|th|td|a|strong|em|del|hr|img)(?=[\s>])")
_PRE_BLOCK = re.compile(r"<pre>.*?</pre>", re.DOTALL)


def tag_for_evidence(html: str) -> str:
    blocks: list[str] = []

    def stash(m: re.Match) -> str:
        blocks.append(m.group(0))
        return f"\x00{len(blocks) - 1}\x00"

    html = _PRE_BLOCK.sub(stash, html)
    html = _TAGGABLE.sub(r'<\1 class="markdown"', html)
    return re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], html)


def markdown_or_none(text: str | None) -> str | None:
    if not text:
        return None
    html = markdown(normalise_markdown(text), extensions=["fenced_code", "tables", "sane_lists"])
    return tag_for_evidence(html)


def code_block_html(code: str | None, language: str = "sql") -> str | None:
    """Render a code snippet as an escaped <pre><code> block.

    hello_world is SQL, not markdown: feeding it to the markdown converter would pass
    any HTML inside string literals straight through to the page.
    """
    if not code:
        return None
    fenced = f"```{language}\n{code.strip()}\n```"
    return markdown(fenced, extensions=["fenced_code"])


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
        code_block_html(docs.get("hello_world")),
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

    try:
        descriptions = fetch_descriptions(session)
    except (requests.RequestException, tarfile.TarError, OSError) as exc:
        log.error("Could not read the extension registry; keeping the existing snapshot: %s", exc)
        return 1

    parsed: dict[str, dict] = {}
    failures: list[str] = []
    removed: list[str] = []
    for name in names:
        text = descriptions.get(name)
        if text is None:
            removed.append(name)  # extension removed from the registry
            continue
        try:
            desc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            log.error("%s: %s", name, exc)
            failures.append(name)
            continue
        if isinstance(desc, dict):
            parsed[name] = desc
        else:
            removed.append(name)

    def repo_of(desc: dict) -> str | None:
        repo = as_dict(desc.get("repo")).get("github")
        return str(repo) if repo else None

    repos = sorted({repo for desc in parsed.values() if (repo := repo_of(desc))})
    stars, failed_repos = fetch_all_stars(session, repos)

    rows: list[tuple] = []
    for name, desc in parsed.items():
        repo = repo_of(desc)
        if repo in failed_repos:
            failures.append(name)
            continue
        star_count = stars.get(repo) if repo else None
        rows.append(build_row(name, desc, star_count, fetched_at))
        log.debug("%s: %s stars", name, star_count)

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
