# Gotchas

Every trap this project has fallen into, in full. CLAUDE.md carries the one-line versions.

## Gotchas

- **`--env-file .env.dev` is required** on every compose invocation, as above.
- **Editing the DDL in `shared/ch.py` does not repartition an existing database.**
  `ensure_schema()` is `CREATE TABLE IF NOT EXISTS`, so a changed `PARTITION BY` applies to
  a fresh deploy and is silently inert on the one that matters. `CRW.cli repartition` is
  the migration; `shared.ch.is_repartitioned()` is what answers "is this server on the new
  key". Stop `scheduler` for the duration — `run`'s ingest and the migration would
  otherwise contend for the same partitions.
- **`process` and `scheduler` share one `image:` name, and that is what gets `process`
  rebuilt.** `process` is behind the `tools` profile, and compose skips services outside
  the active profiles when building — so before `scheduler` existed, `up -d --build` left
  the pipeline image on whatever code it was last built with, `api` could be on new
  `shared/` while `process` was on old, and a new subcommand failed with argparse's
  `invalid choice`. `scheduler` is not behind a profile and builds the same image
  (`osta-prod-process`), so one `up -d --build` now covers both — verified with
  `--dry-run`. **Give them different `image:` names, or put `scheduler` behind a profile,
  and that silent drift comes back.**
- **Pausing in the Prefect UI is undone by the next restart.** `serve()` applies
  `RUN_SCHEDULE_PAUSED` every time it starts, and pauses the schedule when it stops.
  Verified: unpause in the UI, `stop scheduler`, and the deployment reads paused. Unpause
  again, `start scheduler`, and it is paused again. A host reboot restarts the
  container too. **To hold the pipeline, `stop scheduler`.** That is the only pause that
  lasts.
- **`PREFECT_AUTH_STRING` must never be blank.** Prefect treats an empty string as a
  password of `""`, not as "no auth": the server enables auth, the client sends no header,
  and every call 401s — the scheduler dies on start registering its deployment. Dev
  defaults to `admin:admin` for that reason.
- **Three Prefect container details, each found by it failing** (the first two are about
  the server container, so they apply to dev's local `prefect` and to the shared server's
  own compose file, not to anything in prod here):
  - The server's state mounts at `/var/lib/prefect`, **not `/opt/prefect`**. The image
    keeps its `entrypoint.sh` in `/opt/prefect`, so a mount there leaves tini with no file
    to run.
  - Run as `UID`, the server cannot copy its UI bundle out of root-owned site-packages.
    `PREFECT_UI_STATIC_DIRECTORY` must point somewhere writable, or the API comes up and the
    UI is simply not served.
  - `flows.py` cannot use `from __future__ import annotations`. Prefect builds a pydantic
    model from the flow's signature, and a string `dt.date` fails every run at parameter
    validation.
- **`PREFECT_LOGGING_EXTRA_LOGGERS` attaches a handler but sets no level**, so `CRW.*` would
  inherit the root's WARNING and every INFO line would be dropped before reaching the UI.
  `flows._log_to_ui()` sets them to INFO itself; a new package's logger goes in both
  `LOGGERS` there and the compose variable.
- **`PREFECT_UI_API_URL` is what the browser calls**, and left unset it defaults to
  `http://0.0.0.0:4200/api` — the UI loads and then fails every request. It is
  `PREFECT_PUBLIC_URL` + `/api`.
- **`CH_IMAGE_TAG` must be >= the version that wrote `CH_DATA_DIR`.** ClickHouse has no
  downgrade path. Dev runs `clickhouse-server:latest`, so a data directory copied from a
  dev box to prod carries whatever major was current — 26.5.1.882 for the first copy —
  and prod's original `25.8` pin could not load its metadata. **The symptom is not a crash**:
  the container comes up and answers `/ping`, so the healthcheck passes, `SHOW TABLES`
  returns nothing, `api`'s `/health` reports ClickHouse unreachable, and `front` — which
  waits on `api` being healthy — never serves. Read the version off the source archive's own
  log before pinning:
  `grep -ao 'Starting ClickHouse [0-9.]*' <CH_LOG_DIR>/clickhouse-server.log | tail -1`.
