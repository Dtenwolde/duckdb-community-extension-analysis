---
title: DuckDB community extension weekly downloads
---


# Weekly Downloads Overview

```sql all_downloads
select extension, downloads_last_week, week_number, sum(downloads_last_week) as total_downloads from downloads group by all order by total_downloads desc; 
```
```sql ordered_data
WITH extension_totals AS (
    SELECT 
        extension,
        SUM(downloads_last_week) AS total_downloads
    FROM downloads
    GROUP BY extension
    ORDER BY total_downloads DESC
    LIMIT '${inputs.chart_top_or_all}'
)
SELECT 
    d.week_number,
    d.extension,
    d.downloads_last_week
FROM downloads d
JOIN extension_totals et ON d.extension = et.extension
ORDER BY et.total_downloads DESC, d.week_number;
```

```sql weekly_downloads_for_all
WITH weekly_downloads AS (
    SELECT 
        _last_update::DATE AS week_date,
        SUM(downloads_last_week) AS last_week_downloads
    FROM downloads
    GROUP BY _last_update::DATE
    ORDER BY week_date
),
growth_data AS (
    SELECT 
        week_date,
        last_week_downloads,
        (last_week_downloads - LAG(last_week_downloads) OVER (ORDER BY week_date)) 
            / LAG(last_week_downloads) OVER (ORDER BY week_date) AS growth_rate
    FROM weekly_downloads
)
SELECT 
    week_date,
    last_week_downloads,
    growth_rate
FROM growth_data
ORDER BY week_date DESC
LIMIT 10;
```

```sql monthly_downloads_for_all
WITH monthly_downloads AS (
    SELECT 
        DATE_TRUNC('month', _last_update)::DATE AS month_date,
        SUM(downloads_last_week) AS total_monthly_downloads
    FROM downloads
    GROUP BY month_date
    ORDER BY month_date
),
growth_data AS (
    SELECT 
        month_date,
        total_monthly_downloads,
        (total_monthly_downloads - LAG(total_monthly_downloads) OVER (ORDER BY month_date)) 
            / LAG(total_monthly_downloads) OVER (ORDER BY month_date) AS growth_rate
    FROM monthly_downloads
)
SELECT 
    month_date,
    total_monthly_downloads,
    growth_rate
FROM growth_data
ORDER BY month_date DESC
LIMIT 10;
```

<div style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px;">
  <!-- Left Column: BigValues -->
  <div style="display: flex; flex-direction: column; gap: 20px;">
    <BigValue 
      data={weekly_downloads_for_all} 
      value="last_week_downloads"
      sparkline="week_date"
      fmt=num0
      comparison="growth_rate"
      comparisonFmt="pct1"
      comparisonTitle="vs. Last Week"
      title="Total Weekly Downloads"
    />
    <BigValue 
      data={monthly_downloads_for_all} 
      value="total_monthly_downloads"
      sparkline="month_date"
      fmt=num0
      comparison="growth_rate"
      comparisonFmt="pct1"
      comparisonTitle="vs. Last Month"
      title="Total Monthly Downloads"
    />
    <LastRefreshed/>
  </div>

  <!-- Right Column: LineChart and ButtonGroup -->
  <div style="position: relative;">
    <div style="position: absolute; top: 10px; right: 10px; z-index: 10; background-color: white; padding: 5px; border-radius: 5px;">
      <ButtonGroup name=chart_top_or_all defaultValue=5>
          <ButtonGroupItem valueLabel="Top 5" defaultValue=5 value=5 />
          <ButtonGroupItem valueLabel="All" value=1000 />
      </ButtonGroup>
    </div>
    <LineChart
      data={ordered_data}
      x=week_number
      y=downloads_last_week
      series=extension
      yAxisTitle="Downloads per Week"
      title="Weekly Downloads per Extension"
    />
  </div>
</div>

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

```sql github_stars
select repo_url, star_count from github_stars where extension = '${inputs.selected_item.value}'
```


<div style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px; align-items: start;">
  <!-- Left Column -->
  <div>
    <!-- Dropdown for Extension Selection -->
    <Dropdown
        name=selected_item
        data={unique_extensions}
        value=extension
        title="Select an Extension"
        defaultValue="duckpgq"
    />

    <!-- Metrics Section -->
    <div style="margin-top: 20px; display: flex; flex-direction: column; gap: 20px;">
      <BigValue 
        data={selected_extension_data} 
        value="last_week_downloads"
        sparkline="week_date"
        comparison="growth_rate"
        comparisonFmt="pct1"
        comparisonTitle="vs. Last Week"
        title="Weekly Downloads"
      />
      <BigValue 
        data={selected_extension_monthly} 
        value="downloads_last_month"
        sparkline="month_date"
        comparison="growth_rate"
        comparisonFmt="pct1"
        comparisonTitle="vs. Last Month"
        title="Monthly Downloads"
      />
      <BigValue 
        data={selected_extension_data_cumulative} 
        value="total_downloads"
        fmt=num0
        title="Total Downloads"
      />
    </div>

    <!-- GitHub Information -->
    <div style="margin-top: 20px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
      <div style="display: flex; align-items: center; gap: 10px;">
        <!-- GitHub Icon and Link -->
        <img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="GitHub" width="20" height="20" />
        <a href="https://github.com/{github_stars[0].repo_url}" target="_blank">View on GitHub</a>
      </div>
      <!-- Using Material Icons -->
        <div style="display: flex; align-items: center; gap: 10px; margin-top: 10px;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/star/v9/24px.svg" alt="Stars" width="20" height="20" />
          <span>Stars: <strong>{github_stars[0].star_count}</strong></span>
        </div>
    </div>
  </div>

  <!-- Right Column -->
  <div>
    <!-- Weekly Downloads Chart -->
    <LineChart
      data={downloads_by_week}
      x=week
      y=downloads
      yAxisTitle="Downloads per Week"
      title="Weekly Downloads for Selected Extension"
    />
  </div>
</div>

## Weekly Downloads for Selected Extension

```sql downloads_by_week
select week_number as week, downloads_last_week as downloads
from downloads
where extension = '${inputs.selected_item.value}'
```

[//]: # (<BarChart)

[//]: # (    data={downloads_by_week})

[//]: # (    x=week)

[//]: # (    y=downloads)

[//]: # (/>)

[//]: # (## Top Extensions by Weekly Downloads)

[//]: # ()
[//]: # (```sql top_extensions)

[//]: # (select week_number, extension, downloads_last_week as downloads)

[//]: # (from downloads)

[//]: # (where extension in &#40;)

[//]: # (    select extension)

[//]: # (    from downloads)

[//]: # (    group by extension)

[//]: # (    order by sum&#40;downloads_last_week&#41; desc)

[//]: # (    limit 5)

[//]: # (&#41;)

[//]: # (order by week_number, extension)

[//]: # (```)

[//]: # ()
[//]: # (<AreaChart)

[//]: # (    data={top_extensions})

[//]: # (    x=week_number)

[//]: # (    y=downloads)

[//]: # (    yAxisTitle="Downloads per Week")

[//]: # (    series=extension)

[//]: # (    stacked={true})

[//]: # (/>)
