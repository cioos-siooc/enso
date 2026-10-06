/**
 * What the Alt key is called on this machine, for the compare buttons' hover
 * text: `⌥ Option` on a Mac, `Alt` elsewhere.
 *
 * Read on mount, not in setup: `navigator` does not exist under SSR, and a key
 * name that differs between server and browser is a hydration mismatch.
 */
export function useAltKey() {
  const alt = ref('Alt')
  onMounted(() => {
    if (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) alt.value = '⌥ Option'
  })
  return alt
}
