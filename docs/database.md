# `shared/` and ClickHouse

The api/process contract, every table, and how anomalies are derived.

## `shared/` — the contract between `api` and `process`

Both containers mount `./shared` at `/app/shared`. Seven modules:

- **`domain.py` + `domain.yml`** — grid geometry, variable metadata, named region boxes.
  Describes **two** grids and the distinction matters: `global` is the full 7200×3600
  CoralTemp grid that `gy`/`gx` index; `subset` is the Pacific box actually ingested.
  It also carries a **`quantities`** block, which is deliberately not `variables`: a
  variable is something `/image` can draw and the frontend's toggle is built from that
  list, so an entry there with no raster would appear as a map layer rendering nothing.
  A quantity is a number that only exists once cells have been aggregated over an area.
  There is one — `mhw_extent`, what `mhw` means over a region — and every timeseries
  response names its quantity in `quantity` (null at a point) so no client infers it
  from the scope.
- **`mask.py` + `regions/*.geojson`** — the regions that are **not boxes** (15 of 29). A region is
  normally a lat/lon rectangle; Canada's Pacific bioregions are a 200-nautical-mile arc
  closed by two negotiated lateral boundaries, and their bounding box is 55,533 cells
  against the region's 26,222 — so 53% of what a box query would average is Alaskan,
  American or high-seas water. The box survives as the **prefilter** (`ORDER BY (gy, gx, date)` makes it
  contiguous key ranges) and this rasterises the polygon into `region_cells`, which the
  two rollup builders intersect it with. **A cell is in the region when its centre is
  inside the ring** — no partial weighting, because a fractional-coverage weight would be
  a second, subtler definition of "in the region" that `n_cells` could not describe.
  Nothing here decides what is *ocean*: the mask is pure geometry and includes the land
  inside the zone, which `sst_daily` then excludes — which is also why the stored polygon
  carries no interior rings for the islands. A hole is stored only for **water** a region
  does not cover (`Region.holes`; today only Saint-Pierre et Miquelon), and a cell inside
  one is out.
- **`fields.py`** — NetCDF reading, and the single home of both orientation rules above.
- **`render.py`** — field array → Web-Mercator WebP. **Takes arrays, never a DB client.**
- **`periods.py`** — daily/weekly/monthly buckets, shared by query and render.
- **`buckets.py`** — **the single definition of what a bucket's field is.** Reads the days
  on disk and reduces them: mean for `sst`/`anom`, **max for `mhw`**. It lives here rather
  than in `process` because the API once rendered on demand and had grown a second copy of
  it — the exact drift retiring `api/prerender.py` was meant to end.
- **`ch.py`** — the ClickHouse client factory and the **single definition of the schema**
  (`DDL`, applied idempotently by `ensure_schema()`). No `.sql` file; keeping the DDL in
  one Python constant is what stops `api` and `process` drifting apart.

## ClickHouse (`db-ch`, database `enso`)

**`sst_daily`** — one row per (date, ocean cell). ~113.7 B rows, ~85 GB.

```sql
date      Date    CODEC(DoubleDelta, ZSTD(3))
gy        UInt16  -- global row index, 0..3599
gx        UInt16  -- global column index, 0..7199 (0-360 convention)
sst_raw   Int16   -- raw source counts, 0.01 degC
has_clim  UInt8   -- does this cell have a climatology for this date's MMDD?
sst       Float32 ALIAS sst_raw * 0.01
lat       Float32 ALIAS -89.975 + gy * 0.05
lon       Float32 ALIAS 0.025 + gx * 0.05
ENGINE = MergeTree ORDER BY (gy, gx, date)
PARTITION BY if(toYear(date) >= 2026, toString(toYear(date)),
                toString(intDiv(toYear(date), 10) * 10))    -- decades, then years
```

**`sst_clim`** — the 1991–2020 daily climatology, one row per (mmdd, ocean cell).
2.68 B rows, **2.18 GiB**. `ORDER BY (gy, gx, mmdd)`.

**`mhw_daily`** — one row per (date, cell) **that is actually in a heatwave**. ~24.2 B rows.