- **`API_INTERNAL_BASE_URL` is `http://api:4000`, not the published `API_PORT`.** `API_PORT`
  (9021) is the *host* side of the mapping; inside the compose network uvicorn is on 4000.
  Pointing SSR at `api:9021` is the same `ECONNREFUSED` the dev notes warn about, just
  arriving from the other direction — and it surfaces as a plain 500 from the frontend
  while the API itself is fine on the published port.
- **Env vars are baked in at container creation.** Editing `.env.dev` does not affect a
  running container — use `up -d --force-recreate <service>`, not `restart`.
- **`domain.yml` changes need an API restart.** `shared.domain` caches the parsed YAML with
  `lru_cache`, and uvicorn's `--reload` only watches `.py` files, so a colour-range or
  region edit is invisible until the container is restarted. A **colour** change needs
  nothing more — the cached images carry data, not colour, so the palette is applied in the
  browser. Only a change to the grid or the encoding invalidates `./data/images`.
- **`UID`/`GID` in `.env.dev`** are what stop `api` writing root-owned cache files into the
  bind-mounted `./data`. Set them to your own `id -u` / `id -g`.
- **The `process` venv lives at `/opt/venv`, not `/app/.venv`** — compose bind-mounts
  `./process` over `/app`, which would hide anything installed under it.
- **`api` still imports `netCDF4`**, but only to read the land climatology files' attributes
  for `/coverage.land.layers`. It renders nothing; every frame comes from the image cache.
- **The MHW category's on-disk encoding changes on 2024-07-01**, at a URL and filename that
  do not. Anything reading `heatwave_category` must bound the value at 1..5 rather than
  testing a sign or a fill value — see the source section above for what a floor alone
  costs. The check that catches it in one line, and which belongs in any future test suite:
  `SELECT count() FROM mhw_daily WHERE cat > 5` must be 0.
- **A category of 5 can also be land, and only on 29 February.** The leap-day files carry no
  land at all — see the source section — so the value is legal and the row is junk. The
  one-line check, which the `cat > 5` one above cannot see: for any leap day,
  `SELECT countIf(cat = 5) FROM mhw_daily WHERE date = '2024-02-29'` must be in the
  thousands, not the millions. `CRW.cli repair-mhw-land` is the fix, and it needs the
  date's CoralTemp file — `read_mhw_raw` raises rather than guessing without it.
- **A missing `mhw_daily` row is not a zero, it is an unknown.** The table is sparse by
  design, and the LEFT JOIN that restores its zeros cannot tell heatwave-free ocean from a
  date that was never ingested. Anything new that reads it must either go through that join
  *and* respect `/coverage`'s `mhw.complete`, or be honest that it is reporting zeros it
  cannot vouch for.
- **A corrupt climatology file fails the *daily* ingest, and the traceback blames the daily
  file.** `ingest.read_day()` reads the climatology to compute `has_clim`, so one unreadable
  clim file takes out that MMDD **in every year at once** while the daily files are fine.
  Found in practice: `day1106` had silently bit-rotted on disk months after `init` loaded
  it, and every 1988–2011 Nov 6 failed with `NetCDF: HDF error`. The signature to recognise
  is *one MMDD missing across many years*; `CRW.cli verify-clim` is the check, and
  re-downloading that one file plus `backfill --product sst` is the whole fix.
  - Only the older half failed because the backfill ran newest-first and the rot appeared
    partway through — so the boundary year says when, not what.
  - **The file gives nothing away**: it opened, listed all its variables, and had a byte
    count identical to the re-downloaded copy. Only a full read of `analysed_sst` raised.
    That is why `verify_files()` reads the whole array and `missing_files()` is not a
    substitute — the file was present the entire time.
  - **ClickHouse was unaffected** (`sst_clim` still had all 366 keys, loaded before the
    rot), and so was the imagery, which had been rendered before it. Only the ingest of
    dates processed after the rot was lost.
