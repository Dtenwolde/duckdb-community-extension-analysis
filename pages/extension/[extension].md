---
description: Weekly downloads, GitHub stars and metadata for a DuckDB extension.
---

```sql ext
select *
from extension_stats
where extension = '${params.extension}'
```

```sql details
select *
from extension_details
where extension = '${params.extension}'
```

```sql weekly_all
select week_start, week_label, downloads_last_week, type
from downloads
where extension = '${params.extension}'
order by week_start
```

{#if !ext[0]?.type}

# {params.extension}

<Alert status="info">Loading statistics for <b>{params.extension}</b>. If nothing appears, there are no download statistics for an extension with this name. <a href="/extension/">Browse all extensions</a>.</Alert>

{:else}
{@const e = ext[0]}

# {params.extension}

<div class="flex flex-wrap items-center gap-2 text-sm text-base-content-muted mb-4">
  <span class="px-2 py-0.5 rounded-full text-xs font-medium" style="background: {e.type === 'Core' ? '#236aa4' : '#f4b548'}; color: {e.type === 'Core' ? 'white' : '#1f1f1f'}">{e.type} extension</span>
  <span>Rank <b>#{e.type_rank_all_time}</b> of all {e.type.toLowerCase()} extensions all-time, <b>#{e.type_rank_last_week}</b> last week</span>
  <span>Tracked since <Value data={ext} column=first_seen fmt="mmm d, yyyy" /> ({e.weeks_tracked} weeks)</span>
  {#if e.is_new}<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-positive/20 text-positive">New</span>{/if}
  {#if e.is_inactive}<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-warning/30">No downloads in the latest week</span>{/if}
</div>

```sql weekly_kpi
with rolling as (
    select
        week_start,
        downloads_last_week,
        sum(downloads_last_week) over (order by week_start rows between 3 preceding and current row) as downloads_4w
    from ${weekly_all}
)
select
    week_start,
    downloads_last_week,
    (downloads_last_week - lag(downloads_last_week) over (order by week_start))
        / nullif(lag(downloads_last_week) over (order by week_start), 0) as growth_rate,
    downloads_4w,
    (downloads_4w - lag(downloads_4w, 4) over (order by week_start))
        / nullif(lag(downloads_4w, 4) over (order by week_start), 0) as growth_4w
from rolling
order by week_start desc
limit 26
```

```sql stars
select date, star_count
from star_history
where extension = '${params.extension}'
order by date
```

<Grid cols=4 gap="16px">
  <BigValue data={ext} value=total_downloads title="Lifetime downloads" fmt=num0 />
  <BigValue data={weekly_kpi} value=downloads_last_week title="Last week" fmt=num0 sparkline=week_start
    comparison=growth_rate comparisonFmt=pct1 comparisonTitle="vs. previous week" />
  <BigValue data={weekly_kpi} value=downloads_4w title="Last 4 weeks" fmt=num0 sparkline=week_start
    comparison=growth_4w comparisonFmt=pct1 comparisonTitle="vs. previous 4 weeks" />
  {#if details.length > 0 && details[0].star_count !== null}
  <BigValue data={details} value=star_count title="GitHub stars" fmt=num0 />
  {:else}
  <BigValue data={ext} value=peak_week_downloads title="Best week" fmt=num0 />
  {/if}
</Grid>

## Downloads

<div class="flex flex-wrap items-end gap-6 my-4">
  <DateRange name=range data={weekly_all} dates=week_start defaultValue="All Time"
    presetRanges={['Last 3 Months', 'Last 6 Months', 'Last 12 Months', 'All Time']} title="Period" />
</div>

```sql weekly
select week_start, downloads_last_week
from ${weekly_all}
where week_start between '${inputs.range.start}' and '${inputs.range.end}'
order by week_start
```

```sql cumulative
select week_start, sum(downloads_last_week) over (order by week_start) as cumulative_downloads
from ${weekly_all}
where week_start between '${inputs.range.start}' and '${inputs.range.end}'
order by week_start
```

```sql rank_history
select week_start, rank
from (
    select
        extension,
        week_start,
        row_number() over (partition by week_start order by downloads_last_week desc) as rank
    from downloads
    -- chain on the ext query rather than reading e in JS, which is undefined while loading
    where type = (select type from ${ext})
      and week_start between '${inputs.range.start}' and '${inputs.range.end}'
)
where extension = '${params.extension}'
order by week_start
```

<Grid cols=2 gap="20px">
  <LineChart emptySet=pass data={weekly} x=week_start y=downloads_last_week yAxisTitle="Downloads / week"
    title="Weekly downloads" seriesColors={{'downloads_last_week': '#236aa4'}} markers=true markerSize=4 />
  <LineChart emptySet=pass data={cumulative} x=week_start y=cumulative_downloads yAxisTitle="Cumulative downloads"
    title="Cumulative downloads" seriesColors={{'cumulative_downloads': '#45a1bf'}} />
</Grid>

<Grid cols=2 gap="20px">
  <LineChart emptySet=pass data={rank_history} x=week_start y=rank
    title="Weekly rank among {e.type.toLowerCase()} extensions" subtitle="1 = most downloaded that week; lower is better"
    seriesColors={{'rank': '#8f3d56'}} step=true
    echartsOptions={{yAxis: {inverse: true, min: 1, max: Math.max(5, ...rank_history.map((r) => r.rank)), minInterval: 1}}} />
  {#if stars.length > 1}
  <LineChart emptySet=pass data={stars} x=date y=star_count yAxisTitle="Stars" title="GitHub stars over time"
    seriesColors={{'star_count': '#f4b548'}} yMin={0} />
  {:else if stars.length === 1}
  <div class="pt-6">
    <BigValue data={stars} value=star_count title="GitHub stars" fmt=num0 />
    <p class="text-sm text-base-content-muted mt-2">A trend line appears once there are several days of data. Star history has been collected nightly since <Value data={stars} column=date fmt="mmm d, yyyy" /></p>
  </div>
  {:else}
  <div class="pt-6 text-sm text-base-content-muted">No GitHub star history for this extension.</div>
  {/if}
</Grid>

## Compare

```sql peers
select extension
from extension_stats
where extension <> '${params.extension}'
order by total_downloads desc
```

<div class="flex flex-wrap items-end gap-4 my-2">
  <Dropdown name=compare_with data={peers} value=extension title="Compare with" defaultValue={e.type === 'Core' ? 'aws' : 'vss'} />
  <LinkButton url="/compare/?a={params.extension}&b={inputs.compare_with.value}">Open comparison</LinkButton>
</div>

{#if details.length > 0}

## About

<div class="grid grid-cols-1 lg:grid-cols-5 gap-x-10 gap-y-6 mt-2">
  <div class="lg:col-span-2 text-sm">
    <p class="mb-4">{details[0].description}</p>
    <table class="w-full">
      <tbody>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top whitespace-nowrap">Repository</td><td class="py-2 break-all"><a href="https://github.com/{details[0].repo_url}" target="_blank" rel="noopener" class="underline">{details[0].repo_url}</a></td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top">Docs</td><td class="py-2"><a href="https://duckdb.org/community_extensions/extensions/{params.extension}.html" target="_blank" rel="noopener" class="underline">duckdb.org community page</a></td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top">Version</td><td class="py-2 font-mono text-xs">{details[0].version ?? '–'}</td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top">Language</td><td class="py-2">{details[0].language ?? '–'}</td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top">Build</td><td class="py-2">{details[0].build ?? '–'}{details[0].requires_toolchains ? `, toolchains: ${details[0].requires_toolchains}` : ''}</td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top">License</td><td class="py-2">{details[0].license ?? '–'}</td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top">Maintainers</td><td class="py-2">{details[0].maintainers || '–'}</td></tr>
        <tr class="border-b border-base-content-muted/20"><td class="py-2 pr-4 text-base-content-muted align-top whitespace-nowrap">Excluded platforms</td><td class="py-2">{details[0].excluded_platforms === '- None' ? 'None' : (details[0].excluded_platforms ?? '').replace(/^- /gm, '').split('\n').join(', ')}</td></tr>
      </tbody>
    </table>
  </div>
  <div class="lg:col-span-3 text-sm [&_pre]:bg-base-200 [&_pre]:border [&_pre]:border-base-300 [&_pre]:rounded-md [&_pre]:p-3 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:text-xs [&_pre]:leading-relaxed [&_pre]:font-mono [&_pre_code]:bg-transparent [&_pre_code]:border-0 [&_pre_code]:p-0 [&_p]:text-sm [&_li]:text-sm">
    {#if details[0].extended_description_html}
    <article>{@html details[0].extended_description_html}</article>
    {:else}
    <p class="text-base-content-muted">This extension has no extended description in its description.yml.</p>
    {/if}
    {#if details[0].hello_world_html}
    <h3 class="text-base font-semibold mt-6 mb-2">Hello world</h3>
    {@html details[0].hello_world_html}
    {/if}
  </div>
</div>

{:else if e.type === 'Core'}

## About

<p class="text-sm text-base-content-muted">Core extensions are maintained by the DuckDB team. See the <a href="https://duckdb.org/docs/stable/core_extensions/overview" target="_blank" rel="noopener" class="underline">core extensions overview</a> for documentation.</p>

{/if}

{/if}
