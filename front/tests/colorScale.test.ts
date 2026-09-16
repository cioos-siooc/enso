import { describe, expect, it } from 'vitest'
import { NO_CLASS_COLOR, colorScale } from '~/utils/colorScale'
import { quantise } from '~/stores/main'

const stops = [
  { value: 0, color: '#000000' },
  { value: 10, color: '#ffffff' },
]

describe('colorScale', () => {
  it('interpolates between stops and clamps outside them', () => {
    const scale = colorScale(stops)
    expect(scale(5)).toBe('rgb(128, 128, 128)')
    expect(scale(-3)).toBe('#000000')
    expect(scale(99)).toBe('#ffffff')
  })

  it('draws below the first class as no class, when asked', () => {
    expect(colorScale(stops, NO_CLASS_COLOR)(-0.5)).toBe(NO_CLASS_COLOR)
  })

  it('has a neutral fallback for no value', () => {
    expect(colorScale(stops)(null)).toBe(colorScale([])(1))
  })
})

describe('quantise', () => {
  it('keeps the top step that a bare floor would shave off', () => {
    expect(quantise(12.7, 0.1)).toBe(12.7)
    expect(quantise(-12.700000000000001, 0.1)).toBe(-12.7)
  })
})
