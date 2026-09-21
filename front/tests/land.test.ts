import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  formatLog2Percent,
  landLayerName,
  landUnavailableReason,
  parseLog2Percent,
  type LandCoverage,
  type LandMode,
  type LandSource,
} from '~/utils/land'

/**
 * Every layer name the land control can produce must be a layer `domain.yml`
 * declares — `applyView` and the map would otherwise ask `/image` for a name it
 * 422s, and the overlay would silently draw nothing. Read from the file itself,
 * as `stories.test.ts` reads the regions, so a rename there fails here.
 */
const domainYml = readFileSync(new URL('../../shared/domain.yml', import.meta.url), 'utf8')

describe('landLayerName', () => {
  const cases: Array<[LandSource, LandMode, string]> = [
    ['tmax', 'value', 'land_tmax'],
    ['tmin', 'value', 'land_tmin'],
    ['precip', 'value', 'land_precip'],
    ['tmax', 'anomaly', 'land_tmax_anom'],
    ['tmin', 'anomaly', 'land_tmin_anom'],
    // Rain's anomaly is a RATIO, not a difference in millimetres.
    ['precip', 'anomaly', 'land_precip_ratio'],
  ]
  it.each(cases)('%s + %s -> %s', (source, mode, name) => {
    expect(landLayerName(source, mode)).toBe(name)
  })
  it.each(cases)('%s + %s is declared in domain.yml', (source, mode) => {
    expect(domainYml).toMatch(new RegExp(`^  ${landLayerName(source, mode)}:$`, 'm'))
  })
})

describe('log2_percent', () => {
  it('prints halving and doubling symmetrically about 100%', () => {
    expect(formatLog2Percent(0)).toBe('100%')
    expect(formatLog2Percent(-1)).toBe('50%')
    expect(formatLog2Percent(1)).toBe('200%')
    expect(formatLog2Percent(-2)).toBe('25%')
    expect(formatLog2Percent(2)).toBe('400%')
  })
  it('keeps the precision a small share needs', () => {
    expect(formatLog2Percent(-3)).toBe('12.5%')
    expect(formatLog2Percent(-4)).toBe('6.25%')
  })
  it('round-trips a typed percent', () => {
    for (const v of [-4, -2.5, -1, 0, 0.5, 1, 3]) {
      expect(parseLog2Percent(formatLog2Percent(v))).toBeCloseTo(v, 1)
    }
    expect(parseLog2Percent('200 %')).toBeCloseTo(1)
  })
  it('refuses what has no logarithm', () => {
    expect(parseLog2Percent('0')).toBeNaN()
    expect(parseLog2Percent('-50')).toBeNaN()
    expect(parseLog2Percent('rain')).toBeNaN()
  })
})

describe('landUnavailableReason', () => {
  const coverage: LandCoverage = {
    temp: { days: 100, start: '1985-01-01', end: '2026-09-17' },
    precip: { days: 100, start: '1985-01-01', end: '2026-09-16' },
    layers: { land_tmax: true, land_tmax_anom: true, land_precip_ratio: false },
  }
  const temp = { periods: ['daily', 'weekly', 'monthly'] as const, shortName: 'Tmax', source: 'tmax' }
  const ratio = { periods: ['weekly', 'monthly'] as const, shortName: 'Rain vs normal', source: 'precip' }

  it('draws a covered bucket', () => {
    expect(landUnavailableReason('land_tmax', { ...temp, periods: [...temp.periods] }, coverage, 'daily', '2015-07-01', '2015-07-01')).toBeNull()
  })
  it('says why when the server has no land data', () => {
    expect(landUnavailableReason('land_tmax', { ...temp, periods: [...temp.periods] }, null, 'daily', '2015-07-01', '2015-07-01'))
      .toMatch(/not loaded/)
  })
  it('refuses a period the layer does not exist at', () => {
    expect(landUnavailableReason('land_precip_ratio', { ...ratio, periods: [...ratio.periods] }, coverage, 'daily', '2015-07-01', '2015-07-01'))
      .toMatch(/weekly or monthly only/)
  })
  it('refuses an anomaly whose climatology is not built', () => {
    expect(landUnavailableReason('land_precip_ratio', { ...ratio, periods: [...ratio.periods] }, coverage, 'monthly', '2015-07-01', '2015-07-31'))
      .toMatch(/climatology/)
  })
  it('refuses a date past its own product, which is not the other one', () => {
    // Temperature reaches 2026-09-17, rain only 2026-09-16: a day apart, as measured.
    const tempMeta = { ...temp, periods: [...temp.periods] }
    expect(landUnavailableReason('land_tmax', tempMeta, coverage, 'daily', '2026-09-17', '2026-09-17')).toBeNull()
    const rainMeta = { periods: ['daily', 'weekly', 'monthly'] as Array<'daily' | 'weekly' | 'monthly'>, shortName: 'Rain', source: 'precip' }
    expect(landUnavailableReason('land_precip', rainMeta, coverage, 'daily', '2026-09-17', '2026-09-17'))
      .toMatch(/available 1985-01-01 to 2026-09-16/)
  })
  it('draws a bucket that is only partly covered', () => {
    // The open week at the archive's edge is short, not missing.
    expect(landUnavailableReason('land_tmax', { ...temp, periods: [...temp.periods] }, coverage, 'weekly', '2026-09-14', '2026-09-20')).toBeNull()
  })
})
