# Verification log

What has been verified end to end, with the numbers. History, not instructions.

Verified working end to end on the CoralTemp pipeline:

- **Geometry and orientation.** Subset is 2500×3800; 7,477,923 ocean cells/day and
  7,240,513 with climatology, matching the source exactly. Anomaly range −4.14…+6.34 for
  a sample day (a latitude flip gives ±18).
- **Ingest round-trip.** Eight cells checked against the source NetCDF, **including three
  straddling the antimeridian** — 180.025°E and −179.975°E resolve to the same cell,
  179.975°E to its western neighbour. Land correctly absent from the table.
- **Point anomaly.** API `sst` and `anom` match a direct NetCDF computation to the cent
  across eight days.
- **The region identity.** `/region/nino34?variable=anom` equals a direct cell-wise
  `avg(sst - clim)` over the same box to three decimals, on 201,392 cells.
- **The region ranking.** `/region/nino34/monthlyRanking?variable=anom` puts August 2015 at
  rank 2 with a mean of **1.980**, which is exactly the mean of the 31 daily values
  `/region/nino34?start=2015-08-01&end=2015-08-31` returns — the fold and the chart agree
  because they read the same rollup. 15 ms. January's rank 1 is 2016 at +2.51 and August's
  top three are 2026 (partial), 2015, 1997, which are the El Nino years they should be.
  In the browser: the panel draws in region scope with an "area mean" caption, the tooltip
  reads `sd of daily means`, the CSV downloads as `anom_monthly-ranks_nino-3-4.csv` with
  500 rows, and `mhw` ranks the region without printing a category name. No console
  errors.
- **Imagery.** Land transparent, ice-fringe grey, ocean coloured — checked by pixel, not by
  eye. `bounds()` returns west 100 / east 290. `/image` 404s with an explanatory message
  for a bucket with neither cache nor NetCDF.
- **Browser** (Chromium, per the recipe below): the Pacific raster draws across the
  antimeridian, SST/Anomaly and Daily/Weekly/Monthly toggles render, a map click populates
  the chart and the ranks dock, no console errors.

Verified on the Marine Heatwave addition:

- **Ingest.** The per-category histogram in `mhw_daily` for 2023-10-01 matches the source
  NetCDF exactly across all five categories (2,355,517 / 681,076 / 60,027 / 3,618 / 305).
  Land is absent; the 16-day trial slice came to 49,284,004 rows, 3.08 M/day at that
  archive-peak date.
- **Point queries.** Eight cells checked against the NetCDF, the antimeridian pair
  included — 180.025°E and −179.975°E resolve to the same cell. A heatwave-free ocean cell
  returns **0**, not an absent row, which is the LEFT JOIN doing its job; a land cell
  returns nothing.
- **Weekly max.** At one cell over three weeks the weekly series is the max of its daily
  values, not their mean.
- **The region path.** `/region/nino34?variable=mhw` for 2023-10-01 gives 0.855, matching a
  hand-written `sum(cat*cos)/sum(cos)` over the same box to three decimals.
- **Imagery.** By pixel, not by eye: the rendered WebP is opaque *only* where a heatwave is
  (1,087,645 px), alpha is strictly 0 or 255 with nothing in between, and the only codes
  present are 1..5. Per-category proportions match the source. At 81 KB it is a sixth of
  the SST frame.
- **Nearest resampling, measured.** Bilinear would invent 42,088 heatwave pixels (3.9%
  more than exist) and mis-categorise 3,072 more.
- **Browser** (Chromium): the MHW toggle renders and switches, the map draws NOAA's palette
  with land and heatwave-free ocean transparent, the legend is a named key, the chart's
  y-axis is 0..5 with no unit, the ranks dock reads "most severe first" and draws
  zero-mean months neutral rather than Cat 1 yellow. No console errors. Two apparent bugs
  were checked and were not: the Gulf of Mexico and Hudson Bay really were at Cat 1 that
  day and sit inside the box's 70°W edge.

Verified on the PostHog instrumentation (Chromium, with the ingestion host stubbed so
nothing left the machine):

