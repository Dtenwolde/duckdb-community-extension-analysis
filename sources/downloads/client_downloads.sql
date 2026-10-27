-- Daily download counts for DuckDB client libraries (PyPI, npm, CRAN, crates.io),
-- one Parquet file per month under data/client_downloads. `dimension` is 'total' for the
-- package total, or a breakdown ('os', 'python_minor', 'version') whose member is in
-- `dimension_value`. Sum only one dimension at a time.
SELECT
    channel,
    CASE channel
        WHEN 'pypi' THEN 'PyPI (Python)'
        WHEN 'npm' THEN 'npm (Node.js)'
        WHEN 'cran' THEN 'CRAN (R)'
        WHEN 'crates' THEN 'crates.io (Rust)'
        ELSE channel
    END AS channel_label,
    package,
    date,
    date_trunc('week', date)::DATE AS week_start,
    date_trunc('month', date)::DATE AS month_start,
    dimension,
    dimension_value,
    downloads
FROM read_parquet('data/client_downloads/**/*.parquet', hive_partitioning = true)
ORDER BY channel, package, dimension, dimension_value, date
