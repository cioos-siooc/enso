# El Niño 2026 tracker: monthly update

The story is a page in the OSTA front app:
[front/app/pages/stories/el-nino-2026.vue](../../front/app/pages/stories/el-nino-2026.vue),
served at `/stories/el-nino-2026` (dev: <http://localhost:9020/stories/el-nino-2026>).
Its images are in `front/public/story-assets/el-nino-2026/`, its measured data in
`front/app/data/stories/el-nino-2026.json`. This directory holds only the tools.

Edition 1 was also published as a standalone artifact,
<https://claude.ai/artifact/RHX9mAfX6exkUUysC97vbr>; that copy is frozen at
edition 1 and is not updated.

Run an update at the start of each month, once the previous month has closed in
OSTA (prod `/coverage` → `end` past the month's last day; land data lags ~2 days).
Each edition = the newest closed month of OSTA data + that month's news.

## 1. Measure

```bash
python3 stories/el-nino-2026/measure.py 2026-10   # public API, ~2 min
```

It writes the app's data file. The page reads two things from it directly: the
race chart (`race`) and the hero's frames and readings (`nino.nino34.months_2026`,
one hero frame per month listed there, so add the frame image too). Every other
number the page prints is in the prose or in the script's `tiles`, and comes
from this file's printout: Niño 3.4, 3 and 1+2 ranks, the three-month index
against its record, Paita's heatwave run and category days, the land cells,
BC's waters, global and Pacific ranks. **Print nothing that isn't in this file
or measured the same way.**

When the race chart's 2026 line reaches month 24, the event is over; stop
updating `race` and say so.

## 2. Screenshots (dev stack)

Screenshots come from the dev frontend (`localhost:9020`) because the camera
framing uses the dev-only `window.__map`. Check that dev has the month first.

```bash
# Playwright is not a repo dependency: install it in a scratch dir
cd <scratch> && npm i playwright --no-save
cp /Projects/enso/stories/el-nino-2026/shoot.mjs .
PATH=$HOME/.nvm/versions/node/v22.23.1/bin:$PATH \
  node shoot.mjs /Projects/enso/stories/el-nino-2026/shots.json <scratch>/raw
```

Before running, move every date in `shots.json` to the new month (`d=`, the
`frames` list for the hero, Paita's `d=YYYY-MM-last`). Then convert to WebP into
`front/public/story-assets/el-nino-2026/`: hero frames crop `(170, 0, 750, 504)`
into `hero/YYYY-MM-01.webp`, `indonesia` crops `(520, 87, 1440, 900)`, the rest
are full 1440×900. Look at every shot before using it.

## 3. News

Search the month's news: the CPC ENSO discussion (2nd Thursday), WMO updates,
Peru (anchoveta, ENFEN, rain), Ecuador and Galápagos, Indonesia and Australia
(fire, drought), the US West Coast, BC (ocean, salmon, winter), the global
temperature record (Copernicus), coral bleaching.

**Open each article and check every fact and quote against the page itself**
before adding it; a search summary is not a source. Leave out what can't be
opened (SeafoodSource 403s to fetchers) or dated.

## 4. Edit the page

All in `el-nino-2026.vue`:

- `edition`: number, month, data through, news checked, next update.
- `tiles`: the month's five numbers and their previous highs.
- The prose in each chapter: update its numbers. Move or add chapters as the
  story shifts (winter on BC's coast; coastal rain in Peru and Ecuador; the decline).
- `news`: add new items at the top of each chapter's list and keep the older
  ones, since it is a running record.
- `links` and the inline `storyLink(...)` calls: move every `d=` that should
  follow the month.
- `watch`: answer last month's items in the prose, write new ones.
- `log`: one line per edition.

Then check the page at desktop and phone width (no console errors, no
horizontal overflow), and lint: `npx eslint app/pages/stories` in the front
container.

## Known app issue

The land overlay's precipitation **% of normal** mode draws the driest bucket
(floored at 6% of normal) in the grey that means "too dry for a ratio".
The story uses **mm vs normal** for Indonesia until that is fixed.
