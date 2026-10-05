/**
 * The diverging anomaly scale, as a function of value.
 *
 * `ColorLegend` renders `/domain`'s `colorStops` as a CSS gradient; anything
 * that has to colour an individual mark needs the same stops evaluated at a
 * point instead. Both read the one list that comes from `domain.yml`, so
 * changing `vmin`/`vmax`/`colormap` there still moves the whole app at once.
 */

export interface ColorStop {
  value: number
  color: string
  /**
   * The class's name, present only on a **categorical** variable's stops (mhw's
   * "Moderate" .. "Beyond extreme"). A sampled colormap's stops are positions on
   * a continuum and have nothing to be called.
   */
  label?: string
}

function rgb(hex: string): [number, number, number] {
  const n = Number.parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

/**
 * Build an interpolating lookup over `stops`, which must be sorted by value.
 *
 * Values outside the stops' range clamp to the end colours rather than
 * extrapolating — the map's images saturate at vmin/vmax the same way, so a +5 °C
 * day reads as "off the top of the scale" in both views.
 */
/**
 * Neutral ink for a value that is on the scale's axis but not on its ramp.
 *
 * The one case is a **categorical** variable below its first class: a mean
 * heatwave category of 0.0 is a real, common and meaningful reading — "no
 * heatwave all month" — and clamping it to Cat 1's yellow says the opposite.
 * `TimeseriesChart` draws its own 0 the same colour for the same reason.
 */
export const NO_CLASS_COLOR = '#475569'

export function colorScale(
  stops: ColorStop[],
  /**
   * What to draw below the first stop. The default clamps, which is right for a
   * continuous scale — an SST of -4 is simply off the bottom, and the map
   * saturates it the same way. Pass `NO_CLASS_COLOR` for a categorical scale,
   * where below the first class means *no class*, not the first one.
   */
  belowFirst?: string,
): (value: number | null) => string {
  const fallback = '#64748b'
  if (!stops.length) return () => fallback
  const parsed = stops.map(s => ({ value: s.value, rgb: rgb(s.color) }))
  const first = parsed[0]!
  const last = parsed[parsed.length - 1]!

  return (value) => {
    if (value == null || Number.isNaN(value)) return fallback
    if (value < first.value && belowFirst) return belowFirst
    if (value <= first.value) return stops[0]!.color
    if (value >= last.value) return stops[stops.length - 1]!.color

    let hi = 1
    while (hi < parsed.length - 1 && parsed[hi]!.value < value) hi++
    const a = parsed[hi - 1]!
    const b = parsed[hi]!
    const span = b.value - a.value
    const t = span === 0 ? 0 : (value - a.value) / span
    const mix = a.rgb.map((c, i) => Math.round(c + (b.rgb[i]! - c) * t))
    return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`
  }
}

/**
 * The darkest a colour may be when it is drawn as INK on the app's dark panels.
 *
 * The ramps' extremes are near-black — RdBu_r ends at #67001f and #053061,
 * turbo at #30123b and #7a0403, mhw's Cat 5 is #991a00 — which is right on the
 * map, where they are filled areas over the basemap, and nearly invisible as a
 * 1.5px chart line or a headline number on a near-black card. That is backwards
 * for a dashboard: the extremes are what the reader is meant to notice.
 *
 * Relative luminance (WCAG), not HSL lightness, because the eye does not weigh
 * hues equally: a blue needs far more lightness than a yellow to read the same.
 * 0.16 is ~3.5:1 against slate-900, above WCAG's 3:1 for graphics.
 */
const MIN_INK_LUMINANCE = 0.16

function luminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const k = (n: number) => (n + h / 30) % 12
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1))
  return [f(0), f(8), f(4)].map(v => Math.round(v * 255)) as [number, number, number]
}

function rgbToHsl([r, g, b]: [number, number, number]): [number, number, number] {
  const [rn, gn, bn] = [r / 255, g / 255, b / 255]
  const max = Math.max(rn, gn, bn)
  const min = Math.min(rn, gn, bn)
  const l = (max + min) / 2
  const d = max - min
  if (d === 0) return [0, 0, l]
  const s = d / (1 - Math.abs(2 * l - 1))
  const h = max === rn ? ((gn - bn) / d) % 6 : max === gn ? (bn - rn) / d + 2 : (rn - gn) / d + 4
  return [(h * 60 + 360) % 360, s, l]
}

/**
 * `color` lifted, keeping its hue and saturation, until it reads on a dark
 * panel. Colours already bright enough come back unchanged, so only the dark
 * ends of a ramp move and the middle still matches the map exactly.
 */
export function legibleOnDark(color: string): string {
  const c = rgb(color)
  if (luminance(c) >= MIN_INK_LUMINANCE) return color
  const [h, s, l] = rgbToHsl(c)
  let lo = l
  let hi = 1
  for (let i = 0; i < 20; i++) {
    const mid = (lo + hi) / 2
    if (luminance(hslToRgb(h, s, mid)) < MIN_INK_LUMINANCE) lo = mid
    else hi = mid
  }
  const [r, g, b] = hslToRgb(h, s, hi)
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`
}

/** `stops` with every colour passed through `legibleOnDark`. */
export function legibleStops(stops: ColorStop[]): ColorStop[] {
  return stops.map(s => ({ ...s, color: legibleOnDark(s.color) }))
}
