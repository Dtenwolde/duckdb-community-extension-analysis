---
title: Compare extensions
sidebar_position: 2
description: Compare weekly download trends for up to three DuckDB extensions side by side.
---

<script>
  // Query parameters cannot be read while prerendering, so only look at them in the browser.
  const urlParam = (key, fallback) =>
    typeof window === 'undefined' ? fallback : (new URL(window.location.href).searchParams.get(key) ?? fallback);
</script>

```sql all_extensions
select extension, type
from extension_stats
order by total_downloads desc
```

```sql optional_extensions
-- the third slot is optional, so it gets an explicit "none" entry instead of an unset input
select '(none)' as extension, '' as type
union all
select extension, type from (select extension, type from extension_stats order by total_downloads desc)
```

```sql weeks
select distinct week_start from downloads order by week_start
```

{#if typeof window !== 'undefined'}
<!-- Rendered in the browser only: the defaults come from the URL, which the prerenderer cannot see. -->
<div class="flex flex-wrap items-end gap-4 my-4">
  <Dropdown name=ext1 data={all_extensions} value=extension title="Extension 1" defaultValue={urlParam('a', 'duckpgq')} />
  <Dropdown name=ext2 data={all_extensions} value=extension title="Extension 2" defaultValue={urlParam('b', 'vss')} />
  <Dropdown name=ext3 data={optional_extensions} value=extension title="Extension 3 (optional)" defaultValue={urlParam('c', '(none)')} />
</div>
{/if}

<div class="flex flex-wrap items-end gap-6 my-4">
  <DateRange name=range data={weeks} dates=week_start defaultValue="All Time"
    presetRanges={['Last 3 Months', 'Last 6 Months', 'Last 12 Months', 'All Time']} title="Period" />
  <ButtonGroup name=mode defaultValue="weekly" title="View">
    <ButtonGroupItem valueLabel="Weekly" value="weekly" default />
    <ButtonGroupItem valueLabel="Indexed (first week = 100)" value="indexed" />
    <ButtonGroupItem valueLabel="Cumulative" value="cumulative" />
  </ButtonGroup>
</div>

<p class="text-xs text-base-content-muted">Share this comparison: <code>?a={inputs.ext1.value}&b={inputs.ext2.value}{inputs.ext3.value && inputs.ext3.value !== '(none)' ? '&c=' + inputs.ext3.value : ''}</code> appended to this page's address selects these extensions.</p>

```sql selected
select extension, week_start, downloads_last_week
from downloads
where extension in ('${inputs.ext1.value}', '${inputs.ext2.value}', '${inputs.ext3.value}')
  and week_start between '${inputs.range.start}' and '${inputs.range.end}'
order by week_start
```

```sql series
select
    extension,
    week_start,
    downloads_last_week as weekly,
    100.0 * downloads_last_week / nullif(first_value(downloads_last_week) over (partition by extension order by week_start), 0) as indexed,
    sum(downloads_last_week) over (partition by extension order by week_start) as cumulative
from ${selected}
order by week_start
```

{#if inputs.mode === 'indexed'}
<LineChart emptySet=pass data={series} x=week_start y=indexed series=extension colorPalette=compare
  yAxisTitle="Index (first week in period = 100)" title="Growth since the start of the period"
  subtitle="Each extension is scaled to 100 in its first week, so very different sizes can be compared by shape" />
{:else if inputs.mode === 'cumulative'}
<LineChart emptySet=pass data={series} x=week_start y=cumulative series=extension colorPalette=compare
  yAxisTitle="Cumulative downloads" title="Cumulative downloads" />
{:else}
<LineChart emptySet=pass data={series} x=week_start y=weekly series=extension colorPalette=compare
  yAxisTitle="Downloads / week" title="Weekly downloads" />
{/if}

## Summary

```sql sparklines
-- {week, downloads} structs for DataTable sparkline columns, built here because the source
-- export does not preserve nested types. DOUBLE avoids BigInt values in the browser.
select
    extension,
    list({'week': week_start, 'downloads': downloads_last_week::DOUBLE} order by week_start) as history,
    list({'week': week_start, 'downloads': downloads_last_week::DOUBLE} order by week_start)[-12:] as history_12w
from downloads
group by extension
```

```sql stats
select
    s.extension,
    s.type,
    sum(d.downloads_last_week) as period_downloads,
    s.last_week_downloads,
    s.wow_growth,
    max(d.downloads_last_week) as peak_week_downloads,
    count(*) as weeks_in_period,
    k.history_12w,
    '/extension/' || s.extension as link
from ${selected} d
join extension_stats s using (extension)
left join ${sparklines} k using (extension)
group by all
order by period_downloads desc
```

<DataTable data={stats} link=link compact=true subtitle="Downloads within the selected period. Click a row to open the extension.">
  <Column id=extension />
  <Column id=type />
  <Column id=period_downloads fmt=num0 title="In period" />
  <Column id=last_week_downloads fmt=num0 title="Last week" />
  <Column id=wow_growth contentType=delta fmt=pct1 title="WoW" />
  <Column id=peak_week_downloads fmt=num0 title="Best week" />
  <Column id=history_12w contentType=sparkline sparkX=week sparkY=downloads sparkWidth=70 title="12 weeks" />
</DataTable>
