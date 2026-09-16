"""`CRW.cli check`'s verdicts, against a fake client with canned answers.

The SQL is exercised against the real database by running the command; what is
pinned here is the part that decides pass or fail.
"""

import datetime as dt

from CRW import checks


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    """Answers each query with the first canned response whose key it contains."""

    def __init__(self, answers):
        self.answers = answers

    def query(self, sql, parameters=None):
        for needle, rows in self.answers:
            if needle in sql:
                return FakeResult(rows(parameters) if callable(rows) else rows)
        raise AssertionError(f"unexpected query: {sql}")


def test_unrepaired_leap_day_fails_and_repaired_passes():
    since, until = dt.date(2023, 1, 1), dt.date(2026, 8, 30)
    bad = FakeClient([("countIf(cat = 5)", [(dt.date(2024, 2, 29), 2_023_689)])])
    good = FakeClient([("countIf(cat = 5)", [(dt.date(2024, 2, 29), 1_612)])])
    assert checks.check_leap_days(bad, since, until).level == "fail"
    assert checks.check_leap_days(good, since, until).level == "ok"


def test_window_without_a_leap_day_is_skipped():
    client = FakeClient([])
    assert checks.check_leap_days(client, dt.date(2026, 7, 1), dt.date(2026, 8, 30)).level == "skip"


def test_empty_mhw_table_behind_a_full_status_table_fails():
    client = FakeClient([
        ("uniqExact(date)", [(15217,)]),
        ("system.tables", [(0,)]),
    ])
    assert checks.check_mhw_table_matches_status(client).level == "fail"


def test_region_with_no_heatwave_ever_fails():
    client = FakeClient([
        ("GROUP BY region", [("nino34", 15217, 10096), ("pacific_bioregions", 15217, 0)]),
        ("mhw_area_frac = 0", [(30, 0)]),
    ])
    levels = {r.name: r.level for r in checks.check_rollup_mhw(client, dt.date(2026, 8, 30))}
    assert levels["rollup.mhw.nino34"] == "ok"
    assert levels["rollup.mhw.pacific_bioregions"] == "fail"


def test_stale_archive_fails():
    client = FakeClient([("FINAL WHERE status", [(dt.date(2026, 8, 30),)])])
    fresh = checks.check_freshness(client, dt.date(2026, 8, 31), stale_after=3)
    stale = checks.check_freshness(client, dt.date(2026, 9, 16), stale_after=3)
    assert {r.level for r in fresh} == {"ok"}
    assert {r.level for r in stale} == {"fail"}