- **Never truncate `sst_daily` without `ingest_status`.** Emptying one and not the other
  makes every day look already-ingested, and `ingest_files` then issues an
  `ALTER … DELETE` mutation per day against rows that do not exist — on a full archive that
  is ~15 k synchronous no-op mutations and dwarfs the inserts they precede. `backfill
  --fresh` does both together for exactly this reason.
- **An ECharts `piecewise` visualMap whose pieces are exact `value`s draws the line
  invisible.** ECharts turns the pieces into a y-axis gradient, and a `{ value: 1 }` piece
  becomes a *zero-width* band with `stop-opacity: 0` on both sides — so every value that is
  not exactly a class gets no ink at all. `mhw`'s chart shipped that way: the pane looked
  empty while still answering clicks (the ZRender handler is on the canvas, not the line),
  and in region scope nothing could ever show, since an area mean of classes never lands on
  an integer. The pieces are half-open bands (`gte`/`lt`) now, which also matches the map's
  `step` ramp. A region's series is not a category in two more places: it is printed
  rounded rather than named, and its y-axis is not pinned to 0..5 — an archive that never
  leaves 0..1.5 drawn against five classes is a flat line on the axis floor.

- **The anomaly's baseline is not the heatwave category's**, and nothing computes
  with either string — so anything that prints one must read
  `domain.yml`'s per-variable `baseline` block (through `/domain`, or
  `store.baselineFor`) rather than writing out `1991-2020`. `anom` departs from a
  1991-2020 daily mean computed here; `mhw` exceeds NOAA's 1985-2012 90th
  percentile over an 11-day window, applied before ingest and not re-derivable
  from anything in this database. Printing one beside the other's number is a
  plausible-looking sentence rather than an error.
- **A region's `mhw` is a percentage, a point's is a category, and the response says
  which.** Read `quantity` (`mhw_extent` or null), never `scope`. Two code paths serve it
  and **both** must apply `_MHW_EXTENT_SCALE` — the series (`_region_daily_rows`) and the
  ranking (`_region_ranking_source`); scaling only one leaves the ranking in hundredths
  beside a chart drawn in percent, which is a plausible-looking number rather than an error.
- **Anything a Vue component renders under SSR must pin its locale.** `toLocaleDateString`
  or `toLocaleString` with `undefined` formats against Node's container locale on the
  server and the visitor's in the browser: a silent hydration mismatch, visible only as a
  console warning. Pin `'en-GB'`, as `utils/periods.ts` does.
- **A polygon region is only the zone once `region_cells` is current.** Change the
  geometry and the mask, `region_daily` and `region_clim` are all stale, in that order and
  silently: the rollup keeps serving the cells the *old* ring covered, which is a real
  area mean of the wrong water. `CRW.cli mask` rewrites the mask alone (seconds, and it
  prints the cell count against the bounding box, which is the number that says whether
  the new ring is plausible); `rollup --clim --region <key> --fresh` is what actually
  rebuilds the numbers. `build_region_cells` **deletes before inserting** for the same
  reason — replacing collapses rows that are still there, so a ring that *shrank* would
  leave the cells it no longer covers behind.
- **Adding a region to `domain.yml` after `init` leaves it with no `region_clim`**, so its
  `anom` series comes back empty with nothing to say why. `CRW.cli rollup --clim` rebuilds
  that side out of `sst_clim` in seconds — it does not touch the 366 NetCDF files, which is
  what makes it cheap enough to redo on demand.
- **Nuxt UI's own icons default to the `lucide` collection**, and only `@iconify-json/mdi`
  is installed. A component reaching for one of its internal icons (`UModal`'s close button
  is the first that does) logs `Collection lucide is not found locally` and renders nothing.
  `app/app.config.ts` remaps them; add an entry there rather than installing lucide.
- **Nuxt UI v4 renamed `UButtonGroup` to `UFieldGroup`**, and the old name resolves to an
  empty comment node instead of erroring — the control simply vanishes from the DOM.
