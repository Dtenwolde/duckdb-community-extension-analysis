-- Weekly downloads per extension. One Parquet file per ISO week under data/downloads,
-- hive-partitioned by year and week. Paths are relative to the project root, where
-- `npm run sources` runs.
--
-- A few extensions exist in both the core and community registries. The pages treat
-- (extension, week) as unique, so the core row wins in that case.
-- Upstream calls core extensions "Regular"; the site calls them "Core".
-- `_last_update` is kept as an alias of week_start because older pages key on it.
WITH raw AS (
    SELECT
        extension,
        CASE type WHEN 'Regular' THEN 'Core' ELSE type END AS type,
        downloads_last_week,
        week_start,
        source_last_update,
        fetched_at,
        year,
        week::INTEGER AS week_number
    FROM read_parquet('data/downloads/**/*.parquet', hive_partitioning = true)
    -- upstream occasionally leaks a URL path or file name as an extension name
    WHERE regexp_matches(extension, '^[a-z0-9_]+$')
)
SELECT
    extension,
    downloads_last_week,
    week_start AS _last_update,
    week_number,
    year,
    type,
    week_start,
    year || '-W' || lpad(week_number::VARCHAR, 2, '0') AS week_label,
    source_last_update::TIMESTAMP AS source_last_update,
    fetched_at::TIMESTAMP AS fetched_at
FROM raw
QUALIFY row_number() OVER (
    PARTITION BY extension, year, week_number
    ORDER BY CASE WHEN type = 'Core' THEN 0 ELSE 1 END
) = 1
ORDER BY year, week_number, type, extension
