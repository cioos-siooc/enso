# Ocean Heat Atlas

Daily sea-surface temperature, anomaly and marine-heatwave category for the **global ocean**,
from **NOAA Coral Reef Watch**, with land temperature and precipitation from **NOAA CPC**
drawn over it. Everything is ingested into ClickHouse and served as an interactive map plus
point and region timeseries.

**0.05° resolution, 1985-01-01 onward**, one CoralTemp v3.1 NetCDF per day. The whole
7200×3600 grid is ingested: **17.2 million ocean cells per day**. All four Niño boxes, the
Blob, the PDO domain and the Bering Sea are named regions; the header ribbon still reports
the Pacific basin (60°S–65°N, 100°E–290°E), which is itself a region.

**Anomaly is derived, not shipped.** CoralTemp provides SST only; the anomaly is computed
against a separate 366-file **1991–2020 daily climatology** (`data/climatology/`), one per
day of year including 29 February. About 77% of the global ocean has a climatology on a
given day; the rest is the seasonal ice fringe, drawn grey rather than as a zero anomaly.

**Marine heatwave category is a second daily product**, NOAA CRW MHW v1.0.1, on the same
grid and days. Both publish at roughly one day's latency, MHW landing about 90 minutes after
CoralTemp. It is an ordinal class from 1 (Moderate) to 5 (Beyond Extreme), drawn in NOAA's
own palette, measured against NOAA's 1985–2012 90th percentile; only category ≥ 1 is stored.

**The land overlay is NOAA CPC Global Unified** (0.5°, one NetCDF per *year*): daily tmax,
tmin and precipitation, their anomalies against a 1991–2020 climatology built here, and
precipitation as a percentage of normal. It is drawn over whichever ocean layer is showing,
cut exactly to CoralTemp's coastline, and a click on land charts the land cell.

## Services

| Service | Description | Port |
|---|---|---|
| `front` | Nuxt 4 + Nuxt UI + MapboxGL + ECharts | http://localhost:9020 |
| `api` | FastAPI | http://localhost:9021 |
| `db-ch` | ClickHouse | 9023 (HTTP), 9024 (native) |
| `process` | download → ingest → render pipeline (`CRW.cli`, `CPC.cli`) | on demand |
| `prefect` | Prefect server: schedule and run history (dev only, `prefect` profile) | http://localhost:9025 |
| `scheduler` | serves the daily ocean `run` to Prefect | — |

## Quick start

```bash
cp .env.example .env.dev          # then fill in NUXT_PUBLIC_MAPBOX_TOKEN and UID/GID
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d

# ocean: schema, the 366-file climatology and the per-region climatology means (~20 min)
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CRW.cli init

# ingest the daily archives already on disk (newest first), then the region rollup
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CRW.cli backfill --reverse
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CRW.cli rollup --fresh

# render the ocean image cache; must run while the NetCDF is still on disk
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm --no-deps process \
  python -m CRW.cli render --workers 16

# land: tables, year files, ingest, climatology, frames
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process python -m CPC.cli init
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process python -m CPC.cli fetch
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process python -m CPC.cli backfill
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm --no-deps process python -m CPC.cli clim
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm --no-deps process \
  python -m CPC.cli render --workers 16
```

Then open http://localhost:9020.

> `--env-file .env.dev` is required on every compose command; without it the ports fall
> back to their in-file defaults.

Long jobs (`backfill`, `render`) are best run detached: `run -d --name <job> ...`, then
`docker logs -f <job>`. `render` skips every frame already cached, so an interrupted render
resumes where it stopped.

### Where the archives live

`./data` is mounted at `/opt/data`. The daily archives are large (~153 GB SST, ~10 GB MHW,
~9 GB land year files) and can live on another disk by setting host paths in `.env.dev`:

```bash
SST_NC_HOST=/mnt/archive/enso-nc/sst
MHW_NC_HOST=/mnt/archive/enso-nc/MHW
LAND_NC_HOST=/mnt/archive/enso-nc/land
```

Unset, they stay under `./data`. The two climatologies (`data/climatology/` and
`data/land/climatology/`) and the image cache (`data/images/`) always stay under `./data`,
because `api` reads them from there.