```sql
date  Date    CODEC(DoubleDelta, ZSTD(3))
gy    UInt16
gx    UInt16
cat   UInt8   -- 1..5, the source's own ordinal class; no scale factor to undo
lat   Float32 ALIAS -89.975 + gy * 0.05
lon   Float32 ALIAS 0.025 + gx * 0.05
ENGINE = MergeTree ORDER BY (gy, gx, date)
PARTITION BY if(toYear(date) >= 2026, toString(toYear(date)),
                toString(intDiv(toYear(date), 10) * 10))    -- decades, then years
```

**Only `cat >= 1` is stored, and that is what makes it affordable.** Measured over 40
random days spanning the archive, the box averages **1,592,012** heatwave cells a day
against 7,477,923 ocean cells — so ~24.2 B rows rather than ~113.7 B.

**The cost is that absence is ambiguous.** A missing (date, cell) is heatwave-free ocean,
ice, land, *or a date that was never ingested*, and the table cannot say which. Two
consequences, both load-bearing:

1. Every query reads `mhw_daily` as the **right side of a LEFT JOIN against `sst_daily`**,
   which holds exactly the ocean cells for a date. That join supplies the zeros and
   excludes the land, and both tables share `ORDER BY (gy, gx, date)`, so at a point it is
   a primary-key read on both sides. A *box* deliberately does not join — see
   `_region_mhw_daily`.
2. A partly-ingested archive reports a confident **category 0** for every date it has not
   reached, not a gap — so `/coverage` carries `mhw.complete` and the frontend refuses to
   offer the variable until it is true. This is the same shape as `climatology.complete`
   gating `anom`, but sharper: there is no value that could signal the difference.

**`region_cells`** — which grid cells a **polygon** region covers: one row per (region,
cell), and rows only for the `domain.yml` regions that declare a `polygon`. **~12.2 M rows
across 15 regions**: 26,222 of them are `pacific_bioregions`, and 2.8 M are `indian`.

A plain box needs none — its `BETWEEN` says everything there is to say about which cells
it holds. Canada's Pacific waters are not a rectangle: `pacific_bioregions`' bounding box
is 55,533 cells against the region's 26,222, so **53% of what a box query would average is
Alaskan, American or high-seas water**. Measured on 2021-06-28, the heat dome: the region's
SST mean is 13.99 °C against the box's 13.74, and its anomaly +1.58 against +1.48 — the box
dilutes the thing the region exists to show.

**Materialised rather than evaluated.** Point-in-polygon over 55,533 cells is
milliseconds, but it would sit inside the rollup's 113-billion-row scan and be re-decided
on every pass. Written once by `CRW.cli mask`, read thereafter as a set membership —
`AND (gy, gx) IN (SELECT gy, gx FROM region_cells WHERE region = ...)`, appended after the
`gy`/`gx` BETWEEN that still does the primary-key work.

**It is applied by `process`, never by `api`.** A named region is served entirely from
`region_daily` and `region_clim`, so the mask reaches the API only in the numbers those
tables already hold. Nothing in `api/` reads this table, and nothing should: adding a live
masked path would be a second definition of what the region covers.

**Both sides or neither.** `regions.mask_filter()` is appended to the SST half *and* the
MHW half of the daily rollup, and to `region_clim`'s query. Masking one only would divide
a zone numerator by a bounding-box denominator, or put the zone's anomaly against the
box's climatology — the `mean(sst - clim) == mean(sst) - mean(clim)` identity needs both
sides averaging the same cells. Verified: `/region/pacific_bioregions?variable=anom` for
2021-06-28 returns **1.583** against a direct cell-wise `avg(sst - clim)` over the polygon
of **1.5827**, on the same 23,875 cells.

**`region_clim`** — **9,517 rows**: 366 MMDD for most of the 29 regions, but **fewer for
the ice-covered ones**, because an MMDD gets a row only where the region has at least one
cell with a climatology that day: `arctic_basin` 2, `western_arctic` 67, `hudson_bay` 152. The climatology side
of a region anomaly.

**`sst_recent` / `mhw_recent`** — the archive tables' last `RECENT_DAYS` (70) ordered
**`(date, gy, gx)`**, so `run`'s one-date rollup reads that date and nothing else. Partitioned
by month, `TTL date + 70 DAY` with `ttl_only_drop_parts`, so they hold 70–100 days: ~0.9 B a
row, **~1.1–1.5 GB** together (59 days measured at 911 MiB).

