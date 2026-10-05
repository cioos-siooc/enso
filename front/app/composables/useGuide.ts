const INTRO_KEY = 'enso.intro.seen'

/**
 * The guide dialog's open state, shared so something other than the header's
 * two buttons can open it — the first-visit card's `Full guide` link is that
 * something. `AboutDialog` stays the only owner of the dialog itself.
 */
export function useGuide() {
  const open = useState('guideOpen', () => false)
  const tab = useState<'guide' | 'about'>('guideTab', () => 'guide')

  function openOn(which: 'guide' | 'about') {
    tab.value = which
    open.value = true
  }

  return { open, tab, openOn }
}

/**
 * Whether the first-visit card is up. Remembered once dismissed, like the
 * legend and the projection: it is for someone who has never seen the app, so
 * it must not come back on every reload.
 */
export function useIntro() {
  const shown = useState('introShown', () => false)

  /** Browser-only; call from `onMounted`. */
  function restore() {
    try {
      shown.value = localStorage.getItem(INTRO_KEY) !== '1'
    }
    catch {
      // Storage blocked: showing it on every visit would be the worse failure.
      shown.value = false
    }
  }

  function dismiss() {
    shown.value = false
    try {
      localStorage.setItem(INTRO_KEY, '1')
    }
    catch { /* private mode — dismissed for this session */ }
  }

  return { shown, restore, dismiss }
}