### Daily updates

The ocean side is scheduled by **Prefect**. In dev, start the local server and the
scheduler:

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev \
  --profile prefect up -d prefect scheduler
```

The UI is at http://localhost:9025 (`PREFECT_AUTH_STRING`, default `admin:admin`): flow
`enso-daily-run`, deployment `daily`, one task per date. It fires at `RUN_CRON` (default
16:30 UTC, after both products have published). **Dev opens paused and with `keep_nc` on**
(`RUN_SCHEDULE_PAUSED`, `RUN_KEEP_NC`), because a run that prunes deletes the local archive
back to the open week. Unpausing in the UI does not survive a container restart; to hold the
pipeline, `stop scheduler`. An ad-hoc run is *Run → Custom run* on the deployment.

Production registers with the shared Prefect server at `https://pipelines.cioospacific.ca`
instead (`PREFECT_API_URL`, `PREFECT_AUTH_STRING` in `.env.prod`); `scheduler` starts with a
plain `up -d`.

The same job by hand, without Prefect:

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CRW.cli run [--keep-nc]
```

It downloads, ingests and renders every day from the last ingested through yesterday,
re-checks the recent tail for files CoralTemp has revised in place, and appends to the
region rollup. A date that is not published yet is a no-op, not a failure.

**The land overlay is not scheduled.** Update it by hand:

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CPC.cli run --keep-nc
```

It re-downloads the current year's files (CPC rewrites them in place), ingests the new days
and re-renders every bucket its recheck window touches. **Without `--keep-nc` it deletes the
year files it has finished with**, so pass it if you keep the land archive.

### Production

```bash
cp .env.prod.example .env.prod   # set DATA_DIR, CH_DATA_DIR, CH_LOG_DIR, passwords, Prefect
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  run --rm process python -m CRW.cli <command>
```

Create `DATA_DIR`, `CH_DATA_DIR` and `CH_LOG_DIR` and `chown` them to `UID:GID` before the
first `up`; Docker would create them as root. `db-ch` publishes no ports and requires
`CLICKHOUSE_PASSWORD`. `CH_IMAGE_TAG` must be at least the ClickHouse version that wrote
`CH_DATA_DIR`, because there is no downgrade path. `docker-compose.prod.yml`'s header lists
every difference from dev.

**Planned outages use the `maintenance` profile**: a stock nginx that takes over `front`'s
and `api`'s ports and answers **503**, never 200:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod stop front api scheduler
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile maintenance up -d maintenance
# ... the work ...
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile maintenance down maintenance
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### Partitioning

`sst_daily` and `mhw_daily` partition **by decade, and by year from 2026 on**
(`shared.ch.PARTITION_BOUNDARY_YEAR`), not by year throughout. `ORDER BY (gy, gx, date)`
makes one cell's whole history a contiguous key range, and every partition cuts that range
into another piece. The cost is **file opens**, ~4 per selected part: ~50 µs each on NVMe,
~4.3 ms on a spinning disk. Measured on the production HDD, one cold cell over the full
archive went from 196 parts and **3.4 s** (by year) to 8 parts and **0.14 s**. On dev, a
point `anom` query now selects 7 parts and makes 34 file opens.

Only the year still being revised needs its own partition, since replacing a revised date
rewrites every part it touches. Bump `PARTITION_BOUNDARY_YEAR` each January or so; nothing
breaks meanwhile, a point query just reads one more part per elapsed year.

