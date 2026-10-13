# Usage analytics (PostHog)

What is instrumented, what deliberately is not, and why.

## Usage analytics (PostHog)

**PostHog Cloud, not self-hosted, and the same shape as the ocean-acidification
dashboard** — `api/modules/posthog_helpers.py` is a port of that project's file. Cloud is
deliberate in both: the official self-hosted stack bundles its own ClickHouse, Kafka,
Redis, Zookeeper and MinIO, and this box already runs ~100 GB of ClickHouse for the
science data. A `usage_events` table in the database that is already here was the other
candidate and was rejected for what comes with it rather than what it costs — retention,
bot filtering and a query UI, i.e. building an analytics frontend instead of the dashboard.

**Both sides are a silent no-op without a key**, so leaving `POSTHOG_API_KEY` and
`NUXT_PUBLIC_POSTHOG_KEY` blank is a supported configuration and the dev default. Nothing
guards at the call sites.

- **API** (`api/modules/posthog_helpers.py`): `capture_event(http_request, event, props)`,
  configured by `POSTHOG_API_KEY` / `POSTHOG_HOST`. One long-lived client per worker
  process — `capture()` enqueues and a background thread batches over HTTP. Called from
  `/timeseries`, `/monthlyRanking`, `/regionTimeseries`, `/region/{key}` and
  `/region/{key}/monthlyRanking`.
- **Frontend** (`front/app/plugins/posthog.client.ts` + `app/composables/useAnalytics.ts`'s
  `trackEvent()`), configured by `NUXT_PUBLIC_POSTHOG_KEY` / `NUXT_PUBLIC_POSTHOG_HOST`.
  Both live under `app/` because that is Nuxt 4's srcDir — a top-level `front/plugins/` is
  not picked up at all, the same trap the composables note above describes.
  **Autocapture and session replay are off.** This is a full-bleed Mapbox UI: autocapture
  would log a stream of canvas clicks whose coordinates mean nothing, and replay would
  record a map that redraws every frame of playback. Custom events only.
- **Identity.** The plugin sets `axios.defaults.headers.common['X-PostHog-Distinct-Id']`
  once, and `useApi()` uses the module-level axios default rather than an `axios.create()`
  of its own, so every endpoint call carries it with no per-composable change. `SERVER.py`'s
  `_stamp_request_context` middleware reads it into `request.state.distinct_id`, which
  `capture_event` prefers over the IP. Non-browser callers (curl, the healthcheck) send no
  header and fall back to IP; `disable_geoip` stays IP-based either way.

**What is deliberately not instrumented, and why it is the load-bearing part:**

- **`/image`, server-side.** Playback prefetches `AHEAD = 8` frames per tick at up to
  10 fps, so instrumenting the image route would emit hundreds of events a minute from one
  person watching one animation — none of them a decision. `/health`, `/domain`,
  `/coverage` and `/variables` are out for the same reason: page-load plumbing.
- **`store.setDate()`.** The playhead writes through it ten times a second. Playback is one
  `playback_started` per press instead, carrying the fps and the bucket it started from.
- **The colour range slider, per frame.** `ColorLegend`'s `trackRange()` is a 1 s trailing
  debounce, so a drag is one `color_range_changed` at the range it came to rest on. A
  preset chip does *not* go through it — it reports the band's **label**, which is the
  question the presets were added to answer and which a bare pair of bounds cannot
  distinguish from a drag that happened to land there.
- **A refetch is not a selection.** `setVariable`/`setPeriod` reload the cell already on
  screen through `selectPoint()`, so that call takes **`track: false`**. Without it every
  variable toggle also reported a `point_selected` and a map click was indistinguishable
  from a toggle. `track` defaults to `enterScope` — which is what keeps `loadMetadata()`'s
  bootstrap of the opening cell silent — but is a separate flag, because the scope question
  and the gesture question have different answers in the refetch path.

Events, all fired from the store or the component that owns the gesture rather than from
each call site: `point_selected`, `region_selected` (with `enteredScope`), `scope_changed`,
`variable_changed`, `period_changed`, `playback_started`, `color_range_changed`,
`csv_downloaded` (`kind: series | ranking`, plus `quantity` and, on a ranking,
`basis: month | year`), `ranking_guide_opened`, `ranking_basis_changed`,
`baseline_note_opened` (`variable`), `region_about_opened` (`region`),
`about_opened`, `intro_closed` (`action: dismiss | guide`), `state_ribbon_clicked` (`half: enso`), `state_guide_opened`,
`compare_toggled` (`on`), `point_added` (`source`), `region_added`, `point_removed`, `compare_date_changed` (1 s trailing debounce, like the colour
range).
Server-side:
`land_point_queried` (`surface`, `buckets`), `point_queried` (including the out-of-domain 400 — where people click outside the box is
the argument for widening it, which costs only a `domain.yml` edit), `point_ranking_queried`,
`region_queried`, `region_box_queried`, `region_ranking_queried`.

**`region_selected` is reported on every call, not only when the key changes.** It is
reached only from the region menu, so picking the region already active is still a choice
— and from point scope it *is* the gesture that enters region scope. Guarding it on
`changed`, as the fetch below it rightly is, made the commonest path of all — open the
menu, pick the default region — report nothing. Found in the browser, not by reading.
