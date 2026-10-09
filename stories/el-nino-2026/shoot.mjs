// Screenshot the dev OSTA at a list of deep-link views.
// usage: node shoot.mjs shots.json outdir [name-filter]
//
// Per shot: query (the deep link), camera ({center, zoom} via the dev-only
// window.__map), storage (localStorage seed), actions, clip ('map' = the map
// pane, or {x,y,width,height}), hideOverlays, frames (dates stepped through the
// Pinia store, one screenshot each).
import { chromium } from 'playwright'
import fs from 'node:fs'

const [, , listPath, outDir, only] = process.argv
const shots = JSON.parse(fs.readFileSync(listPath, 'utf8')).filter(s => !only || s.name.includes(only))
fs.mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
})

const store = () => document.querySelector('#__nuxt').__vue_app__.config.globalProperties.$pinia._s.get('main')

async function settle(page, ms = 1500) {
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => new Promise((resolve) => {
    const m = window.__map
    if (!m || m.loaded()) return resolve()
    m.once('idle', resolve)
    setTimeout(resolve, 8000)
  }))
  await page.waitForTimeout(ms)
}

async function mapClip(page) {
  return page.evaluate(() => {
    const r = document.querySelector('.mapboxgl-canvas').closest('.relative.size-full.overflow-hidden').getBoundingClientRect()
    return { x: r.x, y: r.y, width: r.width, height: r.height }
  })
}

for (const s of shots) {
  const ctx = await browser.newContext({
    viewport: s.viewport ?? { width: 1440, height: 900 },
    deviceScaleFactor: s.scale ?? 1,
  })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript((kv) => {
    for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v)
  }, { 'enso.map.projection': 'globe', ...(s.storage ?? {}) })
  await page.goto(`http://localhost:9020/?${s.query}`, { waitUntil: 'networkidle', timeout: 120000 })
  await page.waitForFunction(() => window.__map && window.__map.isStyleLoaded !== undefined, null, { timeout: 60000 })
  await page.waitForTimeout(s.wait ?? 4000)
  if (s.camera) {
    await page.evaluate(c => window.__map.jumpTo(c), s.camera)
  }
  for (const a of s.actions ?? []) {
    if (a.click) await page.getByText(a.click, { exact: a.exact ?? true }).first().click()
    if (a.css) await page.locator(a.css).first().click()
    if (a.eval) await page.evaluate(a.eval)
    if (a.drag) {
      const [x1, y1, x2, y2] = a.drag
      await page.mouse.move(x1, y1); await page.mouse.down()
      await page.mouse.move(x2, y2, { steps: 12 }); await page.mouse.up()
    }
    await page.waitForTimeout(a.wait ?? 1500)
  }
  if (s.hideOverlays) {
    await page.addStyleTag({ content: '.mapboxgl-control-container,.mapboxgl-marker,.mapboxgl-popup{display:none!important}' })
    await page.evaluate(() => {
      const root = document.querySelector('.mapboxgl-canvas').closest('.relative.size-full.overflow-hidden')
      const pane = root.parentElement
      for (const el of pane.querySelectorAll('*')) {
        const canvas = root.querySelector('.mapboxgl-canvas')
        if (el.contains(root) || el.contains(canvas) || el.closest('.mapboxgl-map')) continue
        const pos = getComputedStyle(el).position
        if (pos === 'absolute' || pos === 'fixed') el.style.visibility = 'hidden'
      }
      for (const el of pane.parentElement.children) if (el !== pane && !el.contains(root)) el.style.visibility = 'hidden'
    })
  }
  await settle(page)
  const clip = s.clip === 'map' ? await mapClip(page) : s.clip
  if (s.frames) {
    fs.mkdirSync(`${outDir}/${s.name}`, { recursive: true })
    for (const d of s.frames) {
      await page.evaluate((date) => {
        const st = document.querySelector('#__nuxt').__vue_app__.config.globalProperties.$pinia._s.get('main')
        st.setDate(date)
      }, d)
      await page.waitForTimeout(400)
      await settle(page, 900)
      await page.screenshot({ path: `${outDir}/${s.name}/${d}.png`, clip })
    }
    console.log(s.name, `${s.frames.length} frames`, errors.length ? `ERRORS: ${errors.join(' | ')}` : 'ok')
  }
  else {
    await page.screenshot({ path: `${outDir}/${s.name}.png`, clip })
    console.log(s.name, errors.length ? `ERRORS: ${errors.join(' | ')}` : 'ok')
  }
  await ctx.close()
}
await browser.close()
void store
