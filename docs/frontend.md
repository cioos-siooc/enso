# Frontend

`front/`: components, store, compare, phone layout, CSV, colour range and the map.

## Frontend (`front/`)

Nuxt 4 + Nuxt UI v4 (Tailwind v4) + Pinia + MapboxGL + ECharts, dark mode pinned — the
same stack as the ocean-acidification dashboard.

```
app/app.vue                        header + coverage badge; awaits store.loadMetadata()
app/components/StateRibbon.vue     the basin's state in one line, under the header
app/pages/index.vue                numbers + ranks dock on the left, map over the chart
app/components/AnomalyMap.vue      map host: projection, camera, swipe-compare divider
app/components/FieldMap.vue        one MapboxGL map drawing the field for one date
app/components/TimeControl.vue     "when": period toggle, date stepper, playback, Compare (Point / Date)
app/components/ColorLegend.vue     gradient + the colour range control (popover)
app/components/BaselineNote.vue    what the chart's values are measured against (+ popover)
app/components/TimeseriesChart.vue ECharts line with dataZoom
app/components/LayerControl.vue    "what": the map's Layers card, Ocean + Land rows (LayerRows.vue); a popover on a phone
app/components/ScopeControl.vue    point / named-region switch, over the map
app/components/StatsPanel.vue      the dock's headline value and stat cards
app/components/MonthlyRankPanel.vue  the map's month, every year ranked (under the cards)
app/components/SideDock.vue        resizable left-hand dock (drag handle, remembered width)
app/components/IntroCard.vue       first-visit card: three gestures + a link to the guide
app/composables/useApi.ts          axios wrapper
app/composables/usePlayback.ts     page-wide play/stop loop + frame prefetch for the map animation
app/composables/useViewport.ts     the shared phone-width flag (false under SSR)
app/composables/useUrlState.ts     query params <-> store, so a view can be linked
app/utils/periods.ts               daily/weekly/monthly bucket maths (mirrors the API)
app/utils/ranking.ts               ranking layout + both ECharts options (pure -> testable headlessly)
app/utils/colorScale.ts            domain.yml's colour stops evaluated at a single value
app/utils/csv.ts                   CSV export of the plotted series and the rankings (pure text + one download)
app/utils/mapView.ts               CameraView, ProjectionName, the globe's opening view
app/app.config.ts                  maps Nuxt UI's internal icons onto mdi
app/stores/main.ts                 Pinia store
```

### The state ribbon, and what the series getters are for

**`StateRibbon.vue` is the answer to the question a visitor arrives with**, before they have
touched a control: the ENSO phase, in one sentence. It sits under the header rather than in
the dock because it describes the whole basin and must not move when the selection does.
It is a button, and sets the **variable as well as the region** — reading "El Niño" and landing on a
marine-heatwave chart of Nino 3.4 would be a non-sequitur. The heatwave half is gone; see
`/state` above.

Its caveats live in an on-demand popover, not in the sentences. The one that must not be
left unsaid is that the index is not NOAA's RONI, and that is what the popover says, with a
chart of the two. NOAA's number is also in the ribbon itself, linking to CPC's page; it was
tried as a line on the Nino 3.4 chart and removed, since it appeared only for one region and
variable and read as a second measurement of the same thing.

**`store.series*` are a second set of getters beside `store.active*`, and they must stay
separate.** The `active*` pair describes the **map**, which in region scope still draws
NOAA's five categories — so its legend stays categorical and in category colours while the
chart beside it plots a percentage. The two genuinely disagree, and one getter serving both
is exactly how the legend ends up labelling the chart. `seriesStops`, `seriesIsCategorical`,
`seriesUnitLabel`, `seriesPrecision` and `seriesLabel` all resolve through
`activeQuantity` — read off the series the API returned, never derived from `scope` and
`variable`, so the formatting can never describe a series that is no longer on screen.

**Anything rendered under SSR must pin its locale.** `toLocaleDateString`/`toLocaleString`
with `undefined` uses Node's container locale on the server and the visitor's in the
browser, which is a hydration mismatch and nothing else — three of them, found by driving
Chromium. `utils/periods.ts` already pinned `'en-GB'`; the ribbon and `StatsPanel` now do too.

### The first-visit card

**`IntroCard.vue` is a card over the map, not a modal**, because the map is what a first
visit learns from. Three gestures (click the map, click the chart, pick a region) and a
`Full guide` link that opens `AboutDialog`'s guide tab through `useGuide()`'s shared state.
Dismissing it, either way, sets `enso.intro.seen`. **It never shows on a link with a query
string**, which is read at setup, before `useUrlState` writes the defaults back: someone sent
to a view came to see it. It is centred on the map.

### Linkable views

