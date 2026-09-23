# Roadmap: ideas not yet built

These were proposed while v2.0 was being planned (September 2026) and deliberately left for later.
None of them has been started. Each entry says why it is worth doing, what in the codebase it builds on, and roughly what it costs, so whoever picks one up starts from the constraints rather than rediscovering them.

v2.0 takes on the rest of that list: map swipe compare, the mobile layout, guided stories, tests + CI, `CRW.cli check` and `/health/data`. See `CLAUDE.md`.

**Cost tiers**
- **S**: frontend only, or a query on an existing rollup.
- **M**: a new small table, endpoint or component tree.
- **L**: a new archive, a full scan of a daily table, or a re-download.

## Constraints that set every cost below

- **Only the retention window of daily NetCDF is on disk**, about 30 days (`imaging.retention_floor()`). History exists only in ClickHouse and in the image cache.
  - A new *per-cell field over the whole archive* (a trend, a correlation) means a full scan of `sst_daily` (~113.7 B rows) or a re-download of ~153 GB.
  - A new *rendering* of historical frames (a different width, a smaller mobile tier, a different encoding) means re-downloading. **A lighter image tier for phones is not possible for history** for this reason.
- **The production box has ~90 GB free, on HDD** (~4.3 ms per seek). Anything that roughly doubles `sst_daily` does not fit, and a full scan there takes hours, not minutes. Run one-off whole-archive computations on a dev box with NVMe and ship the result.
- **Widening the box needs a re-download.** `gy`/`gx` index the global grid, so no existing key moves, but the cells outside today's box were never ingested and their NetCDF is gone.
- **The cheap path is the rollups.** `region_daily` (~9 regions × 15k days) and `region_clim` answer most region questions in milliseconds. A feature that can be phrased over them is an S; one that needs cells is not.

---

## A. Analysis and charts

### A1. Seasonal "spaghetti" chart (S)
A region's day-of-year curve for every year, with the current year highlighted, the 1991–2020 climatology, and the record min/max envelope.
- **Why:** the most widely shared SST chart format. It answers "is this year unusual" without reading a single number.
- **Builds on:** `region_daily` + `region_clim` via `/region/{key}?period=daily`. Write it as a pure option builder in `utils/`, like `ranking.ts`, so it can be tested with echarts SSR.
- **Watch:** for `mhw` over a region the series is extent in percent, not a category (`quantity`).

### A2. Hovmöller diagram, equatorial Pacific (M)
Anomaly averaged over 5°S–5°N, drawn as time × longitude.
- **Why:** the standard ENSO view. Kelvin waves and the eastward push of the warm pool show as diagonal bands months before an event peaks.
- **Builds on:** a new `hovmoller_daily` rollup (~15k days × 190 1° longitude bins ≈ 2.9 M rows), built with the same shape as `process/CRW/regions.py`. Like `region_daily`, it should be built once after backfill and appended per date by `run`.
- **Watch:** the anomaly must use the `has_clim = 1` identity, exactly as `region_daily.mean_sst_clim` does.

### A3. Calendar heatmap / warming stripes (S)
Year × day-of-year, coloured by anomaly or MHW category, for the current cell or region.
- **Why:** forty years in one image. Heatwave runs show as streaks.
- **Builds on:** the daily series the chart already holds. It needs no request of its own.

### A4. Region heatwave event catalogue (S–M)
Events over a region: start, end, duration, peak extent, cumulative extent-days. Ranked, and each linking to its dates.
- **Why:** turns named events (the Blob, the 2021 heat dome) into clickable history.
- **Builds on:** `region_daily.mhw_area_frac`, plus the run logic in `api/modules/timeseries.py`'s `mhw_events()`.
- **Open question:** what extent threshold starts a regional event. That is a definition to agree with a domain expert, not to invent.

