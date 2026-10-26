-- Current snapshot of community extension metadata and GitHub stars, with the
-- free-text fields from description.yml normalised into groups for charts.
WITH raw AS (
    SELECT *, lower(trim(coalesce(language, ''))) AS lang
    FROM read_parquet('data/extension_details/extension_details.parquet')
),
-- Descriptions are markdown from each extension's repository, so relative image and
-- link targets (e.g. src="photo.jpg") only resolve on GitHub. Rewrite them to absolute
-- URLs; otherwise they 404 on the site and break the static build's link crawler.
-- Step 1 marks absolute targets with a sentinel, step 2 sends in-page anchors to the
-- README on GitHub, step 3 prefixes everything still unmarked, step 4 removes the sentinel.
rewritten AS (
    SELECT
        * EXCLUDE (extended_description_html, hello_world_html),
        replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
            extended_description_html,
            '(src|href)="(https?:|mailto:|data:|//)', '\1="§\2', 'g'),
            'href="#', 'href="§https://github.com/' || repo_url || '#', 'g'),
            'src="([^§"])', 'src="https://raw.githubusercontent.com/' || repo_url || '/HEAD/\1', 'g'),
            'href="([^§"])', 'href="https://github.com/' || repo_url || '/blob/HEAD/\1', 'g'),
            '§', '') AS extended_description_html,
        replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
            hello_world_html,
            '(src|href)="(https?:|mailto:|data:|//)', '\1="§\2', 'g'),
            'href="#', 'href="§https://github.com/' || repo_url || '#', 'g'),
            'src="([^§"])', 'src="https://raw.githubusercontent.com/' || repo_url || '/HEAD/\1', 'g'),
            'href="([^§"])', 'href="https://github.com/' || repo_url || '/blob/HEAD/\1', 'g'),
            '§', '') AS hello_world_html
    FROM raw
)
SELECT
    * EXCLUDE (lang),
    CASE
        WHEN lang = '' THEN 'Unknown'
        WHEN lang LIKE '%rust%' AND (lang LIKE '%c++%' OR lang LIKE 'c %' OR lang LIKE 'c/%' OR lang LIKE '% c' OR lang LIKE '%& c%')
            THEN 'C++ & Rust'
        WHEN lang LIKE '%rust%' AND (lang LIKE '%&%' OR lang LIKE '%,%' OR lang LIKE '%/%') THEN 'Rust & other'
        WHEN lang LIKE '%rust%' THEN 'Rust'
        WHEN lang LIKE '%c++%' AND (lang LIKE '%&%' OR lang LIKE '%,%') THEN 'C++ & other'
        WHEN lang LIKE '%c++%' THEN 'C++'
        WHEN lang = 'c' THEN 'C'
        ELSE trim(language)
    END AS language_group,
    lower(trim(coalesce(build, 'unknown'))) AS build_system,
    -- keep license labels short: strip trailing notes/URLs and truncate the rest
    CASE
        WHEN nullif(trim(license), '') IS NULL THEN 'Unspecified'
        WHEN length(trim(license)) > 24 THEN left(regexp_replace(trim(license), '\s*[/(-].*$', ''), 21) || '…'
        ELSE trim(license)
    END AS license_group,
    'https://github.com/' || repo_url AS github_url,
    'https://duckdb.org/community_extensions/extensions/' || extension || '.html' AS community_page_url
FROM rewritten
ORDER BY extension
