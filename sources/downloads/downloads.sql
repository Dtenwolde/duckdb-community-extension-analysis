-- Weekly downloads per extension. One Parquet file per ISO week under data/downloads,
-- hive-partitioned by year and week. Paths are relative to the project root, where
-- `npm run sources` runs.
--
-- A few extensions exist in both the core ("Regular") and community registries.
-- The pages treat (extension, week) as unique, so the core row wins in that case.
-- `_last_update` is kept as an alias of week_start because the pages key on it.
WITH raw AS (
    SELECT
        extension,
        type,
        downloads_last_week,
        week_start,
        source_last_update,
        fetched_at,
        year,
        week::INTEGER AS week_number
    FROM read_parquet('data/downloads/**/*.parquet', hive_partitioning = true)
)
SELECT
    extension,
    downloads_last_week,
    week_start AS _last_update,
    week_number,
    year,
    type,
    week_start,
    source_last_update::TIMESTAMP AS source_last_update,
    fetched_at::TIMESTAMP AS fetched_at
FROM raw
QUALIFY row_number() OVER (
    PARTITION BY extension, year, week_number
    ORDER BY CASE WHEN type = 'Regular' THEN 0 ELSE 1 END
) = 1
ORDER BY year, week_number, type, extension
