declare global {
  interface Window {
    umami?: { track: (event: string, data?: Record<string, unknown>) => void }
  }
}

/** Events fired before Umami's deferred script loaded; `flushAnalytics` sends them. */
const pending: [string, Record<string, unknown> | undefined][] = []

/**
 * Fire a custom Umami event.
 *
 * A no-op during SSR (the tracker is loaded only by the client-only plugin) and
 * in any environment without a website ID, so call sites never guard. An event
 * fired before the deferred script has loaded is held until it has, not dropped;
 * without a website ID the plugin never flushes, and the queue is capped.
 *
 * The events are *decisions*, not requests: what someone chose to look at.
 * Anything that fires on its own — playback's per-frame `setDate`, the colour
 * slider's per-frame drag, a map pan — is either excluded or reduced to one
 * event at the call site.
 */
export function trackEvent(event: string, properties?: Record<string, unknown>) {
  if (!import.meta.client) return
  if (window.umami) window.umami.track(event, properties)
  else if (pending.length < 50) pending.push([event, properties])
}

/** Called by `umami.client.ts` once the tracker has loaded. */
export function flushAnalytics() {
  if (!window.umami) return
  for (const [event, properties] of pending.splice(0)) window.umami.track(event, properties)
}
