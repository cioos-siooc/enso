// Screenshots the built front page for the `preview` CI job. Playwright is not a
// dependency of front/ — the job installs it next to a copy of this file.
//
// The map is screenshotted, never read back off its canvas: Mapbox runs with
// `preserveDrawingBuffer: false`, so drawImage() of it is always blank
// (docs/testing.md).
import { chromium } from 'playwright'

const base = process.env.PREVIEW_URL || 'http://localhost:3000'
const out = process.env.PREVIEW_OUT || 'screenshots'

const viewports = [
  { name: 'desktop', width: 1600, height: 1000 },
  { name: 'phone', width: 390, height: 844, isMobile: true, hasTouch: true },
]

// Headless Chromium draws the Mapbox canvas under SwiftShader (docs/testing.md).
const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
})

for (const { name, width, height, ...rest } of viewports) {
  const page = await browser.newPage({ viewport: { width, height }, ...rest })
  // A returning visitor's view: the first-visit card (useGuide.ts) covers the map.
  await page.addInitScript(() => localStorage.setItem('enso.intro.seen', '1'))
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log(`[${name}] console: ${msg.text()}`)
  })
  page.on('pageerror', (err) => console.log(`[${name}] pageerror: ${err.message}`))

  await page.goto(base, { waitUntil: 'load' })
  await page.waitForSelector('.mapboxgl-canvas', { timeout: 60_000 })
  // Basemap tiles and the first value frame arrive after `load`; the prod API
  // and Mapbox are both remote, so give them a quiet network and then a margin.
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {})
  await page.waitForTimeout(5_000)

  await page.screenshot({ path: `${out}/${name}.png` })
  console.log(`wrote ${out}/${name}.png`)
  await page.close()
}

await browser.close()
