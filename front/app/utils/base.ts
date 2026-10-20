/**
 * A root-relative path under the app's base URL. Prod serves from `/`, where
 * this is the identity; the CI preview serves from `/enso/` on GitHub Pages,
 * where a bare `/osta-logo.svg` is a 404. NuxtLink and the router add the base
 * themselves — this is for plain `src`/`href` attributes.
 */
export function withAppBase(path: string): string {
  return useRuntimeConfig().app.baseURL.replace(/\/+$/, '') + path
}
