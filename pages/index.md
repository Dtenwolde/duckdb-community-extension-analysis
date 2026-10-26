---
title: DuckDB extension weekly downloads
description: Weekly and monthly download trends for DuckDB core and community extensions, updated nightly.
og: /images/main.png
---

```sql latest_week
select max(week_start) as latest_week, max(week_label) as latest_label
from downloads
```

```sql weekly_totals
select week_start, type, sum(downloads_last_week) as downloads, count(*) as extensions
from downloads
group by all
order by week_start
```

```sql kpi_weekly
with rolling as (
    select
        type,
        week_start,
        downloads,
        sum(downloads) over (partition by type order by week_start rows between 3 preceding and current row) as downloads_4w
    from ${weekly_totals}
)
select
    type,
    week_start,
    downloads,
    (downloads - lag(downloads) over (partition by type order by week_start))
        / lag(downloads) over (partition by type order by week_start) as growth_rate,
    downloads_4w,
    (downloads_4w - lag(downloads_4w, 4) over (partition by type order by week_start))
        / lag(downloads_4w, 4) over (partition by type order by week_start) as growth_4w
from rolling
order by week_start desc
```

```sql kpi_core
select * from ${kpi_weekly} where type = 'Core' order by week_start desc limit 26
```

```sql kpi_community
select * from ${kpi_weekly} where type = 'Community' order by week_start desc limit 26
```

<Grid cols=4 gap="16px">
  <BigValue data={kpi_core} value=downloads title="Core downloads, last week" fmt=num0
    sparkline=week_start sparklineColor="#236aa4" comparison=growth_rate comparisonFmt=pct1 comparisonTitle="vs. previous week" />
  <BigValue data={kpi_core} value=downloads_4w title="Core downloads, last 4 weeks" fmt=num0
    sparkline=week_start sparklineColor="#236aa4" comparison=growth_4w comparisonFmt=pct1 comparisonTitle="vs. previous 4 weeks" />
  <BigValue data={kpi_community} value=downloads title="Community downloads, last week" fmt=num0
    sparkline=week_start sparklineColor="#f4b548" comparison=growth_rate comparisonFmt=pct1 comparisonTitle="vs. previous week" />
  <BigValue data={kpi_community} value=downloads_4w title="Community downloads, last 4 weeks" fmt=num0
    sparkline=week_start sparklineColor="#f4b548" comparison=growth_4w comparisonFmt=pct1 comparisonTitle="vs. previous 4 weeks" />
</Grid>

<div class="text-xs text-base-content-muted mt-1">
  Latest week is <Value data={latest_week} column=latest_label />, starting <Value data={latest_week} column=latest_week fmt="mmm d, yyyy" />. Core statistics are published from 2025-W39 and community statistics from 2024-W40. <LastRefreshed prefix="Data refreshed" />
</div>

## Trends

<div class="flex flex-wrap items-end gap-6 my-4">
  <DateRange name=range data={weekly_totals} dates=week_start defaultValue="All Time"
    presetRanges={['Last 3 Months', 'Last 6 Months', 'Last 12 Months', 'All Time']} title="Period" />
  <ButtonGroup name=type_filter defaultValue="Community" title="Registry">
    <ButtonGroupItem valueLabel="Community" value="Community" default />
    <ButtonGroupItem valueLabel="Core" value="Core" />
  </ButtonGroup>
</div>

```sql core_vs_community
select
    week_start,
    sum(downloads) filter (where type = 'Core') as "Core",
    sum(downloads) filter (where type = 'Community') as "Community"
from ${weekly_totals}
where week_start between '${inputs.range.start}' and '${inputs.range.end}'
group by week_start
order by week_start
```

```sql top10_trend
with in_range as (
    select extension, week_start, downloads_last_week
    from downloads
    where type = '${inputs.type_filter}'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
),
top as (
    select extension
    from in_range
    group by extension
    order by sum(downloads_last_week) desc
    limit 10
)
select r.extension, r.week_start, r.downloads_last_week
from in_range r
join top using (extension)
order by r.week_start, r.extension
```

<Grid cols=2 gap="20px">
  <LineChart emptySet=pass
    data={core_vs_community}
    x=week_start
    y="Core"
    y2="Community"
    yAxisTitle="Core downloads / week"
    y2AxisTitle="Community downloads / week"
    seriesColors={{'Core': '#236aa4', 'Community': '#f4b548'}}
    title="Core vs community downloads"
    subtitle="Separate axes; community volume is roughly 50x smaller"
  />
  <LineChart emptySet=pass
    data={top10_trend}
    x=week_start
    y=downloads_last_week
    series=extension
    yAxisTitle="Downloads / week"
    title="Top 10 {inputs.type_filter.toLowerCase()} extensions"
    subtitle="Ranked by downloads in the selected period"
  />
</Grid>

```sql concentration
with ranked as (
    select
        week_start,
        extension,
        downloads_last_week,
        row_number() over (partition by week_start order by downloads_last_week desc) as rk
    from downloads
    where type = '${inputs.type_filter}'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
)
select
    week_start,
    case when rk <= 10 then 'Top 10' else 'All others' end as bucket,
    sum(downloads_last_week) as downloads
from ranked
group by all
order by week_start, bucket desc
```

```sql active_extensions
select week_start, count(*) as extensions
from downloads
where type = '${inputs.type_filter}'
  and week_start between '${inputs.range.start}' and '${inputs.range.end}'
group by week_start
order by week_start
```