- **Every gesture fires exactly one event, and nothing else does.** A page load reports
  nothing (the opening cell is a bootstrap); variable, period, scope, region, map click,
  playback, both CSV buttons and the reading guide each report once. Closing a popover
  reports nothing. Twelve arrow-key steps on the colour slider collapse to **one**
  `color_range_changed` at the resting range; a typed bound reports once with
  `source: field`.
- **The identity correlation works end to end.** The browser's distinct_id arrives on
  `/timeseries`, `/monthlyRanking` and every `/region/*` call, and `capture_event` puts it
  on the event; a header-less caller falls back to its IP. `duration_ms` lands, and
  `$geoip_disable` is set for private addresses and not for public ones.
- **The no-key path is genuinely silent**: zero ingestion requests, no distinct_id header,
  no console errors, map and panels unchanged.


Verified on the state ribbon, the extent quantity, deep links and the point context cards:

- **The rollup is exact.** `region_daily.mhw_area_frac` for the `pacific` box reproduces a
  direct `sum(cos)/sum(cos)` over `mhw_daily` to the second decimal on every spot-checked
  day (46.95 / 46.82 for 24 and 30 Aug 2026), and its archive maximum, 62.4%, matches the
  direct scan exactly. Rebuild: 6 min for `pacific`, ~9 min for all nine regions.
  One date across all nine — what `run` appends daily — is **2.2 s**.
- **`/state` reads what the panels read.** Its ENSO half puts August 2026 at +2.74 °C,
  rank 1 of 42 Augusts, which is the number `/region/nino34/monthlyRanking` returns; its
  heatwave half reports 46.8% against a 14.9% late-August normal, 27th highest of 15,217
  days. The season label was off by one month before it was checked against the underlying
  monthly means — every value it produced was still a real season name, just the
  neighbouring one, which is exactly the class of error that survives a glance.
- **The normal band is consistent with the anomaly.** At 48.03°N 127.98°W the SST series'
  16.66 minus its climatology's 16.49 is 0.17, which is what `variable=anom` returns for
  the same bucket.
- **Heatwave runs are right about a known event.** The NE Pacific cell's longest run is
  2014-12-09 to 2015-05-02, 145 days — the Blob, which is what that cell should say.
- **Browser** (Chromium, per the recipe below): the ribbon renders under SSR and after
  hydration with **no console errors**; both halves select what their sentence is about;
  a deep link reopens on the same cell, variable, period and date, and the URL it writes
  round-trips; the region MHW view reads "45.6% · 2nd most widespread of 500 months ·
  trend +6.12% per decade" while the map legend beside it stays NOAA's five categories;
  both CSVs export as `mhw_extent_*` with a `mhw_extent_pct` column.

