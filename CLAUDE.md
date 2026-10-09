# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
It is the short version: **the full design notes live in [`docs/`](docs/)**, one file per area
(index below). Read the relevant one before changing that area — most decisions there were
measured, and most of the traps fail silently.

The app is the **Ocean Surface Temperature Atlas (OSTA)**: full name on first mention, OSTA
thereafter. The repo, compose project, database and `enso.*` storage keys keep the old name;
the `process` image, its package and everything registered with Prefect use `osta`.

**Public URL: <https://osta.cioospacific.ca>** (API: `https://mhw-api.cioospacific.ca`). Prod
runs the same global v2.1 as dev. Deep links into the app use this host.

Modelled on the `ocean-acidification-dashboard` project next door — same four-service
compose shape (`front` / `api` / `db-ch` / `process`), same ClickHouse-as-sole-database
approach, same conventions for env files and Dockerfiles.

**This project used to run on NOAA OISST v2.1 (0.25°).** It does not any more. Anything
describing a 0.25° grid, an `sst_anom` table, a `by_date` projection, or a
`_preliminary`/final download lifecycle is from that era (preserved on `wip/oisst-global`,
not intended to merge).

## Where the details are

| file | covers |
|---|---|
| [docs/operations.md](docs/operations.md) | compose dev/prod, prod's divergences, the `maintenance` profile, both CLIs in full, rollup/render ordering |
| [docs/ocean-data.md](docs/ocean-data.md) | CoralTemp and MHW sources, the 2024-07-01 re-encoding and leap-day bug, the two baselines, orientation rules, the domain, the no-climatology third state |
| [docs/land.md](docs/land.md) | NOAA CPC land archive: year files, tables, climatology, coastline cut, land canvas, frontend overlay, `/landTimeseries` |
| [docs/regions.md](docs/regions.md) | every named region, polygon provenance, disputed boundaries, wrapping longitudes, `shared/mask.py` |
| [docs/database.md](docs/database.md) | `shared/` modules, every ClickHouse table, partitioning, how `anom` is derived |
| [docs/pipeline.md](docs/pipeline.md) | `process/`: download, ingest, `run`, retention window, `repartition`, Prefect |
| [docs/api.md](docs/api.md) | endpoints, how `mhw` is bucketed per query shape, `/state`, rankings |
| [docs/imagery.md](docs/imagery.md) | value-encoded WebP frames, `raster-color`, categorical `mhw` |
| [docs/frontend.md](docs/frontend.md) | components, store getters, URL state, compare modes, phone layout, CSV, colour range, map |
| [docs/analytics.md](docs/analytics.md) | PostHog: what is and is deliberately not instrumented |
| [docs/testing.md](docs/testing.md) | CI, `CRW.cli check`, driving the app in headless Chromium |
| [docs/gotchas.md](docs/gotchas.md) | every gotcha in full (one-liners below) |
| [docs/verification.md](docs/verification.md) | what has been verified, with numbers — history, not instructions |

Ideas deliberately deferred, with costs: [ROADMAP.md](ROADMAP.md) — read it before proposing a feature.

## Services & Ports

Host ports come from `docker-compose.dev.yml`'s `${VAR:-default}` fallbacks, overridden by
`.env.dev`:

| Service | Description | Port |
|---|---|---|
| `front` | Nuxt 4 frontend | 9020 |
| `api` | FastAPI backend | 9021 |
| `db-ch` | ClickHouse | 9023 (HTTP), 9024 (native) |
| `process` | NetCDF → ClickHouse ingest + image rendering (the CLI) | — |
| `prefect` | Prefect server (**dev only**; prod uses `pipelines.cioospacific.ca`) | 9025 |
| `scheduler` | the `process` image serving `flows.py` (ocean and land runs) to Prefect | — |

Offset from the ocean-acidification-dashboard's 9010–9014 so both stacks can run at once.

## Common commands

```bash
# dev — --env-file is REQUIRED, or compose falls back to ports 3000/4000
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d

# prod — see docs/operations.md for the seven divergences before deploying
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# the pipeline (process idles on sleep infinity)
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CRW.cli <command>

# ClickHouse
docker compose -f docker-compose.dev.yml --env-file .env.dev exec db-ch \
  clickhouse-client --database enso --query "SHOW TABLES"

# frontend outside Docker
cd front && npm install && npm run dev
```

**Ocean CLI** (`python -m CRW.cli`): `init`, `verify-clim`, `scan`, `backfill`, `render`,
`mask`, `rollup`, `run`, `status`, `check`, `repair-mhw-land`, `recent`, `repartition`.
**Land CLI** (`python -m CPC.cli`): `init`, `fetch`, `backfill`, `run`, `clim`, `render`,
`prune`, `ocean-mask`, `scan`, `status`. Flags and order of operations: docs/operations.md.

## Architecture in brief

- **Data, all NOAA.** CoralTemp v3.1 SST (0.05°, global, daily, 1985→), CRW Marine Heatwave
  category (same grid, separate product, lands ~90 min after SST), a 1991–2020 SST
  climatology (366 files, kept forever), and CPC Global Unified land tmax/tmin/precip
  (0.5°, **one file per year**). The anomaly is derived here; nothing ships one.
- **`shared/`** is the contract between `api` and `process` — one definition each of the
  grid (`domain.py` + `domain.yml`), NetCDF reading and orientation (`fields.py`), bucket
  reduction (`buckets.py`), periods (`periods.py`), rendering (`render.py`), region masks
  (`mask.py`) and the schema (`ch.py`). Don't create a second copy of any of them in `api/`
  or `front/`.
