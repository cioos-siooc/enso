# Tests, CI and browser verification

CI, `CRW.cli check`, and how to drive the app in headless Chromium.

## Tests and CI

`.github/workflows/ci.yml` runs two jobs on push and PR: **pytest** over `shared/` and
`CRW.checks` (`uv run --project process pytest tests`), and, in `front/`, **lint, vitest and
`nuxt build`**. Type checking is not gated: `vue-tsc` reports ~100 errors on the existing
code (mostly `mapbox-gl` having no bundled types, and Pinia getters losing inference in
`main.ts`).

- **`shared/testdata/periods_cases.json` is asserted by both** `tests/test_periods.py` and
  `front/tests/periods.test.ts`. That turns "change one and change the other" into a failing
  test; editing only the TypeScript week rule fails 20 cases.
- **The Python tests use synthetic arrays, never NetCDF.** The orientation and leap-day
  tests build 3600×7200 grids in memory and monkeypatch `_read_raw`.
- **CI installs with `npm install --legacy-peer-deps`, not `npm ci`**, the same as
  `front/Dockerfile`. The committed lock had drifted out of sync with `package.json` and
  was regenerated that way.
- **Running front tooling on the host:** `front/node_modules` on the host is an empty,
  root-owned mount point left by Docker, so `npm install` there fails with EACCES. Copy
  `front/` (without `node_modules`) to a scratch directory and install there.

## `CRW.cli check`

One line per invariant, exit 1 if any fails. Each one is a failure this project has already
had, and none of them was reported at the time. It checks: freshness per archive, 366
climatology keys, **`mhw_status` saying "ingested" while `mhw_daily` is empty** (a
repartition in flight, which `/coverage` cannot see), category range and leap-day land over
the last `--days` (default 45), every region rolled up through the last ingested date, and
any region whose heatwave extent is zero on every day.

**`--full` read 0 rows on dev.** ClickHouse 26.5 answered the whole-archive category count
over 17.6 B rows from per-part metadata in 6 ms. Not verified on prod.

## Browser verification

**Browser verification works here.** Headless Chromium renders the Mapbox canvas fine under
ANGLE/SwiftShader; launch it with
`args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']`. Note the
host's default node is 18 and Playwright needs 20+, so run it under
`$HOME/.nvm/versions/node/v22.23.1/bin`. Playwright is not a dependency of this repo —
`npm i playwright --no-save` into a scratch dir, and since a fresh install will not match
the browsers already in `~/.cache/ms-playwright`, pass `executablePath` at that cache's
`chromium-<build>/chrome-linux64/chrome` rather than downloading another one.

**Do not read the map back off its own canvas.** Mapbox runs with
`preserveDrawingBuffer: false`, so `drawImage(mapCanvas)` yields a blank frame and a
colour-count assertion on it fails even when the map is drawn correctly. Take a Playwright
screenshot and look at that instead.

Chart maths can be rendered head-lessly with echarts' SSR mode and asserted on, which is
much cheaper than driving a browser. That check does **not** catch mount-order bugs — the
ranking grid first shipped blank because its canvas sits inside `<ClientOnly>`, so
`container.value` was still null at `onMounted` and nothing ever observed it. Watch the
template ref, not the mount.
