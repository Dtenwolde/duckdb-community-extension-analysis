---
title: Client downloads
sidebar_position: 4
description: Downloads of DuckDB itself across package registries - PyPI, npm, CRAN, crates.io, NuGet, conda-forge, Homebrew, Docker Hub and GitHub releases.
---

```sql channel_latest
-- the last day with data differs per channel: npm and PyPI publish counts a few days late
select channel, channel_label, max(date) as last_date, min(date) as first_date
from client_downloads
where dimension = 'total'
group by channel, channel_label
```

```sql channel_kpis
-- registries publish daily counts late and out of order, so compare the last seven published
-- days with the seven before them rather than fixed calendar windows
with daily as (
    select channel, channel_label, date, sum(downloads) as downloads
    from client_downloads
    where dimension = 'total'
    group by all
),
ranked as (
    select *, row_number() over (partition by channel order by date desc) as rn
    from daily
),
windows as (
    select
        channel,
        channel_label,
        max(date) as last_date,
        sum(downloads) filter (where rn <= 7) as last_7d,
        sum(downloads) filter (where rn > 7 and rn <= 14) as prev_7d
    from ranked
    group by all
)
select
    *,
    (last_7d - prev_7d)::double / nullif(prev_7d, 0) as growth
from windows
order by last_7d desc
```

<p class="text-sm text-base-content-muted">
  Downloads of DuckDB's own client libraries and binaries, as published by each registry. Counts are not comparable across
  channels: CI pipelines dominate PyPI and npm, Homebrew only counts opted-in installs, and conda-forge and NuGet count
  per file. Read each channel for its trend rather than adding them together.
</p>