- **ClickHouse** holds `sst_daily` (~114 B rows), sparse `mhw_daily` (cat ≥ 1 only),
  `sst_clim`, the land tables, `region_cells`/`region_daily`/`region_clim` rollups, the
  `*_recent` date-ordered twins, and per-archive status tables. All archive tables are
  `ORDER BY (gy, gx, date)`, no projections.
- **`process/`** — `CRW/` (ocean) and `CPC/` (land) packages; `flows.py` is the only Prefect
  importer. Images are rendered from NetCDF while it is still on disk; the cache is the
  durable artifact.
- **`api/`** serves timeseries live from ClickHouse and imagery **only from the cache**.
- **`front/`** — Nuxt 4 (`app/` is srcDir) + Nuxt UI v4 + Pinia + MapboxGL + ECharts, dark
  mode. Map frames carry **values, not colour**; the browser applies the ramp.

## Rules that fail silently

Each line is expanded in the doc it links to. These are the ones worth knowing before
touching anything.

**Data and orientation** ([ocean-data](docs/ocean-data.md), [land](docs/land.md))
- Longitude is 0–360 via a half-grid roll; daily files are south-up, CoralTemp climatology is
  north-up and must be flipped. CPC land is already 0–360 (**don't** roll) and north-up
  (**do** flip). All of it lives in `shared/fields.py` only.
- MHW category must be bounded `1 <= raw <= 5`: since 2024-07-01 land/ice is 251. Every
  29 February ships land as Cat 5; `read_mhw_raw` repairs it from CoralTemp's land mask.
- `anom` (1991–2020 mean) and `mhw` (1985–2012 P90, NOAA's) use different baselines. Never
  write a baseline string; read `domain.yml`'s `baseline` block.

**Database** ([database](docs/database.md), [pipeline](docs/pipeline.md))
- A missing `mhw_daily` row is an unknown, not a zero: read it via LEFT JOIN against
  `sst_daily` and respect `/coverage`'s `mhw.complete`.
- Region anomaly relies on `mean(sst − clim) == mean(sst) − mean(clim)`, which needs
  `has_clim = 1` on the daily side and the polygon mask on **both** sides.
- Roll up only once `mhw_daily` is complete. Never truncate `sst_daily` without
  `ingest_status`.
- Editing DDL in `shared/ch.py` changes nothing on an existing DB (`CREATE IF NOT EXISTS`);
  `CRW.cli repartition` is the migration — site down, `scheduler` stopped, run detached.
- Changing a polygon region needs `CRW.cli mask` then `rollup --clim --region <key> --fresh`.
  A new region after `init` needs `rollup --clim`. Region SQL must use `region.gx_sql()`;
  regions can wrap the prime meridian.

**Imagery and rendering** ([imagery](docs/imagery.md), [operations](docs/operations.md))
- `render` reads NetCDF, not ClickHouse: render (including `--variable mhw`) **before**
  anything prunes, or pass `--keep-nc`. A `run` without it deletes the MHW archive back to
  the open week.
- `/image` never renders; a missing frame is a 404 and the map silently keeps the previous
  frame. Fix with `CRW.cli render` / `CPC.cli render`.
- Image width is keyed: `DEFAULT_WIDTH` 2048 must match `useApi.ts`'s `IMAGE_WIDTH`.
- Frames are lossless WebP with `raster-resampling: nearest`; values clamp, never wrap.
  `mhw` is categorical: nearest resample, `step` ramp, no user range.
- Every NetCDF read takes `shared/fields.py`'s `_NC_LOCK` (HDF5 deadlocks otherwise);
  `render`'s pool uses `spawn`.

**API and frontend** ([api](docs/api.md), [frontend](docs/frontend.md))
- `shared/periods.py` and `front/app/utils/periods.ts` must change together (a shared JSON
  test enforces it). Weeks start Monday; buckets are labelled by first day.
- A region's `mhw` is extent in %, a point's is a category: read `quantity`, never `scope`;
  both series and ranking paths apply `_MHW_EXTENT_SCALE`.
- `store.selectedDate` is always a bucket start — go through `setDate()`/`setPeriod()`.
  `series*` and `active*` getters are deliberately separate (chart vs map).
- The API's ClickHouse client is per-thread. SSR reaches the API at `http://api:4000`, the
  browser at the published URL.
- Pin `'en-GB'` for any locale formatting rendered under SSR. Prefetched images need
  `crossOrigin = 'anonymous'`. Resize observers watch the template ref (`<ClientOnly>`).
- Nuxt UI: icons are mdi (remap in `app.config.ts`); `UButtonGroup` is now `UFieldGroup`.

**Containers and Prefect** ([gotchas](docs/gotchas.md), [pipeline](docs/pipeline.md))
- Env vars and PostHog keys are baked in at creation: `up -d --force-recreate`, not
  `restart`. `domain.yml` edits need an API restart.
- `process` and `scheduler` must keep sharing one `image:` name, or `process` stops being
  rebuilt.
- UI pause doesn't survive a restart — `stop scheduler` to hold the pipeline.
  `PREFECT_AUTH_STRING` must never be blank. `flows.py` can't use
  `from __future__ import annotations`.
- `CH_IMAGE_TAG` must be ≥ the version that wrote the data dir; a downgrade comes up
  "healthy" with no tables.

## Tests

CI runs pytest (`uv run --project process pytest tests`) and, in `front/`, lint + vitest +
`nuxt build`. `vue-tsc` is not gated. Host `front/node_modules` is a root-owned Docker mount:
copy `front/` to a scratch dir to run tooling. Browser checks: headless Chromium recipe in
[docs/testing.md](docs/testing.md) — screenshot the map, never read its canvas back.
