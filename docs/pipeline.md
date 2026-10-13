# Process pipeline

`process/`: download, ingest, `run`, retention, `repartition` and Prefect.

## Process pipeline (`process/`)

Entry point `process/CRW/cli.py` (`python -m CRW.cli`). Modules:
- `config.py` — filename parsing, `scan()` / `scan_mhw()`
- `download.py` — NOAA CRW fetching; a `Product` value per archive (`SST`, `MHW`)
- `ingest.py` — NetCDF → ClickHouse; a `Target` per archive (`SST_TARGET`, `MHW_TARGET`)
- `climatology.py` — the 366-file load and `region_clim`
- `regions.py` — the `region_daily` rollup (`CRW.cli rollup`)
- `imaging.py` — day/week/month × sst/anom/mhw rendering, and the retention window
- `status.py` — the `ingest_status` table
- `repartition.py` — the one-off partition-key migration (`CRW.cli repartition`)

**`process/CPC/` is a second package, not a subdirectory of the first** (`python -m CPC.cli`),
for the land layers. Same module names, same shapes, importing the same `shared/` contract:
- `config.py` — `YearFile` (a `(variable, year)` pair, not a date), `scan()`, `ARCHIVE_START`
- `download.py` — a `Product` per variable (`PRECIP`, `TMAX`, `TMIN`); validates the body
  before the rename, retries, and falls back to a second host
- `ingest.py` — a `Target` per table (`TEMP_TARGET`, `PRECIP_TARGET`); `ingest_year` walks
  time indices **inside** a year file rather than walking files
- `status.py` — a **binding**, not a copy: `CRW/status.py` is already table-parameterised, so
  the land products import its functions and bind them to `land_temp_status` /
  `land_precip_status`

The naming is deliberate and worth keeping: CPC is the Climate Prediction Center, a different
NOAA program, and a CPC product inside a package named for Coral Reef Watch would be the same
class of misnaming as calling a bioregion an EEZ. Its `run` is also a genuinely different
shape — yearly files, no watermark, a version check that stops an unchanged run after its
HEADs — rather than a flag on the ocean one.

Land inserts are **one per year** (~23 M temperature rows, ~34 M rain rows), not batched by
day: a land day is only ~63–93 k rows, so finer batching would only create parts.

