-- Current snapshot of community extension metadata and GitHub stars.
SELECT *
FROM read_parquet('data/extension_details/extension_details.parquet')
ORDER BY extension