- **A prefetched image must set `crossOrigin = 'anonymous'`.** Mapbox fetches an image
  source in CORS mode, while a bare `new Image()` sends no `Origin` — and the API's
  `CORSMiddleware` only answers with `Access-Control-Allow-Origin` when it sees one. Warming
  the cache without it parks a header-less response that Mapbox's own fetch then reuses and
  the browser blocks, so every prefetched frame fails and the map freezes on one image.
- **The API's ClickHouse client is per-*thread*, not per-process**
  (`modules/clickhouse_helpers.py`). Every endpoint is a sync `def`, so FastAPI runs it in
  the thread pool, and a client's session refuses a second concurrent query with
  `ProgrammingError: Attempt to execute concurrent queries within the same session`. A
  shared singleton fails ~7 of 8 overlapping requests. Symptom to recognise: intermittent
  500s under no real load, and a **map that silently keeps showing the previous frame** —
  Mapbox's `ImageSource` never retries a failed image and logs the error only to the
  browser console.
- **`CRW.cli render` runs its pool under `multiprocessing`'s `spawn` context.** Workers
  each open their own NetCDF handles and HDF5 is not fork-safe once a file has been
  touched in the parent.
- **Editing a PostHog key does not affect a running container**, the same way every other
  env var here does not: they are baked in at container creation. Use
  `up -d --force-recreate front api`, not `restart`. The frontend key additionally has to
  survive a rebuild — `posthog-js` is a dependency, so a changed `package.json` needs
  `up -d -V` (renew the anonymous `node_modules` volume) or the container keeps the old
  install.
- **`_is_routable_public_ip` is false for the documentation ranges too** (192.0.2.0/24,
  198.51.100.0/24, 203.0.113.0/24) — Python's `ipaddress` counts them as private. Real
  public IPv4 and IPv6 pass; a test with `203.0.113.7` looks like geoip is broken when it
  is not.
- **Lossless WebP rewrites the RGB of fully transparent pixels.** Without `exact=True`,
  libwebp may replace the value channels under alpha 0, so `_bleed()`'s coastline fill does
  not fully survive encoding. Measured on a cached 1996 frame: 1,784 of 23,279 coastal land
  texels decode as code 0. `raster-resampling: nearest` keeps it off screen, and passing
  `exact=True` would only fix frames rendered from now on.
- **`TimeseriesChart`'s resize observer must watch the template ref.** The plot sits in
  `<ClientOnly>`, so `container` is null at `onMounted`. For its whole life before v2.0 the
  chart never followed its container, and it only showed once the time bar started wrapping
  and the canvas spilled over the note below.
- **Every NetCDF read in a process takes `shared/fields.py`'s `_NC_LOCK`, and a new reader
  must too.** netCDF4-python releases the GIL around HDF5 calls, and the HDF5 it links isn't
  thread-safe. Two FastAPI pool threads inside HDF5 at once **deadlock the whole API**: 0%
  CPU, `/health` included, no log line, because a request is only logged when it completes.
  Found when swipe compare asked for two uncached land frames at the same instant (back when
  the API rendered on demand, which it no longer does — `process`'s threads are the exposure now);
  reproduced with three concurrent `/image` requests, and fixed by the lock (six concurrent
  renders plus an ocean one, all 200, `/health` in 25 ms during). The ocean path always had
  the exposure and rarely hit it, because its frames are cached. `test_land.py` fails if a
  `netCDF4.Dataset(` appears outside `_open`.
- **`/image` serves the cache and nothing else** (`api/modules/render.py`). It used to render
  a bucket on demand when its NetCDF was still on disk, which cost ~1–9 s of an API thread
  per miss (playback's prefetch could saturate the pool) and hid a missing frame for exactly
  as long as a source file happened to exist. Now a frame `process` hasn't written is a fast
  404. Symptom of an unrendered range: the map keeps showing the previous frame (Mapbox's
  image source keeps it on a 404). Fix is `CRW.cli render` or `CPC.cli render`.
