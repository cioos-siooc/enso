import posthog from 'posthog-js'

declare global {
  interface Window {
    umami?: { track: (event: string, data?: Record<string, unknown>) => void }
  }
}

/**
 * Fire a custom event at PostHog and at Umami (on trial side by side).
 *
 * A no-op during SSR (both are initialised only in client-only plugins) and a
 * no-op in any environment without their settings, so call sites never guard.
 * `window.umami` exists only once its deferred script has loaded; an event
 * before that is dropped on Umami's side, never queued.
 *
 * The events are *decisions*, not requests: what someone chose to look at.
 * Anything that fires on its own — playback's per-frame `setDate`, the colour
 * slider's per-frame drag, a map pan — is either excluded or reduced to one
 * event at the call site, for the same reason `/image` is not instrumented
 * server-side.
 */
export function trackEvent(event: string, properties?: Record<string, unknown>) {
  if (!import.meta.client) return
  posthog.capture(event, properties)
  window.umami?.track(event, properties)
}
