/**
 * The land overlay's pure helpers: which layer a choice means, whether it can
 * be drawn on a given bucket, and how the precipitation ratio is printed.
 *
 * Pure so they can be tested without a store or a map. The store's getters are
 * thin wrappers over these.
 *
 * **The overlay is not a fourth ocean variable.** It is drawn over whichever
 * ocean variable is showing, with its own legend; the chart, stats and rankings
 * stay ocean. So a land choice is two independent picks — WHAT (tmax, tmin,
 * precipitation) and HOW (the value itself, or its departure from normal) — and this maps
 * the pair onto one of `domain.yml`'s seven `land_*` layers.
 */
import type { Period } from './periods'

/** The CPC variable a land layer is built from. */
export type LandSource = 'tmax' | 'tmin' | 'precip'

/**
 * The value itself, or its departure from the 1991-2020 normal. `anomaly` is
 * the source's default departure — a difference for temperature, a ratio for
 * precipitation — and `difference` asks for precipitation's in mm/day instead.
 * A temperature anomaly already is a difference, so only precipitation offers
 * the third mode (`landModesFor`).
 */
export type LandMode = 'value' | 'anomaly' | 'difference'

export type LandVariableName =
  | 'land_tmax' | 'land_tmin' | 'land_precip'
  | 'land_tmax_anom' | 'land_tmin_anom' | 'land_precip_ratio' | 'land_precip_anom'

/** Which archive a source's dates come from: temperature and rain publish apart. */
export type LandProduct = 'temp' | 'precip'

export const LAND_SOURCES: LandSource[] = ['tmax', 'tmin', 'precip']

/**
 * The layer a choice means.
 *
 * Precipitation's default anomaly is a RATIO — `land_precip_ratio`, drawn as
 * percent of normal — because a difference in millimetres cannot share one
 * scale between a desert and a monsoon; `difference` gives the millimetres
 * anyway (`land_precip_anom`), since how much water went missing is a question
 * the ratio cannot answer. The two temperatures are differences in degrees,
 * like the ocean's anomaly, under either departure mode.
 */
export function landLayerName(source: LandSource, mode: LandMode): LandVariableName {
  if (mode === 'value') return `land_${source}`
  if (source === 'precip') return mode === 'difference' ? 'land_precip_anom' : 'land_precip_ratio'
  return `land_${source}_anom`
}

/** The modes a source offers, in button order. */
export function landModesFor(source: LandSource): LandMode[] {
  return source === 'precip' ? ['value', 'anomaly', 'difference'] : ['value', 'anomaly']
}

/** `mode`, or the nearest one `source` offers: a difference is an anomaly. */
export function landModeFor(source: LandSource | null, mode: LandMode): LandMode {
  if (!source || landModesFor(source).includes(mode)) return mode
  return 'anomaly'
}

export function landProduct(source: LandSource): LandProduct {
  return source === 'precip' ? 'precip' : 'temp'
}

/** What `/coverage.land` reports; null when the land tables do not exist. */
export interface LandCoverage {
  temp: { days: number, start: string | null, end: string | null }
  precip: { days: number, start: string | null, end: string | null }
  /** Per layer: absolute always true, anomaly once its climatology is built. */
  layers: Partial<Record<LandVariableName, boolean>>
}

/**
 * Why a land layer cannot be drawn on this bucket, or null if it can.
 *
 * A reason rather than a boolean because the legend prints it: the layer is
 * REMOVED from the map when it cannot be drawn, not left on its last frame —
 * Mapbox's image source silently keeps the previous image on a 404, which would
 * show last week's rain under this week's date — and a layer that vanishes
 * without saying why reads as a bug.
 *
 * `bucketStart` is the bucket's first day and `bucketEnd` its last; a bucket is
 * drawable if any of it is covered, since a week at the archive's edge is
 * simply short.
 */
export function landUnavailableReason(
  layer: LandVariableName,
  meta: { periods: Period[], shortName?: string, source?: string | null } | undefined,
  coverage: LandCoverage | null | undefined,
  period: Period,
  bucketStart: string,
  bucketEnd: string,
): string | null {
  if (!coverage) return 'Land data is not loaded on this server'
  if (!meta) return 'Unknown land layer'
  if (!meta.periods.includes(period)) {
    return `${meta.shortName ?? 'This layer'} is shown ${meta.periods.join(' or ')} only`
  }
  if (coverage.layers[layer] === false) {
    return 'The 1991-2020 land climatology has not been built yet'
  }
  // Read off the layer's declared source, not its name: temperature and rain
  // publish on their own schedules and end on different days.
  const product = meta.source === 'precip' ? coverage.precip : coverage.temp
  if (!product.start || !product.end) return 'No land data has been ingested yet'
  if (bucketEnd < product.start || bucketStart > product.end) {
    return `No land data for this date (available ${product.start} to ${product.end})`
  }
  return null
}

/**
 * `log2_percent`: the rainfall ratio's value, printed.
 *
 * Stored as log2(actual / normal) so a halving and a doubling sit the same
 * distance from normal; shown as percent of normal so nobody has to read a
 * logarithm. -1 -> 50%, 0 -> 100%, +1 -> 200%.
 *
 * Rounded to a number of significant figures that suits the size: 12.5% keeps
 * its half, 1600% does not need one.
 */
export function formatLog2Percent(value: number): string {
  const pct = 100 * 2 ** value
  if (pct >= 100) return `${Math.round(pct)}%`
  if (pct >= 10) return `${Number(pct.toFixed(1))}%`
  return `${Number(pct.toFixed(2))}%`
}

/** The inverse, for a percent typed into the range control. NaN if unparseable. */
export function parseLog2Percent(text: string): number {
  const pct = Number(String(text).replace('%', '').trim())
  if (!Number.isFinite(pct) || pct <= 0) return Number.NaN
  return Math.log2(pct / 100)
}
