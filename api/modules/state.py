"""The one-line answer: what the Pacific is doing today.

Everything else in this API answers a question the visitor has already framed —
this cell, that region, this date. This module answers the question they have
not framed yet, which is the one a first-time visitor actually arrives with:
*is anything happening out there right now?* It is what the header ribbon reads,
and it is deliberately the only endpoint that decides what is worth saying rather
than serving what was asked for.

One finding: the **ENSO state**, from the Nino 3.4 anomaly. See `enso_state`
for why this is ONI-*style* and not the ONI. It comes off `region_daily`, so the
endpoint is a few hundred rows and runs in milliseconds.

There used to be a second, the Pacific's marine heatwave extent against its
1991-2020 mean for the date. It was removed because that mean is not a normal:
NOAA's heatwave threshold is a fixed 1985-2012 90th percentile, so in a warming
ocean the extent trends upward (~10% averaged over 1985-2012, ~14% over
1991-2020, ~28% over 2014-2025) and any period's average is one point on a
rising series. The key stays `null` in the payload so an older cached frontend
does not break.
"""

from __future__ import annotations

import datetime as dt

from shared.domain import regions, variable

from . import roni
from .clickhouse_helpers import DATABASE, client
from .timeseries import MMDD_SQL, data_through

# The region whose anomaly defines the ENSO state. Nino 3.4 is the box the ONI is
# computed over and the one this repo is named for.
ENSO_REGION = "nino34"

# NOAA's ENSO threshold, on the 3-month running mean of the Nino 3.4 anomaly.
THRESHOLD = 0.5

# How many consecutive overlapping seasons past the threshold make an *episode*
# rather than merely *conditions*. NOAA's definition, and the distinction is
# worth keeping: conditions are what is measured this season, an episode is a
# claim about a run of them.
EPISODE_SEASONS = 5

# |index| bands. NOAA publishes these for episodes; used here to put a word next
# to a number so the ribbon reads without a legend.
_STRENGTH = ((2.0, "very strong"), (1.5, "strong"), (1.0, "moderate"), (0.0, "weak"))

# Three-letter season names, indexed by the season's MIDDLE month minus one.
#
# A season spans the month before its middle and the month after, so index 0 is
# January's season, DJF. Getting this off by one is silent and plausible: every
# label is still a real season name, just the neighbouring one, and "AMJ" beside
# an index built from May, June and July reads perfectly well.
_SEASONS = (
    "DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ",
    "JJA", "JAS", "ASO", "SON", "OND", "NDJ",
)

# The climatological baseline, matching `sst_clim` and every anomaly this API
# serves. Reported in the payload so the ribbon can name it rather than assume.
#
# Read off `anom`'s own declaration rather than restated, because the dashboard
# has TWO baselines — `mhw`'s is NOAA's 1985-2012 90th percentile — and a
# hard-coded string here is how the wrong one gets printed beside the right
# number. `domain.yml` is the single definition; see `shared.domain.Baseline`.
BASELINE = variable("anom").baseline.period


def _through_params(key: str, column: str = "date") -> tuple[str, dict]:
    """The `data_through()` bound the rollup read takes, as SQL and params.

    Without it the ribbon would report a date the rest of the dashboard does not
    serve yet, one `run` has rolled up from SST alone.
    """
    through = data_through()
    if through is None:
        return "", {"key": key}
    return f" AND {column} <= %(through)s", {"key": key, "through": through}


def _monthly_nino34() -> list[tuple[dt.date, float, int]]:
    """(month, mean anomaly, days) for Nino 3.4, over the whole archive.

    Straight off the two rollups, the same pair `_region_ranking_source` reads:
    `region_daily.mean_sst_clim` minus `region_clim.mean_clim` for the date's
    MMDD. Per day and not per month, because the identity
    `mean(sst - clim) == mean(sst) - mean(clim)` holds over cells, not over
    calendar spans — a month straddling the ice edge's seasonal move must still
    subtract the climatology that matches each day.
    """
    bound, params = _through_params(ENSO_REGION, "d.date")
    return [
        (month, float(value), int(n))
        for month, value, n in client().query(
            f"""
            SELECT toStartOfMonth(d.date) AS month,
                   avg(d.mean_sst_clim - c.mean_clim) AS anom,
                   count() AS n
            FROM {DATABASE}.region_daily AS d FINAL
            INNER JOIN {DATABASE}.region_clim AS c FINAL
                ON c.region = d.region
               AND c.mmdd = {MMDD_SQL.format(d="d.date")}
            WHERE d.region = %(key)s AND isFinite(d.mean_sst_clim){bound}
            GROUP BY month ORDER BY month
            """,
            parameters=params,
        ).result_rows
    ]


