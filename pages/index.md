---
title: DuckDB extension weekly downloads
description: Explore dynamic insights into weekly and monthly download trends for DuckDB extensions, all in one interactive dashboard!
og: /images/main.png
---


# Weekly Downloads Overview

```sql all_downloads
select extension, downloads_last_week, year, week_number, type
from downloads
where _last_update = (select max(_last_update) from downloads)
order by downloads_last_week desc;
```
```sql ordered_data
WITH extension_totals AS (
    SELECT 
        extension,
        SUM(downloads_last_week) AS total_downloads
    FROM downloads
    where type = coalesce(nullif('${inputs.regular_or_community}', ''), 'Regular')
    GROUP BY extension
    ORDER BY total_downloads DESC
    LIMIT 10
)
SELECT 
--     array_slice(d.year::VARCHAR, 3, 4) || '-' || d.week_number as week_number,
    d.extension,
    d._last_update as date,
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
    FROM downloads
    WHERE type = 'Community'
    GROUP BY month_date
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
          <ButtonGroupItem valueLabel="Regular" value="Regular" default />
          <ButtonGroupItem valueLabel="Community" value="Community" />
      </ButtonGroup>
    </div>
    <LineChart
      data={ordered_data}
      x="date"
      y="downloads_last_week"
      series="extension"
      yAxisTitle="Downloads per Week"
      title="Weekly Downloads per Extension"
      subtitle="Top 10"
    />
  </div>
</Grid>

## Top Movers

```sql top_gainers
WITH latest_two_weeks AS (
    SELECT
        extension,
        type,
        downloads_last_week,
        _last_update,
        ROW_NUMBER() OVER (PARTITION BY extension ORDER BY _last_update DESC) as rn
    FROM downloads
),
current_week AS (
    SELECT extension, type, downloads_last_week FROM latest_two_weeks WHERE rn = 1
),
prev_week AS (
    SELECT extension, downloads_last_week as prev_downloads FROM latest_two_weeks WHERE rn = 2
)
SELECT
    c.extension,
    c.type,
    c.downloads_last_week,
    p.prev_downloads,
    c.downloads_last_week - p.prev_downloads AS absolute_change,
    (c.downloads_last_week - p.prev_downloads)::FLOAT / NULLIF(p.prev_downloads, 0) AS growth_rate
FROM current_week c
JOIN prev_week p ON c.extension = p.extension
WHERE p.prev_downloads >= 50
ORDER BY growth_rate DESC
LIMIT 5
```

```sql top_losers
WITH latest_two_weeks AS (
    SELECT
        extension,
        type,
        downloads_last_week,
        _last_update,
        ROW_NUMBER() OVER (PARTITION BY extension ORDER BY _last_update DESC) as rn
    FROM downloads
),
current_week AS (
    SELECT extension, type, downloads_last_week FROM latest_two_weeks WHERE rn = 1
),
prev_week AS (
    SELECT extension, downloads_last_week as prev_downloads FROM latest_two_weeks WHERE rn = 2
)
SELECT
    c.extension,
    c.type,
    c.downloads_last_week,
    p.prev_downloads,
    c.downloads_last_week - p.prev_downloads AS absolute_change,
    (c.downloads_last_week - p.prev_downloads)::FLOAT / NULLIF(p.prev_downloads, 0) AS growth_rate
FROM current_week c
JOIN prev_week p ON c.extension = p.extension
WHERE p.prev_downloads >= 50
ORDER BY growth_rate ASC
LIMIT 5
```

<Grid cols="2" gap="20px">
  <div>
    <h3>Biggest Gainers</h3>
    <DataTable data={top_gainers} rows=5>
      <Column id="extension" />
      <Column id="type" />
      <Column id="downloads_last_week" fmt=num0 title="This Week" />
      <Column id="absolute_change" contentType=delta fmt=num0 title="Change" />
      <Column id="growth_rate" contentType=delta fmt=pct1 title="Growth" />
    </DataTable>
  </div>
  <div>
    <h3>Biggest Losers</h3>
    <DataTable data={top_losers} rows=5>
      <Column id="extension" />
      <Column id="type" />
      <Column id="downloads_last_week" fmt=num0 title="This Week" />
      <Column id="absolute_change" contentType=delta fmt=num0 title="Change" />
      <Column id="growth_rate" contentType=delta fmt=pct1 title="Growth" />
    </DataTable>
  </div>
</Grid>

## This Week

```sql current_week_top
SELECT
    extension,
    type,
    downloads_last_week
FROM downloads
WHERE _last_update = (SELECT MAX(_last_update) FROM downloads)
ORDER BY downloads_last_week DESC
LIMIT 20
```

```sql leaderboard
SELECT
    ROW_NUMBER() OVER (ORDER BY total_downloads DESC) as rank,
    extension,
    type,
    total_downloads,
    last_week_downloads
