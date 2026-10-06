/**
 * Whether the page is on a phone-sized screen, as one shared reactive flag.
 *
 * **False under SSR and until mount.** The server cannot know the viewport, so
 * it renders the desktop layout, and the flag flips on the client after
 * hydration. That is one layout switch on a phone, while the map is still
 * loading, and no hydration mismatch — reading `matchMedia` during setup would
 * render different markup in the browser than the server sent.
 *
 * Only for what CSS cannot do: which component tree is mounted (dock or bottom
 * sheet), a component prop (button size, a fullscreen modal), or a number in
 * script (the playback prefetch window). Anything that is only styling uses
 * Tailwind's `md:` breakpoint, which is the same 768px.
 */
const QUERY = '(max-width: 767px)'

const narrow = ref(false)
let listening = false

export function useViewport() {
  onMounted(() => {
    if (listening) return
    listening = true
    const media = window.matchMedia(QUERY)
    narrow.value = media.matches
    media.addEventListener('change', (event) => { narrow.value = event.matches })
  })
  return { narrow: readonly(narrow) }
}

/** The flag without registering a mount hook, for code that runs outside setup. */
export function isNarrow(): boolean {
  return narrow.value
}