<Grid cols=2 gap="20px">
  <AreaChart emptySet=pass
    data={concentration}
    x=week_start
    y=downloads
    series=bucket
    type=stacked100
    seriesOrder={['Top 10', 'All others']}
    seriesColors={{'Top 10': '#236aa4', 'All others': '#a5cdee'}}
    yAxisTitle="Share of weekly downloads"
    title="How concentrated are {inputs.type_filter.toLowerCase()} downloads?"
    subtitle="Share taken by the 10 most downloaded extensions each week"
  />
  <LineChart emptySet=pass
    data={active_extensions}
    x=week_start
    y=extensions
    yAxisTitle="Extensions with downloads"
    title="Number of {inputs.type_filter.toLowerCase()} extensions"
    subtitle="Extensions with at least one download that week"
    seriesColors={{'extensions': '#46a485'}}
  />
</Grid>

## Top movers

```sql top_gainers
select
    extension,
    type,
    last_week_downloads,
    prev_week_downloads,
    wow_change,
    wow_growth,
    '/extension/' || extension as link
from extension_stats
where prev_week_downloads >= 50 and last_week_downloads is not null
order by wow_growth desc
limit 5
```

```sql top_losers
select
    extension,
    type,
    last_week_downloads,
    prev_week_downloads,
    wow_change,
    wow_growth,
    '/extension/' || extension as link
from extension_stats
where prev_week_downloads >= 50 and last_week_downloads is not null
order by wow_growth asc
limit 5
```

<Grid cols=2 gap="20px">
  <DataTable data={top_gainers} link=link compact=true title="Biggest gainers" subtitle="Week over week, extensions with at least 50 downloads the week before">
    <Column id=extension />
    <Column id=last_week_downloads fmt=num0 title="Week" />
    <Column id=wow_change contentType=delta fmt=num0 title="Change" />
    <Column id=wow_growth contentType=delta fmt=pct1 title="Growth" />
  </DataTable>
  <DataTable data={top_losers} link=link compact=true title="Biggest losers" subtitle="Week over week, extensions with at least 50 downloads the week before">
    <Column id=extension />
    <Column id=last_week_downloads fmt=num0 title="Week" />
    <Column id=wow_change contentType=delta fmt=num0 title="Change" />
    <Column id=wow_growth contentType=delta fmt=pct1 title="Growth" />
  </DataTable>
</Grid>

## This week

```sql current_week_top
select
    type_rank_last_week as rank,
    extension,
    type,
    last_week_downloads,
    wow_growth,
    '/extension/' || extension as link
from extension_stats
where type = '${inputs.type_filter}' and last_week_downloads is not null
order by last_week_downloads desc
limit 20
```

<DataTable data={current_week_top} link=link rows=20 title="Top 20 {inputs.type_filter.toLowerCase()} extensions this week" subtitle="Click a row to open the extension">
  <Column id=rank align=center />
  <Column id=extension />
  <Column id=last_week_downloads contentType=bar fmt=num0 title="Downloads" barColor={inputs.type_filter === 'Core' ? '#236aa4' : '#f4b548'} />
  <Column id=wow_growth contentType=delta fmt=pct1 title="vs. last week" />
</DataTable>

```sql heatmap
with top as (
    select extension
    from downloads
    where type = '${inputs.type_filter}'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
    group by extension
    order by sum(downloads_last_week) desc
    limit 30
)
select d.extension, d.week_label, d.downloads_last_week
from downloads d
join top using (extension)
where d.week_start between '${inputs.range.start}' and '${inputs.range.end}'
order by d.week_start
```

```sql heatmap_scale
-- cap the colour scale at the 95th percentile so one spike does not wash out every other cell
select quantile_cont(downloads_last_week, 0.95) as p95 from ${heatmap}
```

<Heatmap emptySet=pass
  data={heatmap}
  x=week_label
  y=extension
  value=downloads_last_week
  valueFmt=num0
  valueLabels=false
  colorPalette={['#eef5fb', '#236aa4']}
  max={heatmap_scale[0]?.p95}
  ySort=downloads_last_week
  ySortOrder=desc
  cellHeight=14
  xLabelRotation=60
  legend=true
  title="Weekly downloads, top 30 {inputs.type_filter.toLowerCase()} extensions"
  subtitle="Rows are extensions, columns are ISO weeks. Colour scale is capped at the 95th percentile."
/>

## Leaderboard

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

```sql leaderboard
select
    s.rank_all_time as rank,
    s.extension,
    s.type,
    s.total_downloads,
    s.last_week_downloads,
    s.wow_growth,
    k.history_12w,
    '/extension/' || s.extension as link
from extension_stats s
left join ${sparklines} k using (extension)
order by rank
```

<DataTable data={leaderboard} link=link search=true rows=15 title="All extensions" subtitle="Lifetime downloads since tracking began. Click a row to open the extension.">
  <Column id=rank align=center />
  <Column id=extension />
  <Column id=type />
  <Column id=total_downloads fmt=num0 title="Total" />
  <Column id=last_week_downloads fmt=num0 title="Last week" />
  <Column id=wow_growth contentType=delta fmt=pct1 title="vs. prev. week" />
  <Column id=history_12w contentType=sparkline sparkX=week sparkY=downloads title="Last 12 weeks" />
</DataTable>

## Explore an extension

```sql all_extensions
select extension, type from extension_stats order by extension
```

<div class="flex flex-wrap items-end gap-4 my-2">
  <Dropdown name=jump data={all_extensions} value=extension title="Pick an extension" defaultValue="duckpgq" />
  <LinkButton url="/extension/{inputs.jump.value}">Open {inputs.jump.value}</LinkButton>
  <LinkButton url="/extension/">Browse all extensions</LinkButton>
</div>
