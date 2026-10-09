# API

`api/`: endpoints, bucketing rules, `/state` and the rankings.

## API (`api/`)

FastAPI in `SERVER.py`. **Timeseries are read live from ClickHouse; imagery is not.**

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness + ClickHouse reachability, plus each archive's last ingested date and lag (never fails over staleness) |
| `GET /health/data` | 503 once either archive is more than `STALE_AFTER_DAYS` (default 3) behind — for an external monitor |
| `GET /domain` | grid extent, image bounds, variable metadata, per-variable colour stops and `encoding` (mix, ranges, `limits`), `noClimColor`, region list |
| `GET /coverage` | served date range (`end` = last date both archives have), row count, climatology completeness, MHW archive range and completeness |
| `GET /state` | the header ribbon's finding: ENSO phase from Nino 3.4 (`heatwave` is always null; see below) |
| `GET /variables` | variable list, with `derived` on `anom` |
| `POST /timeseries` | `{lat, lon, start?, end?, period?, variable?}` → record at the nearest cell |
| `POST /landTimeseries` | `{lat, lon, start?, end?, period?, variable: land_*}` → the land overlay layer at the nearest CPC cell; empty on CoralTemp ocean |
| `POST /regionTimeseries` | `{lat: [a,b], lon: [a,b], ...}` → area-mean over an arbitrary box |
| `GET /region/{key}` | same, for a named `domain.yml` region, using `region_clim` |
| `GET /region/{key}/geometry` | a polygon region's outline as GeoJSON; 404 for a plain box |
| `GET /region/{key}/about` | why the region matters, how its edges are drawn, its references, and a polygon's outline source |
| `POST /monthlyRanking` | every calendar month at a cell ranked within its month-of-year, plus every year ranked against every other (`annual`) |
| `GET /region/{key}/monthlyRanking` | the same two rankings over a named region, from `region_daily` |
| `GET /image/{date}.webp` | one bucket as a Web-Mercator WebP |

**`variable` — `sst` (default) / `anom` / `mhw`** — is accepted by every endpoint above.

**How `mhw` is bucketed differs by query shape, and each difference is deliberate:**

- **A point and the map take the MAX** over the bucket. A category is an ordinal class and
  its mean is not one — a cell at Cat 1 for two days of seven averages to 0.29, which is no
  category at all. The max answers what the frame is read for (*how bad did it get this
  week*), keeps every period on the same 1..5 scale so one legend serves all three, and
  keeps the invariant the whole period mechanism exists for: a chart point and the map
  frame carrying the same date agree.
- **A box reports EXTENT, and buckets it by the MEAN of daily extents.** A box's `mhw` is
  the share of its ocean area at category >= 1 (`mhw_extent`, in percent) rather than a
  category at all — see `region_daily` above for why the mean category it used to report
  was unreadable. Being continuous, there is nothing ordinal left for a max to preserve,
  and a max of daily extents would be a spike detector for each week's worst day.
- **The monthly rankings take the MEAN**, and the point one is the place `mhw` is
  deliberately averaged at a cell (a region's ranks its daily extents, which were never a
  category). They rank years against each other, and a max would put
  most of the archive on Cat 1 and rank nothing; the mean daily category over a month is a
  severity-days index that separates one bad week from a whole month at Cat 1. The region
  ranking is a mean of daily area means, which was never a category to begin with.

### `/state`, and the two things a point series now carries

**`/state` is the only endpoint that decides what is worth saying rather than serving what
was asked for.** Everything else answers a question the visitor has already framed — this
cell, that region, this date — and none of it says whether anything is happening out there.
It reports one finding:

- **ENSO phase**, from Nino 3.4. **This is ONI-*style*, not NOAA's index, and the payload
  says so** (`official: false`, `baseline`). Since February 2025 NOAA rates ENSO with its
  **RONI** (Relative Oceanic Niño Index): Nino 3.4's anomaly minus the 20°S–20°N tropical
  mean, rescaled. This archive has one fixed 1991–2020 climatology and subtracts nothing, so
  when the tropics are warm it runs well above NOAA's (JAS 2026: +2.65 against +1.69).
  **NOAA's own number rides along, read and never computed**: `api/modules/roni.py` fetches
  CPC's `RONI.ascii.txt`, holds it 6 h per worker and keeps the last copy on failure;
  `enso.noaa` is the newest season and `enso.history` the last 24 of both, which the
  popover charts (`EnsoCompare.vue`). The API needs outbound HTTPS to
  `cpc.ncep.noaa.gov`; without it both are null and the ribbon omits them. Everything
  else is NOAA's: overlapping three-month seasons, the ±0.5 °C threshold, the five
  consecutive seasons that separate an **episode** from **conditions** (the ribbon's
  wording turns on it), and the strength bands. Seasons are built from **complete calendar
  months only** — the month in progress would drag a running mean that is meant to be three
  whole months — and it is reported separately as `latestMonth`, flagged partial, with its
  rank among the same calendar month in every other year.

**There used to be a second, the Pacific's marine heatwave extent against its 1991–2020
mean for the day of year, and it was removed (2026-10-07) on a reviewer's comment.** That
mean is not a normal. NOAA's heatwave threshold is a fixed 1985–2012 90th percentile, so in
a warming ocean extent trends upward: measured on the `pacific` rollup, ~10% averaged over
1985–2012, ~14% over 1991–2020, ~28% over 2014–2025. Calling 14% "normal" implied a stable
reference when the reference is what is moving, and the bare percentage without it
says nothing. `heatwave` stays in the payload as `null` so a cached frontend does not break.

