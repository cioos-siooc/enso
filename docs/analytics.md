# Usage analytics (Umami)

What is instrumented, what deliberately is not, and why.

## Umami

**Umami only, from 2026-10-20.** PostHog ran next to it on trial from 2026-10-13 and was
removed. In prod, PostHog showed every API event under an IP as the person and with no
city: posthog-js was not sending (no `$pageview`s at all, so no distinct_id header), and
the API's server-side capture geolocated the API server's address, not the visitor's. It
also sent the data to US servers with a cookie. Umami is self-hosted, cookieless, and
answers the same questions.

- **One shared instance, not part of this stack.** Umami runs at
  `analytics.cioospacific.ca` from its own repo, `cioos-pacific-analytics` (Umami v3 +
  Postgres + Cloudflare Tunnel), the same way Prefect runs at
  `pipelines.cioospacific.ca`.
  Every CIOOS Pacific app is a website there; OSTA is one. Its README covers deploying,
  adding an app, backups and upgrades.
- **The browser loads the script straight from that host — no proxy in `front`.** Behind
  Cloudflare, Umami reads the visitor IP from `CF-Connecting-IP`, which Cloudflare sets from
  whoever connected. Through a `front` proxy that is this server, so every visitor would get
  its location. The cost: some ad blockers stop a separate analytics hostname.
- **Front end only.** `app/plugins/umami.client.ts` injects `NUXT_PUBLIC_UMAMI_SCRIPT_URL`
  when `NUXT_PUBLIC_UMAMI_WEBSITE_ID` is set; `app/composables/useAnalytics.ts`'s
  `trackEvent()` calls `window.umami.track()`. Both live under `app/` because that is
  Nuxt 4's srcDir — a top-level `front/plugins/` is not picked up at all.
  **A blank website ID is a silent no-op** and the dev default; nothing guards at the call
  sites.
- **The API sends nothing.** Its server-side events duplicated the browser's
  `point_selected`/`region_selected`; only direct API users (curl, scripts) are not
  counted.
- **Events before the script loads are queued, not lost.** The script is deferred, so
  `trackEvent()` holds up to 50 events and the plugin flushes them on the script's `load`.
- **`data-exclude-search="true"` is load-bearing.** The tracker reports a pageview on every
  `replaceState` that changes the URL, and `useUrlState` rewrites the query string on every
  selection — ten times a second in playback. With it, one pageview per path; verified in
  headless Chromium (one pageview across a map click that rewrote the query).
- **Umami drops bots by user agent**, headless Chromium included: `/api/send` still
  answers 200, but nothing is stored. Set a desktop `userAgent` to test in Playwright.
- **No autocapture.** This is a full-bleed Mapbox UI: a click stream on the canvas means
  nothing. Custom events only, plus Umami's own pageviews.

**What is deliberately not instrumented, and why it is the load-bearing part:**

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
`color_scale_linked`, `land_layer_changed`,
`csv_downloaded` (`kind: series | ranking`, plus `quantity` and, on a ranking,
`basis: month | year`), `ranking_guide_opened`, `ranking_basis_changed`,
`baseline_note_opened` (`variable`), `region_about_opened` (`region`),
`about_opened`, `guide_opened`, `intro_closed` (`action: dismiss | guide`),
`state_ribbon_clicked` (`half: enso`), `state_guide_opened`,
`compare_toggled` (`on`), `point_added` (`source`), `region_added`, `point_removed`,
`compare_date_changed` (1 s trailing debounce, like the colour range).

**`region_selected` is reported on every call, not only when the key changes.** It is
reached only from the region menu, so picking the region already active is still a choice
— and from point scope it *is* the gesture that enters region scope. Guarding it on
`changed`, as the fetch below it rightly is, made the commonest path of all — open the
menu, pick the default region — report nothing. Found in the browser, not by reading.
