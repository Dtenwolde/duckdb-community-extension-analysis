---
title: Compare Extensions
description: Compare weekly download trends for up to 3 DuckDB extensions side by side.
---

# Compare Extensions

```sql all_extensions
SELECT extension, type
FROM downloads
GROUP BY extension, type
ORDER BY extension
```

<Grid cols="2" gap="20px">
  <Dropdown
    name=ext1
    data={all_extensions}
    value=extension
    title="Extension 1"
    defaultValue="duckpgq"
  />
  <Dropdown
    name=ext2
    data={all_extensions}
    value=extension
    title="Extension 2"
    defaultValue="vss"
  />
</Grid>

```sql comparison_data
SELECT
    extension,
    _last_update::DATE AS date,
    downloads_last_week AS downloads
FROM downloads
WHERE extension IN (
    '${inputs.ext1?.value || "duckpgq"}',
    '${inputs.ext2?.value || "vss"}'
)
ORDER BY date ASC
```

```sql comparison_cumulative
SELECT
    extension,
    _last_update::DATE AS date,
    SUM(downloads_last_week) OVER (PARTITION BY extension ORDER BY _last_update::DATE) AS cumulative_downloads
FROM downloads
WHERE extension IN (
    '${inputs.ext1?.value || "duckpgq"}',
    '${inputs.ext2?.value || "vss"}'
)
ORDER BY date ASC
```

```sql comparison_stats
SELECT
    extension,
    SUM(downloads_last_week) AS total_downloads,
    MAX(CASE WHEN _last_update = (SELECT MAX(_last_update) FROM downloads) THEN downloads_last_week END) AS last_week_downloads,
    MAX(downloads_last_week) AS peak_week_downloads,
    COUNT(*) AS weeks_tracked
FROM downloads
WHERE extension IN (
    '${inputs.ext1?.value || "duckpgq"}',
    '${inputs.ext2?.value || "vss"}'
)
GROUP BY extension
ORDER BY total_downloads DESC
```

<LineChart
  data={comparison_data}
  x="date"
  y="downloads"
  series="extension"
  colorPalette=compare
  yAxisTitle="Downloads per Week"
  title="Weekly Downloads"
/>

<LineChart
  data={comparison_cumulative}
  x="date"
  y="cumulative_downloads"
  series="extension"
  colorPalette=compare
  yAxisTitle="Cumulative Downloads"
  title="Cumulative Downloads"
/>

## Summary

<DataTable data={comparison_stats}>
  <Column id="extension" />
  <Column id="total_downloads" fmt=num0 title="Total Downloads" />
  <Column id="last_week_downloads" fmt=num0 title="Last Week" />
  <Column id="peak_week_downloads" fmt=num0 title="Peak Week" />
  <Column id="weeks_tracked" title="Weeks Tracked" />
</DataTable>
