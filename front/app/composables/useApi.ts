import axios from 'axios'
import { getRequestHeader, getRequestIP, parseCookies } from 'h3'
import type { Period } from '~/utils/periods'

/** Mirrors `shared/render.py`'s DEFAULT_WIDTH — see `imageUrl` below. */
export const IMAGE_WIDTH = 4096

/**
 * Thin axios wrapper bound to the API.
 *
 * Requests use two different base URLs on purpose: during SSR the Nitro server
 * talks to the API over the compose network (`http://api:4000`), while anything
 * the browser fetches — including image URLs handed to Mapbox — must use the
 * published host URL.
 */
export function useApi() {
  const config = useRuntimeConfig()
  // Trailing slashes are stripped because every URL below is built by plain
  // concatenation with a leading-slash path. A base ending in `/` yields
  // `//image/...`, and the API 404s a doubled slash on every route — which
  // surfaces as a blank map and a chart that never updates, while SSR (on the
  // internal base, which has no slash to trim) keeps working and hides it.
  const publicBase = String(config.public.apiBaseUrl ?? '').replace(/\/+$/, '')
  const internalBase = String(config.apiInternalBaseUrl ?? '').replace(/\/+$/, '')
  const requestBase = import.meta.server ? internalBase : publicBase
  // During SSR the API's TCP peer is this container and the posthog-js header
  // is not set (the plugin is client-only), so without this every
  // server-rendered request is attributed in PostHog to `front`'s Docker IP.
  // Read here, in the synchronous part of setup, where the request event exists.
  const headers = import.meta.server ? visitorHeaders(String(config.public.posthogKey ?? '')) : undefined

  return {
    baseURL: publicBase,
    async get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
      const { data } = await axios.get<T>(`${requestBase}${path}`, { params, headers })
      return data
    },
    async post<T>(path: string, body?: unknown): Promise<T> {
      const { data } = await axios.post<T>(`${requestBase}${path}`, body, { headers })
      return data
    },
    /**
     * Always browser-facing: this URL is handed to Mapbox, not fetched here.
     *
     * `width` must match what `CRW.cli render` was run with — the cache is keyed
     * by (variable, period, bucket start, width), so a different width is a
     * different file, and for a historical bucket there is no NetCDF left to
     * render one from. A mismatch shows up as a 404 and a blank map, not as a
     * slower render.
     */
    imageUrl(date: string, period: Period = 'daily', variable = 'sst', width = IMAGE_WIDTH): string {
      return `${publicBase}/image/${date}.webp?width=${width}&period=${period}&variable=${variable}`
    },
  }
}

/**
 * The visitor's identity, for the API's `capture_event()`: what posthog-js would
 * have sent from the browser, plus the visitor's address.
 *
 * The distinct_id comes from posthog-js's own cookie, `ph_<key>_posthog`, so a
 * returning visitor's server-rendered requests land on the same person as their
 * clicks. A first visit has no cookie yet and falls back to the IP. The IP
 * forwards the proxy's own headers where it sent them rather than re-deriving
 * one: a proxy that sets only `X-Real-IP` would otherwise leave `getRequestIP`
 * the proxy's socket address, which is the Docker IP this exists to avoid.
 */
function visitorHeaders(posthogKey: string): Record<string, string> | undefined {
  const event = useRequestEvent()
  if (!event) return undefined
  const headers: Record<string, string> = {}

  if (posthogKey) {
    const cookie = parseCookies(event)[`ph_${posthogKey.replace(/\+/g, 'PL').replace(/\//g, 'SL')}_posthog`]
    try {
      const id = cookie && JSON.parse(cookie).distinct_id
      if (typeof id === 'string' && id) headers['X-PostHog-Distinct-Id'] = id
    } catch { /* a malformed cookie is no identity, not an error */ }
  }

  const realIp = getRequestHeader(event, 'x-real-ip')?.trim()
  const ip = getRequestIP(event, { xForwardedFor: true })
  if (realIp && !getRequestHeader(event, 'x-forwarded-for')) headers['X-Real-IP'] = realIp
  else if (ip) headers['X-Forwarded-For'] = ip

  return Object.keys(headers).length ? headers : undefined
}