**`useUrlState()` keeps the address bar saying what is on screen** — `?v=anom&p=weekly&d=2026-08-24&at=47.98,-127.98`,
or `&r=nino34` in region scope. A dashboard whose every view lives at one address cannot be
sent to anyone, and "look at the Blob in September 2015" is four gestures to describe and
one link to send.

Three things about it:

- **Client-only, from `onMounted`, deliberately after `loadMetadata()`.** Applying the
  query during SSR would issue the selection fetches inside the render, and `useApi()` only
  survives the *synchronous* part of an SSR call chain — the trap `loadRegionSeries`'s
  `api` parameter exists for. Running after costs at most one extra request (the opening
  cell the bootstrap already fetched) and cannot strand the page.
- **`replaceState`, never `push`.** Every one of these is a change of view, not of page;
  pushing would make Back step through a hundred playback frames instead of leaving.
- **Variable and period are `$patch`ed, not set through their actions.** Each action fires
  its own refetch of a selection about to be replaced anyway — three requests for one link
  — and each reports an analytics event. Arriving on a link is not the same gesture as
  pressing a toggle, so a deep link looks like a page view rather than like the visitor
  having changed the variable. The URL writes the resolved **cell**, not the raw click, so
  a link reopens on the same grid cell.

**Applying a view is `store.applyView(view)`.** The URL is parsed into a `View` and handed
over, so there is one definition of entering a view. One more key: `c=YYYY-MM-DD` is swipe
compare's second date.

### Two-selection compare

**A second selection, B, plotted beside A on the chart, and nothing else.** B is a cell
(`secondPoint`) or a named region (`secondRegion`), never both, and is **independent of A's
scope**: point+point, point+region, region+point and region+region all work. The dock's stats
and ranking stay on A, whose heading reads `A · <cell or region>` while B exists, so no second
ranking is fetched. B is chosen from the `Compare` menu beside the scope control on the map (`Point on map`,
which arms the next click — crosshair cursor, Esc disarms — or any region but A's own), or a
point B by **Alt-click** — Shift-drag is Mapbox's box zoom and Ctrl-click is a right click on a
Mac. It is removed from its pin's popup, the `Remove B` button, or the × in `PointPair.vue`'s
chip row under the time bar.

- **Store:** `secondSeries`, fetched by `refreshSecondPoint()` (`/timeseries` for a cell,
  `/region/{key}` for a region), a no-op when `secondKey` is current. `selectPoint`,
  `loadRegionSeries`, `setScope` and `applyView` call it, so every refetch of A refreshes B.
  A B failure lands in `secondError` and never touches A's state; a land cell's empty series
  says so there. A point B's land series is fetched in either scope.
- **`mhw` refuses a mixed pair.** A cell's `mhw` is a category and a region's is an extent in
  percent, so `secondMismatch` drops B's line and the chip says why. `sst` and `anom` are the
  same quantity at either scope and mix freely.
- **The chart colours by selection, not value, while B is drawn.** Two lines on one value ramp
  are the same colour wherever they agree. The visualMap and the normal line are dropped;
  A and B take `utils/points.ts`'s `PIN_COLORS` (green, violet — not amber `MAP` or sky
  `CMP`), and the chip row is the legend. Pins carry an `A`/`B` letter, A's only while B
  exists; a region B is outlined in violet beside A's green box (`FieldMap`'s `REGION_SLOTS`).
- **A click on a pin or popup is ignored by the map's click handler.** Both sit inside the
  canvas container, so without that check opening B's popup also moved A there.
- URL keys `at2=` / `r2=`; `View.point2` / `View.region2` (`null` removes, absent leaves
  alone). The series CSV gains `<column>_a,<column>_b`, joined on bucket start, named
  `<A>_vs_<B>`. Events: `point_added` (`source`, `scope`), `region_added`, `point_removed`
  (`kind`).

### Swipe compare

**Only the date differs between the two halves.** Variable, period, colour range, scope and
region are shared by construction, so one legend describes both and a colour means the same
thing either side of the divider. Comparing anom against MHW was deliberately not built (see
`ROADMAP.md`, A7).

That is why the map was split in two. **`FieldMap.vue` holds all the Mapbox drawing and takes
`date` as a prop**: everything else it reads from the store, so two instances can only differ
in the date. **`AnomalyMap.vue` is the host**: it owns the projection, the camera and the
divider, because two components each deciding where to fly would fight. Framing (`frame()`,
`frameRegion()`) and `store.cameraRequest` go to the primary map; the compare map follows.

- **The second map mounts only while compare is on.** It is a second WebGL context.
- **It is stacked on the first and clipped with `clip-path: inset(0 0 0 X%)`.** A clip path
  clips hit-testing too, so each half takes the drags and clicks for the map it shows.
