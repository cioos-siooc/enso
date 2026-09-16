import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { STORIES } from '~/stories'

/**
 * A story step that names a region, variable or period the app does not know is
 * not an error at runtime: `applyView` ignores what it cannot apply and leaves
 * the previous view on screen, which reads as the story being wrong rather than
 * broken. So the check is here.
 */
const domainYml = readFileSync(new URL('../../shared/domain.yml', import.meta.url), 'utf8')
const regionsBlock = domainYml.slice(domainYml.indexOf('\nregions:'), domainYml.indexOf('\nquantities:'))
const REGIONS = new Set([...regionsBlock.matchAll(/^ {2}([a-z0-9_]+):\s*$/gm)].map(m => m[1]))
const ISO = /^\d{4}-\d{2}-\d{2}$/

describe('stories', () => {
  it('found the regions it checks against', () => {
    expect(REGIONS.has('nino34')).toBe(true)
    expect(REGIONS.has('pacific_bioregions')).toBe(true)
  })

  it('have unique keys', () => {
    expect(new Set(STORIES.map(s => s.key)).size).toBe(STORIES.length)
  })

  for (const story of STORIES) {
    describe(story.key, () => {
      it('has steps with captions', () => {
        expect(story.steps.length).toBeGreaterThan(0)
        for (const step of story.steps) expect(step.caption.trim()).not.toBe('')
      })

      it.each(story.steps.map((step, i) => [i + 1, step] as const))('step %i names only known things', (_, step) => {
        const { view } = step
        if (view.variable) expect(['sst', 'anom', 'mhw']).toContain(view.variable)
        if (view.period) expect(['daily', 'weekly', 'monthly']).toContain(view.period)
        if (view.region) expect(REGIONS).toContain(view.region)
        for (const date of [view.date, view.compareDate, step.play?.until]) {
          if (date) expect(date).toMatch(ISO)
        }
        if (step.play) {
          expect(step.play.until > (view.date ?? '')).toBe(true)
        }
        if (view.point) {
          expect(Math.abs(view.point.lat)).toBeLessThanOrEqual(90)
        }
      })
    })
  }
})
