const LEGEND_KEY = 'enso.legend.hidden'

/**
 * Whether the colour legend is on the map. Shared state rather than a prop,
 * because the control that hides it lives in the legend and the one that brings
 * it back lives in the map's control column — the legend cannot hold its own
 * way back, or hiding it would leave nothing to click.
 *
 * Remembered like the projection and the dock width: someone who hid it for a
 * screenshot series should not have to hide it again on every reload.
 */
export function useLegend() {
  const hidden = useState('legendHidden', () => false)

  function setHidden(value: boolean) {
    hidden.value = value
    try {
      localStorage.setItem(LEGEND_KEY, value ? '1' : '0')
    }
    catch { /* private mode — the choice still applies this session */ }
  }

  /** Browser-only; call from `onMounted`. */
  function restore() {
    try {
      hidden.value = localStorage.getItem(LEGEND_KEY) === '1'
    }
    catch { /* see setHidden */ }
  }

  return { hidden, setHidden, restore }
}