- **`FieldMap`'s root is a wrapper around the Mapbox container, and must stay one.** Mapbox
  adds `.mapboxgl-map { position: relative }` to its container, unlayered, which beats the
  host's layered Tailwind `absolute`. With the class on the container itself the compare map
  sat below the primary, hidden by `overflow: hidden`, and both halves showed the primary's
  date. Nothing errored and both maps reported their own image URL.
- **The cameras are locked both ways** with `jumpTo` inside a re-entrancy guard, since
  `jumpTo` fires the other map's `move` synchronously. Hand-rolled; no `mapbox-gl-compare`.
- **`toggleCompare()` opens on the same bucket a year earlier**, clamped to coverage, and
  `setPeriod()` re-snaps `compareDate` with `selectedDate`. Playback moves the main date
  only.
- **The field maps are created after the host mounts.** The saved projection is read in
  the host's `onMounted`. Reading it during setup would render the projection buttons
  differently on the server, and a child's `onMounted` runs before its parent's, so the
  map would open on the wrong projection.
- **Alt-click on the chart sets the compare date**, while compare is on — the same modifier
  that drops pin B on the map, so "the second one" is one gesture everywhere. With
  compare off the modifier is ignored, so a click never opens a second map. It reports
  `compare_date_changed` with `source: 'chart'` and no debounce, since one click is one
  choice.
- The chart marks the compare bucket with a dashed sky `CMP` line beside `MAP`. Each half's
  date label is dropped when that half is too narrow to hold it.

### The phone layout

**`useViewport()` is one shared `narrow` flag (below 768px), false under SSR and set on
mount.** The server cannot know the viewport, so it renders desktop and a phone switches
once after hydration. Reading `matchMedia` in setup would be a hydration mismatch. Use the
flag only where CSS cannot help (which component tree mounts, a prop, a number in script);
anything that is only styling uses Tailwind's `md:`, the same breakpoint.

- **The dock becomes a `UDrawer` bottom sheet** behind a peek bar naming the selection.
  Exactly one of dock or sheet is mounted, so `MonthlyRankPanel`'s chart never initialises
  in a hidden, zero-sized box. Both mount the panels through one `statsProps`/`rankProps`.
- **The time bar wraps** (`flex-wrap`), on desktop too once compare's second stepper is
  open. On a phone it uses `sm` controls, icon-only labels and no fps slider, because every
  wrapped row comes out of the chart's pane.
- **Playback prefetches 3 frames and holds 8 on a phone**, not 8 and 24. The frames cannot
  be made lighter instead: a smaller image tier would have to be rendered from NetCDF, and
  only the retention window is on disk.
- **`usePlayback()` is module-level state**, one playhead for the page. It does not stop
  itself on unmount; `TimeControl` does that.

**Guided stories were built in v2.0 and removed on 2026-10-05**, before any real story was
written (the only one was a draft placeholder). Gone with them: `StoryPicker`, `StoryCard`,
`useStory`, `stories/index.ts`, the `story=`/`step=` URL keys, `View.camera`,
`store.currentView()`/`mapCamera`/`cameraRequest`, and playback's `until` bound. A
`story=` link now opens on its other keys and the story key is dropped from the URL.

### Downloading what is plotted

Two download buttons, both exporting **the data the chart already has** rather than issuing
a request of their own — a second path to the same numbers would be a second definition of
"the weekly mean", the drift `shared/buckets.py` exists to prevent. `utils/csv.ts` is pure
text-building plus a single DOM-touching `downloadCsv()`, for the same reason `ranking.ts`
and `stats.ts` are pure.

- **`TimeControl`'s button saves the series**, at whatever variable, period and scope the
  chart is on. Columns are `start_date,end_date,<variable>` — **both** date columns, on
  every period: a weekly row labelled `2024-05-06` is a mean over seven days, and a file
  saying only `date` invites reading it as that Monday's reading. On a daily series the two
  are equal, which is honest rather than redundant. A null value is an **empty field**; any
  placeholder would read back as a reading.
- **`MonthlyRankPanel`'s button saves all twelve months**, not the one on screen — the
  panel shows the map's month because 45 rows twelve times over is unreadable on
  screen, which is not a limit a file has, and a `month` column is what makes the table
  filterable. `partial` is carried as a boolean: it is the difference between a settled rank
  and one that will move.

**Both name the quantity, not the variable, where they differ.** A region's heatwave file
is `mhw_extent_monthly_whole-pacific_....csv` with a `mhw_extent_pct` column, because a
file headed `mhw` reads back as a category — and a folder holding both would look like two
comparable files that are not.