It is a rollup read — a few hundred rows, milliseconds. Not instrumented
server-side: it is page-load plumbing like `/domain` and `/coverage`. The ribbon's *clicks*
are tracked in the frontend, because those are choices.

**A point `sst` series carries its climatology** (`climatology`, `climatologyBaseline`) so
the chart can draw the normal the temperature is departing from — an absolute SST is close
to unreadable without it, and this is what lets the SST view answer "compared to what"
without switching variables. **LEFT JOIN, not INNER**, which is the whole difference from
the `anom` branch: 3.2% of the box's ocean has SST and no climatology, and an inner join
would silently drop the ice fringe's dates from the SST series itself. A bucket missing any
day's climatology reports `null` rather than averaging the days that have one, which would
make a bucket's normal cover a different set of days than its value.

**A point `mhw` series carries its heatwave runs** (`events`). A category answers "how bad
is it today" and the reader's next question is always "how long has this been going on",
which the daily line answers only by being counted along by eye and which a weekly line has
already destroyed by taking a max over seven days. So `mhw_events()` is **its own daily
read**, never a fold of the buckets. **A gap in the archive breaks a run, deliberately**:
consecutive means consecutive *dates*, and `mhw_daily` is sparse, so the day after a
heatwave day is absent whether it was calm or never ingested — stitching across it would
invent duration out of a missing file.

**`period` — `daily` (default) / `weekly` / `monthly`** — buckets are defined once in
`shared/periods.py`: weeks start on **Monday** (`toMonday`), months are calendar months, and
a bucket is always labelled by its **first day**. The frontend mirrors the same arithmetic
in `front/app/utils/periods.ts` — **change one and change the other.**

**Area means are cos(latitude)-weighted** (`sum(v*cos(lat)) / sum(cos(lat))`). At 60°N a
0.05° cell covers half the area of one at the equator, so a plain `avg()` over-weights the
poleward end of any box tall enough to matter.

**Out-of-domain points** raise `OutsideDomainError`, rendered as a **400 carrying both a
plain-string `detail` and a structured `error` object** (`code: "outside_domain"`,
`requested`, `domain`). `detail` stays a sentence so callers that just print it keep
working; `error.code` is what lets the frontend show this as an informational empty state
rather than a red failure.

**The rankings never follow the caller's `period`**, and they rank `anom` by default
because ranking years by absolute SST is a different question. Every period is ranked
including the archive's truncated edges, which carry `partial: true` — the month or year in
progress is the one people most want to look at, so it is starred rather than hidden. A
month missing an *interior* day is **not** partial: it is as complete as it will ever be.

**Each response carries two rankings, not one: `months` and `annual`.** The panel's heading
read as the whole year when it was one calendar month — "2015 was the warmest" when what it
said was "the warmest August" — so ranking whole calendar years is now the other half of the
same answer rather than a thing that cannot be asked. **A year's mean is the mean of its
days, never of its twelve monthly means**: the months are not the same length, so averaging
averages would weight February like July.

**Both groupings come off one scan**, via `GROUP BY GROUPING SETS ((month, year), (year))`.
The annual set arrives with `month = 0`, which is also the window function's partition — so
the years are ranked against each other by exactly the same expression that ranks the
Augusts against each other, and there is still one definition of "the ranking". Two queries
would have been two definitions of it again. `_ranked_periods()` splits `month = 0` out
into `annual` on the way to the response, so no client has to know about the sentinel.

**There are two of them — a cell and a named region — and the ranking itself is defined
once.** `_ranked_periods()` takes any subquery yielding `(date, value)` and does the
grouping, the `stddevSamp` and the `row_number()`; only the series underneath differs, so
the two cannot drift into meaning different things. A cell's series is the ~15k-row
primary-key read the point timeseries makes; a **named region's is `region_daily`**, folded
by month instead of by period bucket — the same numbers `/region/{key}` plots, so the year
that ranks first is the year whose month the chart draws highest. Measured, that is **15 ms**
for Nino 3.4, because the rollup already exists.

Two things about the region ranking are not the cell ranking, and the response says so
rather than leaving them to be inferred:

- **`sd` is the spread of daily *area* means**, not of daily values. Spatial averaging
  cancels the noise one cell keeps — Nino 3.4's August 2015 is 0.176 against the same
  month's 0.308 at a cell inside it — so the two columns are not comparable. `areaMean:
  true` is what the frontend reads to label it (`sd of daily means`) rather than renaming
  the field.
- **`anom` comes off `mean_sst_clim`, not `mean_sst`** — `_ROLLUP_COLUMNS`, same choice
  `named_region_timeseries()` makes, because the `mean(sst - clim) == mean(sst) - mean(clim)`
  identity needs both sides averaging the `has_clim = 1` cells. The subtraction is per day
  against `region_clim`'s MMDD, not per month, so a month spanning the ice edge's seasonal
  move still subtracts the matching climatology.

**Only named regions get one.** An arbitrary box through `/regionTimeseries` has no rollup
and would be the 3–12 s live aggregation, so there is no ranking endpoint for one.