**Editing the DDL does not change an existing database** (`ensure_schema()` is
`CREATE TABLE IF NOT EXISTS`). `CRW.cli repartition` migrates a table in place, one
partition at a time, dropping each source partition once its rows are confirmed landed, so
it never needs room for a second copy. Take the site down with the `maintenance` profile
first, run it detached, and expect it to be forward-only. Start with the free, read-only
plan:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  run --rm process python -m CRW.cli repartition --dry-run
```

Full runbook in [CLAUDE.md](CLAUDE.md).

### Scale

Measured on dev, archive through 2026-09-27:

| | |
|---|---|
| ocean cells/day | 17,193,140 |
| `sst_daily` | 262.1 B rows, 264 GiB |
| `mhw_daily` | 30.9 B rows, 11.2 GiB (only category ≥ 1 is stored) |
| `sst_clim` | 4.79 B rows, 4.3 GiB |
| `land_temp_daily` / `land_precip_daily` | 1.00 B / 1.41 B rows, 3.1 GiB / 0.6 GiB |
| NetCDF | 153 GB SST + 9.7 GB MHW (15,245 days), 9.1 GB land year files, 2.2 GB + 0.27 GB climatologies |
| ocean images | ~54k WebPs (3 variables × 3 periods), width 4096; a daily SST frame is ~1.4 MB |
| land images | 94,980 WebPs (7 layers), 16.7 GB |

## Map imagery

There is no tile pyramid. Each bucket is **one Web-Mercator WebP** covering
−180…180° × ±85.05°, **4096 px wide**, served by `/image` from a pre-rendered cache
(`data/images/{variable}/{period}/YYYY/{bucket-start}_w4096.webp`). The API never renders;
an uncached frame is a 404.

**The images carry data, not colour.** The value is packed into the RGB channels
(SST at 0.1 °C in two bytes, anomaly at 0.1 °C in one, MHW category in one) with land in
alpha, and the browser applies the colour ramp. So palettes and display ranges are
client-side settings, and changing one needs no re-render. Lossless WebP is required: lossy
compression corrupts packed values. **Changing the grid, the width or an encoding
invalidates the whole cache**, and re-rendering needs the NetCDF back on disk.

## Layout

```
api/                 FastAPI service: queries ClickHouse, serves the image cache
front/               Nuxt 4 frontend (everything under front/app/)
process/CRW/         Coral Reef Watch pipeline (CRW.cli): ocean download / ingest / render
process/CPC/         CPC land pipeline (CPC.cli): year files, ingest, climatology, render
shared/              grid geometry, NetCDF reading, rendering, schema; mounted into api and process
clickhouse/          local ClickHouse volumes and user config
deploy/maintenance/  the 503 page and nginx conf served during any planned outage
data/sst/            daily CoralTemp NetCDF (untracked; or SST_NC_HOST)
data/MHW/            daily marine-heatwave NetCDF (untracked; or MHW_NC_HOST)
data/land/           CPC year files (untracked; or LAND_NC_HOST)
data/climatology/    the 366-file 1991-2020 ocean climatology, kept forever
data/land/climatology/  the land climatology built by CPC.cli clim
data/images/         the rendered image cache
```

## API

```bash
curl localhost:9021/health
curl localhost:9021/coverage
curl localhost:9021/domain
curl localhost:9021/state

# variable is sst (default), anom or mhw; period is daily / weekly / monthly
curl -X POST localhost:9021/timeseries \
  -H 'content-type: application/json' \
  -d '{"lat": 0.0, "lon": 200.0, "variable": "anom", "period": "monthly"}'

# a land cell, for one of the overlay's layers
curl -X POST localhost:9021/landTimeseries \
  -H 'content-type: application/json' \
  -d '{"lat": -6.2, "lon": 106.8, "variable": "land_precip_ratio", "period": "monthly"}'

curl "localhost:9021/region/nino34?variable=anom&period=monthly"

curl -o day.webp "localhost:9021/image/2026-08-24.webp?variable=anom&period=weekly"
```

`mhw` buckets differently from the other two, and deliberately: a point and the map take
the **max** category over a week or month (a category's mean is not a category), a region
reports the **share of its ocean area** in a heatwave, and `/monthlyRanking` ranks a month
by its mean daily category.

Full endpoint notes, schema rationale and gotchas: [CLAUDE.md](CLAUDE.md). Ideas not yet built,
with what each would cost: [ROADMAP.md](ROADMAP.md).

> Two conventions in this codebase are load-bearing and fail silently if broken: the
> longitude roll onto a 0–360 grid, and the north-up→south-up flip of the climatology
> files. Both live in `shared/fields.py`, along with the land files' opposite conventions.
> See CLAUDE.md before touching either.
