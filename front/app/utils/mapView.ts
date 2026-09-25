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