### A5. Hobday metrics at a cell (S)
For each heatwave run: maximum and mean category, duration, onset and decline rate.
- **Why:** finishes what `events` started, using the method the UI already cites.
- **Builds on:** `mhw_events()` and the point series.
- **Watch:** the category is ordinal, so an "intensity" in °C is not available from `mhw_daily`. That would need the NOAA MHW climatology, which this repo deliberately does not download.

### A6. Percentile of today (S)
"Warmer than 97% of 24 Augusts on record" for a cell or region.
- **Builds on:** the point series or `region_daily`, grouped by day of year.

### A7. Map compare against another *variable* (S)
v2.0's swipe compare is date-only. Allowing anomaly | MHW on the same week needs two legends, and a colour meaning different things on each side. It was deferred for that reason, not for cost.

### A8. Trend map and ENSO correlation map (L, one-off)
°C per decade per cell, and each cell's correlation with Niño 3.4.
- **Why:** where the Pacific is warming fastest, and where ENSO reaches.
- **Builds on:** one pass of `simpleLinearRegression` / `corr` grouped by `(gy, gx)` over monthly means. The result is rendered to one static WebP per map through `shared/render.py`.
- **Watch:** a full scan of `sst_daily`. Run it on NVMe, not the prod HDD, and measure it on one decade first.

### A9. User-drawn box or polygon (M–L)
- **Why:** arbitrary areas without editing `domain.yml`.
- **Watch:** `/regionTimeseries` already does a live box and takes 3–12 s. A drawn polygon needs an async job with progress, or a coarser grid. There is no rollup to lean on.

### A10. Multiple point / region selection (M)
Select several cells or named regions at once and chart their series together, so different locations can be compared on one chart.
- **Why:** compare places without flipping back and forth, e.g. Niño 3.4 against the Blob's cell, or two coastal cells.
- **Builds on:** `/timeseries` and `/region/{key}` as they are, one request per selection. Named regions are rollup reads and cheap; points are primary-key reads.
- **Partly built (2026-09-23):** two *points* — pin B, chart-only, the dock stays on A (see CLAUDE.md, "Two-point selection"). Still open: regions, more than two, and mixed point/region selections.
- **Open:** max 2 or more depends on the implementation. The stats and ranking dock currently describe one selection, and the map draws one pin or one box. A point and a region mix a category with an extent under `mhw`, so mixed selections need the `quantity` rule applied per series.

---

## B. More data

### B1. CRW Degree Heating Weeks and Bleaching Alert Area (M–L)
- **Why:** CoralTemp is a coral-reef product, and bleaching risk is the question its users ask next.
- **Builds on:** the whole MHW machinery. BAA (0–4) is an ordinal class and mostly zero, so it takes the same path:
  - `categorical: true` in `domain.yml`
  - a sparse table read through a LEFT JOIN against `sst_daily`
  - its own `*_status` table
  - a `Product` in `download.py` and a `Target` in `ingest.py`
  - a `*.complete` gate in `/coverage`
- **Before starting:** measure sparsity and file size on real files, and check the product's encoding history across the archive. The MHW category was re-encoded mid-archive under an unchanged filename.

### B2. `sea_ice_fraction` (M forward / L history)
Already inside every CoralTemp file, and not ingested.
- **Why:** it would explain the grey no-climatology fringe instead of just drawing it.
- **Watch:** only the retention window can be ingested without re-downloading.

### B3. Official indices beside ours (S–M)
NOAA CPC ONI, PDO and IOD (DMI), which are small monthly text files.
- **Why:** `/state` reports an ONI-*style* index and has to say so. Plotting it beside NOAA's official ONI shows the difference instead of describing it.
- **Builds on:** a new `index_monthly` table and a fetch in `download.py`.

### B4. ENSO forecast plume (S–M)
IRI/CPC probabilistic ENSO forecast, or the NMME plume.
- **Why:** the archive answers "what happened"; this answers "what's next".