Verified on `pacific_bioregions` (the one polygon region, DFO's Federal Marine Bioregions,
swapped in for VLIZ's EEZ on 2026-09-15):

- **The union is the right four polygons.** The dataset's 14 features carry an `OCEAN_E`
  field; the four marked `Pacific` are Offshore Pacific (315,724 km²), Northern Shelf
  (101,663), Southern Shelf (28,158) and Strait of Georgia (8,969), and their union is
  454,181 km² in the source's own Albers projection — against ~450,000 km² for the
  Canadian Pacific EEZ, so the footprint is the same water.
- **The 362 interior rings really are islands.** The largest measure 31,840 km²
  (Vancouver Island, actual 31,285), 6,499 (Graham), 2,608 (Moresby), 2,294 (Princess
  Royal) — all land, so dropping them loses no water.
- **The mask is the region, not its box.** 26,222 cells of a 55,533-cell bounding box, and
  point-in-polygon spot checks land where they should: Puget Sound, SE Alaska, the Juan de
  Fuca wedge and the high seas 250 nm out all outside; the Strait of Georgia, offshore
  Haida Gwaii and the water off Tofino inside. **Dixon Entrance north of the A–B line is
  inside**, which is the one place this differs from VLIZ's EEZ and the reason for the
  swap.
- **The rollup agrees with the geometry, end to end.** For 2021-06-28,
  `/region/pacific_bioregions?variable=anom` returns **1.583** on **23,875** cells;
  recomputing the same day in Python — pull the 40,921 bounding-box rows out of
  ClickHouse, test each cell centre against the ring, take the cos(lat)-weighted
  `avg(sst − clim)` — gives **1.5827** on **23,875** cells. So the SQL mask and
  `shared/mask.py` select the same cells, and the commuting-means identity survives the
  mask.
- **The box would have been a different number**: 1.4839 over the same day, on 40,921
  cells; SST 13.74 against the region's 13.99. The mask is worth ~0.10 °C on the heat
  dome's peak day.
- **Cost.** `mask` is **2.5 s**; `rollup --clim --region pacific_bioregions --fresh` builds
  `region_cells`, all 366 `region_clim` rows and all 15,217 `region_daily` rows in
  **6.2 s** — it is a small region, and the bounding box still does the key-range work.
- **The ranking comes through it.** `monthlyRanking?variable=anom` puts June 2015 first
  (the Blob) at +1.614 over 42 years with `areaMean: true`, and the annual ranking reads
  2015, 2016, 2014 — the same years the EEZ version gave.
- **Renaming the key orphans its rows**, and nothing cleans them up: `region_cells`,
  `region_daily` and `region_clim` all keep the old `bc_eez` rows until an
  `ALTER … DELETE WHERE region = 'bc_eez'` removes them. `/region/bc_eez` 404s from
  `/domain` alone, so the stale rows are invisible rather than wrong — which is exactly
  why they are easy to leave behind.

- **Browser** (Chromium, per the recipe above): the region's real outline draws — the
  200 nm arc offshore, the Dixon Entrance line across the top, the Juan de Fuca boundary
  at the bottom — the dock reads `Pacific Bioregions (DFO) / Area mean over the region`,
  the chart and the 42-year August ranking populate, and
  `/region/pacific_bioregions/geometry` is fetched exactly once. The CSV downloads as
  `anom_weekly_pacific-bioregions-dfo_1984-12-31_2026-08-24.csv`. **No console errors at
  all** — including the Mapbox marker fog-opacity throw the EEZ version used to trip,
  which is a globe-at-northern-latitudes thing and not about the geometry. One cosmetic
  difference from VLIZ's ring: DFO's outline follows the mainland inlets and the east side
  of Vancouver Island in detail, so the coastal half of the outline is a busier green line
  than the EEZ's was.

**Not yet re-verified since the swap:** the `mhw` extent series — see below.

**`region_daily`'s `mhw` columns for this region are zeros and must be rebuilt.** The
rollup was run on a dev database in the middle of `CRW.cli repartition mhw_daily`: all
17.58 B rows were sitting in `mhw_daily_repart` awaiting the `--finish` exchange, so
`mhw_daily` was empty and the fresh rollup wrote confident `mhw_area_frac = 0` for all
15,217 days. This is precisely the failure the "roll up only once `mhw_daily` is complete"
note warns about, arriving through the migration rather than through a partial backfill —
and `/coverage` reports `mhw.complete: false`, so the frontend gates the variable off and
the zeros are not on screen. **After `repartition --finish`, re-run
`rollup --region pacific_bioregions --fresh`.** The other nine regions were rolled up
before the migration and still carry good `mhw` numbers, so this region is the only one
affected.

Verified on the annual ranking (Chromium, per the recipe above):

- **The years are the right years.** At 47.98N 127.98W the annual `anom` ranking puts
  2015, 2014, 2016 on top — the Blob — and Nino 3.4's puts 2015, 1987, 1997, which are the
  El Nino years. 2026 is starred and reads `ranked on 242 of 365 days`.
- **The toggle fetches nothing.** Month -> Year -> Month issues no `/monthlyRanking` at
  all; the payload already holds both. Measured, the extra grouping set costs nothing
  visible: a cell's ranking is 70 ms end to end.
- **A clicked row keeps the month.** On the `Year` basis, clicking 2016 while the map is on
  August 2015 moves it to 2016-08-01, not to January.
- **The copy follows the basis.** The guide reads `Every year on record at the selected
  cell` and `an edge year of the archive`; the tooltip drops the month prefix (`2015 / mean
  +1.3 degC / sd 0.6 degC over 365 days / rank 1 of 42`). Over a region on `mhw` it still
  reads `most widespread first · area mean` and names the extent quantity.
- **The CSV is its own file.** `anom_annual-ranks_47-98n_127-98w.csv`, header
  `year,rank,mean_anom_degC,sd,days,partial`, no `month` column.
- No console errors in either scope.

Verified on the baseline labelling (Chromium, per the recipe above):

- **The note follows the variable.** Anomaly reads `SST anomaly vs the 1991-2020
  daily mean`, MHW reads `MHW exceeds the 1985-2012 90th percentile, applied by
  NOAA`, and `sst` — which declares no baseline — renders no row at all rather
  than an empty phrase. In region scope it reads `MHW extent`, following
  `seriesLabel` rather than the map's field.
- **The header does the same.** `app.vue`'s subtitle was a hard-coded
  `vs. 1991-2020` behind a `v-if` on `anom`; it now reads the declaration and
  says the right one for all three.
- **The popover contrasts the two** without naming either variable in code — it
  finds the other declared baseline whose `period` differs, so a fourth variable
  would appear there with no edit — and lists the three Hobday/Oliver citations
  as links.
- **The ranking payload names its own baseline.** `climatologyBaseline` is
  `1991-2020` on an `anom` ranking and **null** on `mhw` and `sst`, since neither
  is a departure; the reading guide falls back to naming no years rather than the
  wrong ones.
- **A pre-existing layout bug surfaced and is fixed**: `TimeseriesChart`'s root
  was `relative size-full` with `size-full` on the plot too, so the canvas
  overflowed the pane by exactly `TimeControl`'s height (measured: canvas bottom
  984 against a 950 viewport) and the x-axis labels ran off the bottom of the
  screen. It is a flex column now, and the plot ends where its container does.
