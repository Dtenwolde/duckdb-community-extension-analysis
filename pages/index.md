---
title: DuckDB community extension weekly downloads
---


# Weekly Downloads Overview

```sql all_downloads
select extension, downloads_last_week, week_number, sum(downloads_last_week) as total_downloads from downloads group by all order by total_downloads desc; 
```

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

```sql selected_extension_monthly
select 
    date_trunc('month', _last_update)::DATE as month_date,
    sum(downloads_last_week) as downloads_last_month,
    (sum(downloads_last_week) - lag(sum(downloads_last_week)) over (order by date_trunc('month', _last_update))) / lag(sum(downloads_last_week)) over (order by date_trunc('month', _last_update)) as growth_rate
from downloads
where extension = '${inputs.selected_item.value}'
group by date_trunc('month', _last_update)
order by month_date desc
limit 10;
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
      data={selected_extension_monthly} 
      value="downloads_last_month"
      sparkline="month_date"
      comparison="growth_rate"
      comparisonFmt="pct1"
      comparisonTitle="vs. Last Month"
    />
  </div>
  <div style="flex: 4;">
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
