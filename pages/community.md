---
title: Community extensions
sidebar_position: 1
description: All DuckDB community extensions with GitHub metadata, star counts, and download trends.
---

```sql kpis
select
    count(*) as total_extensions,
    count(*) filter (where is_new) as new_extensions,
    sum(last_week_downloads) as downloads_last_week,
    sum(total_downloads) as downloads_all_time
from extension_stats
where type = 'Community'
```

```sql total_stars
select sum(star_count) as total_stars
from (select distinct repo_url, star_count from extension_details where repo_url is not null)
```

<Grid cols=5 gap="16px">
  <BigValue data={kpis} value=total_extensions title="Community extensions" />
  <BigValue data={kpis} value=new_extensions title="New in the last 8 weeks" />
  <BigValue data={kpis} value=downloads_last_week fmt=num0 title="Downloads last week" />
  <BigValue data={kpis} value=downloads_all_time fmt=num0 title="All-time downloads" />
  <BigValue data={total_stars} value=total_stars fmt=num0 title="GitHub stars" />
</Grid>

## This week

```sql top_week
select
    type_rank_last_week as rank,
    extension,
    last_week_downloads,
    wow_growth,
    d.star_count,
    '/extension/' || extension as link
from extension_stats s
left join extension_details d using (extension)
where s.type = 'Community' and last_week_downloads is not null
order by last_week_downloads desc
limit 15
```

<DataTable data={top_week} link=link rows=15 title="Top 15 community extensions this week" subtitle="Click a row to open the extension">
  <Column id=rank align=center />
  <Column id=extension />
  <Column id=last_week_downloads contentType=bar barColor="#f4b548" fmt=num0 title="Downloads" />
  <Column id=wow_growth contentType=delta fmt=pct1 title="vs. last week" />
  <Column id=star_count fmt=num0 title="Stars" />
</DataTable>

## New extensions

```sql new_per_week
with first_weeks as (
    select first_seen, count(*) as new_extensions
    from extension_stats
    where type = 'Community'
    group by first_seen
)
select first_seen as week_start, new_extensions
from first_weeks
where first_seen > (select min(first_seen) from first_weeks)  -- the first tracked week is not a "launch" week
order by week_start
```

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

```sql recently_added
select
    s.extension,
    s.first_seen,
    s.weeks_tracked,
    s.total_downloads,
    s.last_week_downloads,
    k.history,
    '/extension/' || s.extension as link
from extension_stats s
left join ${sparklines} k using (extension)
where s.type = 'Community' and s.is_new
order by s.first_seen desc, s.total_downloads desc
```

<Grid cols=2 gap="20px">
  <BarChart emptySet=pass data={new_per_week} x=week_start y=new_extensions yAxisTitle="Extensions first seen"
    title="Extensions appearing for the first time, per week" subtitle="Based on the first week an extension had any downloads"
    seriesColors={{'new_extensions': '#46a485'}} />
  <DataTable data={recently_added} link=link rows=10 compact=true title="Added in the last 8 weeks" subtitle="Click a row to open the extension">
    <Column id=extension />
    <Column id=first_seen fmt="mmm d" title="Since" />
    <Column id=total_downloads fmt=num0 title="Downloads" />
    <Column id=history contentType=sparkline sparkX=week sparkY=downloads sparkWidth=60 title="Trend" />
  </DataTable>
</Grid>

## GitHub stars

```sql star_window
select min(date) as first_date, max(date) as last_date, count(distinct date) as days
from star_history
```

```sql star_movers
with first_last as (
    select
        extension,
        arg_min(star_count, date) as stars_start,
        arg_max(star_count, date) as stars_now
    from star_history
    where date >= (select max(date) from star_history) - interval 30 day
    group by extension
)
select
    f.extension,
    f.stars_now,
    f.stars_now - f.stars_start as stars_gained,
    (f.stars_now - f.stars_start)::double / nullif(f.stars_start, 0) as stars_growth,
    s.last_week_downloads,
    '/extension/' || f.extension as link
from first_last f
join extension_stats s using (extension)
where f.stars_now is not null
order by stars_gained desc, stars_now desc
limit 10
```