Filenames carry everything that decides what the numbers are —
`anom_weekly_nino-3-4_1984-12-31_2026-08-24.csv`,
`anom_monthly-ranks_47-98n_127-98w.csv`, `anom_monthly-ranks_nino-3-4.csv` — because a
folder of `timeseries.csv` files is indistinguishable a week later, and a cell and a region
are not comparable numbers: one is a point reading, the other an area mean.
Cells are slugged as hemispheres for the same reason `index.vue` prints them that way: the
0-360 longitudes the API returns would name 128 W as `232.00`.

Values are written through `toFixed` at the variable's own precision — the API's floats
arrive as `0.20200000000000001`, which a spreadsheet shows verbatim.

**The chart rail is point-only, and the map click is the only selection.** There was a
`Point | Region mean` tab pair here; the region side is gone from the UI, though
`/region/{key}` and `/regionTimeseries` still exist and now take `variable` too. The Niño
indices are the obvious thing to surface there next.

**`store.variable` (`sst` | `anom` | `mhw`) works exactly like `store.period`**: it drives the
chart request and the image URL together, so the map and the chart can never show
different fields. **It opens on `anom`** — how far from normal it is, is the question the
dashboard exists for; absolute SST is the reference view you switch to, and it comes second
in the toggle. `anom` is the derived one, though: it is undefined over the ice fringe and
needs the full 366-key climatology, so the Anomaly button stays **disabled until
`/coverage` reports `climatology.complete`**, and `loadMetadata()` falls back to `sst` when
it is not. A partly-loaded climatology would blank the missing dates rather than fail,
which is worse — and opening on a variable whose own toggle is disabled is worse still.

**`mhw` is gated the same way, for a sharper reason.** `store.variableReady()` holds both
rules in one place: `anom` needs `climatology.complete`, `mhw` needs `mhw.complete`, and
`sst` — the stored field the other two are built from — is always available, which is what
makes it the fallback. The MHW case is sharper because its table is *sparse*: a
half-backfilled archive does not blank the missing dates, it reports a confident **category
0** for them, and a monthly ranking then ranks forty fabricated zeroes below one real
month. No value could signal the difference, so the toggle is disabled and says why.

Three more things `mhw` changes in the UI, all because it is a class rather than a
measurement:

- **`ColorLegend` shows a named key**, not a gradient with a range popover. The names are
  the point — Cat 3 means Severe, which is what the map is being read for — and there is
  nothing between two classes to re-range.
- **Nothing prints a degree sign at it.** `store.activeUnitLabel` is `''` for `mhw`, and
  the chart tooltip, the legend title, the y-axis name and the ranking rows all read it.
  The tooltip names the class too: `3 (Severe)`, and `0 (no heatwave)` — which is the
  common reading and needs saying rather than looking like a missing point.
