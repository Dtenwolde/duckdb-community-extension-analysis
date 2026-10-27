-- Nightly snapshots of running totals that registries publish without history
-- (NuGet, conda-forge, Homebrew, Docker Hub, GitHub, crates.io lifetime, PyPI recent).
-- One file per day under data/client_snapshots. `item`/`sub_item` hold the release tag
-- and asset name for GitHub release downloads.
SELECT
    date::DATE AS date,
    channel,
    package,
    metric,
    item,
    sub_item,
    value,
    fetched_at::TIMESTAMP AS fetched_at
FROM read_parquet('data/client_snapshots/**/*.parquet', hive_partitioning = true)
ORDER BY date, channel, package, metric, item, sub_item