```sql stars_vs_downloads
select
    s.extension,
    d.star_count,
    s.total_downloads,
    s.last_week_downloads,
    d.language_group
from extension_stats s
join extension_details d using (extension)
where s.type = 'Community' and d.star_count > 0 and s.total_downloads > 0
order by s.total_downloads desc
```

<Grid cols=2 gap="20px">
  <div>
    <DataTable data={star_movers} link=link rows=10 compact=true title="Most stars gained in the last 30 days" subtitle="Click a row to open the extension">
      <Column id=extension />
      <Column id=stars_now fmt=num0 title="Stars" />
      <Column id=stars_gained contentType=delta fmt=num0 title="Gained" />
      <Column id=stars_growth contentType=delta fmt=pct1 title="Growth" />
    </DataTable>
    {#if star_window.length > 0 && star_window[0].days < 7}
    <p class="text-xs text-base-content-muted mt-1">Star history is collected nightly since <Value data={star_window} column=first_date fmt="mmm d, yyyy" />. Gains become meaningful after a few weeks of data.</p>
    {/if}
  </div>
  <ScatterPlot emptySet=pass data={stars_vs_downloads} x=star_count y=total_downloads series=language_group
    xAxisTitle="GitHub stars" yAxisTitle="All-time downloads" yLog={true} yMin={1} xMin={0}
    title="GitHub stars vs all-time downloads" subtitle="Log scale on downloads; colour is the implementation language" tooltipTitle=extension />
</Grid>

## By language and license

```sql by_language
select
    d.language_group,
    count(*) as extensions,
    sum(s.last_week_downloads) as downloads_last_week
from extension_details d
join extension_stats s using (extension)
where s.type = 'Community'
group by d.language_group
order by downloads_last_week desc
```

```sql by_license
with counted as (
    select d.license_group, count(*) as n
    from extension_details d
    join extension_stats s using (extension)
    where s.type = 'Community'
    group by d.license_group
)
select
    case when c.n >= 3 then d.license_group else 'Other' end as license_group,
    count(*) as extensions,
    sum(s.last_week_downloads) as downloads_last_week
from extension_details d
join extension_stats s using (extension)
join counted c using (license_group)
where s.type = 'Community'
group by 1
order by extensions desc
```

<Grid cols=2 gap="20px">
  <BarChart emptySet=pass data={by_language} x=language_group y=extensions swapXY=true xAxisTitle="Extensions" title="Extensions by implementation language" seriesColors={{'extensions': '#236aa4'}} />
  <BarChart emptySet=pass data={by_language} x=language_group y=downloads_last_week swapXY=true xAxisTitle="Downloads last week" title="Downloads last week by language" seriesColors={{'downloads_last_week': '#f4b548'}} />
</Grid>

<Grid cols=2 gap="20px">
  <BarChart emptySet=pass data={by_license} x=license_group y=extensions swapXY=true xAxisTitle="Extensions" title="Extensions by license" seriesColors={{'extensions': '#236aa4'}} />
  <BarChart emptySet=pass data={by_license} x=license_group y=downloads_last_week swapXY=true xAxisTitle="Downloads last week" title="Downloads last week by license" seriesColors={{'downloads_last_week': '#f4b548'}} />
</Grid>

## Directory

```sql directory
select
    s.type_rank_all_time as rank,
    s.extension,
    d.maintainers,
    d.language_group,
    d.star_count,
    s.total_downloads,
    s.last_week_downloads,
    s.wow_growth,
    k.history_12w,
    '/extension/' || s.extension as link
from extension_stats s
left join extension_details d using (extension)
left join ${sparklines} k using (extension)
where s.type = 'Community'
order by s.total_downloads desc
```

<DataTable data={directory} link=link search=true rows=20 compact=true title="All community extensions" subtitle="Ranked by lifetime downloads. Search also matches maintainers and language. Click a row to open it.">
  <Column id=rank align=center title="#" />
  <Column id=extension />
  <Column id=maintainers wrap=true />
  <Column id=star_count fmt=num0 title="Stars" />
  <Column id=total_downloads fmt=num0 title="Total" />
  <Column id=last_week_downloads fmt=num0 title="Last week" />
  <Column id=wow_growth contentType=delta fmt=pct1 title="WoW" />
  <Column id=history_12w contentType=sparkline sparkX=week sparkY=downloads sparkWidth=70 title="12 weeks" />
</DataTable>