- **Below Cat 1 is drawn neutral, not clamped** (`NO_CLASS_COLOR`, shared by the chart's
  piecewise `0` piece and `colorScale`'s `belowFirst`). A ranked month whose mean category
  is 0.0 had no heatwave at all; painting it Cat 1's yellow says exactly the opposite.
  Continuous variables keep clamping, which is right for them — an SST of −4 is simply off
  the bottom, and the map saturates it the same way. The ranking's copy follows too:
  rank 1 is "most severe", not "warmest".

The ranking **refetches on a variable change** but not on a period change: ranking
years by absolute SST is a different question from ranking by anomaly, whereas the ranking
is period-independent by construction.

**`MonthlyRankPanel`'s `Month | Year` toggle refetches nothing.** Both groupings arrive in
the one payload, so the toggle picks which array to draw — no loading state, no guard
against a stale response, and switching back and forth costs nothing. It is the one choice
this panel owns; the *month* is still the map's, since a month picker here would be a
second date control disagreeing with the time bar. Three things follow the basis rather
than being written twice: the heading (the month's name, or nothing beside a selected
`Year`), `partialNote`'s denominator (`periodDays()` — 242 of 365, not of 31), and the
reading guide's nouns. **Clicking a row on the `Year` basis moves only the year**, keeping
the map's month: a year has no one date to land on, and jumping to 1 January would make two
clicked years incomparable on the map, which is the comparison the click is being made to
see. The CSV follows too — `anom_annual-ranks_nino-3-4.csv`, one row per year and no
`month` column, because a 0 there would read back as a thirteenth month. **`AboutDialog`'s
"Compare years" step names both bases and carries the toggle as a replica**, like every
other step there: the guide is the only place the panel is explained before it is clicked,
and a control it does not mention is one nobody looks for.

### The colour range control

**The displayed range is a user setting, per variable, and this is what the value-encoded
imagery is for.** Clicking the legend opens a popover (`ColorLegend.vue`) with a
two-handle slider, exact min/max number fields, and Reset. **The affordance is
spelled out rather than left to the cursor** — a gradient reads as a legend, a
thing you consult, so the trigger ends in a ringed tune icon and the whole row
(title, end values, bar, icon) is one button. The legend is **one line**, not a
stacked block — it sits bottom-centre over the map, and every row of height is
ocean it hides; `mhw`'s key is the same row of named swatches. An `×` at its end
hides it outright (for screenshots); the way back is a `Legend` button beside the
Globe/Flat toggle, shown only while it is hidden — the legend cannot carry its own
restore control. Shared through `useLegend()`, remembered as `enso.legend.hidden`. Categorical variables
keep a plain title: there is no range to edit. Narrowing `sst` to 20–30 recolours
the map instantly and **issues no network request at all** — verified in Chromium, zero
`/image` fetches — because the frame on screen carries the value and Mapbox re-applies the
ramp. Nothing in the cache is invalidated, and the range is not part of the image URL's key.

**Named bands make that adjustability legible**, which the slider alone did not: it says
*that* the range moves without saying what range is worth asking for. `domain.yml` declares
a `presets` list per continuous variable — sst `Coral 24-32 / Tropical 20-32 / Temperate
10-25 / Cold -2-12`, anom `Fine ±1 / Wide ±5` — served through `/domain` beside `vmin`,
`limits` and the stops, so **the numbers are never mirrored in TypeScript**. Three things
about them:

- **The default is not declared as a preset.** It is `vmin`/`vmax`, and `ColorLegend`
  synthesises its chip from those, so the file holds one definition of the default rather
  than two that drift apart the first time one is edited. It is also the only chip that
  calls `resetScale` rather than `setScale`, which is what makes it agree with the `custom`
  badge and the Reset button without a third rule. Every other chip is `setScale` and
  nothing else — no `activePreset` state, so `colorRangeFor`/`stopsFor`/`activeScale` needed
  no changes, and a preset click is indistinguishable from a drag once persisted (verified:
  pick Tropical, reload, it reopens on 20-32 with the chip marked).
- **A band is clipped by nobody, and validated by `shared/domain.py`.** `_check_presets()`
  raises on one outside `range_limits()` rather than clamping it — the frontend's `setScale`
  would clamp it silently, and a chip that lands somewhere other than its label is worse
  than an import that fails. Raised, not asserted: `assert` vanishes under `-O`.
- **Narrowing clamps; it does not isolate.** On 20-32 the band gets all 256 ramp entries,
  which is the point, but colder water still paints the bottom colour rather than dropping
  out. "Show me only the 15-20 water" is a different feature (out-of-band drawn neutral) and
  is deliberately not built.

Chip membership is compared through the same `quantise` `setScale` applies on the way in —
exported from the store for that one caller. Every declared band is a step multiple today,
so `===` would work by luck; this keeps working when someone adds one at 24.05.

The range lives in `store.scales` and everything reads it through one getter, so the map,
the legend and the ranking dots cannot disagree about what a colour means:

- **`stopsFor(v)`** spreads `/domain`'s stops over the range in force. The server samples
  the colormap at 33 **evenly spaced** points (`render.colormap_stops`), so stop *i* is the
  colormap at `t = i/32` and re-labelling those same colours onto a new range is exact.
  **The frontend never evaluates a colormap** — that stays matplotlib's job, server-side,
  which is why there is no colormap picker.
- **`colorRangeFor(v)`** mirrors the conditional in `/domain` and must stay conditional:
  `anom` has a sentinel, so it keeps tabulating its whole encoding span (code 0 needs a slot
  of its own) and its `raster-color-range` **never follows the display range**; `sst` has
  none, so its does.
- **`scaleBoundsFor(v)`** is `encoding.limits`, with the low end stepping over the sentinel
  so a user's `vmin` can never land on the grey no-climatology entry and overwrite it.
- **`setScale`** owns all clamping, so the slider and a typed value are constrained
  identically. It holds the ends at least one step apart — a zero-width range makes the
  ramp's interpolation degenerate and the map undrawable.

Three things here fail in ways worth knowing about, all found by driving the browser:

- **The ramp's sentinel anchor collides at full range.** `anom`'s ramp is grey at −12.8,
  then the first scale colour at −12.7; drag `vmin` to its floor and the first *stop* is
  also −12.7, and Mapbox rejects an `interpolate` with two identical inputs — taking down
  the whole layer, not just the pair. `AnomalyMap.vue` skips the anchor when the first stop
  has already reached it.
- **The control's step is deliberately not the encoding's** (`rangeStep`, `max(scale, 0.1)`).
  `sst` encodes at 0.01 °C, which is right for the data and absurd for a slider: one arrow
  press would move a hundredth of a degree and crossing the range would take 3800 of them.
  Slider and number fields share the one step, so a typed value can never sit off the
  slider's grid and get silently snapped.
- **Quantising needs the quotient settled first.** `12.7 / 0.1` is `126.99999999999999`, so
  a bare `Math.floor` quietly shaves the top step off the anomaly's range.

Persistence follows `SideDock`'s convention — `localStorage`, key `enso.scale.<variable>`,
read once from `ColorLegend`'s `onMounted` (**not** `loadMetadata()`, which runs under SSR)
and re-clamped on read, since the encoding may have moved since it was written.

**The numbers and the monthly ranking are one panel, not two tabs.** They were a
`Numbers | Monthly ranks` pair in the same dock, which made two halves of one answer about
one cell take turns — and the ranking's own month rail then asked the same "which month"
question the numbers above had already answered. So the tabs are gone, `StatsPanel` takes
its natural height at the top, and `MonthlyRankPanel` is spent out of whatever the dock has
left below it. **Both scopes fill it**: `store.activeRanking` picks the cell's ranking or
the region's exactly as `activeSeries` picks the series, so the panel stays presentational
and the scope keeps one definition. The honest "monthly ranks are per cell" empty state
that used to sit there is gone with the endpoint that made it true.

The region ranking is fetched **alongside the region series**, in `loadRegionSeries()`'s
one `Promise.all`, and guarded the same way `selectPoint`'s `sameCell` is: a **period**
toggle re-enters with the same region and must not refetch a ranking that is always monthly
(it would flash the grid), while a **variable** toggle must — ranking years by absolute SST
is a different question from ranking them by anomaly. Verified in Chromium: Daily / Weekly /
Monthly issue only the series request, and switching variable issues only the ranking one.

**The ranking's month is the map's** (`selectedDate`'s), with no local state beside it —
the rail of twelve thumbnails that used to pick it is gone, and `thumbOption()` with it.
One consequence worth knowing: clicking a *row* still moves the map, so the panel would
follow the map straight off the month just clicked, because the store snaps to a bucket
start and the Monday of the week containing the 1st sits in the previous month. `dateFor()`
emits the first Monday *inside* the month on a weekly period for exactly that reason; on
daily and monthly the 1st already snaps to itself.

**The panel lives in a dock beside the map**, not over it. It needs full page height —
one month of ~45 years is already taller than the chart below the map — but it was a
fullscreen modal first, and that made picking a cell cost close / click / reopen every
time, which is unusable if you want to compare ten cells. `SideDock.vue` is a plain
column on the **left** (the map's own controls — projection, scope, legend, time bar —
grew on the right and below): the map keeps its clicks, the store updates, and the panel
follows.

Its width is the user's, not a constant — the dock and the map want the same pixels, so
there is a drag handle on its edge (arrow keys too) and the width is remembered in
`localStorage` under `enso.dock.width`. The floor is **420px**, which is where the panel's
fixed 74px of rank labels stop leaving a readable plot; the ceiling is 1000px and leaves
380px for the map. Both panels are therefore sized by **container queries** (`@container`
on their roots) rather than viewport breakpoints — the stat cards drop from two columns to
one when the dock is dragged in. `MonthlyRankPanel`'s `ResizeObserver` redraw is debounced
100ms because a drag fires it every frame and one redraw is a 45-row panel.

`detailOption()` is built by `utils/ranking.ts` rather than inside the SFC, for the same
reason `periods.ts` exists: being a pure function of its inputs it can be rendered
head-lessly with echarts' SSR mode and asserted on, which is much cheaper than driving a
browser for chart maths.

- **The month scales to itself.** `xDomainOf()` still takes a list of months — it shared
  one domain across the rail's twelve — but is now called with the one month on screen,
  which is what lets it spend the full width on the month being read. At a cell whose
  August reaches +6 °C, a domain covering the whole year left January using a third of
  the pane.
- **The row pitch is spent out of the pane's height** (`detailPitch()`, clamped to
  9–40px), so 45 years normally fit with no scrolling at all. Only a short pane hits the
  floor and lets the panel overflow. Measure the scroll container, not the section — the
  heading sits outside it deliberately.

Three encodings, three separate jobs, deliberately not overlapping: **dot colour** is the
value on the active variable's scale — the same colour that cell has on the map;
**label weight and ink** mark the top N (never hue, which already means anomaly); **amber**
is "where the map is", matching `TimeseriesChart`'s `MAP` markLine — the map's year is
ringed in the plot.

**None of those encodings is self-evident, so there is a `How to read` popover** in the
panel's header, beside the CSV button. Its copy is `readingGuide()` in `utils/ranking.ts`,
pure like `detailOption()` and for the same reason — what it *claims* about the chart can
be asserted on beside the option it describes, which is the only thing that keeps a legend
from drifting off the plot it explains. It is built from the ranking on screen rather than
written once: it names the scope (`the selected cell` vs `Nino 3.4 (area mean)`), the
variable (the anomaly's 1991-2020 baseline, or the heatwave category's "a severity index,
not a category"), what the whisker's `sd` is the spread *of* — daily values at a cell,
daily area means over a region — and the `partial` line only when that month actually has
one. The panel draws a matching glyph per item from the `glyph` key, in the active scale's
colour at the middle of the domain on screen, so the sample dot is a colour in play.
On demand rather than always on: it is read once and then in the way.

**A `partial` month is starred, not hidden.** The API ranks the archive's edge months
with the rest, and the panel marks them twice: the row label reads `15. 2026 *`, and its
dot is drawn **open** (no fill, its own colour as the stroke) so it reads on the same
scale without looking like a settled datum. The star is cashed in by `partialNote()` —
one dimmed line above the plot, "August 2026 is incomplete — ranked on 24 of 31 days" —
which sits *outside* the scroll pane, so it costs the pitch a row's worth of height and
nothing else.

**Playback (`usePlayback.ts`) is a paced loop over `store.setDate()`, not a second
clock.** The play button steps the map one bucket at a time until stopped — reaching the
end of coverage stops it rather than wrapping (the archive is a record with an end, and
looping back to 1985 mid-watch reads as a glitch; pressing play again while parked on the
last bucket rewinds to the first, since it would otherwise do nothing) — and because each
tick advances from whatever
`store.selectedDate` currently is, stepping or clicking the chart mid-run just relocates the
playhead. Typing in the date field stops it, since otherwise the field is a moving target.
Speed is a 1–10 fps slider read *per frame*, so it takes effect on the next one.

Frames are **not** all preloaded: the daily archive is ~15.2k WebPs per variable, so what is
held is a window of `AHEAD = 8` in front of the playhead,
warmed with `new Image()` + `decode()` and capped at `CACHE_MAX = 24`. `/image` sends
`Cache-Control` (30 days for a bucket ended more than 45 days ago, an hour otherwise) and an
ETag, so Mapbox's own fetch for the same URL then resolves out of the browser cache, and a
revalidation is a 304. The loop waits on frame readiness rather than firing on a bare
`setInterval`, because a Mapbox `ImageSource` never retries a failed image and silently keeps
the previous frame — a fixed interval would render that as an unexplained stutter. A 3 s
per-frame timeout keeps one slow frame from freezing playback.

**`store.selectedDate` is always a bucket start**, snapped through `store.setDate()` /
`store.setPeriod()` — never assign it directly. Both `store.period` and `store.variable`
drive the chart request and the image URL together, so switching either re-renders both.

**Clicking the chart sets the map date** (as in the ocean-acidification dashboard). The
line is drawn with `showSymbol: false` + `large`, so there is nothing for ECharts' own
`'click'` to hit — the handler sits on the ZRender canvas, converts the raw pixel with
`convertFromPixel`, and snaps to the nearest date *in the series*, which guarantees the
emitted value is a real bucket inside coverage. An amber `MAP` markLine shows which
bucket the map is on, and it is merged in (`setOption` without `notMerge`) rather than
re-rendered, because a full re-render would reset the `dataZoom` window on every click.
`TimeseriesChart` stays presentational: it emits `select`, and `index.vue` calls
`store.setDate()`.

**Everything lives under `app/`** — Nuxt 4's `srcDir`. A top-level `front/composables/`
is *not* picked up and `~/composables/...` will fail to resolve (the ocean-acidification
dashboard has one at the top level; do not copy that layout here).

**SSR vs. browser base URLs.** `useApi()` uses two: during SSR the Nitro server is inside
the compose network and must reach the API by service name (`API_INTERNAL_BASE_URL`,
`http://api:4000`), while anything the browser fetches — including the image URLs handed
to Mapbox — must use the published `NUXT_PUBLIC_API_BASE_URL` (`http://localhost:9021`).
Getting this wrong surfaces as `ECONNREFUSED ::1:9021` from the Nitro server.

**The projection is the user's, and it opens on the globe.** A Globe/Flat pair sits at the
map's top-left and the choice is remembered in `localStorage` under `enso.map.projection`.
The two are framed differently and cannot share a view: Mercator fits the whole box
(`fitBounds`; the old `INITIAL_NORTH = 68` clip is gone — that existed because the OISST
domain ran to 90°N and dominated a Mercator fit, and this box stops at 65°N), while the
globe takes a centre and a zoom — the North Pacific at `[-170, 25]`, zoom 1.7 — because no
`fitBounds` frames a 190°-wide box on a sphere without putting half of it behind the limb.

**The globe needs the field image twice.** Mercator draws world copies, so the single quad
at 100…290 crosses the antimeridian and is drawn whole. The globe has none: measured in
Chromium, that quad **clips dead at 180** and the entire eastern Pacific silently vanishes.
`AnomalyMap.vue` therefore adds a second image source with the *same* URL at −260…−70 while
the globe is on. Each source draws only the part of itself inside −180…180, so the two abut
at the dateline, do not overlap, and no image has to be cropped. It is removed again in
Mercator, where both quads land on the same ground and two layers at 0.85 opacity would
double into a visibly darker box.

**`imageBounds.east` is 290, not −70, and is passed to Mapbox as-is.** Normalising it into
−180…180 would make west > east and collapse the image source — see the Map imagery
section for the verification. (Confirmed again on the globe: west > east draws nothing at
all.)

Stepping days calls `ImageSource.updateImage()` rather than removing and re-adding the
layer, so the basemap does not flash between frames.

**The active region's box is a GeoJSON polygon, and it needs neither of the raster's two
workarounds.** Every named region's east edge is above 180 and three cross the antimeridian
(Niño 4 160..210, Bering Sea 180..200, PDO 180..250). Verified in Chromium in **both**
projections: an unwrapped ring draws as one continuous box on the globe and on Mercator —
no westward second copy, no split ring, no MultiPolygon. Splitting at 180 was tried and is
unnecessary. The edges *are* densified (a vertex every 2°), because a region box follows a
parallel and a four-corner polygon would draw the PDO box's 70°-wide edges as straight
chords bowing off it.

**`queryRenderedFeatures` is not a witness on the globe** — it returns 0 for a box that is
plainly on screen. This is the same lesson as `preserveDrawingBuffer: false`: take a
screenshot and look at it.

**A polygon region draws its real outline, fetched on demand.** `/domain` carries
`masked` per region and the ring itself lives at `/region/{key}/geometry` — 120 KB against
~2 KB for the whole domain payload, and most sessions never select it — so `AnomalyMap`
fetches it once, keeps it in a module-level `Map`, and guards the response against the
selection having moved while it was in flight. **Nothing is drawn until it arrives**:
showing the bounding box first and swapping it for the zone a moment later reads as a bug,
and for `pacific_bioregions` the box is 2.1× the region's area, so it would be claiming the numbers
cover water they do not. If the fetch fails, the region draws no box at all rather than a
rectangle that misstates it — the numbers beside it are unaffected, since they come off a
rollup built from the mask. `frameRegion()` still flies to the **bounding box**, which is
what a camera wants.

**Only one box is ever drawn, and only in region scope.** The box is the visual half of what
the numbers panel is reading, so the two are one selection seen twice rather than a layer
with a toggle of its own.

**Selecting a region flies the camera to it** (`frameRegion()`), because Nino 1+2 is 10
degrees wide on a basin that spans 190 and an amber rectangle at 3% of the map's width is
something you have to go looking for. It uses `fitBounds` **on the globe too** — unlike
`frame()`, which cannot, since half a 190-degree box sits behind the limb at any zoom that
fits it; the widest region is the PDO box at 70 degrees, which frames fine on the sphere
(verified in Chromium, screenshot). Longitudes go in unwrapped like everywhere else here,
and Mapbox wraps the resulting centre itself — Nino 4 at 160..210 lands centred on -175,
the Bering Sea at 180..200 on -170. `maxZoom` (4.5) keeps the smallest boxes from filling
the pane with no coastline around them to say where they are. Leaving region scope moves
nothing: the pin is already where the user clicked. Switching projection while a region is
active re-frames to the *region*, not back out to the whole basin.

**`map.isStyleLoaded()` is not "can I add layers".** It reports whether every source in the
style has settled and is routinely **false** on a fully drawn map — measured at 10 s into a
loaded page with both raster layers up. Guarding layer creation on it silently skips the
layer forever. `AnomalyMap.vue` tracks a `styleReady` flag set in the `load` handler, which
is the actual precondition.

**Charts**: always ECharts, never a hand-rolled `<canvas>`. The point series is ~15k daily
values; `dataZoom` is what makes that browsable.

**The line is coloured on the active variable's scale**, by a continuous `visualMap` built
from `store.activeStops` — the same stops the map and the ranking dots read, so a value has
one colour everywhere and dragging the colour range recolours the chart with the map (and,
like the map, fetches nothing). It was a hard-coded diverging ±3 ramp, which is right for
`anom` and nonsense for `sst`, where every ocean temperature above 3 °C sat pinned red. Two
things about it fail quietly: an explicit `series.lineStyle.color` **beats** the visualMap
rather than losing to it, so the fallback colour is only set when there are no stops; and
the y-axis needs `scale: true` plus a zero `markLine` drawn **only for `anom`** — either one
alone drags a 25–30 °C SST record down against a 0–30 axis and draws it as a flat line.