def _days_in_month(month: dt.date) -> int:
    return ((month.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - month).days


def _strength(index: float) -> str:
    magnitude = abs(index)
    for floor, word in _STRENGTH:
        if magnitude >= floor:
            return word
    return "weak"


def _run_length(seasons: list[float], sign: int) -> int:
    """How many seasons, counting back from the newest, stay past the threshold.

    Same sign throughout: a run that flips from El Nino to La Nina is two runs,
    which is what makes this the episode test rather than a count of anything
    unusual.
    """
    n = 0
    for value in reversed(seasons):
        if value * sign < THRESHOLD:
            break
        n += 1
    return n


HISTORY = 24


def _history(seasons: list[tuple[dt.date, float]]) -> list[dict]:
    noaa = {r["middle"]: r["value"] for r in roni.seasons() or []}
    return [
        {
            "season": f"{_SEASONS[middle.month - 1]} {middle.year}",
            "middle": str(middle),
            "osta": round(value, 2),
            "noaa": noaa.get(str(middle)),
        }
        for middle, value in seasons[-HISTORY:]
    ]


def enso_state() -> dict | None:
    """The ENSO phase, ONI-style, from the Nino 3.4 anomaly.

    **This is not NOAA's index, and the payload says so.** Since February 2025
    NOAA rates ENSO with its Relative Oceanic Nino Index (RONI): the Nino 3.4
    anomaly minus the tropical-mean anomaly, rescaled, so warming the whole
    tropics shares is taken out. This archive carries one fixed 1991-2020
    climatology and subtracts nothing, so in a year when the tropics are warm
    the index here runs well above NOAA's (+2.65 against +1.69 for JAS 2026).
    NOAA's own number rides along as `noaa`, read from CPC's file. Everything else is NOAA's: the
    three-month overlapping seasons, the +/-0.5 degC threshold, the five
    consecutive seasons that separate an *episode* from *conditions*, and the
    strength bands.

    The distinction is reported rather than smoothed over -- `official: False`
    and `baseline` are in the payload -- because a dashboard that quietly
    published a number under the ONI's name and thresholds would be wrong in the
    one way nobody would check.

    Seasons are built from **complete calendar months only**. The month in
    progress is a mean over however many days have landed and would drag a
    running mean that is supposed to be three whole months; it is reported
    separately as `latestMonth`, flagged partial, since it is also the most
    interesting number on the page.
    """
    monthly = _monthly_nino34()
    if len(monthly) < 3:
        return None

    latest_month, latest_value, latest_days = monthly[-1]
    partial = latest_days < _days_in_month(latest_month)
    complete = monthly[:-1] if partial else monthly

    if len(complete) < 3:
        return None

    # Overlapping 3-month means, each labelled by its middle month.
    seasons = [
        (complete[i + 1][0], (complete[i][1] + complete[i + 1][1] + complete[i + 2][1]) / 3)
        for i in range(len(complete) - 2)
    ]
    middle, index = seasons[-1]
    values = [v for _, v in seasons]

    if index >= THRESHOLD:
        phase, sign = "el_nino", 1
    elif index <= -THRESHOLD:
        phase, sign = "la_nina", -1
    else:
        phase, sign = "neutral", 0

    run = _run_length(values, sign) if sign else 0

    # Where the month in progress sits among every other instance of that
    # calendar month. Folded from `monthly` in Python rather than asked of
    # `_ranked_months`, because it is one number out of a list already in hand
    # and the ranking endpoint would re-read the rollup to produce forty-two.
    same_month = [v for m, v, _ in monthly if m.month == latest_month.month]
    warmer = sum(1 for v in same_month if v > latest_value)

    return {
        "region": ENSO_REGION,
        "label": regions()[ENSO_REGION].label,
        "phase": phase,
        # Only meaningful once there is a phase; a "weak neutral" is not a thing.
        "strength": _strength(index) if sign else None,
        "index": round(index, 2),
        "season": f"{_SEASONS[middle.month - 1]} {middle.year}",
        "seasonEnd": str(middle),
        # Consecutive overlapping seasons at or past the threshold, same sign.
        "seasons": run,
        # NOAA's five-season rule: below it these are *conditions*, not an
        # episode. The ribbon's wording turns on this.
        "episode": run >= EPISODE_SEASONS,
        "latestMonth": {
            "month": str(latest_month),
            "value": round(latest_value, 2),
            "days": latest_days,
            "partial": partial,
            # Among the same calendar month in every other year. This is the
            # line that turns a number into a finding: +2.74 means little, and
            # "the warmest August in 42 years" means a great deal.
            "rank": warmer + 1,
            "of": len(same_month),
        },
        "threshold": THRESHOLD,
        "baseline": BASELINE,
        # Not NOAA's index. See the docstring.
        "official": False,
        # NOAA's official index for its newest season, shown beside this one.
        # None when CPC's file could not be read; the ribbon then omits it.
        "noaa": roni.latest(),
        # The last HISTORY seasons of both, for the popover's chart. `noaa` is
        # null for a season CPC has not published yet.
        "history": _history(seasons),
    }


def pacific_state() -> dict:
    """The ENSO finding, or None with fewer than three months of rollup.

    `heatwave` is always None; see the module docstring for why it was removed.
    """
    return {"enso": enso_state(), "heatwave": None}
