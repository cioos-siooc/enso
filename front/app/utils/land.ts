/**
 * The land overlay's pure helpers: which layer a choice means, whether it can
 * be drawn on a given bucket, and how the rainfall ratio is printed.
 *
 * Pure so they can be tested without a store or a map. The store's getters are
 * thin wrappers over these.
 *
 * **The overlay is not a fourth ocean variable.** It is drawn over whichever
 * ocean variable is showing, with its own legend; the chart, stats and rankings
 * stay ocean. So a land choice is two independent picks — WHAT (tmax, tmin,
 * rain) and HOW (the value itself, or its departure from normal) — and this maps
 * the pair onto one of `domain.yml`'s six `land_*` layers.
 */
import type { Period } from './periods'

/** The CPC variable a land layer is built from. */
export type LandSource = 'tmax' | 'tmin' | 'precip'

/** The value itself, or its departure from the 1991-2020 normal. */
export type LandMode = 'value' | 'anomaly'

export type LandVariableName =
  | 'land_tmax' | 'land_tmin' | 'land_precip'
  | 'land_tmax_anom' | 'land_tmin_anom' | 'land_precip_ratio'

/** Which archive a source's dates come from: temperature and rain publish apart. */
export type LandProduct = 'temp' | 'precip'

export const LAND_SOURCES: LandSource[] = ['tmax', 'tmin', 'precip']

/**
 * The layer a choice means.
 *
 * Rain's anomaly is a RATIO, not a difference — `land_precip_ratio`, drawn as
 * percent of normal — because a difference in millimetres cannot share one
 * scale between a desert and a monsoon. The two temperatures are differences in
 * degrees, like the ocean's anomaly.
 */
export function landLayerName(source: LandSource, mode: LandMode): LandVariableName {
  if (mode === 'value') return `land_${source}`
  return source === 'precip' ? 'land_precip_ratio' : `land_${source}_anom`
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
