/**
 * Camera vocabulary shared by the map host, both field maps and the stories.
 *
 * Kept out of the components so a story step can name a view without importing
 * a `.vue` file, and so the globe's opening view has one definition.
 */

export type ProjectionName = 'globe' | 'mercator'

export interface CameraView {
  center: [number, number]
  zoom: number
  bearing?: number
  pitch?: number
}

/**
 * Where the globe opens: zoomed out over the whole basin, the default Nino 3
 * box in view.
 *
 * A globe cannot be framed with `fitBounds` — half the box is behind the limb at
 * any zoom that fits it — so it gets a centre and a zoom instead. Mercator keeps
 * fitting the full box, which is the shape it is good at.
 */
export const GLOBE_VIEW: CameraView = { center: [-130, 15], zoom: 2 }

type Box = { west: number, south: number, east: number, north: number }

/**
 * Where Mercator opens: the Pacific basin, not the whole frame.
 *
 * The frame is the whole world to +/-85 degrees, and fitting that on a flat map
 * spends half the pane on the polar stretch and splits the Pacific at the
 * dateline. The `pacific` region is the basin the ribbon reports on, so it is
 * the opening view; its longitudes are unwrapped (100..290), which `fitBounds`
 * takes as a box across the antimeridian. Falls back to the frame.
 */
export function mercatorOpenBounds(
  regions: Array<{ key: string, lat: [number, number], lon: [number, number] }> | undefined,
  frame: Box,
): [[number, number], [number, number]] {
  const r = regions?.find(r => r.key === 'pacific')
  return r
    ? [[r.lon[0], r.lat[0]], [r.lon[1], r.lat[1]]]
    : [[frame.west, frame.south], [frame.east, frame.north]]
}
