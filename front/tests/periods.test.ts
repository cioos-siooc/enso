import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { bucketEnd, bucketLabel, bucketStart, shiftBuckets, type Period } from '~/utils/periods'

/**
 * The same fixture `tests/test_periods.py` asserts `shared/periods.py` against.
 * The two implementations are one definition written twice; this is what
 * notices when only one of them changes.
 */
interface Case { date: string, period: Period, start: string, end: string }
const { cases } = JSON.parse(
  readFileSync(new URL('../../shared/testdata/periods_cases.json', import.meta.url), 'utf8'),
) as { cases: Case[] }

describe('bucket parity with shared/periods.py', () => {
  it.each(cases)('$date $period', ({ date, period, start, end }) => {
    expect(bucketStart(date, period)).toBe(start)
    expect(bucketEnd(date, period)).toBe(end)
  })
})

describe('shiftBuckets', () => {
  it('lands on bucket starts and round-trips', () => {
    for (const { date, period } of cases) {
      const moved = shiftBuckets(date, period, 5)
      expect(bucketStart(moved, period)).toBe(moved)
      expect(shiftBuckets(moved, period, -5)).toBe(bucketStart(date, period))
    }
  })

  it('does not overflow month ends', () => {
    expect(shiftBuckets('2024-01-31', 'monthly', 1)).toBe('2024-02-01')
  })
})

describe('bucketLabel', () => {
  it('is pinned to en-GB, so SSR and the browser agree', () => {
    expect(bucketLabel('2026-08-26', 'monthly')).toBe('August 2026')
    expect(bucketLabel('2026-08-26', 'weekly')).toBe('24 Aug – 30 Aug')
  })
})
