---
title: DuckDB community extension weekly downloads
queries: 
 - all_downloads.sql
---


# Weekly Downloads Overview

<LineChart 
  data={all_downloads}
  x=week_number
  y=downloads_last_week 
  yAxisTitle="Downloads per Week"
  series=extension
/>

## Extension Details

```sql unique_extensions
select extension
from downloads 
group by 1
```

```sql selected_extension_data
select 
        _last_update::DATE as week_date,
        downloads_last_week as last_week_downloads,
        (downloads_last_week - lag(downloads_last_week) over (order by _last_update::DATE)) / lag(downloads_last_week) over (order by _last_update::DATE) as growth_rate
from downloads
where extension = '${inputs.selected_item.value}'
order by week_date desc
limit 10;
```

```sql selected_extension_data_cumulative
select 
        sum(downloads_last_week) as total_downloads
from downloads
where extension = '${inputs.selected_item.value}'
```


<div style="display: flex; align-items: center;">
  <div style="flex: 1;">
    <Dropdown
        name=selected_item
        data={unique_extensions}
        value=extension
        title="Select an extension"
        defaultValue="duckpgq"
    />
  </div>
  <div style="flex: 2;">
    <BigValue 
      data={selected_extension_data} 
      value="last_week_downloads"
      sparkline="week_date"
      comparison="growth_rate"
      comparisonFmt="pct1"
      comparisonTitle="vs. Last Week"
    />
  </div>
    <div style="flex: 3;">
    <BigValue 
      data={selected_extension_data_cumulative} 
      value="total_downloads"
      fmt=num0
    />
  </div>
</div>

## Weekly Downloads for Selected Extension

```sql downloads_by_week
select week_number as week, downloads_last_week as downloads
from downloads
where extension = '${inputs.selected_item.value}'
```

<BarChart
    data={downloads_by_week}
    x=week
    y=downloads
/>

## Top Extensions by Weekly Downloads

```sql top_extensions
select week_number, extension, downloads_last_week as downloads
from downloads
where extension in (
    select extension
    from downloads
    group by extension
    order by sum(downloads_last_week) desc
    limit 5
)
order by week_number, extension
```

<AreaChart
    data={top_extensions}
    x=week_number
    y=downloads
    yAxisTitle="Downloads per Week"
    series=extension
    stacked={true}
/>
