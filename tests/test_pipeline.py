"""The pipeline's pure decisions: what a run covers, what counts as current,
which buckets are closed, and the bytes a daily insert sends.

The SQL and the downloads are exercised by running the commands; these pin the
parts that decide what gets done.
"""

import datetime as dt

import numpy as np
import pytest

from shared.ch import ROW_BINARY, row_binary
from shared.domain import gx_sql

from CRW import cli, imaging, status


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    def __init__(self, last: dict[str, dt.date | None]):
        self.last = last

    def query(self, sql, parameters=None):
        table = next(t for t in self.last if f".{t} " in sql)
        return FakeResult([(self.last[table],)])


def _row(**kw):
    return {"status": status.STATUS_SUCCESS, "remote_size": 100, "remote_modified": "Mon", **kw}


def test_row_binary_round_trips():
    columns = ["date", "gy", "gx", "sst_raw", "has_clim"]
    days = [
        (np.array([1, 2], "uint16"), np.array([3, 4], "uint16"),
         np.array([-5, 2500], "int16"), np.array([1, 0], "uint8")),
        (np.array([7], "uint16"), np.array([8], "uint16"),
         np.array([-32000], "int16"), np.array([1], "uint8")),
    ]
    dates = [dt.date(2026, 9, 20), dt.date(2026, 9, 21)]
    back = np.frombuffer(
        row_binary(columns, dates, days),
        dtype=np.dtype([(c, ROW_BINARY[c]) for c in columns]),
    )
    epoch = dt.date(1970, 1, 1)
    assert [epoch + dt.timedelta(days=int(d)) for d in back["date"]] == [dates[0]] * 2 + [dates[1]]
    assert back["gy"].tolist() == [1, 2, 7]
    assert back["sst_raw"].tolist() == [-5, 2500, -32000]
    assert back["has_clim"].tolist() == [1, 0, 1]


def test_row_binary_refuses_a_missing_column():
    with pytest.raises(ValueError):
        row_binary(["date", "gy", "gx"], [dt.date(2026, 1, 1)], [(np.zeros(1, "uint16"),)])


def test_is_current_follows_the_remote_version():
    assert status.is_current(_row()) is True
    assert status.is_current(_row(), (100, "Mon")) is True
    assert status.is_current(_row(), (101, "Mon")) is False   # revised: new size
    assert status.is_current(_row(), (100, "Tue")) is False   # revised: new mtime
    assert status.is_current(_row(remote_size=0), (5, "x")) is True  # predates tracking
    assert status.is_current(_row(status="ingesting")) is False
    assert status.is_current(None) is False


def test_run_targets_starts_at_the_earlier_archive(monkeypatch):
    today = dt.date(2026, 10, 8)

    class FixedDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 10, 8, 12, tzinfo=tz)

    monkeypatch.setattr(cli.dt, "datetime", FixedDatetime)
    client = FakeClient({
        status.SST_TABLE: dt.date(2026, 10, 6),
        status.MHW_TABLE: dt.date(2026, 10, 5),  # MHW lands ~90 minutes later
    })
    targets = cli.run_targets(client, date=None, recheck_days=3, max_days=None)
    yesterday = today - dt.timedelta(days=1)
    # From the day after the EARLIER watermark (6 Oct) through yesterday, plus
    # the recheck tail that is already ingested (4 and 5 Oct).
    assert targets == [dt.date(2026, 10, 4), dt.date(2026, 10, 5), dt.date(2026, 10, 6), yesterday]
    assert cli.run_targets(client, date=dt.date(2020, 1, 1), recheck_days=3, max_days=None) == [
        dt.date(2020, 1, 1)
    ]


def test_closed_buckets_leave_the_open_ones_to_the_daily_run():
    lo, hi = dt.date(2026, 8, 1), dt.date(2026, 9, 2)
    weeks = imaging.closed_buckets("weekly", lo, hi)
    # The week of 31 August runs to 6 September, past `hi`: still open.
    assert weeks[0] == dt.date(2026, 7, 27) and weeks[-1] == dt.date(2026, 8, 24)
    assert imaging.closed_buckets("monthly", lo, hi) == [dt.date(2026, 8, 1)]


def test_retention_keeps_the_open_week_across_a_month_boundary():
    # 2 September's week began on Monday 31 August, before its month did.
    assert imaging.retention_floor(dt.date(2026, 9, 2)) == dt.date(2026, 8, 31)
    assert imaging.retention_floor(dt.date(2026, 9, 20)) == dt.date(2026, 9, 1)


def test_gx_clause_wraps_rather_than_sorting():
    assert gx_sql(100, 200) == "gx BETWEEN %(gx0)s AND %(gx1)s"
    # West of the prime meridian to east of it: two ranges, not the complement.
    assert gx_sql(7000, 200) == "(gx >= %(gx0)s OR gx <= %(gx1)s)"


class CannedClient:
    """Answers each query with the first canned rows whose needle it contains."""

    def __init__(self, answers):
        self.answers = answers

    def query(self, sql, parameters=None):
        for needle, rows in self.answers:
            if needle in sql:
                return FakeResult(rows)
        raise AssertionError(f"unexpected query: {sql}")


def test_recent_window_keeps_clear_of_the_ttl_edge():
    from CRW import recent
    from shared.ch import RECENT_DAYS

    today = dt.date(2026, 10, 8)
    day = today - dt.timedelta(days=1)
    assert recent.in_window(day, day, today)
    edge = today - dt.timedelta(days=RECENT_DAYS - 1)
    assert not recent.in_window(edge, day, today)
    assert not recent.in_window(None, day, today)


def test_recent_tables_are_read_only_when_their_counts_match_status(monkeypatch):
    from CRW import recent

    day = dt.date(2026, 10, 1)
    monkeypatch.setattr(recent, "_today", lambda: dt.date(2026, 10, 8))
    match = CannedClient([("n_rows", [(day, 17_193_140)]), ("count()", [(day, 17_193_140)])])
    assert recent.covers(match, day, day)
    # A date ingested before the views existed: status has it, recent does not.
    missing = CannedClient([("n_rows", [(day, 17_193_140)]), ("count()", [])])
    assert not recent.covers(missing, day, day)
    # Rows left behind by a one-sided delete.
    doubled = CannedClient([("n_rows", [(day, 10)]), ("count()", [(day, 20)])])
    assert not recent.covers(doubled, day, day)
