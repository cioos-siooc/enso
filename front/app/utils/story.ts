/**
 * Helpers shared by the stories under pages/stories.
 */
import type { View } from '~/stores/main'

/** A deep link into the app's own view; the keys are useUrlState's. */
export function storyLink(q: Record<string, string>): string {
  return `/?${new URLSearchParams(q).toString()}`
}

/** '+3.07' / '−0.46': a signed figure with a true minus sign. */
export function signed(v: number, digits = 2): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}`
}

// --- The scrolling map story (components/story/Scroll.vue) -------------------

/** Where the camera flies for a step. Longitudes signed, as Mapbox takes them. */
export interface StoryCamera {
  center: [number, number]
  zoom: number
  pitch?: number
  bearing?: number
}

/** A source, linked by name under the card that uses it. */
export interface StoryReference {
  /** What the link says, e.g. 'DFO, State of the Pacific Ocean 2015'. */
  short: string
  /** The full citation, shown as the link's tooltip. */
  full: string
  url: string
}

/**
 * One step of a scrolling map story: a card (or, centred, a title over the
 * map), the app view the map switches to, and where the camera goes.
 */
export interface StoryStep {
  /** Unique within the story. */
  id: string
  eyebrow: string
  title: string
  /** Paragraphs, plain text. */
  body: string[]
  /**
   * The whole view, every time: compare, B and the land overlay included
   * (spread `STORY_BASE`), so scrolling back up restores a step exactly.
   */
  view: View
  camera: StoryCamera
  /** `center` puts the step's type on the map with no card or date: titles, intro, outro. */
  align?: 'left' | 'right' | 'center'
  /** A big number that counts up when the step arrives. */
  readout?: { value: number, digits: number, unit: string, prefix?: string, signed?: boolean, label: string, color: string }
  quote?: { text: string, cite: string }
  /**
   * A page slot rendered in the card under the body, for what the map cannot
   * show: a chart, a table. The page fills `<template #name>`.
   */
  figure?: string
  /** A wider card, for a `figure` that needs the room. */
  wide?: boolean
  /**
   * A line drawn on the map for this step only, with a dot at each vertex: a
   * survey line, a ship's track. A single vertex marks a place: a dot and its label.
   * Not part of the view, so its link leaves it off.
   */
  line?: { coords: [lon: number, lat: number][], label?: string }
  /** Across the top of the card, credited and linked to where it came from. */
  photo?: { src: string, alt: string, credit: string, href: string }
  /** Keys into the story's references, linked under the card. */
  refs?: string[]
  /**
   * Monthly frames from `from` to `to`, run by scrolling through the step.
   * The step is several screens tall and its card stays pinned meanwhile.
   * `values`, one per month from `from`, makes the readout follow the clock.
   */
  scrub?: { from: string, to: string, values?: number[] }
  /** The last step: the page's `#outro` slot. */
  outro?: boolean
  /** Leave off the card's "Open this view in OSTA" link. */
  noLink?: boolean
}

/** What every step's view starts from, so nothing leaks from the step before. */
export const STORY_BASE = { compareDate: null, point2: null, region2: null, landLayer: null } satisfies View

/** A cell as useUrlState writes it: `48.03,-127.97`. */
function urlPoint(p: { lat: number, lon: number }): string {
  const lon = ((p.lon + 180) % 360 + 360) % 360 - 180
  return `${p.lat.toFixed(2)},${lon.toFixed(2)}`
}

/** The app link that opens `view`, in useUrlState's keys. */
export function viewLink(view: View): string {
  const q: Record<string, string> = {}
  if (view.variable) q.v = view.variable
  if (view.period) q.p = view.period
  if (view.date) q.d = view.date
  if (view.compareDate) q.c = view.compareDate
  if (view.region) q.r = view.region
  else if (view.point) q.at = urlPoint(view.point)
  if (view.region2) q.r2 = view.region2
  else if (view.point2) q.at2 = urlPoint(view.point2)
  if (view.landLayer) {
    q.land = view.landLayer
    if (view.landMode) q.lm = view.landMode
  }
  return storyLink(q)
}
