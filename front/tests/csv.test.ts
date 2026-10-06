import { describe, expect, it } from 'vitest'
import type { Series } from '~/stores/main'
import { cellSlug, csvText, seriesCsv, slug } from '~/utils/csv'

describe('csvText', () => {
  it('quotes what needs quoting and uses CRLF', () => {
    expect(csvText([['a', 'b,c', 'say "hi"'], [1, null]])).toBe('a,"b,c","say ""hi"""\r\n1,\r\n')
  })
})

describe('filenames', () => {
  it('slugs labels', () => {
    expect(slug('Nino 3.4')).toBe('nino-3-4')
    expect(slug('Pacific Bioregions (DFO)')).toBe('pacific-bioregions-dfo')
    expect(slug('!!!')).toBe('export')
  })

  it('names a cell by hemisphere, unwrapping 0-360 longitudes', () => {
    expect(cellSlug({ lat: 47.98, lon: 232.02 })).toBe('47-98n_127-98w')
    expect(cellSlug({ lat: -5, lon: 160 })).toBe('5-00s_160-00e')
  })
})

describe('seriesCsv', () => {
  const series = {
    dates: ['2024-05-06', '2024-05-13'],
    values: [0.20200000000000001, null],
    period: 'weekly',
  } as unknown as Series

  it('writes both bucket ends, fixed precision, and an empty field for null', () => {
    expect(seriesCsv(series, { variable: 'anom', period: 'weekly', unit: '°C', precision: 2 })).toBe(
      'start_date,end_date,anom_degC\r\n2024-05-06,2024-05-12,0.20\r\n2024-05-13,2024-05-19,\r\n',
    )
  })

  it('joins a second point on the bucket start, one column per point', () => {
    const b = { dates: ['2024-05-13', '2024-05-20'], values: [1.5, -0.25], period: 'weekly' } as unknown as Series
    expect(seriesCsv(series, { variable: 'anom', period: 'weekly', unit: '°C', precision: 2, second: b })).toBe(
      'start_date,end_date,anom_degC_a,anom_degC_b\r\n'
      + '2024-05-06,2024-05-12,0.20,\r\n'
      + '2024-05-13,2024-05-19,,1.50\r\n'
      + '2024-05-20,2024-05-26,,-0.25\r\n',
    )
  })

  it('names the quantity over the variable', () => {
    const extent = { ...series, quantity: 'mhw_extent' } as Series
    expect(seriesCsv(extent, { variable: 'mhw', period: 'weekly', unit: '%', precision: 1 }))
      .toMatch(/^start_date,end_date,mhw_extent_pct\r\n/)
  })
})
