/**
 * Keep the URL saying what is on screen, and honour one that already does.
 *
 * A dashboard whose every view lives at the same address cannot be sent to
 * anyone. "Look at the Blob in September 2015" is four gestures to describe and
 * one link to send, and the link is also what lets the guide, a colleague's
 * email and a CIOOS page point at a specific finding rather than at the app.
 *
 * **Client-only, and deliberately after `loadMetadata()`.** Applying the query
 * during SSR would mean issuing the selection fetches inside the render, and
 * `useApi()` only survives the synchronous part of an SSR call chain — the trap
 * `loadRegionSeries`'s `api` parameter exists for. Running from `onMounted`
 * instead costs at most one extra request (the opening cell the bootstrap
 * already fetched) and cannot strand the page.
 *
 * **`replaceState`, never `push`.** Every one of these is a change of view
 * rather than a change of page; pushing would make the browser's Back button
 * step through a hundred playback frames instead of leaving the site.
 */
import { useMainStore, type VariableName } from '~/stores/main'
import { LAND_SOURCES, type LandMode, type LandSource } from '~/utils/land'
import { PERIODS, type Period } from '~/utils/periods'
import { findStory } from '~/stories'
import { useStory } from '~/composables/useStory'

/** Query keys, kept short because these links get pasted into chat and email. */
const KEYS = {
  variable: 'v',
  period: 'p',
  date: 'd',
  region: 'r',
  point: 'at',
  /** Swipe compare's second date; absent when compare is off. */
  compare: 'c',
  /** The land overlay (`tmax` | `tmin` | `precip`) and its mode; absent when off. */
  land: 'land',
  landMode: 'lm',
  /** A guided story and its 1-based step. */
  story: 'story',
  step: 'step',
} as const

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

const VARIABLES: VariableName[] = ['sst', 'anom', 'mhw']

function parsePoint(value: string): { lat: number, lon: number } | null {
  const [lat, lon] = value.split(',').map(Number)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  if (lat! < -90 || lat! > 90) return null
  return { lat: lat!, lon: lon! }
}

/** A cell as `48.03,-127.97` — trimmed, since the grid is 0.05 degrees. */
function formatPoint(p: { lat: number, lon: number }): string {
  // Longitudes come back on the API's 0-360 convention; written signed here
  // because that is what a person pastes and what `GlobalGrid.gx()` accepts
  // either way.
  const lon = ((p.lon + 180) % 360 + 360) % 360 - 180
  return `${p.lat.toFixed(2)},${lon.toFixed(2)}`
}

function first(value: unknown): string | null {
  const v = Array.isArray(value) ? value[0] : value
  return typeof v === 'string' && v ? v : null
}

export function useUrlState() {
  const store = useMainStore()
  const route = useRoute()
  const story = useStory()

  /**
   * Read the query into the store. A story link opens the story at its step,
   * whose own view wins over any other key; anything else is one `applyView`.
   */
  async function applyQuery() {
    const q = route.query
    const storyKey = first(q[KEYS.story])
    if (storyKey && findStory(storyKey)) {
      await story.start(storyKey, Number(first(q[KEYS.step]) ?? 1) - 1, { fromLink: true })
      return
    }

    const variable = first(q[KEYS.variable]) as VariableName | null
    const period = first(q[KEYS.period]) as Period | null
    const date = first(q[KEYS.date])
    const region = first(q[KEYS.region])
    const point = first(q[KEYS.point])
    const compare = first(q[KEYS.compare])
    const land = first(q[KEYS.land]) as LandSource | null
    const landMode = first(q[KEYS.landMode]) as LandMode | null

    await store.applyView({
      variable: variable && VARIABLES.includes(variable) ? variable : undefined,
      period: period && PERIODS.some(p => p.value === period) ? period : undefined,
      date: date ?? undefined,
      region: region ?? undefined,
      point: point ? parsePoint(point) ?? undefined : undefined,
      compareDate: compare && ISO_DATE.test(compare) ? compare : undefined,
      // Unknown values are dropped rather than trusted, like the variable: a
      // hand-edited link must not put the store into a state no button reaches.
      landLayer: land && LAND_SOURCES.includes(land) ? land : undefined,
      landMode: landMode === 'value' || landMode === 'anomaly' ? landMode : undefined,
    })
  }

  /** The query the current state deserves, with defaults left out. */
  function currentQuery(): Record<string, string> {
    const q: Record<string, string> = {
      [KEYS.variable]: store.variable,
      [KEYS.period]: store.period,
    }
    // A story link reopens on the step, and the step's own view is what it
    // shows; the view keys are written too, so the link still says what is on
    // screen to someone reading it.
    if (story.active.value) {
      q[KEYS.story] = story.active.value.key
      q[KEYS.step] = String(story.step.value + 1)
    }
    if (store.selectedDate) q[KEYS.date] = store.selectedDate
    if (store.compareDate) q[KEYS.compare] = store.compareDate
    if (store.landLayer) {
      q[KEYS.land] = store.landLayer
      q[KEYS.landMode] = store.landMode
    }
    if (store.scope === 'region') {
      if (store.activeRegion) q[KEYS.region] = store.activeRegion
    }
    else if (store.pointSeries?.cell) {
      // The resolved CELL, not the raw click: a link should reopen on the same
      // grid cell rather than on whatever pixel happened to be under the cursor,
      // and the two round to the same place anyway.
      q[KEYS.point] = formatPoint(store.pointSeries.cell)
    }
    return q
  }

  function sync() {
    const q = currentQuery()
    const search = new URLSearchParams(q).toString()
    const url = `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`
    if (url !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
      window.history.replaceState(window.history.state, '', url)
    }
  }

  onMounted(async () => {
    await applyQuery()
    sync()
    // One watcher over everything the URL carries. Playback writes
    // `selectedDate` up to ten times a second and `replaceState` is cheap, but
    // `flush: 'post'` keeps it off the critical path of the frame.
    watch(
      () => [store.variable, store.period, store.selectedDate, store.compareDate, store.scope,
             store.landLayer, store.landMode,
             store.activeRegion, store.pointSeries?.cell?.lat, store.pointSeries?.cell?.lon,
             story.active.value?.key, story.step.value],
      sync,
      { flush: 'post' },
    )
  })
}