FROM (
    SELECT
        extension,
        type,
        SUM(downloads_last_week) as total_downloads,
        MAX(CASE WHEN _last_update = (SELECT MAX(_last_update) FROM downloads) THEN downloads_last_week ELSE NULL END) as last_week_downloads
    FROM downloads
    GROUP BY extension, type
) sub
ORDER BY rank
```

<BarChart
  data={current_week_top}
  x="extension"
  y="downloads_last_week"
  series="type"
  swapXY=true
  title="Top 20 Extensions This Week"
  xAxisTitle="Downloads"
/>

## Leaderboard

<DataTable data={leaderboard} search=true rows=15>
  <Column id="rank" />
  <Column id="extension" />
  <Column id="type" />
  <Column id="total_downloads" fmt=num0 title="Total Downloads" />
  <Column id="last_week_downloads" fmt=num0 title="Last Week" />
</DataTable>

## Extension Details

```sql unique_extensions
select extension, type
from downloads
where type = coalesce(nullif('${inputs.extension_type_filter}', ''), 'Community')
group by all
order by extension
```

```sql selected_extension_type
select coalesce(
    (select type from downloads where extension = '${inputs.selected_item?.value || "duckpgq"}' limit 1),
    'Community'
) as type
```

```sql selected_extension_data
WITH all_weeks AS (
    SELECT
        _last_update::DATE as week_date,
        downloads_last_week as last_week_downloads,
        (downloads_last_week - LAG(downloads_last_week) OVER (ORDER BY _last_update::DATE))
            / LAG(downloads_last_week) OVER (ORDER BY _last_update::DATE) AS growth_rate
    FROM downloads
    WHERE extension = '${inputs.selected_item?.value || "duckpgq"}'
)
SELECT week_date, last_week_downloads, growth_rate
FROM all_weeks
ORDER BY week_date DESC
LIMIT 10;
```

```sql selected_extension_data_cumulative
select 
        sum(downloads_last_week) as total_downloads
from downloads
where extension = '${inputs.selected_item?.value || "duckpgq"}'
```

```sql selected_extension_monthly
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', _last_update)::DATE AS month_date,
        SUM(downloads_last_week) AS downloads_last_month
    FROM downloads
    WHERE extension = '${inputs.selected_item?.value || "duckpgq"}'
    GROUP BY DATE_TRUNC('month', _last_update)
),
growth_data AS (
    SELECT
        month_date,
        downloads_last_month,
        (downloads_last_month - LAG(downloads_last_month) OVER (ORDER BY month_date))
            / LAG(downloads_last_month) OVER (ORDER BY month_date) AS growth_rate
    FROM monthly
)
SELECT month_date, downloads_last_month, growth_rate
FROM growth_data
ORDER BY month_date DESC
LIMIT 10;
```

```sql extension_details
select * from extension_details where extension = '${inputs.selected_item?.value || "duckpgq"}'
```

```sql total_downloads_extension_data
select sum(downloads_last_week) as total_downloads from downloads where extension = '${inputs.selected_item?.value || "duckpgq"}' group by extension 
```

```sql downloads_by_week
select _last_update as date, downloads_last_week as downloads
from downloads
where extension = '${inputs.selected_item?.value || "duckpgq"}'
```


<Grid cols="2" gap="30px">
  <!-- Left Column: Metadata and Links -->
  <div>
    <!-- Type filter then extension dropdown -->
    <ButtonGroup name=extension_type_filter defaultValue="Community">
        <ButtonGroupItem valueLabel="Community" value="Community" default />
        <ButtonGroupItem valueLabel="Regular" value="Regular" />
    </ButtonGroup>
    <Dropdown
        name=selected_item
        data={unique_extensions}
        value=extension
        title="Select an Extension"
        defaultValue="duckpgq"
    />

    {#if selected_extension_type.length > 0}
    <Alert status="info">
        {selected_extension_type[0].type} Extension
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

    <div class="p-4 rounded-md bg-gray-200 text-black markdown">
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
          <a href={`https://duckdb.org/community_extensions/extensions/${inputs.selected_item?.value || "duckpgq"}.html`} target="_blank" style="margin-left: 8px;">View on Community Page</a>
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
      x=date
      y=downloads
      yAxisTitle="Downloads per Week"
      title="Weekly Downloads for {inputs.selected_item?.value || 'duckpgq'}"
    />

    {#if extension_details.length !== 0}

    <!-- Extended Description -->
    <div class="p-4 rounded-md bg-gray-200 text-black markdown">
      <h2>Description</h2>
      {@html extension_details[0].extended_description_html}
    </div>

    {/if}

  </div>
</Grid>