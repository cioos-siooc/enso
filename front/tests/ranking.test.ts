import { describe, expect, it } from 'vitest'
import {
  daysInMonth, daysInYear, detailPitch, partialNote, periodDays, readingGuide,
  type MonthlyRanking, type RankingRow,
} from '~/utils/ranking'

const row = (year: number, extra: Partial<RankingRow> = {}) =>
  ({ year, rank: 1, mean: 1, sd: 0.1, n: 31, partial: false, ...extra }) as RankingRow

describe('calendar', () => {
  it('counts days', () => {
    expect(daysInMonth(2024, 2)).toBe(29)
    expect(daysInMonth(2026, 2)).toBe(28)
    expect(daysInYear(2000)).toBe(366)
    expect(daysInYear(1900)).toBe(365)
    expect(periodDays(null, 2026)).toBe(365)
    expect(periodDays(8, 2026)).toBe(31)
  })
})

describe('detailPitch', () => {
  it('stays within its floor and ceiling', () => {
    expect(detailPitch(45, 100)).toBe(9)
    expect(detailPitch(3, 5000)).toBe(40)
  })
})

describe('partialNote', () => {
  it('names the period and its denominator', () => {
    const rows = [row(2015), row(2026, { partial: true, n: 24 })]
    expect(partialNote(rows, 8)).toContain('August 2026 is incomplete — ranked on 24 of 31 days')
    expect(partialNote([row(2026, { partial: true, n: 242 })], null)).toContain('2026 is incomplete — ranked on 242 of 365 days')
    expect(partialNote([row(2015)], 8)).toBeNull()
  })
})

describe('readingGuide', () => {
  const base = { top: 3, months: {}, span: null } as unknown as MonthlyRanking

  it('names a cell and a region differently', () => {
    const cell = readingGuide({ ranking: base, basis: 8, rows: [row(2015)], topN: 3 })
    const region = readingGuide({
      ranking: { ...base, region: 'nino34', label: 'Nino 3.4', areaMean: true },
      basis: null, rows: [row(2015)], topN: 3,
    })
    expect(cell.summary).toContain('Every August on record at the selected cell')
    expect(region.summary).toContain('Every year on record at Nino 3.4 (area mean)')
    expect(region.items.some(i => i.text.includes('daily area means'))).toBe(true)
  })

  it('explains the partial glyph only when one is on screen', () => {
    const without = readingGuide({ ranking: base, basis: 8, rows: [row(2015)], topN: 3 })
    const withPartial = readingGuide({ ranking: base, basis: 8, rows: [row(2026, { partial: true })], topN: 3 })
    expect(without.items.some(i => i.glyph === 'partial')).toBe(false)
    expect(withPartial.items.some(i => i.glyph === 'partial')).toBe(true)
  })
})
