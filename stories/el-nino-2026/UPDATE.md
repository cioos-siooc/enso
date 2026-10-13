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

It writes the app's data file, and the page reads it directly in three places:
the race chart (`race`), the opening scrub (`nino.nino34.months_2026`: its last
month is the edition's month, the date every "now" step shows, and its values
are the scrub's readout), and the map cards' readouts (Paita's "Beyond extreme"
days, Isabela, Piura, Palangka Raya, San Diego, BC's waters, the global ocean).
Everything else it prints goes into the prose by hand: Niño 3.4, 3 and 1+2
ranks, the three-month index against its record, Paita's heatwave run, the land
cells, Pacific ranks. **Print nothing that isn't in this file or measured the
same way.**

When the race chart's 2026 line reaches month 24, the event is over; stop
updating `race` and say so.

## 2. No screenshots

The page is a `<StoryScroll>` story (docs/frontend.md, "Story pages"): every
map is the live app, drawn from each step's `view`, and every card links to the
same view. There is nothing to shoot. `shots.json` and `shoot.mjs` are left
from the screenshot edition and are not used.

Do look at the result: scroll the page in the dev stack, or screenshot a step
per section in headless Chromium (docs/testing.md), at desktop and phone width.

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

- `EDITION`: number, month, data through, news checked, next update.
- `steps`: update the numbers in each card's `body`. Steps that show "now" take
  `MONTH` / `DAY` and move by themselves; dates in the past (1997, 2016) stay.
  Move or add steps as the story shifts (winter on BC's coast; coastal rain in
  Peru and Ecuador; the decline). Canadian examples and sources first, DFO's
  State of the Pacific Ocean reports among them.
- News: a new article is a `REFERENCES` entry (`short` carries the outlet and
  date) plus a sentence, quote or readout on the card it belongs to, with the
  key in that card's `refs`. Keep older items while they still tell the story;
  the log records what changed.
- Photos: only cleared ones (US federal and NASA images are public domain; DFO
  and press photos are not), re-encoded to WebP in
  `front/public/story-assets/el-nino-2026/img/`, with `credit` and `href`.
- `WATCH`: answer last month's items in the cards, write new ones.
- `LOG`: one line per edition.

Then check the page at desktop and phone width (no console errors, no
horizontal overflow, no card taller than the screen), and lint:
`npx eslint app/pages/stories` in the front container.

## Known app issue

The land overlay's precipitation **% of normal** mode draws the driest bucket
(floored at 6% of normal) in the grey that means "too dry for a ratio".
The story uses **mm vs normal** for Indonesia until that is fixed.