### B5. Subsurface: equatorial depth × longitude section (L)
From GODAS, ORAS5 or Argo gridded products; for example, the 20 °C isotherm depth.
- **Why:** ENSO starts below the surface, before SST shows it. This is also the only 3D view the science supports (see D2).

### B6. Land temperature and precipitation — **built as a map overlay** (M–L)
Daily land temperature and rainfall over the same years as the ocean layers, to show what an El Niño does on land: a dry Indonesia and northern Australia, a wet coast in Peru and Ecuador, and a warm winter in western Canada.

**Built (2026-09-18):** download and ingest (`process/CPC/`, `land_temp_daily`, `land_precip_daily`), then the 1991–2020 land climatology, six map layers served by `/image`, and a **map overlay** in the frontend with its own control and legend, drawn over whichever ocean variable is showing. See CLAUDE.md's *The land archive* and *The land overlay* sections. The chart, stats and rankings stay ocean: clicking land for a timeseries is the next step, under *Still to do*.

- **Source: NOAA CPC Global Unified**, from NOAA PSL. precip, tmax and tmin on a 0.5° grid, one NetCDF **per year**, public domain, no login, ~2 days behind. **Global since 2026-09-18** (the whole 360×720 grid in the tables and climatology; frames 60°S–85°N): ~62,900 cells a day carry temperature and ~93,000 precipitation. Over the Pacific box it was 250×380 cells, 20,878 and 22,952.
- **Decisions taken, so they are not relitigated:** both `tmax` and `tmin` are stored with `tmean` as a zero-storage ALIAS; two tables rather than one, because the two products do not share a land mask; every frame is **pre-rendered and the year files are deleted once ingested and rendered** (`CPC.cli prune`, checked per product-year; the API never renders), so re-rendering history or rebuilding the climatology means re-fetching (~9.5 GB); the archive starts **1985**, matching CoralTemp, so `/coverage` reports one date range. CPC itself reaches back to **1979**, which would buy the 1982/83 super El Niño the ocean layers cannot show — deliberately left on the table, and it is a backfill plus a presentation decision, not new code.
- **Rejected sources:** *ERA5-Land* (0.1°, needs a Copernicus account and request queue, ~5 days behind, ~25× the cells). It is the upgrade if 0.5° looks too coarse beside the 0.05° ocean. *CHIRPS* (precip on exactly the CoralTemp grid, but only 50°S–50°N, which loses BC and Alaska, and files are revised ~3 weeks later). *IMERG* (starts 1998/2000).
- **Still to do:**
  - **Clicking land for a chart.** Land `/timeseries` and `/monthlyRanking`, a `land_clim` ClickHouse table (the climatology exists as files; the API's anomaly queries will want it in the database, computed from the same files so there is one normal), region rollups for land, and the store/chart work to plot a land cell. The overlay model means the chart would need to know which surface was clicked.
  - **SPI** as an alternative rain anomaly: WMO standard, bounded ±3, works in the arid cells that are grey today. A gamma fit per cell per calendar month, monthly and longer only, and a named method to cite.
  - **The 1979 extension** (the 1982/83 super El Niño): a `fetch` + `backfill` + `render` plus a decision on how the map presents land years with no ocean under them.
  - **A compact two-legend layout on a phone.** With the overlay on, the ocean and land legends stack and cover about half of a 390 px map.
- **Map layers, decided with the user (2026-09-18)** — measured first, so these are not to be relitigated:
  - **Six layers.** Absolute `tmax`, `tmin`, `precip` and anomaly `tmax`, `tmin` at daily/weekly/monthly; the **precip anomaly at weekly and monthly only**, since a daily rainfall anomaly is noise while a daily temperature anomaly (a heatwave day) is not. `tmean` gets no layer — it stays an ALIAS.
  - **Precip anomaly is `log2(actual / normal)`, labelled as percent** (25/50/100/200/400). Measured, the absolute departure's middle 50% is −17…+12 mm/month with a tail to 7,812 mm, so no one scale works; linear percent-of-normal squeezes every drought into 0–100% while wet runs past 700%, which makes the dry half — what El Niño does to Indonesia and Australia — the unreadable one. The log puts ×2 and ÷2 equidistant from normal.
  - **Cells with a normal under 0.1 mm/day draw flat grey** — 7% of the Pacific box's land in January (much more globally: the Sahara and Arabia in their dry season), where one 0.5 mm shower reads as 500%. This reuses `render.NO_CLIM_RGBA`, the ocean's ice-fringe third state, and means the same thing: a value exists, a meaningful anomaly does not.
  - **A precip bucket is mean mm/day, not a total**, so one legend serves all three periods, as MHW's already does. The ratio layer is unaffected (a ratio of means is a ratio of totals). A monthly total is a UI label, not a second raster.
  - **`tmax`/`tmin` buckets are the mean of the dailies** ("average daily high"), which is what a normal is — never the max of `tmax`, which would compare a weekly extreme against a mean.
  - **The precip normal is a per-MMDD normal smoothed over a 7-day window, averaged over the bucket's days** — corrected during the build. The note here used to say "per month and per week-of-year", but a windowed daily normal smooths away the per-day noise just as well, serves Monday-anchored weeks (which a week-of-year table cannot), and keeps one table shape for all three sources. A month's normal is blurred by only ±3 days, so a monsoon onset keeps its month. Temperature uses 15 days.
  - **Temperature anomaly needs two bytes and a wider range than the ocean's.** Within-month day-to-day spread of `tmax` is ~5 °C north of 45°N (p99 ~10 °C) against the ocean anomaly's ±3 display range; the ocean `anom`'s one byte at 0.1 °C tops out at ±12.7, uncomfortably close to real continental winter anomalies. Default display ≈ ±8, with presets.
  - **SPI is the follow-up, not the first version.** The WMO standard, bounded ±3, works in arid cells and would retire the grey state — but it is a gamma fit per cell per month per timescale, valid monthly and longer only, and a named method to cite.
- **What the build found in existing code:**
  - `to_mercator()` took its row spacing from `subset().nlat`, the OCEAN grid's 2500, which is wrong for a 250-row land field. It now derives spacing from the field's shape against the image edges; the ocean output is byte-identical.
  - **Land has its own image bounds** (`landImageBounds`), since going global. The land frame is the ocean frame's pixel grid carried round to just inside ±180°, so the no-overlap cut still works pixel for pixel (exactly west of the dateline; east of it the grids are offset by a sub-pixel and the cut leaves at most a one-pixel basemap strip). It stops at ±180 because **Mapbox draws a 360°-wide image source only in the world copy nearest the camera**: a ~−30…330° frame lost the Americas with the camera on Asia, and explicit ±360 copies did not help.
  - **Layer order cannot keep land off the sea.** The style's only land is `country-boundaries`, a fill; the land raster must sit above it to be seen, where its 0.5° blocks would overhang every coast. Fixed by cutting land frames to CoralTemp's own coastline at render time (a committed ocean mask, global since the land went global, 116 KB): measured 0 overlapping pixels against the ocean rasters under `sst` and `mhw`.
  - **Concurrent NetCDF reads deadlocked the API** when the API still rendered land frames on demand and swipe compare asked for two at once; the API is cache-only now. All reads now take one process-wide lock; see CLAUDE.md's gotchas.
  - A land frame is **~120 KB (rain) to ~190 KB (temperature)** globally, 3,880 × 2,747 px; it was 27–56 KB over the Pacific box (the estimate here said 22). Encoding ~0.5–2 s. Two legends side by side, never one: ±3 and ±8 cannot share a scale.
- **Watch:**
  - CPC is built from rain gauges and weather stations. Where stations are sparse (interior New Guinea, Borneo, the Amazon), it is less reliable.
  - Show anomalies, monthly by default. A daily rainfall anomaly is mostly noise; the ENSO signal is seasonal.
  - Precip needs its own palette (e.g. BrBG), and probably a percent-of-normal option, since rainfall is skewed.
  - ~~The box (100°E–70°W) misses the famous links outside the Pacific~~ — done: land is global, so India, southern and east Africa and eastern Brazil are on the map, with land reaching past the ocean image by design.
- **Check when built:** DJF 1997/98 and 2015/16 rainfall anomalies should show a dry Indonesia and northern Australia, and a wet Peru, Ecuador and US Gulf coast.

---

## C. Coverage

### C1. Indian Ocean or tropical Atlantic (L)
- **Why:** the IOD is ENSO's sibling mode, and the Atlantic Niño is its analogue.
- **Watch:** the new cells must be re-downloaded and ingested. Size the added ocean cells against the prod disk before committing. Clicks outside the box are already recorded as `point_queried` with the out-of-domain 400, which is the evidence for which way to widen.

### C2. Global (L+)
~17.2 M ocean cells against 7.5 M, so roughly 2.3× `sst_daily` (~200 GB). It does not fit the current prod disk.

### C3. More named regions (S each)
Coral Triangle, Great Barrier Reef, Hawaii, California Current, Humboldt, Kuroshio, Sea of Okhotsk.
- **Builds on:** a `domain.yml` entry, then `rollup --clim --region <key>` and `rollup --region <key>`. Use a `polygon:` (`shared/mask.py`) where a box would dilute the region.
- **Watch:** a polygon from a legal or planning instrument needs its provenance recorded, as `pacific_bioregions` does.

---

## D. 3D

The data is **surface only**. A 3D "terrain" of anomaly would be decoration, so only these two versions carry information.

### D1. Space-time cube for one event (M)
Lat × lon × time voxels of MHW category over an event's weeks (deck.gl or three.js), showing how the Blob grew, drifted and faded.
- **Builds on:** the cached weekly `mhw` WebPs alone. They carry the class value, not colour.

### D2. Equatorial vertical section (L)
Needs B5 first.

---

## E. Reach and usability

### E1. French / bilingual UI (M)
- **Why:** the project sits under CIOOS, and bilingual is likely expected.
- **Watch:** copy is spread across `AboutDialog`, `readingGuide()` in `utils/ranking.ts`, the ribbon, the story captions, and `domain.yml` labels and baseline notes. `domain.yml` needs a per-language label scheme, not a second file.

### E4. Embeddable widgets (S–M)
The ribbon, chart or map as iframes for partner sites, reusing the components under a bare layout and driven by the same deep-link query keys.

### E5. Open data access (S–M)
- An OpenAPI docs page. FastAPI generates one; it needs curating, not writing.
- `region_daily` published as an ERDDAP dataset, which makes the rollups citable and machine-usable.

### E6. Alerts (M)
An RSS/Atom feed (no accounts), or email when a region crosses an extent or anomaly threshold. Depends on the daily cron below.

---

## F. Operations

### F1. Daily cron for `CRW.cli run` (dropped from v2.0)
A host crontab entry calling a wrapper script:
- `flock -n` so two runs never overlap.
- `docker compose ... run --rm --name enso-run process python -m CRW.cli run`. The fixed `--name` makes a second container fail loudly, because a `compose run` container outlives the client that started it.
- A second slot after MHW publishes (~15:20 UTC), since `run` landing between the two publications sees SST done and MHW pending.
- `CRW.cli check` afterwards, and a log file per day.

Two preconditions:
- **Rebuild `process` with `--profile tools` on every deploy.** `up -d --build` skips it silently.
- **Pass `--keep-nc` until the MHW history render is confirmed on prod.** Otherwise the retention prune deletes MHW NetCDF that has no rendered frames yet.

Point an uptime monitor at `/health/data` once this exists.
