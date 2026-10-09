# Operations: compose, prod and the CLIs

Starting the stacks, how prod differs from dev, and the pipeline commands in full.

## Common Commands

**Start dev environment:**
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
```
Without `--env-file .env.dev`, compose falls back to the in-file defaults (front 3000,
api 4000) and can recreate dependent services on the wrong ports.

**Start prod environment:**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
`docker-compose.prod.yml` carries its own header comment explaining every divergence from
the dev file; `.env.prod.example` is the template. The seven that matter:

- **`name: enso-prod`.** Both compose files would otherwise take the project name `enso`
  from the directory and clobber each other's containers, network and volumes.
- **No source bind mounts, and `./shared` is mounted nowhere.** The images carry `api/`,
  `process/` and `shared/` as built, so a deploy is `--build`. Mounting `shared` would let
  the host tree diverge from the code the image was tested with, which is the one thing the
  "single definition" design of that directory exists to prevent.
- **`DATA_DIR` / `CH_DATA_DIR` / `CH_LOG_DIR` replace `./data` and `./clickhouse`.** The
  archive is ~163 GB and ClickHouse another ~100 GB; neither belongs in the checkout.
  **Create them and `chown` them to `UID:GID` before the first `up`** — Docker creates a
  missing bind source as *root*, and that surfaces as an empty archive rather than as a
  permission error. `api` gets `/opt/data` **read-only**, since only `process` writes the
  image cache.
- **`db-ch` publishes no host ports and requires `CLICKHOUSE_PASSWORD`.** Verified: the
  password is enforced, `enso` is created, the healthcheck passes, and
  `/health` reports `clickhouse: ok` through it. Do **not** mount `./clickhouse/users.d`
  here — the image's entrypoint writes `users.d/default-user.xml` itself, so a `:ro` mount
  stops the container starting, and the file it generates already grants `default` the
  `::/0` networks that dev's `allow_docker_network.xml` is there for.
- **A `maintenance` service, behind its own profile**, which takes over `front`'s and
  `api`'s published ports while those two are stopped — `deploy/maintenance/`, an
  `nginx:alpine` and two files, no build. **It is general**: any planned outage uses it — a
  schema migration, a ClickHouse upgrade, restoring a backup, host maintenance — and it
  answers **503**, never 200, because a maintenance page served as 200 is cached by
  intermediaries, indexed by crawlers, and recorded by uptime monitors as a healthy site.
  The frontend's port gets a page; the API's port gets JSON in the same shape `SERVER.py`'s
  errors use (`detail` a sentence, `error.code` machine readable), so a client that parses
  one parses this.

  **The page names no cause and takes no parameters, deliberately.** Which internal job is
  running helps no visitor, and a page that must be edited before each use is one that gets
  used with the previous outage's text still on it. `CRW.cli repartition` is the case it was
  first needed for — see below for why that one cannot simply run against a live site.

  Two details, both verified by driving it: the API port answers an `OPTIONS` preflight
  **204 with the CORS headers**, because a tab left open on the dashboard sends
  `POST /timeseries` with a JSON content type and a preflight answered 503 surfaces as a
  CORS error, which says nothing about maintenance. And the volumes are **directories, not
  the two files** — a bind mount of a single file pins an inode and every editor
  writes-then-renames, so editing the page would leave the container serving the old one
  with nothing to say so.

  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod stop front api
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
    --profile maintenance up -d maintenance
  # ... the work ...
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
    --profile maintenance down maintenance
  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
  ```
