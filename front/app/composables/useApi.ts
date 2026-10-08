import axios from 'axios'
import { getRequestIP } from 'h3'
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
  // During SSR the API's TCP peer is this container, so without this every
  // server-rendered request is attributed in PostHog to `front`'s Docker IP.
  // Read here, in the synchronous part of setup, where the request event exists.
  const headers = import.meta.server ? visitorHeaders() : undefined

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

/** The visitor's IP as `X-Forwarded-For`, for the API's `client_ip()`. */
function visitorHeaders(): Record<string, string> | undefined {
  const event = useRequestEvent()
  const ip = event && getRequestIP(event, { xForwardedFor: true })
  return ip ? { 'X-Forwarded-For': ip } : undefined
}
