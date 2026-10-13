/**
 * Umami, browser side, on trial next to PostHog (docs/analytics.md).
 * **Client-only**, like `posthog.client.ts`, and the same no-op without its
 * setting.
 *
 * The script comes **straight from the shared instance**
 * (analytics.cioospacific.ca, the cioos-pacific-analytics stack), not through
 * a proxy here: behind Cloudflare, Umami reads the visitor IP from
 * `CF-Connecting-IP`, which a proxy would turn into this server's address.
 *
 * **`data-exclude-search` is load-bearing.** The tracker hooks `replaceState`
 * and reports a pageview whenever the URL changes, and `useUrlState` rewrites
 * the query string on every selection — up to ten times a second during
 * playback. Ignoring the search string leaves one pageview per path.
 */
export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const websiteId = config.public.umamiWebsiteId as string
  if (!websiteId) return

  const script = document.createElement('script')
  script.defer = true
  script.src = config.public.umamiScriptUrl as string
  script.dataset.websiteId = websiteId
  script.dataset.excludeSearch = 'true'
  document.head.appendChild(script)
})
