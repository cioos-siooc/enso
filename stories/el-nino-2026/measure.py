"""Read every number the El Nino 2026 story prints, for one closed month.

    python3 measure.py 2026-09   # -> front/app/data/stories/el-nino-2026.json
    python3 measure.py 2026-10 --api http://localhost:9021

Reads the public API by default, so the numbers are the ones a reader who
follows the story's links will see. Prints a summary to check the narrative
against; the page (front/app/pages/stories/el-nino-2026.vue) itself reads only
`race` and Nino 3.4's `months_2026` from the file.
"""
import argparse
import calendar
import json
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

API = "https://mhw-api.cioospacific.ca"
# The public host refuses urllib's default User-Agent with a 403.
HEADERS = {"user-agent": "osta-story-measure/1.0"}

# The three events the race chart draws, as (label, first year). Each line runs
# 24 months from January of that year.
EVENTS = [("1997–98", 1997), ("2015–16", 2015), ("2026–27", 2026)]

# Cells named in the story. Keep in step with the deep links in index.html.
POINTS = {
    "paita": (-5.07, -81.28),
    "chimbote": (-9.07, -78.78),
    "callao": (-12.07, -77.28),
    "isabela": (-0.52, -91.72),
    "santa_cruz": (-0.92, -90.28),
    "santa_elena": (-2.22, -81.08),
    "san_diego": (32.72, -117.43),
}
LAND = {
    "palangka_raya": (-2.21, 113.92),
    "palembang": (-2.98, 104.76),
    "pontianak": (-0.03, 109.33),
    "piura": (-5.19, -80.63),
    "quininde": (0.33, -79.47),
    "kamloops": (50.67, -120.33),
    "vancouver": (49.25, -123.10),
}


def get(path, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}" if params else f"{API}{path}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=300) as r:
        return json.load(r)


def post(path, body):
    req = urllib.request.Request(f"{API}{path}", json.dumps(body).encode(),
                                 {"content-type": "application/json", **HEADERS})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def rows(d):
    return [(a, b) for a, b in zip(d["dates"], d["values"]) if b is not None]


def r2(x, n=2):
    return None if x is None else round(x, n)


def region_month(key, year, month, variable="anom"):
    rk = get(f"/region/{key}/monthlyRanking", variable=variable)
    col = rk["months"][str(month)]
    me = next(e for e in col if e["year"] == year)
    return {"value": r2(me["mean"]), "rank": me["rank"], "of": len(col),
            "next": [(e["year"], r2(e["mean"])) for e in col if e["year"] != year][:2]}


def main():
    global API
    ap = argparse.ArgumentParser()
    ap.add_argument("month", help="the closed month, YYYY-MM")
    ap.add_argument("--api", default=API)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "front/app/data/stories/el-nino-2026.json"))
    a = ap.parse_args()
    API = a.api.rstrip("/")
    y, m = map(int, a.month.split("-"))
    first = f"{y:04d}-{m:02d}-01"
    last = f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
    out = {"edition": {"month": a.month, "through": last}}

    # Nino regions: this month, its rank, and the pre-2026 record month.
    nino = {}
    for key in ("nino34", "nino3", "nino4", "nino12"):
        series = rows(get(f"/region/{key}", variable="anom", period="monthly", end=last))
        pre = [r for r in series if r[0] < "2026-01-01"]
        rec = max(pre, key=lambda r: r[1])
        nino[key] = {**region_month(key, y, m),
                     "record_before_2026": [rec[0][:7], r2(rec[1])],
                     "months_2026": [(d[:7], r2(v)) for d, v in series if d >= "2026-01-01"]}
    # The three-month index, complete months only, as /state builds it.
    s34 = rows(get("/region/nino34", variable="anom", period="monthly", end=last))
    run3 = [(s34[i][0][:7], sum(v for _, v in s34[i - 1:i + 2]) / 3) for i in range(1, len(s34) - 1)]
    pre3 = max((r for r in run3 if r[0] < "2026-01"), key=lambda r: r[1])
    out["oni_style"] = {"latest_centre": run3[-1][0], "latest": r2(run3[-1][1]),
                        "record_before_2026": [pre3[0], r2(pre3[1])]}
    daily = rows(get("/region/nino34", variable="anom", end=last))
    pre_d = max((r for r in daily if r[0] < "2026-01-01"), key=lambda r: r[1])
    month_d = max((r for r in daily if first <= r[0] <= last), key=lambda r: r[1])
    out["nino34_daily"] = {"month_max": [month_d[0], r2(month_d[1])],
                           "record_before_2026": [pre_d[0], r2(pre_d[1])]}
    out["nino"] = nino

    # The race chart: 24 months from January of each event's first year.
    race = []
    by_month = dict((d[:7], v) for d, v in s34)
    for label, y0 in EVENTS:
        vals = []
        for i in range(24):
            yy, mm = y0 + i // 12, i % 12 + 1
            vals.append(r2(by_month.get(f"{yy:04d}-{mm:02d}")))
        race.append({"label": label, "values": vals})
    out["race"] = race

    # Basin and globe: anomaly rank, heatwave extent rank.
    out["regions"] = {k: {"anom": region_month(k, y, m), "mhw_extent": region_month(k, y, m, "mhw")}
                      for k in ("global", "pacific", "pacific_bioregions", "ne_pacific")}

    # Cells: the month's anomaly and rank, heatwave run, category days.
    pts = {}
    for name, (lat, lon) in POINTS.items():
        rk = post("/monthlyRanking", {"lat": lat, "lon": lon, "variable": "anom"})["months"][str(m)]
        me = next(e for e in rk if e["year"] == y)
        mhw = post("/timeseries", {"lat": lat, "lon": lon, "variable": "mhw", "end": last})
        cats = Counter(int(v) for d, v in rows(mhw) if first <= d <= last)
        pts[name] = {"anom": r2(me["mean"]), "rank": me["rank"], "of": len(rk),
                     "next": [(e["year"], r2(e["mean"])) for e in rk if e["year"] != y][:1],
                     "run": mhw["events"]["current"], "longest": mhw["events"]["longest"],
                     "category_days": dict(sorted(cats.items()))}
    out["points"] = pts

    # Land: the month's precipitation (mm/day, mm/day vs normal) and Tmax/Tmin anomaly.
    land = {}
    for name, (lat, lon) in LAND.items():
        rec = {}
        for layer in ("land_precip", "land_precip_anom", "land_tmax_anom", "land_tmin_anom"):
            d = post("/landTimeseries", {"lat": lat, "lon": lon, "variable": layer,
                                         "period": "monthly", "start": first, "end": last})
            rec["surface"] = d.get("surface")
            rec[layer] = r2(d["values"][0], 1) if d["values"] else None
        land[name] = rec
    out["land"] = land

    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
