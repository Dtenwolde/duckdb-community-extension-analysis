# DuckDB extension download analysis

An [Evidence](https://evidence.dev) site that tracks weekly download statistics for
DuckDB core and community extensions, published at
<https://dtenwolde.github.io/duckdb-community-extension-analysis/>.

## How it works

Every night a GitHub Actions workflow (`.github/workflows/update_data.yml`) runs two
scripts and commits the result to the `evidence` branch. When that finishes, the
deploy workflow rebuilds the site and publishes it to GitHub Pages.

| Script | What it does |
|---|---|
| `scripts/fetch_downloads.py` | Fetches the weekly download JSON for core and community extensions from `extensions.duckdb.org` and `community-extensions.duckdb.org`. Weeks that are missing locally are fetched once; the three most recent weeks are re-fetched every run because upstream rewrites the current week nightly. |
| `scripts/fetch_extension_details.py` | Reads each community extension's `description.yml` from `duckdb/community-extensions` and its GitHub star count. Needs `GITHUB_TOKEN`. |

## Data layout

All data is stored as Parquet under `data/`, hive-partitioned so DuckDB can prune
by week:

```
data/
  downloads/year=2026/week=43/downloads.parquet     one file per ISO week, both registries
  extension_details/extension_details.parquet       current snapshot of community extension metadata
  star_history/date=2026-10-26/stars.parquet        one file per day of GitHub star counts
```

Columns in `downloads`: `extension`, `type` (`Regular` or `Community`),
`downloads_last_week`, `week_start` (Monday of the ISO week), `source_last_update`
(upstream timestamp), `fetched_at`. The `year` and `week` columns come from the
directory names.

Query it directly with DuckDB:

```sql
SELECT * FROM read_parquet('data/downloads/**/*.parquet', hive_partitioning = true);
```

The Evidence source definitions in `sources/downloads/` expose these files to the
pages. A handful of extensions appear in both registries; the `downloads` source
keeps the core (`Regular`) row in that case.

## Site structure

| Page | Content |
|---|---|
| `pages/index.md` | Overview: core vs community KPIs, trends with a date range and registry toggle, concentration, top movers, this week, heatmap, leaderboard |
| `pages/community.md` | Community registry: new extensions, GitHub stars, language and license breakdowns, directory |
| `pages/compare.md` | Compare up to three extensions (weekly, indexed, cumulative). Accepts `?a=&b=&c=` query parameters |
| `pages/extension/[extension].md` | One page per extension: downloads, rank, stars, metadata and description |
| `pages/extension/index.md` | Directory of all extension pages |

The Evidence sources in `sources/downloads/` expose `downloads`, `extension_details`,
`extension_stats` (one row per extension with totals, growth and sparkline arrays) and
`star_history`. Core extensions are labelled `Core` in the site; upstream calls them `Regular`.

## Running locally

```bash
# data
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_downloads.py            # add --all to rebuild every week from upstream
GITHUB_TOKEN=$(gh auth token) python scripts/fetch_extension_details.py

# site
npm install
npm run sources
npm run dev
```