<Grid cols=4 gap="16px">
  {#each channel_kpis as k}
  <BigValue data={[k]} value=last_7d title="{k.channel_label}, last 7 days" fmt=num0
    comparison=growth comparisonFmt=pct1 comparisonTitle="vs. previous 7 days" />
  {/each}
</Grid>

<p class="text-xs text-base-content-muted mt-1">
  Latest day with data:
  {#each channel_latest as l, i}{i > 0 ? ' · ' : ''}{l.channel_label} <Value data={[l]} column=last_date fmt="mmm d" />{/each}
</p>

## Weekly downloads by channel

```sql weeks
select distinct week_start from client_downloads order by week_start
```

<div class="flex flex-wrap items-end gap-6 my-4">
  <DateRange name=range data={weeks} dates=week_start defaultValue="Last 12 Months"
    presetRanges={['Last 3 Months', 'Last 6 Months', 'Last 12 Months', 'All Time']} title="Period" />
</div>

```sql weekly_by_channel
-- complete weeks only: a week counts when every channel day in it has been published
with per_week as (
    select channel, channel_label, week_start, sum(downloads) as downloads, count(distinct date) as days
    from client_downloads
    where dimension = 'total'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
    group by all
)
select channel, channel_label, week_start, downloads
from per_week
where days = 7
order by week_start
```

<Grid cols=2 gap="20px">
  {#each ['pypi', 'npm', 'cran', 'crates'] as ch}
  <LineChart emptySet=pass data={weekly_by_channel.filter(r => r.channel === ch)} x=week_start y=downloads
    title={weekly_by_channel.find(r => r.channel === ch)?.channel_label ?? ch} yAxisTitle="Downloads / week"
    seriesColors={{'downloads': ch === 'pypi' ? '#236aa4' : ch === 'npm' ? '#46a485' : ch === 'cran' ? '#8f3d56' : '#f4b548'}} />
  {/each}
</Grid>

```sql weekly_indexed
with per_week as (
    select channel_label, week_start, sum(downloads) as downloads, count(distinct date) as days
    from client_downloads
    where dimension = 'total'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
    group by all
)
select
    channel_label,
    week_start,
    100.0 * downloads / first_value(downloads) over (partition by channel_label order by week_start) as indexed
from per_week
where days = 7
order by week_start
```

<LineChart emptySet=pass data={weekly_indexed} x=week_start y=indexed series=channel_label
  title="Relative growth" subtitle="Each channel scaled to 100 in the first week of the period"
  yAxisTitle="Index (first week = 100)"
  seriesColors={{'PyPI (Python)': '#236aa4', 'npm (Node.js)': '#46a485', 'CRAN (R)': '#8f3d56', 'crates.io (Rust)': '#f4b548'}} />

## PyPI breakdowns

```sql pypi_os
with w as (
    select week_start, case dimension_value when 'Darwin' then 'macOS' else dimension_value end as os, sum(downloads) as downloads, count(distinct date) as days
    from client_downloads
    where channel = 'pypi' and dimension = 'os'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
    group by all
)
select week_start, os, downloads from w where days = 7 order by week_start, os
```

```sql pypi_python
with w as (
    select week_start, dimension_value as python_version, sum(downloads) as downloads, count(distinct date) as days
    from client_downloads
    where channel = 'pypi' and dimension = 'python_minor'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
    group by all
),
ranked as (
    select python_version, sum(downloads) as total from w group by python_version order by total desc limit 7
)
select
    w.week_start,
    case when r.python_version is not null then 'Python ' || w.python_version else 'Other / unknown' end as python_version,
    sum(w.downloads) as downloads
from w
left join ranked r using (python_version)
where w.days = 7
group by all
order by week_start, python_version
```

<Grid cols=2 gap="20px">
  <AreaChart emptySet=pass data={pypi_os} x=week_start y=downloads series=os type=stacked100 yFmt=pct0
    title="PyPI downloads by operating system" subtitle="Share of weekly downloads" />
  <AreaChart emptySet=pass data={pypi_python} x=week_start y=downloads series=python_version type=stacked100 yFmt=pct0
    title="PyPI downloads by Python version" subtitle="Share of weekly downloads; seven most used versions, the rest grouped" />
</Grid>

## npm packages and Rust crate versions

```sql npm_packages
with w as (
    select package, week_start, sum(downloads) as downloads, count(distinct date) as days
    from client_downloads
    where channel = 'npm' and dimension = 'total'
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
    group by all
)
select package, week_start, downloads from w where days = 7 order by week_start
```

```sql crate_versions
with ranked as (
    select dimension_value as version, sum(downloads) as total
    from client_downloads
    where channel = 'crates' and dimension = 'version'
    group by 1 order by total desc limit 6
)
select
    d.date,
    case when r.version is not null then d.dimension_value else 'other versions' end as version,
    sum(d.downloads) as downloads
from client_downloads d
left join ranked r on r.version = d.dimension_value
where d.channel = 'crates' and d.dimension = 'version'
group by all
order by d.date, version
```

<Grid cols=2 gap="20px">
  <LineChart emptySet=pass data={npm_packages} x=week_start y=downloads series=package
    title="npm downloads per package" subtitle="@duckdb/node-api is the current client. The legacy duckdb package only exposes totals; see Running totals." yAxisTitle="Downloads / week" />
  <AreaChart emptySet=pass data={crate_versions} x=date y=downloads series=version type=stacked
    title="crates.io downloads by version" subtitle="Daily; crates.io keeps 90 days of per-version history" yAxisTitle="Downloads / day" />
</Grid>

## Running totals

```sql snapshot_dates
select min(date) as first_date, max(date) as last_date, count(distinct date) as days from client_snapshots
```

```sql totals
with latest as (
    select * from client_snapshots where date = (select max(date) from client_snapshots)
),
first as (
    select channel, package, metric, value as first_value
    from client_snapshots where date = (select min(date) from client_snapshots)
)
select
    case l.channel
        when 'nuget' then 'NuGet (.NET)'
        when 'conda-forge' then 'conda-forge'
        when 'docker' then 'Docker Hub'
        when 'homebrew' then 'Homebrew'
        when 'github' then 'GitHub'
        when 'crates' then 'crates.io (Rust)'
        when 'pypi' then 'PyPI (Python)'
        when 'npm' then 'npm (Node.js)'
        else l.channel
    end as channel,
    l.package,
    case l.metric
        when 'total_downloads' then 'Lifetime downloads'
        when 'pull_count' then 'Lifetime pulls'
        when 'install_30d' then 'Installs, last 30 days'
        when 'install_90d' then 'Installs, last 90 days'
        when 'install_365d' then 'Installs, last 365 days'
        when 'stars' then 'Stars'
        when 'forks' then 'Forks'
        when 'open_issues' then 'Open issues'
        when 'subscribers' then 'Watchers'
        when 'recent_downloads_90d' then 'Downloads, last 90 days'
        when 'recent_last_month' then 'Downloads, last 30 days'
        when 'downloads_last_week' then 'Downloads, last 7 days'
        when 'downloads_last_month' then 'Downloads, last 30 days'
        when 'downloads_last_year' then 'Downloads, last 365 days'
        when 'npm' then 'npm (Node.js)'
        else l.metric
    end as metric,
    l.value,
    l.value - f.first_value as change_since_first
from latest l
left join first f using (channel, package, metric)
where l.item is null
  and l.metric not in ('files', 'star_count', 'install_on_request_30d', 'install_on_request_90d', 'install_on_request_365d', 'recent_last_day', 'recent_last_week', 'downloads_last_month')
order by channel, package, metric
```

<p class="text-sm text-base-content-muted">
  These registries publish only a running total, so the site records it every night. Snapshots started
  <Value data={snapshot_dates} column=first_date fmt="mmm d, yyyy" />; the change column compares the latest snapshot to the first one.
</p>

<DataTable data={totals} rows=30 compact=true>
  <Column id=channel />
  <Column id=package />
  <Column id=metric />
  <Column id=value fmt=num0 />
  <Column id=change_since_first fmt=num0 contentType=delta title="Change since first snapshot" />
</DataTable>

```sql snapshot_trends
select
    date,
    channel || ' · ' || package || ' · ' || metric as series,
    value
from client_snapshots
where item is null
  and metric in ('total_downloads', 'pull_count', 'stars', 'install_30d')
order by date, series
```

{#if snapshot_dates.length > 0 && snapshot_dates[0].days > 1}

```sql trend_indexed
select date, series, 100.0 * value / first_value(value) over (partition by series order by date) as indexed
from ${snapshot_trends}
order by date, series
```

<LineChart emptySet=pass data={trend_indexed} x=date y=indexed series=series
  title="Running totals over time" subtitle="Each series scaled to 100 at the first snapshot" yAxisTitle="Index" />

{:else}
<p class="text-xs text-base-content-muted">A trend chart of these totals appears once several nightly snapshots have accumulated.</p>
{/if}

## GitHub releases

```sql releases
select
    item as release,
    sub_item::date as published,
    value as downloads,
    greatest(1, datediff('day', sub_item::date, (select max(date) from client_snapshots))) as days_since_release,
    value::double / greatest(1, datediff('day', sub_item::date, (select max(date) from client_snapshots))) as downloads_per_day
from client_snapshots
where date = (select max(date) from client_snapshots)
  and channel = 'github_releases' and metric = 'release_downloads'
order by published desc
limit 20
```

<p class="text-sm text-base-content-muted">
  Lifetime counts favour releases that have been available longer, while a per-day average flatters a release that
  is only days old and understates one that peaked and was superseded. Both views are shown; the nightly snapshots
  below build the fairer picture over time, downloads per day for each release as it ages.
</p>

<Grid cols=2 gap="20px">
  <BarChart emptySet=pass data={releases} x=release y=downloads swapXY=true
    title="Lifetime downloads per release" subtitle="20 most recent releases" xAxisTitle="Downloads" seriesColors={{'downloads': '#236aa4'}} />
  <BarChart emptySet=pass data={releases} x=release y=downloads_per_day swapXY=true yFmt=num0
    title="Average downloads per day since release" subtitle="Lifetime downloads divided by days since publication" xAxisTitle="Downloads / day" seriesColors={{'downloads_per_day': '#45a1bf'}} />
</Grid>

```sql release_daily
-- day-over-day change of each release's lifetime count across snapshots
with s as (
    select date, item as release, sub_item::date as published, value
    from client_snapshots
    where channel = 'github_releases' and metric = 'release_downloads'
),
deltas as (
    select
        date,
        release,
        published,
        value - lag(value) over (partition by release order by date) as downloads,
        datediff('day', lag(date) over (partition by release order by date), date) as days
    from s
),
recent as (
    select release from ${releases} order by published desc limit 6
)
select d.date, d.release, d.downloads::double / d.days as downloads_per_day
from deltas d
join recent using (release)
where d.downloads is not null
order by d.date, d.release
```

{#if snapshot_dates.length > 0 && snapshot_dates[0].days > 1}
<LineChart emptySet=pass data={release_daily} x=date y=downloads_per_day series=release
  title="Downloads per day by release" subtitle="From nightly snapshots; six most recent releases" yAxisTitle="Downloads / day" markers=true />
{:else}
<p class="text-xs text-base-content-muted">Downloads per day by release appear here once several nightly snapshots have accumulated.</p>
{/if}

```sql release_platforms
-- derive the platform from the asset file name, e.g. duckdb_cli-linux-amd64.zip
with assets as (
    select item as release, sub_item as asset, value as downloads
    from client_snapshots
    where date = (select max(date) from client_snapshots)
      and channel = 'github_releases' and metric = 'asset_downloads'
),
recent as (
    select release from ${releases} order by published desc limit 8
)
select
    a.release,
    case
        when a.asset ilike '%linux%' then 'Linux'
        when a.asset ilike '%osx%' or a.asset ilike '%macos%' then 'macOS'
        when a.asset ilike '%windows%' then 'Windows'
        when a.asset ilike '%wasm%' then 'WebAssembly'
        when a.asset ilike '%android%' then 'Android'
        else 'Other'
    end as platform,
    sum(a.downloads) as downloads
from assets a
join recent using (release)
group by all
order by a.release, platform
```

```sql release_kinds
with assets as (
    select item as release, sub_item as asset, value as downloads
    from client_snapshots
    where date = (select max(date) from client_snapshots)
      and channel = 'github_releases' and metric = 'asset_downloads'
),
recent as (
    select release from ${releases} order by published desc limit 8
)
select
    a.release,
    case
        when a.asset ilike 'duckdb_cli%' then 'CLI'
        when a.asset ilike 'libduckdb%' then 'libduckdb (C/C++)'
        when a.asset ilike '%odbc%' then 'ODBC'
        when a.asset ilike '%jdbc%' then 'JDBC'
        when a.asset ilike '%python%' then 'Python wheels'
        else 'Other'
    end as kind,
    sum(a.downloads) as downloads
from assets a
join recent using (release)
group by all
order by a.release, kind
```

<Grid cols=2 gap="20px">
  <BarChart emptySet=pass data={release_platforms} x=release y=downloads series=platform swapXY=true type=stacked100 yFmt=pct0
    title="Release downloads by platform" subtitle="Share of each release's downloads, eight most recent releases" />
  <BarChart emptySet=pass data={release_kinds} x=release y=downloads series=kind swapXY=true type=stacked
    title="Release downloads by artifact type" subtitle="Eight most recent releases" xAxisTitle="Downloads" />
</Grid>

