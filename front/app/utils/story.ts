/**
 * Helpers shared by the stories under pages/stories.
 */

/** A deep link into the app's own view; the keys are useUrlState's. */
export function storyLink(q: Record<string, string>): string {
  return `/?${new URLSearchParams(q).toString()}`
}

/** '+3.07' / '−0.46': a signed figure with a true minus sign. */
export function signed(v: number, digits = 2): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}`
}
