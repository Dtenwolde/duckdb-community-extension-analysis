-- One row per extension with the figures every page needs: lifetime totals, the two
-- most recent weeks, peak, first/last week seen, and arrays for sparklines.
WITH d AS (
    SELECT * EXCLUDE (week)
    FROM (
        SELECT
            extension,
            CASE type WHEN 'Regular' THEN 'Core' ELSE type END AS type,
            downloads_last_week,
            week_start,
            week
        FROM read_parquet('data/downloads/**/*.parquet', hive_partitioning = true)
        WHERE regexp_matches(extension, '^[a-z0-9_]+$')
        QUALIFY row_number() OVER (PARTITION BY extension, week_start ORDER BY CASE WHEN type = 'Regular' THEN 0 ELSE 1 END) = 1
    )
),
latest AS (
    SELECT max(week_start) AS latest_week FROM d
),
prev AS (
    SELECT max(week_start) AS prev_week FROM d WHERE week_start < (SELECT latest_week FROM latest)
),
per_ext AS (
    SELECT
        extension,
        -- an extension that moved registries keeps the type of its most recent week
        arg_max(type, week_start) AS type,
        sum(downloads_last_week) AS total_downloads,
        max(downloads_last_week) AS peak_week_downloads,
        arg_max(week_start, downloads_last_week) AS peak_week,
        min(week_start) AS first_seen,
        max(week_start) AS last_seen,
        count(*) AS weeks_tracked,
        max(CASE WHEN week_start = (SELECT latest_week FROM latest) THEN downloads_last_week END) AS last_week_downloads,
        max(CASE WHEN week_start = (SELECT prev_week FROM prev) THEN downloads_last_week END) AS prev_week_downloads
    FROM d
    GROUP BY extension
)
SELECT
    *,
    last_week_downloads - prev_week_downloads AS wow_change,
    (last_week_downloads - prev_week_downloads)::DOUBLE / nullif(prev_week_downloads, 0) AS wow_growth,
    row_number() OVER (ORDER BY total_downloads DESC) AS rank_all_time,
    row_number() OVER (ORDER BY last_week_downloads DESC NULLS LAST) AS rank_last_week,
    row_number() OVER (PARTITION BY type ORDER BY total_downloads DESC) AS type_rank_all_time,
    row_number() OVER (PARTITION BY type ORDER BY last_week_downloads DESC NULLS LAST) AS type_rank_last_week,
    first_seen >= (SELECT latest_week FROM latest) - INTERVAL 8 WEEK AS is_new,
    last_seen < (SELECT latest_week FROM latest) AS is_inactive
FROM per_ext
ORDER BY total_downloads DESC
