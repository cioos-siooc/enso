"""Bucket spans, checked against the fixture the frontend's test also reads.

`shared/periods.py` and `front/app/utils/periods.ts` are two implementations of
one definition, and CLAUDE.md's "change one and change the other" used to be the
only thing holding them together. The fixture makes drift a failing test on
whichever side moved.
"""

import datetime as dt
import json

import pytest

from shared.periods import PERIODS, bucket_sql, span, start_of

from conftest import ROOT

CASES = json.loads((ROOT / "shared/testdata/periods_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['date']}-{c['period']}")
def test_span_matches_fixture(case):
    first, last = span(dt.date.fromisoformat(case["date"]), case["period"])
    assert (first.isoformat(), last.isoformat()) == (case["start"], case["end"])


def test_fixture_covers_every_period():
    assert {c["period"] for c in CASES} == set(PERIODS)


def test_weeks_start_on_monday():
    for day in range(14):
        date = dt.date(2026, 8, 17) + dt.timedelta(days=day)
        assert start_of(date, "weekly").weekday() == 0


def test_unknown_period_raises():
    with pytest.raises(ValueError):
        start_of(dt.date(2026, 1, 1), "yearly")
    with pytest.raises(ValueError):
        bucket_sql("yearly")