- **Filled by materialized views** (`sst_recent_mv`, `mhw_recent_mv`) on every insert into
  the archive tables, for in-window dates only, so a backfill of 1985 writes nothing here.
- **Deletes do not propagate through a view.** `ingest.delete_day` clears the twin as well
  (lightweight, synchronous); `backfill --fresh` truncates both.
- **Read only when provably complete.** `CRW/recent.py`'s `covers()` compares each date's row
  count with the `n_rows` its status table recorded; one mismatch and the rollup reads the
  archive tables, as before. `rollup` (bulk) always reads the archive (`source="archive"`).
  Same SQL either way, only the table names differ.
- **`CRW.cli recent` is the one-off after deploying them**: it copies whichever window dates
  the views have not seen (2 m 39 s for 59 days on dev; it reads the window's archive
  partitions once). Stop `scheduler` while it runs, or a concurrent ingest can leave a date
  doubled — harmless, since `covers()` then falls back, but slow until the next fill.
  `CRW.cli check` warns (`rollup.recent_tables`) when the last 30 days are not covered.
- In January the window reaches into the previous year, which sits in a decade partition,
  so a fill then reads that whole decade. Fill before the new year or accept the scan.

**`region_daily`** — 29 regions × ~15,250 days = **~442,000 rows**, ~8 MiB. The daily side, and the
one that actually costs something.

```sql
region         LowCardinality(String)
date           Date
mean_sst       Float32   -- over every ocean cell in the box      -> sst
n_cells        UInt32
mean_sst_clim  Float32   -- over its has_clim = 1 cells only      -> anom
n_cells_clim   UInt32
mean_mhw       Float32   -- sum(cat*cos) / sum(cos) over the ocean  (severity, a card)
mhw_area_frac  Float32   -- sumIf(cos, cat>=1) / sum(cos)           -> mhw
n_cells_mhw    UInt32
ENGINE = ReplacingMergeTree(updated_at) ORDER BY (region, date)
```

**`mhw` over a region is `mhw_area_frac`, not `mean_mhw`, and that is the point of
having both.** `mean_mhw` is an area mean of NOAA's five *ordinal* classes, so it folds
severity and extent into one number: half a box at Cat 1 and a tenth of it at Cat 5 both
come to about 0.5, and `StatsPanel` carried four sentences of warning saying so. The share
of the box's ocean **area** at category >= 1 answers the question a box is actually asked,
needs no warning, and is what the chart plots, the ranking ranks and the CSV exports.
`mean_mhw` survives as the only column that carries severity at all. Both come off the same
scan and the same denominator; the fraction is stored unscaled and served as a percentage
by `_MHW_EXTENT_SCALE`, in the one place a region's `mhw` value leaves the database.

**A point is untouched**: there the value is a class, `max` still reduces a bucket, and an
"extent" at one cell would only ever be 0% or 100%.

**Measured, this is the 97.6% that `region_clim` is not.** The climatology side costs
0.296 s live against a daily side of 12.14 s for Niño 3.4 — so `region_clim` removes 2.4%
of the request. The live daily query runs **3.14 s** for the smallest named region (Niño
1+2, 38,455 cells) and **12.14 s** for Niño 3.4 (201,392 cells), which is not a latency an
interactive panel can be built on. That measurement is what the "deliberately absent until
measurement says otherwise" note above `region_daily` was waiting for.

**The two SST columns are not redundant, and collapsing them is the way this table gets
silently wrong.** `region_timeseries()` restricts the daily mean to `has_clim = 1` for
`anom` and deliberately does not for `sst`, so the two variables average different cell
sets — and the gap moves through the year with the climatological ice edge. The Bering Sea
box holds 70,166 ocean cells but only **12,086** with a climatology on 15 March. Serving
`anom` from `mean_sst` would break the `mean(sst - clim) == mean(sst) - mean(clim)`
identity exactly over the ice fringe, which is where a marine-heatwave question gets asked.

**No bucketing lives here.** Weekly and monthly reduction stays in `region_timeseries()`,
which folds these daily rows in Python through `shared/periods.py`. Materialising weeks
would put a second definition of "a week" in the codebase — the drift retiring
`api/prerender.py` was meant to end. `mean_sst_clim` is **NaN**, not 0, when a region has
no climatology cells at all on a date; no configured region hits this, but a 0 there would
read as "exactly at climatology".

