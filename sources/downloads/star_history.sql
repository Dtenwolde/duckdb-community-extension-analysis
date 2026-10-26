-- Daily GitHub star counts per community extension, one Parquet file per day.
SELECT
    extension,
    repo_url,
    star_count,
    date::DATE AS date
FROM read_parquet('data/star_history/**/*.parquet', hive_partitioning = true)
ORDER BY date, extension