- No console errors. The two eslint errors in the touched files
  (`vue/no-multiple-template-root` in `index.vue`, `no-dynamic-delete` in
  `main.ts`) are pre-existing.

Verified on v2.0 (Chromium, per the recipe above; desktop 1440×900 and phone 390×844):

- **Compare.** December 2015 against December 2010 over Nino 3.4 shows El Nino red left of
  the divider and La Nina blue right of it, and a chart click moves only the left half. The
  first v2.0 check missed the stacking bug above because the two dates it used looked alike.
  On the globe and on Mercator both halves draw, and the region outline shows
  on both. Dragging either half moves both cameras to the same centre and zoom. Monthly
  re-snaps both dates (`2026-08-01` / `2025-08-01`). A `c=` link with `r=ne_pacific`
  reopens both dates and the region. No page errors.
- **Phone.** No horizontal overflow; the sheet opens with the stats and the ranking; the
  divider drags by touch (50% → 19%); playback advances; the chart's canvas matches its
  container after the time bar wraps.
- **`/health`** stays 200 with a 17-day lag; **`/health/data`** answers 503 at the default
  3 days and 200 with `STALE_AFTER_DAYS=30`.
- **`CRW.cli check`** on the dev database fails exactly the two known problems (empty
  `mhw_daily` mid-repartition, and `pacific_bioregions`' all-zero extent).
- **The leap-day repair is not in the dev copy of the MHW archive.** In
  `mhw_daily_repart`, every 29 February from 1988 to 2024 carries ~2,022,000 Cat 5 cells,
  the unrepaired signature. After `repartition --finish`, `check` will fail
  `mhw.leap_day_land` until `CRW.cli repair-mhw-land` has run.
- **Not verified:** that each new analytics event fires exactly once. Dev runs with no
  PostHog key, so `trackEvent` is a no-op and the events were read from code, not observed.

Ideas deliberately deferred, with their costs and
constraints, are in [ROADMAP.md](ROADMAP.md) — read it before proposing a feature.