**Only named regions have a rollup.** `/regionTimeseries` on an arbitrary box still
aggregates live, and that is the only difference between the two endpoints.

**`pacific` is the Pacific basin, as a polygon region.** It was added so the header ribbon's
basin-wide heatwave extent (since removed) was a rollup read rather than a scan, and adding it there rather
than writing a second aggregation path means `region_daily`, `region_clim`,
`/region/{key}`, the monthly ranking, the region outline on the map and the CSV export all
serve it with no new code.

**It was the old ingested box (60°S–65°N, 100°E–70°W) until 2026-10-02**, which counted the
Gulf of Mexico, the Caribbean, Hudson Bay and the eastern Indian Ocean as Pacific: 995,980
of the box's 7,477,923 ocean cells (13%). It is now GOaS's North + South Pacific plus its
*South China and Eastern Archipelagic Seas* (GOaS keeps those as their own region; dropping
them would take the warm pool out of the basin). 6,496,585 ocean cells, 14,642 of them
outside the old box (the Bering Sea up to the strait, Drake Passage). GOaS cuts the ocean at
the antimeridian, so the file's western halves were shifted +360 and unioned into one ring;
its `properties` record how. The scanline mask equals shapely's count exactly (6,582,607
cells including coastal land). Changing the outline changes what every stored row for this
key means, so it needs `rollup --clim --region pacific --fresh`.

**`ingest_status`** / **`mhw_status`** — `ReplacingMergeTree(updated_at) ORDER BY date`, one
row per day, one table per archive. Two tables rather than one with a `product` column
because the sorting key is `date` and a product would have to join it, which cannot be
altered in place — and because the two archives genuinely progress independently.

Five decisions worth not undoing:

1. **There are no projections anywhere, and this is the central design decision.** The
   OISST schema carried a `by_date` projection so whole-day map reads did not scan a table
   ordered for point timeseries. Measured, that projection was **1.47 of 2.22 bytes per
   row — 66% of total storage**. At CoralTemp's volume it would cost ~150 GB.

   It is gone because **images are no longer rendered from the database**: the daily
   NetCDF is still on disk when `process` renders that day's frames. ClickHouse now serves
   only what it is ordered for. The cost, stated plainly: re-rendering a historical bucket
   without its NetCDF is a partition scan, so pre-rendered images are the durable artifact
   and a mass re-render means re-downloading the range. `/image` 404s rather than hangs.

2. **`gy`/`gx` index the global grid, not the subset**, so a cell's identity does not
   depend on the current box. Conversions go through `shared.domain.global_grid()` — never
   hand-roll them.

3. **`sst_raw` is the source's own Int16, with an ALIAS doing the ×0.01.** Lossless,
   2 bytes, compresses far better than Float32. ALIAS columns cost no storage.

4. **`has_clim` is per (cell, date), not per cell.** The ice edge moves through the year,
   so it cannot be a static property. It is what makes the region identity below exact.