- **`process` sits behind the `tools` profile**, so `up -d` does not start a container
  idling on `sleep infinity`. Drive it the same way as dev:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
    run --rm process python -m CRW.cli run
  ```
- **`scheduler` runs the daily `run` on a schedule, against a Prefect server that is not
  in this stack.** Prod registers with the shared server at `https://pipelines.cioospacific.ca`
  (the [cioos-pacific-pipeline](https://github.com/cioos-siooc/cioos-pacific-pipeline) stack,
  serving other projects' flows too), with its history in that UI — see "Prefect" under the
  process pipeline. `scheduler` starts with a plain `up -d`. Prod **requires** `PREFECT_API_URL`
  (`https://pipelines.cioospacific.ca/api`) and `PREFECT_AUTH_STRING` (that server's
  `user:password`).

`api` runs without `--reload` (it would watch source that is no longer mounted) on
`--workers ${API_WORKERS:-4}` — separate *processes*, so the per-thread ClickHouse client
gotcha below is unaffected by the count. `front` runs the built Nitro entry
(`node .output/server/index.mjs`) rather than `npm run start`, which is `nuxt preview`, a
dev wrapper that re-reads `.env` and needs the full nuxt devDependency tree at runtime.

**Pipeline CLI** (the `process` service idles on `sleep infinity` and is driven on demand):
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm process \
  python -m CRW.cli <command>

python -m CRW.cli init                                    # tables + climatology + region means
python -m CRW.cli verify-clim                             # full-read all 366 climatology files
python -m CRW.cli scan     [--limit N]                    # disk vs. already ingested, per archive
python -m CRW.cli backfill [--start|--end] [--product sst|mhw] [--reverse] [--fresh] [--delete-nc]
python -m CRW.cli render   [--start|--end] [--variable|--period] [--workers N] [--force]
python -m CRW.cli mask     [--region KEY]                  # region_cells, for polygon regions
python -m CRW.cli rollup   [--start|--end] [--region KEY] [--fresh] [--clim]  # region_daily
python -m CRW.cli run      [--date] [--keep-nc] [--recheck-days N]
python -m CRW.cli status                                  # per-status day/row counts, per archive
python -m CRW.cli check    [--days N] [--full] [--stale-after N]  # data invariants, exit 1 on failure
python -m CRW.cli repair-mhw-land [--date]                # re-do the leap days (see below)
python -m CRW.cli recent                                  # fill the date-ordered rollup tables (once)
python -m CRW.cli repartition [--table] [--dry-run] [--optimize] [--finish]  # one-off
```

**The land pipeline is a second CLI, `python -m CPC.cli`**, because NOAA CPC is a different
program from Coral Reef Watch and its files are one per **year**, not per date:
```bash
python -m CPC.cli init                                    # the two land tables
python -m CPC.cli fetch    [--year|--start-year|--end-year] [--variable] [--force]
python -m CPC.cli backfill [--year ...] [--product temp|precip] [--start|--end] [--fresh]
python -m CPC.cli run      [--recheck-days N] [--keep-nc] [--force] # HEAD check, then fetch + ingest + re-render + prune
python -m CPC.cli clim     [--source]                     # the 1991-2020 land climatology
python -m CPC.cli render   [--variable|--period|--start|--end] [--workers N] [--force]
python -m CPC.cli prune    [--year ...] [--product] [--dry-run]  # delete used year files
python -m CPC.cli ocean-mask --date YYYY-MM-DD            # rebuild the coastline land frames are cut to
python -m CPC.cli scan                                    # year files on disk, per variable
python -m CPC.cli status                                  # per-status day/row counts, per product
```
It has no `rollup`. Order on a fresh box: `fetch` → `backfill` → `clim` → `render` →
`prune`. `render` refuses while a year file is missing mid-range, since it would cache short
weeks and months that can't be told apart from good ones once the neighbours are pruned.
`run` re-renders every bucket its recheck window touches, open or closed, because a CPC
revision lands inside a year file, then prunes what it fetched.

**There are two daily archives and every command covers both by default.** CoralTemp SST
and the Marine Heatwave category are separate products with separate URLs, separate
directories, separate tables and separate status bookkeeping — `--product` narrows
`backfill` to one, and `--fresh` then truncates only that one's tables. `run` walks both
per date and treats each independently, because MHW is published about 90 minutes after
CoralTemp and a run landing between the two sees a date as SST-ingested and MHW-pending.

`init` is not just DDL — it loads all 366 climatology files (2.68 B rows, ~20 min) and
then builds `region_clim`. It is idempotent and resumable: an interrupted load skips the
MMDD keys already present.

**ClickHouse client:**
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec db-ch \
  clickhouse-client --database enso --query "SHOW TABLES"
```

**Build the region rollup** (after both archives are ingested, not during):
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm --no-deps process \
  python -m CRW.cli rollup --fresh
```
`backfill` deliberately does not maintain `region_daily` per date — one pass per region
over the whole range reduces the big tables once, where a per-date hook would re-run eight
aggregations 15,212 times. Same split as `render`. `run` is the exception and appends the
single date it just ingested. **Roll up only once `mhw_daily` is complete**: `mean_mhw`
divides a sparse numerator by an `sst_daily` denominator, so a partial MHW archive freezes
confident zeros into the rollup, where they are harder to spot than in the sparse table.

**Render the image cache in bulk:**
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev run --rm --no-deps process \
  python -m CRW.cli render --workers 12
```
**This reads NetCDF, not ClickHouse**, so it has a hard prerequisite: the daily archive
must still be on disk. Run it before `backfill --delete-nc` and before the daily retention
prune has eaten the range. Afterwards the source for those frames is gone.

**This now applies to `./data/MHW/` as well, and that is a live trap rather than a
theoretical one.** `imaging.prune()` walks both archives, so a single `CRW.cli run` without
`--keep-nc` deletes the whole MHW archive back to the open week — and if the MHW render
pass has not been done, every historical MHW frame becomes unrecoverable without
re-downloading 9.7 GB. **Order is: backfill MHW → `render --variable mhw` → only then let
`run` prune.** Until that render has finished, pass `--keep-nc`.

`render` and `run` are the same code path — both go through `shared.buckets.bucket_field()`,
so a change to how a week is reduced cannot apply to one and not the other. **The API no
longer renders at all** (see the `/image` gotcha); it used to, through a second copy of
this in `api/modules/render.py` that would have kept averaging the MHW category, which is
reduced by max. `run` renders
the date it just ingested; `render` walks history in a `spawn` pool. It touches neither
ClickHouse nor the network (hence `--no-deps`), so it is safe to run against a
half-finished backfill — though the two contend for the same `./data` mount, ingest being
disk-bound and rendering CPU-bound.

Only **closed** buckets are written: a week or month whose last day is past the end of
the archive is still filling, and caching it would freeze a mean over however many days
happen to be present. `run` rewrites those daily until they close.

**Frontend (outside Docker):**
```bash
cd front && npm install && npm run dev
```
