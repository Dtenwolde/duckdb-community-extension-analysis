---
title: DuckDB extension weekly downloads
description: Explore dynamic insights into weekly and monthly download trends for DuckDB extensions, all in one interactive dashboard!
og: /images/main.png
---


# Weekly Downloads Overview

```sql all_downloads
select extension, downloads_last_week, week_number, sum(downloads_last_week), type as total_downloads from downloads group by all order by total_downloads desc; 
```
```sql ordered_data
WITH extension_totals AS (
    SELECT 
        extension,
        SUM(downloads_last_week) AS total_downloads
    FROM downloads
    where type = '${inputs.regular_or_community}'
    GROUP BY extension
    ORDER BY total_downloads DESC
    LIMIT 10
)
SELECT 
    d.week_number,
    d.extension,
    d.downloads_last_week
FROM downloads d
JOIN extension_totals et ON d.extension = et.extension
ORDER BY et.total_downloads DESC, d.week_number;
```

```sql weekly_downloads_for_all_community
WITH weekly_downloads AS (
    SELECT 
        _last_update::DATE AS week_date,
        SUM(downloads_last_week) AS last_week_downloads
    FROM downloads
    WHERE type = 'Community'
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

```sql weekly_downloads_for_all_regular
WITH weekly_downloads AS (
    SELECT 
        _last_update::DATE AS week_date,
        SUM(downloads_last_week) AS last_week_downloads
    FROM downloads
    WHERE type = 'Regular'
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

```sql monthly_downloads_for_all_community
WITH monthly_downloads AS (
    SELECT 
        DATE_TRUNC('month', _last_update)::DATE AS month_date,
        SUM(downloads_last_week) AS total_monthly_downloads
    FROM downloads where type = 'Community'
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
```sql monthly_downloads_for_all_regular
WITH monthly_downloads AS (
    SELECT 
        DATE_TRUNC('month', _last_update)::DATE AS month_date,
        SUM(downloads_last_week) AS total_monthly_downloads
    FROM downloads
    WHERE type = 'Regular'
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

<Grid cols="2" gap="20px">
  <!-- Left Column: BigValues -->
  <Grid cols="2" gap="20px">
    <Grid cols="1" gap="20px">
        <BigValue 
          data={weekly_downloads_for_all_regular} 
          value="last_week_downloads"
          sparkline="week_date"
          fmt=num0
          comparison="growth_rate"
          comparisonFmt="pct1"
          comparisonTitle="vs. Last Week"
          title="Total Regular Downloads Last Week"
        />
        <BigValue 
          data={monthly_downloads_for_all_regular} 
          value="total_monthly_downloads"
          sparkline="month_date"
          fmt=num0
          comparison="growth_rate"
          comparisonFmt="pct1"
          comparisonTitle="vs. Last Month"
          title="Total Regular Downloads Last Month"
        />
    </Grid>
    <Grid cols="1" gap="20px">
        <BigValue 
          data={weekly_downloads_for_all_community} 
          value="last_week_downloads"
          sparkline="week_date"
          fmt=num0
          comparison="growth_rate"
          comparisonFmt="pct1"
          comparisonTitle="vs. Last Week"
          title="Total Community Downloads Last Week"
        />
        <BigValue 
          data={monthly_downloads_for_all_community} 
          value="total_monthly_downloads"
          sparkline="month_date"
          fmt=num0
          comparison="growth_rate"
          comparisonFmt="pct1"
          comparisonTitle="vs. Last Month"
          title="Total Community Downloads Last Month"
        />
    </Grid>
    <LastRefreshed />
  </Grid>

  <!-- Right Column: LineChart and ButtonGroup -->
  <div style="position: relative;">
    <div style="position: absolute; top: -30px; right: 0px; z-index: 10; padding: 1px; border-radius: 1px;">
      <ButtonGroup name=regular_or_community defaultValue="Regular" colorPalette=myColorPalette>
          <ButtonGroupItem valueLabel="Regular" value="Regular" />
          <ButtonGroupItem valueLabel="Community" value="Community" />
      </ButtonGroup>
    </div>
    <LineChart
      data={ordered_data}
      x="week_number"
      y="downloads_last_week"
      series="extension"
      yAxisTitle="Downloads per Week"
      title="Weekly Downloads per Extension"
    />
  </div>
</Grid>

## Extension Details

```sql unique_extensions
select extension, type
from downloads
group by all
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

```sql extension_details
select * from extension_details where extension = '${inputs.selected_item.value}'
```

```sql total_downloads_extension_data
select sum(downloads_last_week) as total_downloads from downloads where extension = '${inputs.selected_item.value}' group by extension 
```

```sql downloads_by_week
select week_number as week, downloads_last_week as downloads
from downloads
where extension = '${inputs.selected_item.value}'
```


<Grid cols="2" gap="30px">
  <!-- Left Column: Metadata and Links -->
  <div>
    <!-- Dropdown for selecting extensions -->
    <Dropdown
        name=selected_item
        data={unique_extensions}
        value=extension
        title="Select an Extension"
        defaultValue="duckpgq"
    />

    {#if extension_details.length !== 0}
        <Alert status="info">
            Community Extension    
        </Alert>
    {:else}
        <Alert status="info">
            Regular Extension    
        </Alert>
    {/if}

    <!-- BigValue Stats -->
    <Grid cols="1" gap="15px" style="margin-top: 15px;" >
      <BigValue
      data={total_downloads_extension_data}
      value="total_downloads"
      title="Total Downloads Lifetime"
      fmt=num0
      />
      <BigValue 
        data={selected_extension_data} 
        value="last_week_downloads"
        sparkline="week_date"
        fmt=num0
        comparison="growth_rate"
        comparisonFmt="pct1"
        comparisonTitle="vs. Last Week"
        title="Total Downloads Last Week"
      />
      <BigValue 
        data={selected_extension_monthly} 
        value="downloads_last_month"
        sparkline="month_date"
        fmt=num0
        comparison="growth_rate"
        comparisonFmt="pct1"
        comparisonTitle="vs. Last Month"
        title="Total Downloads Last Month"
      />

    <div>

    {#if extension_details.length !== 0}

    <div style="margin-top: 20px; padding: 15px; background-color: #0284c7; border-radius: 8px;">
      <!-- Links and Metadata -->
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <!-- GitHub Link -->
        <div style="display: flex; align-items: center;">
          <img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="GitHub" width="16" height="16" />
          <a href="https://github.com/{extension_details[0].repo_url}" target="_blank" style="margin-left: 8px;">View on GitHub</a>
        </div>

        <!-- Community Page Link -->
        <div style="display: flex; align-items: center;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/group/v8/24px.svg" alt="Community" width="16" height="16" />
          <a href={`https://duckdb.org/community_extensions/extensions/${inputs.selected_item.value}.html`} target="_blank" style="margin-left: 8px;">View on Community Page</a>
        </div>

        <!-- Stars -->
        <div style="display: flex; align-items: center;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/star/v9/24px.svg" alt="Stars" width="16" height="16" />
          <span style="margin-left: 8px;">Stars: <strong>{extension_details[0].star_count}</strong></span>
        </div>

        <!-- Version -->
        <div style="display: flex; align-items: center;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/update/v6/24px.svg" alt="Version" width="16" height="16" />
          <span style="margin-left: 8px;">Version: <strong>{extension_details[0].version}</strong></span>
        </div>

        <!-- Build -->
        <div style="display: flex; align-items: center;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/build/v8/24px.svg" alt="Build" width="16" height="16" />
          <span style="margin-left: 8px;">Build: <strong>{extension_details[0].build}</strong></span>
        </div>

        <!-- Language -->
        <div style="display: flex; align-items: center;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/code/v8/24px.svg" alt="Language" width="16" height="16" />
          <span style="margin-left: 8px;">Language: <strong>{extension_details[0].language}</strong></span>
        </div>

        <!-- Maintainers -->
        <div style="display: flex; align-items: center;">
          <img src="https://fonts.gstatic.com/s/i/materialicons/group/v8/24px.svg" alt="Maintainers" width="16" height="16" />
          <span style="margin-left: 8px;">Maintainers: <strong>{extension_details[0].maintainers}</strong></span>
        </div>

        <!-- Excluded Platforms -->
        <div style="display: flex; flex-direction: column;">
          <span><strong>Excluded Platforms:</strong></span>
          <div style="margin-left: 20px;">{@html extension_details[0].excluded_platforms_html}</div>
        </div>
    </div>

    </div>

    {/if}

    </Grid>
  </div>
  <!-- Right Column: Line Chart and Description -->
  <div>
    <LineChart
      data={downloads_by_week}
      x=week
      y=downloads
      yAxisTitle="Downloads per Week"
      title="Weekly Downloads for {inputs.selected_item.value}"
    />

    {#if extension_details.length !== 0}

    <!-- Extended Description -->
    <div style="margin-top: 20px; padding: 15px; background-color: #0284c7; border-radius: 8px;">
      <h2>Description</h2>
      {@html extension_details[0].extended_description_html}
    </div>

    {/if}

  </div>
</Grid>