"""The API's own decisions, without a server or a database.

`modules.*` import `shared` and a ClickHouse client factory but no FastAPI, so
they run in the process environment CI already builds. The queries are
exercised against the real database by the endpoints; what is pinned here is
the arithmetic around them.
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from modules import state, timeseries  # noqa: E402


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class CountingClient:
    def __init__(self, rows):
        self.rows, self.calls = rows, 0

    def query(self, sql, parameters=None):
        self.calls += 1
        return FakeResult(self.rows)


def test_seasons_are_labelled_by_their_middle_month(monkeypatch):
    # Twelve complete months ending in August, then a partial September.
    months = [dt.date(2026, m, 1) for m in range(1, 10)]
    values = [0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]
    days = [31, 28, 31, 30, 31, 30, 31, 31, 10]
    monkeypatch.setattr(state, "_monthly_nino34", lambda: list(zip(months, values, days)))
    out = state.enso_state()
    # The newest complete season is Jun-Jul-Aug, labelled by July: JJA.
    assert out["season"] == "JJA 2026"
    assert out["index"] == round((0.8 + 1.0 + 1.2) / 3, 2)
    assert out["phase"] == "el_nino" and out["strength"] == "moderate"
    # MJJ, JJA cross 0.5; AMJ (0.6) too: three seasons, not yet an episode.
    assert out["seasons"] == 3 and out["episode"] is False
    assert out["latestMonth"]["partial"] is True and out["latestMonth"]["days"] == 10


def test_a_run_stops_at_a_sign_change():
    assert state._run_length([0.6, -0.7, 0.8, 0.9], 1) == 2
    assert state._run_length([-0.6, -0.7, -0.5], -1) == 3
    assert state._run_length([0.6, 0.4], 1) == 0


def test_only_the_archive_edges_are_partial():
    lo, hi = dt.date(1985, 1, 1), dt.date(2026, 10, 3)
    assert timeseries._partial_months(lo, hi) == {(2026, 10)}
    assert timeseries._partial_years(lo, hi) == {2026}
    assert timeseries._partial_months(dt.date(1985, 1, 2), dt.date(2026, 9, 30)) == {(1985, 1)}


def test_mhw_is_complete_within_a_days_lag():
    assert timeseries._mhw_complete(15000, 14999)
    assert not timeseries._mhw_complete(15000, 14000)
    assert not timeseries._mhw_complete(0, 0)


def test_the_climatology_count_is_read_until_it_is_complete(monkeypatch):
    monkeypatch.setattr(timeseries, "_clim_keys_seen", 0)
    partial = CountingClient([(300,)])
    monkeypatch.setattr(timeseries, "client", lambda: partial)
    assert timeseries._clim_keys() == 300
    assert timeseries._clim_keys() == 300
    assert partial.calls == 2          # a load in progress is re-read
    full = CountingClient([(366,)])
    monkeypatch.setattr(timeseries, "client", lambda: full)
    timeseries._clim_keys(), timeseries._clim_keys()
    assert full.calls == 1             # and a complete one is not


def test_the_archive_state_is_held_for_its_ttl(monkeypatch):
    monkeypatch.setattr(timeseries, "_archive_state_cache", None)
    reads = []
    monkeypatch.setattr(timeseries, "_read_archive_state", lambda: reads.append(1) or {"n": len(reads)})
    clock = iter([0.0, 10.0, 61.0])
    monkeypatch.setattr(timeseries.time, "monotonic", lambda: next(clock))
    assert timeseries._archive_state() == {"n": 1}
    assert timeseries._archive_state() == {"n": 1}   # 10 s later: cached
    assert timeseries._archive_state() == {"n": 2}   # past the TTL: re-read
