---
title: All extensions
description: Every DuckDB core and community extension with download statistics, with a page per extension.
---

```sql all_extensions
select
    extension,
    type,
    total_downloads,
    last_week_downloads,
    wow_growth,
    first_seen,
    is_new,
    '/extension/' || extension as link
from extension_stats
order by extension
```

```sql counts
select type, count(*) as n from extension_stats group by type order by type
```

<p class="text-sm text-base-content-muted">
  <Value data={counts.filter(r => r.type === 'Community')} column=n /> community and <Value data={counts.filter(r => r.type === 'Core')} column=n /> core extensions. Click a row to open its page.
</p>

<DataTable data={all_extensions} link=link search=true rows=25>
  <Column id=extension />
  <Column id=type />
  <Column id=total_downloads fmt=num0 title="Lifetime downloads" />
  <Column id=last_week_downloads fmt=num0 title="Last week" />
  <Column id=wow_growth contentType=delta fmt=pct1 title="vs. prev. week" />
  <Column id=first_seen fmt="mmm yyyy" title="First seen" />
</DataTable>

<details class="mt-8 text-sm">
  <summary class="cursor-pointer text-base-content-muted">Plain list of all extension pages</summary>
  <div class="flex flex-wrap gap-x-3 gap-y-1 mt-2">
    {#each all_extensions as row}
      <a href="/extension/{row.extension}" class="underline">{row.extension}</a>
    {/each}
  </div>
</details>