5. **Partitioning is by decade for the archive and by year from 2026 on, and the point
   query is the whole reason.** `ORDER BY (gy, gx, date)` makes one cell's 15k-row history
   a single contiguous key range — which is exactly what the chart asks for on every map
   click — and a partition key cuts that range into one piece per partition. The cost is
   **not** the bytes: a point query reads ~8.5 MiB either way. It is the **file opens**,
   measured at **~4.0 per selected part** (729 opens over 181 parts; 12 over 3). Each one
   is a seek, and that is ~50 us on NVMe against **~4.3 ms** on the production box's HDD.

   Measured against that server, one cold cell, full archive:

   | | partitions | parts | file opens | cold TTFB |
   |---|---|---|---|---|
   | `PARTITION BY toYear(date)` | 42 | 196 | ~790 | **~3.4 s** |
   | this expression (boundary 2024) | 8 | 8 | ~32 | **~0.14 s** |

   On dev after the 2026-09 global rebuild (boundary 2026, 6 partitions, each merged to one
   part, `sst_clim` merged to one): an `anom` point query selects **7 parts** (6 + 1) and
   makes **34 file opens**. Before `sst_clim` was merged it was 17 parts and ~70 opens —
   the climatology table counts too.

   **The symptom this fixes is "only the first click is slow."** A second query on the same
   cell is ~0.18 s under either scheme, because the granules are in the page cache by then —
   which is also why prewarming the mark cache changed nothing measurable. `sst_daily`'s
   marks are only 89 MiB and were already resident; the cost is the *data* granules,
   scattered over 129 GB, which nothing can hold.

   **The current year stays per-year deliberately.** `ingest.delete_day()` replaces a
   revised date with an `ALTER ... DELETE`, a mutation that rewrites every part it
   touches, and folding the current year into a decade would take that from ~7 GiB to
   ~40–65 GiB (global). The source only ever revises the recent end (`--recheck-days`),
   so splitting the key at that boundary buys the fast read without paying for it on
   ingest. **Only the year still being revised needs its own partition**, which is why the
   boundary moved from 2024 to 2026 in the 2026-09 rebuild and 2024–2025 folded into the
   2020s.

   **It is also sized to the disk it runs on, and the rule is 2× free, not 1×.** Merges are
   capped by free space: ClickHouse will only select a merge (including `OPTIMIZE FINAL`)
   when free space, less what running merges have reserved, is about **twice** the
   partition's size — below that `OPTIMIZE` returns immediately and merges nothing, with no
   error. Globally the decades are **~62–65 GiB** (the 2020s ~38 GiB), so merging one needs
   ~130 GB free; one ~250 GiB `archive` partition would never merge at all.

   Bumping `shared.ch.PARTITION_BOUNDARY_YEAR` is the maintenance this needs, each January
   or so: years past it accumulate one partition each. Nothing breaks meanwhile — a point
   query just picks up one more part per elapsed year.

   **Moving a partition between keys, without rewriting it.** `ATTACH PARTITION ... FROM`
   refuses across differing partition keys, even for a partition whose value is the same
   under both. What works is `DETACH PARTITION` (with `SETTINGS max_partition_size_to_drop
   = 0` above 50 GB), `mv` the part directories into the new table's `detached/`, and
   `ATTACH PARTITION` — a rename, seconds for 60 GiB. **ClickHouse does not validate a
   moved part against the new key**: a 2024 part attached under the 2026 key kept partition
   `2024` silently. So move only partitions whose value is unchanged, copy the rest with
   `INSERT ... SELECT`, and check every part's `min_date`/`max_date` against the new
   expression with `partitionId()` before `EXCHANGE TABLES`.

   **Changing the DDL does not change an existing database.** `ensure_schema()` is
   `CREATE TABLE IF NOT EXISTS`, so `CRW.cli repartition` is what actually rewrites the
   archive — see below.

### Anomaly is derived, and how depends on the query shape

`anom = sst - climatology(mmdd)`. There is no anomaly column.

- **A point** joins `sst_daily` to `sst_clim` on `(gy, gx, mmdd)`. For one cell that is
  ~15 k rows against 366, both primary-key reads. Trivial.
- **A box never joins**, because the means commute:

  ```
  mean(sst - clim) == mean(sst) - mean(clim)
  ```

  over the same cells with the same cos(lat) weights. So the daily side stays a plain
  aggregation and the climatology side collapses to one value per MMDD — precomputed in
  `region_clim` for named regions, computed on the fly for an arbitrary box. Joining
  instead would put box_cells × 366 rows on the right of a hash join — 461 M for the PDO
  box — to produce 366 numbers.

  **The identity's precondition is `has_clim = 1` on the daily side.** Both sides must
  average the same cells; without the filter the two drift apart wherever the ice edge
  sits, which is exactly where a marine-heatwave question gets asked. Verified equal to
  three decimals against a direct cell-wise `avg(sst - clim)`.

**Named-region timeseries are served from `region_daily`; arbitrary boxes are queried
live.** Named regions are 0.6–14.6 B rows over the archive (Niño 3.4 is 3.04 B; the PDO
box, the largest, 14.55 B), and `ORDER BY (gy, gx, date)` makes a box a set of contiguous
key ranges — one per `gy` — not a scan. That is still 3.14–12.14 s, so the rollup was added
exactly as predicted: a pure cache, 8 × 15,212 rows, without touching the big table.
