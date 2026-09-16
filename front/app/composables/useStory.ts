/**
 * The story being told, if any, and moving through it.
 *
 * Page-wide state, like the playhead: the header's picker starts a story, the
 * card over the map steps it, and the URL writes it, and all three must see the
 * same one.
 */
import { trackEvent } from '~/composables/useAnalytics'
import { usePlayback } from '~/composables/usePlayback'
import { useMainStore, type View } from '~/stores/main'
import { findStory, type Story } from '~/stories'

const active = shallowRef<Story | null>(null)
const step = ref(0)
/** What was on screen before the story started; Exit puts it back. */
let before: View | null = null
/** Guards against a slow step landing after a later one was asked for. */
let seq = 0

export function useStory() {
  const store = useMainStore()
  const playback = usePlayback()

  async function show(index: number) {
    const story = active.value
    if (!story) return
    const clamped = Math.min(Math.max(index, 0), story.steps.length - 1)
    const target = story.steps[clamped]!
    const mine = ++seq
    playback.stop()
    step.value = clamped
    await store.applyView(target.view)
    if (mine !== seq || active.value !== story) return
    if (target.play) playback.play({ until: target.play.until })
  }

  /**
   * Open a story at `index`.
   *
   * `fromLink` is arriving on a shared story URL: it has no view of its own to
   * return to, so Exit leaves the app where the story left it.
   */
  async function start(key: string, index = 0, { fromLink = false } = {}) {
    const story = findStory(key)
    if (!story) return
    before = fromLink ? null : store.currentView()
    active.value = story
    trackEvent('story_started', { story: key, step: index + 1, fromLink })
    await show(Number.isFinite(index) ? index : 0)
  }

  function go(delta: number) {
    const story = active.value
    if (!story) return
    const index = step.value + delta
    if (index < 0 || index >= story.steps.length) return
    trackEvent('story_step', { story: story.key, step: index + 1, direction: delta > 0 ? 'next' : 'back' })
    void show(index)
  }

  async function exit() {
    const story = active.value
    if (!story) return
    trackEvent('story_exited', {
      story: story.key,
      step: step.value + 1,
      of: story.steps.length,
      completed: step.value === story.steps.length - 1,
    })
    seq++
    playback.stop()
    active.value = null
    step.value = 0
    const restore = before
    before = null
    if (restore) await store.applyView(restore)
  }

  return {
    active: readonly(active),
    step: readonly(step),
    start,
    next: () => go(1),
    back: () => go(-1),
    exit,
  }
}
