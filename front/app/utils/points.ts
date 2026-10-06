/**
 * The two pins of a two-point selection, shared by the map, the chart and the
 * chip row under the time bar.
 *
 * One definition of each pin's colour, because the colour is the only thing
 * that ties a line on the chart to a pin on the map. Neither is amber (the
 * chart's `MAP` marker) nor sky (`CMP`), and neither sits on a value ramp: in
 * two-point mode the lines are coloured by WHICH point, not by value.
 */
export const PIN_COLORS = { a: '#05df72', b: '#c084fc' } as const

export type PinKey = keyof typeof PIN_COLORS

/**
 * A cell as hemispheres, not signed degrees.
 *
 * Cells come back on the 0-360 convention the database stores, so most of this
 * box's longitudes are above 180 and have to be unwrapped for display. Printing
 * the signed result as "°E" gave `-168.125°E`, which is a compass direction
 * contradicting its own sign.
 */
export function formatCell(cell: { lat: number, lon: number } | undefined | null): string {
  if (!cell) return ''
  const lon = ((cell.lon + 180) % 360) - 180
  return `${Math.abs(cell.lat).toFixed(2)}°${cell.lat < 0 ? 'S' : 'N'}, `
    + `${Math.abs(lon).toFixed(2)}°${lon < 0 ? 'W' : 'E'}`
}