Inserts are batched across days (`--batch`, default **5** — a day is ~7.5 M rows now, not
OISST's 96 k, so the old default of 30 was a 225 M-row insert).

### `repartition`, and why it never needs a second copy of the table

**A one-off migration, and the only command here that rewrites a table it did not
ingest.** It exists because `ensure_schema()` is `CREATE TABLE IF NOT EXISTS`: editing the
DDL fixes a fresh database and does nothing at all to the one holding the archive.

**The obvious `INSERT INTO new SELECT * FROM old` wants 129 GB of headroom, and the
production box has 90 GB.** So it goes one source partition at a time and **drops each one
once its rows are confirmed landed** — occupancy stays flat at the table's own size with a
one-year bulge of ~3.1 GB, and the run is resumable at every partition boundary. That is
the whole design of the module.

The order of operations is the safety rail and only ever moves one way:

```
rows in old partition -> INSERT -> rows landed == rows expected -> only then DROP
```

so an interruption loses work, never data. Verified on a synthetic 42-partition table:
300,000 rows in, 300,000 out, 42 partitions to 8; and separately that `finish` refuses
while source partitions remain, that a low-disk plan refuses before touching anything,
and that a row-count mismatch raises **with the source partition still in place**.

Three details worth knowing:

- **Row counts come from `system.parts`, not `count()`.** They are exact and a merge never
  changes them, so verifying a 2.7-billion-row year is free. The one query in the module
  that reads data is the stale-row check, which is why it runs **once per invocation**
  rather than once per year: after the first partition the run has done every subsequent
  one itself and knows they were clean.
- **A crash mid-insert leaves a partial year**, which the next run detects and clears with
  an `ALTER ... DELETE` before retrying. That mutation is expensive and is meant to be — it
  is the crash path only, and the alternative is a second partial copy appended silently.
- **Partitions move oldest first**, because the recent end is what `run` touches daily.

`--dry-run` prints the plan and its disk cost; the default copies; `--finish` performs the
`EXCHANGE TABLES` swap, kept separate because it is the only irreversible moment.
`--optimize` merges each new partition to one part **where free space allows** and skips
with a warning where it does not — at that point the table is already ~40x fewer parts than
it started with, so it is a finishing touch rather than the point.

Do `mhw_daily` first: same code, a fortieth of the bytes, and it is the bigger share of the
`mhw` variable's latency anyway, since that query pays both tables' part counts.

**Take the site down while it runs, and the reason is not politeness.** A migration moves
whole partitions out of the daily tables before it puts them back, and **nothing the
frontend reads can see that**: `/coverage`'s `mhw.complete` gate is computed from
`mhw_status`, not from `mhw_daily`'s contents, and the migration does not touch the status
tables. So the dashboard stays up, keeps offering `mhw`, and the sparse table's LEFT JOIN
reports a confident **category 0** for every year currently in flight — the exact failure
`mhw.complete` exists to prevent, arriving by a route it cannot observe. `sst_daily` is the
same shape without even the gate: migrated-away years simply go missing. Use the
`maintenance` profile above.

**Once started it has to finish.** Source partitions are dropped as they land, so there is
no half-way rollback, only forward. Interruption is fine and expected — it resumes at a
partition boundary — but abandonment leaves the archive split across two tables.

**Skip `--optimize` on the first pass over `sst_daily`.** It re-reads and rewrites every
partition again, 129 GB of extra HDD I/O, and background merges consolidate the decade
partitions on their own as long as free space exceeds the largest one (~31 GiB against
90 GB). Check `system.parts` afterwards and spend it only where something is still
fragmented.

**Do not pass `--no-deps`.** `repartition` reads `system.parts` and does every insert
through ClickHouse, so it needs `db-ch` up — unlike `render`, which is the command that
flag exists for. Without it compose starts `db-ch` and waits on its healthcheck; with it
you get `Connection refused` on `db-ch:8123` and nothing else to go on.

**Stop `scheduler` first**, alongside `front` and `api`. A scheduled `run` would ingest into
the partitions the migration is moving, and the UI's pause toggle does not survive a
container restart — see "Prefect" below.

**Run it detached** — `run -d --name ...`, then `docker logs -f`. A `docker compose run`
container **outlives the client that started it**, so a terminal closing does not stop the
migration; starting a second one then gives two concurrent runs, which is what
`_assert_no_concurrent_run` and `finish()`'s total check are both there to catch. Found the
hard way: it put 491 M duplicate rows into a single year, and every per-partition count
still agreed, because each run verifies only the delta its own INSERT produced.

### Downloading, and revisions in place

```
.../5km/v3.1_op/nc/v1.0/daily/sst/{YYYY}/coraltemp_v3.1_{YYYYMMDD}.nc
```

**CRW has no preliminary/final filename pair.** `v3.1_op` is the operational near-real-time
stream and a date's file is **revised in place** at a URL that never changes. Since `run`
deletes the local NetCDF after ingesting, the only way to notice is to keep what the server
reported — `Content-Length` and `Last-Modified` — in `ingest_status` and HEAD the URL again
later. That is `--recheck-days` (default 30). This replaces the OISST `is_preliminary`
mechanism entirely.

Downloads stream to a `.part` file and rename on completion; `DAILY_RE` does not match
`.part`, so an interrupted transfer can never be picked up as a complete file.

### `run`, and why it is a range

With no `--date`, `run` processes **every day from the last ingested through yesterday**,
not just yesterday. One code path then covers normal daily operation, a missed cron run,
and a bulk download that has outrun the ingest. A 404 on yesterday exits 0, not failure —
CRW publishes at ~1 day latency and not at a fixed hour, so a cron retry must be a
no-op-or-succeed.

Per date: `download+ingest SST → download+ingest MHW → render 9 images → prune both
retention windows`. The two products are handled **independently** — one being unpublished
is not a failure of the other, and the date's frames are rendered for whatever landed. The
catch-up watermark is the **earlier** of the two archives' last ingested day, so a date
that is SST-done but MHW-pending — which happens whenever a run lands in the ~90 minutes
between the two publications — is picked up on the next run rather than stranded behind
the SST watermark.

**The API serves nothing past the last date both archives have landed for**
(`timeseries.data_through()`), and `/coverage`'s `end` is that date, with the SST table's own
edge in `sstEnd`. An SST-only date is not visibly incomplete: the sparse LEFT JOIN reads it
as category 0 everywhere, and `run` has already rolled it into `region_daily` with an
`mhw_area_frac` of 0 — which the ribbon printed as "0% of the Pacific". `_date_filter()`
clamps every series, `_ranked_periods()` every ranking, and `/state` both of its rollup
reads. Only while `mhw.complete`; a half-backfilled MHW archive would otherwise pin the whole
dashboard to wherever the backfill had reached.

### The retention window

A weekly frame is the mean over seven days, but `run` deletes each `.nc` after ingesting
it — so days N−6…N−1 are gone by the time day N is processed. **`imaging.retention_floor()`
keeps the files the open week and month still need** (at most ~37 files, ~380 MB) and
prunes only what has fallen out of both. `prune()` walks **both** archives: an MHW weekly
frame is a max over the same span of days and needs its own files kept for exactly as long,
and at ~640 KB a file the second window costs ~24 MB. Losing that window does not corrupt anything, but
it freezes weekly and monthly frames at whatever was last rendered.

### Prefect: the schedule and the run history

**Both `run`s are scheduled by Prefect, and it adds nothing else.** `process/flows.py`
(`python -m flows`) serves two deployments from one `scheduler` container. `ocean_run` wraps
`CRW.cli.run_targets()` (which dates a run covers) and `CRW.cli._process_date()` (what happens
to one); `land_run` runs `CPC.cli.run()`'s stages as tasks. So each scheduled run and its CLI command are the
same job. It sits beside `CRW/` and `CPC/` rather than in either, since it serves both. It
is the only module that imports Prefect, and neither CLI imports it. Prefect 3.8.6.

**Prod and dev use different servers, deliberately.** Prod's `scheduler` registers with the
shared server at `https://pipelines.cioospacific.ca` (`PREFECT_API_URL`), which is not part of
this repo: it is the [cioos-pacific-pipeline](https://github.com/cioos-siooc/cioos-pacific-pipeline)
stack, whose README documents this flow beside its own pipelines. Dev keeps its own local `prefect` service on SQLite, because dev and prod
registering the same deployment on one server would overwrite each other's schedule. **The
client pin in `pyproject.toml` must match both**: the shared server's version and dev's
`PREFECT_IMAGE_TAG`. So a Prefect upgrade means upgrading the shared server first, which
affects every project on it.

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev \
  --profile prefect up -d prefect scheduler          # dev: http://localhost:9025, admin:admin
```

- **What the UI shows**: tag `osta` on both. Flow `osta-ocean-run`, deployment `osta-ocean`:
  one flow run per firing and
  **one task run per date**, named after the date. Each date's task ends in a state named
  for its outcome: `Ingested`, `Skipped`, `Unpublished` or `Failed`. So on a normal day the
  thirty recheck dates show as `Skipped` and the one new date as `Ingested`. The flow ends
  `Failed` if any date did, with `cli.run_summary()`'s line as its message. The pipeline's
  own log lines (`CRW.*`, `CPC.*`, `shared.*`) appear in each run's logs. Flow
  `osta-land-run`, deployment `osta-land`: one flow run per firing, ending `Unchanged` (most
  hours), `Ingested` or `Failed`, with **one task run per stage**: `check versions`, then per
  product `fetch`, `ingest <product> <year>` per year file, `render` and `finish` (versions
  recorded, then pruned). These are `CPC.cli.run()`'s own stages (`plan_run` …
  `finish_product`), so the CLI and the flow stay one job. A product whose download or
  render failed records no version, so the next hour retries it.
- **An ad-hoc run** is *Run → Custom run* on the deployment. Ocean: `date` for one day,
  `force`, `keep_nc`, `recheck_days`, `max_days`. `width` is deliberately absent: a cached
  frame at any other width is a 404 and a blank map. Land: `product`, `force`, `keep_nc`,
  `recheck_days`.
- **Schedule: hourly**, `RUN_CRON` (default `0 * * * *`) and `LAND_RUN_CRON` (`30 * * * *`),
  UTC. Neither source publishes at a fixed hour, so the first run after a publication picks
  it up. `limit=1` is **across both deployments**, so no two runs overlap, ocean or land; the
  half-hour offset keeps the land run from waiting behind the ocean one. **No retries**: each
  run picks up whatever the last one missed, so the next firing is the retry.
- **A run with nothing new is cheap, and that is what makes hourly affordable.** The ocean
  run HEADs its 30-day recheck window and skips every date whose `Content-Length` and
  `Last-Modified` match status. The land run HEADs its year files (six, or nine early in
  January) and stops if every one matches `land_source_files`, the version the last
  successful run finished with. Without that check every firing would download ~200 MB. It is
  per product, since temperature and precipitation are rewritten at different hours, and a
  version is recorded only after ingest and render succeed, so a failed run is retried next
  hour. `CPC.cli run --force` skips the check.
- **Dev opens paused with `keep_nc` on** (`RUN_SCHEDULE_PAUSED`, `RUN_KEEP_NC`). A dev run
  that prunes deletes the local archive back to the open week. Prod defaults to live and
  pruning, so **leave `RUN_KEEP_NC=true` until `render --variable mhw` has finished.**

Verified in dev, through the API the UI reads:

- A run for 2026-09-20 ingested both products, rendered 9 frames and rolled up nine
  regions. The task ended `Ingested`, and all 25 log lines (download, ingest, imaging,
  regions) reached the run.
- With the NetCDF directory unwritable, the date's task failed with the traceback and the
  flow ended `Failed`, reading `run: 1 failed`.
- Requests without the auth string get a 401, and `/api/health` answers without it.
- `CRW.cli run --date 2026-09-20` still works, with `prefect` never imported.
