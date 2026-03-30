---
title: Community Extensions
description: Explore all DuckDB community extensions with GitHub metadata, star counts, and download trends.
---

```sql total_community_extensions
SELECT COUNT(DISTINCT extension) AS total_extensions
FROM downloads
WHERE type = 'Community'
```

```sql community_downloads_last_week
SELECT SUM(downloads_last_week) AS total_downloads_last_week
FROM downloads
WHERE type = 'Community'
  AND _last_update = (SELECT MAX(_last_update) FROM downloads)
```

```sql community_downloads_all_time
SELECT SUM(downloads_last_week) AS total_downloads_all_time
FROM downloads
WHERE type = 'Community'
```

```sql community_total_stars
SELECT SUM(star_count) AS total_stars
FROM (
    SELECT DISTINCT repo_url, star_count
    FROM extension_details
    WHERE repo_url IS NOT NULL
) unique_repos
```

<Grid cols="4" gap="20px">
  <BigValue data={total_community_extensions} value="total_extensions" title="Community Extensions" />
  <BigValue data={community_downloads_last_week} value="total_downloads_last_week" fmt=num0 title="Downloads Last Week" />
  <BigValue data={community_downloads_all_time} value="total_downloads_all_time" fmt=num0 title="All-Time Downloads" />
  <BigValue data={community_total_stars} value="total_stars" fmt=num0 title="Total GitHub Stars" />
</Grid>

## Top Extensions This Week

```sql community_top_week
SELECT
    d.extension,
    d.downloads_last_week,
    e.star_count
FROM downloads d
LEFT JOIN extension_details e ON d.extension = e.extension
WHERE d.type = 'Community'
  AND d._last_update = (SELECT MAX(_last_update) FROM downloads)
ORDER BY d.downloads_last_week DESC
LIMIT 15
```

<BarChart
  data={community_top_week}
  x="extension"
  y="downloads_last_week"
  swapXY=true
  title="Top 15 Community Extensions This Week"
  xAxisTitle="Downloads"
/>

## Stars vs Downloads

```sql stars_vs_downloads
SELECT
    d.extension,
    e.star_count,
    d.total_downloads,
    e.maintainers
FROM (
    SELECT extension, SUM(downloads_last_week) AS total_downloads
    FROM downloads
    WHERE type = 'Community'
    GROUP BY extension
) d
JOIN extension_details e ON d.extension = e.extension
WHERE e.star_count IS NOT NULL
  AND e.star_count > 0
ORDER BY d.total_downloads DESC
```

<ScatterPlot
  data={stars_vs_downloads}
  x="star_count"
  y="total_downloads"
  series="extension"
  xAxisTitle="GitHub Stars"
  yAxisTitle="All-Time Downloads"
  title="GitHub Stars vs All-Time Downloads"
  tooltipTitle="extension"
/>

## All Community Extensions

```sql community_directory
SELECT
    ROW_NUMBER() OVER (ORDER BY total_downloads DESC) AS rank,
    d.extension,
    e.description,
    e.maintainers,
    e.star_count,
    e.language,
    e.version,
    d.total_downloads,
    d.last_week_downloads,
    d.growth_rate,
    'https://github.com/' || e.repo_url AS github_url
FROM (
    SELECT
        extension,
        SUM(downloads_last_week) AS total_downloads,
        MAX(CASE WHEN _last_update = (SELECT MAX(_last_update) FROM downloads) THEN downloads_last_week END) AS last_week_downloads,
        MAX(CASE WHEN _last_update = (SELECT MAX(_last_update) FROM downloads) THEN downloads_last_week END)::FLOAT
            / NULLIF(MAX(CASE WHEN _last_update = (
                SELECT MAX(_last_update) FROM downloads WHERE _last_update < (SELECT MAX(_last_update) FROM downloads)
            ) THEN downloads_last_week END), 0) - 1 AS growth_rate
    FROM downloads
    WHERE type = 'Community'
    GROUP BY extension
) d
LEFT JOIN extension_details e ON d.extension = e.extension
ORDER BY rank
```

<DataTable data={community_directory} search=true rows=20>
  <Column id="rank" />
  <Column id="extension" />
  <Column id="description" />
  <Column id="maintainers" />
  <Column id="star_count" title="Stars" fmt=num0 />
  <Column id="language" />
  <Column id="version" />
  <Column id="total_downloads" title="Total Downloads" fmt=num0 />
  <Column id="last_week_downloads" title="Last Week" fmt=num0 />
  <Column id="growth_rate" title="WoW Growth" fmt=pct1 contentType=delta />
  <Column id="github_url" title="GitHub" contentType=link linkLabel="View →" />
</DataTable>
