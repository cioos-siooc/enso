/**
 * Guided stories: short sequences of views with a caption each.
 *
 * Editorial copy, not data, which is why they live in the frontend rather than
 * in `domain.yml`. A step is a `View` — the same thing a deep link is — so a
 * story can show nothing a link could not, and `store.applyView` is the only
 * code that puts the app into one.
 *
 * **Writing one.** Each step names only what it changes; anything it leaves out
 * stays as the previous step left it. Say the variable and period on the first
 * step anyway, since a visitor may arrive on any view. Dates are any day inside
 * the bucket. `tests/stories.test.ts` checks every step against the region keys
 * in `shared/domain.yml`, so a typo fails a test rather than silently falling
 * back to the current view.
 *
 * **`draft: true` stories are shown in dev only.** The placeholder below is one:
 * it exists to exercise the player until the real stories are written.
 */
import type { View } from '~/stores/main'

export interface StoryStep {
  /** Plain text. A blank line starts a new paragraph. */
  caption: string
  view: View
  /**
   * Play the map from the step's date up to this date's bucket, then stop.
   * The step's own `view.date` is where it starts.
   */
  play?: { until: string }
}

export interface Story {
  key: string
  title: string
  /** One sentence for the picker. */
  summary: string
  steps: StoryStep[]
  draft?: boolean
}

export const STORIES: Story[] = [
  {
    key: 'player-check',
    title: 'Story player check',
    summary: 'A placeholder that exercises every kind of step. Replace with real stories.',
    draft: true,
    steps: [
      {
        caption: 'Placeholder step 1 of 4: a named region, a variable and a period.\n\nThe map flies to the region by itself.',
        view: { variable: 'anom', period: 'monthly', date: '2015-08-01', region: 'nino34', compareDate: null },
      },
      {
        caption: 'Placeholder step 2 of 4: a single cell, with an explicit camera.',
        view: {
          period: 'weekly',
          date: '2014-12-08',
          point: { lat: 47.98, lon: -127.98 },
          camera: { center: [-138, 46], zoom: 3.2 },
        },
      },
      {
        caption: 'Placeholder step 3 of 4: the same cell, playing a range and stopping at its end.',
        view: { date: '2015-03-02' },
        play: { until: '2015-05-04' },
      },
      {
        caption: 'Placeholder step 4 of 4: swipe compare between two dates over a polygon region.',
        view: { period: 'daily', date: '2021-06-28', compareDate: '2020-06-28', region: 'pacific_bioregions' },
      },
    ],
  },
]

/** Stories this build may show: drafts only in dev. */
export function visibleStories(): Story[] {
  return STORIES.filter(s => !s.draft || import.meta.dev)
}

export function findStory(key: string): Story | undefined {
  return visibleStories().find(s => s.key === key)
}
