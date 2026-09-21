"""The daily `run`, as a Prefect flow on a schedule.

    python -m CRW.flows        # serve: register the deployment, poll for runs

This is the only module that imports Prefect, so `python -m CRW.cli ...` keeps
working with no server. It adds a scheduler and a UI and nothing else: which
dates a run covers is `cli.run_targets()`, and what happens to one date is
`cli._process_date()`, both unchanged. A second copy of either here would be a
second definition of the daily job.

### What the UI shows

One flow run per scheduled run, and inside it **one task run per date**, named
after the date. Its final state is the date's outcome — `Ingested`, `Skipped`,
`Unpublished` or `Failed` — so the thirty revision rechecks that are no-ops on a
normal day read as `Skipped` rather than as thirty indistinguishable greens.
The pipeline's own `logging` lines (download, ingest, imaging, regions,
shared.*) land in each task's log tab through `PREFECT_LOGGING_EXTRA_LOGGERS`.

### Choices worth not undoing

- **Dates run sequentially**, never `.submit()`ed: the ClickHouse client is not
  safe across threads and ingest is disk-bound, so parallel dates would contend
  for the same disk rather than finish sooner.
- **`limit=1`.** Two overlapping runs are the failure `repartition` hit once —
  every per-date count agreeing while a year held duplicate rows.
- **No retries.** `run` is a range from the last ingested day, so tomorrow's run
  is the retry by design; a retry here would only re-hit a NOAA outage sooner.
- **`width` is not a parameter.** A cached frame at any other width is a 404
  and a blank map, so a UI field for it is a way to fill the cache with images
  nothing requests.

### Pausing

`serve()` re-applies `RUN_SCHEDULE_PAUSED` every time it starts, and pauses the
schedule when it stops. So the UI's pause toggle lasts only until the container
next restarts — for a migration, `stop scheduler` is the pause.
"""

# No `from __future__ import annotations`: Prefect builds a pydantic model from
# the flow's signature, and string annotations leave `dt.date` unresolvable —
# every run then fails parameter validation before it starts.
import datetime as dt
import logging
import os

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.states import Completed, Failed, State
from shared.ch import _bool_env, ensure_schema, get_client
from shared.render import DEFAULT_WIDTH

from CRW import cli, download

# After CoralTemp (~14:52 UTC) and MHW (~15:20 UTC) have both published, with
# margin for a late day. A run that lands early is harmless: the next one picks
# the date up, since the catch-up watermark is the earlier of the two archives.
DEFAULT_CRON = "30 16 * * *"


@task(
    name="process-date",
    task_run_name="{date}",
    # The task takes live clients, which cannot be hashed into a cache key, and
    # returns only an outcome word; there is nothing worth caching or persisting.
    cache_policy=NO_CACHE,
    persist_result=False,
)
def process_date(client, http, date: dt.date, *, force: bool, keep_nc: bool) -> State:
    outcome = cli._process_date(
        client, http, date, force=force, keep_nc=keep_nc, width=DEFAULT_WIDTH
    )
    if outcome == "failed":
        # `ingest_files` counted a failure without raising; the traceback is
        # already in this task's logs.
        return Failed(message=f"{date}: ingest failed")
    return Completed(name=outcome.capitalize(), message=f"{date}: {outcome}")


@flow(name="daily-run", log_prints=True)
def daily_run(
    date: dt.date | None = None,
    recheck_days: int = 30,
    max_days: int | None = None,
    keep_nc: bool = False,
    force: bool = False,
) -> State:
    """Download, ingest and render every date from the last ingested through
    yesterday, plus a revision recheck of the recent tail. Pass `date` for one
    day only. `keep_nc` skips the retention prune."""
    # PREFECT_LOGGING_EXTRA_LOGGERS attaches the API handler but sets no level,
    # so these would inherit the root's WARNING and every INFO line — which is
    # all of them — would be dropped before reaching the UI.
    for name in ("CRW", "shared"):
        logging.getLogger(name).setLevel(logging.INFO)

    ensure_schema()

    with get_client() as client, download.new_client() as http:
        targets = cli.run_targets(
            client, date=date, recheck_days=recheck_days, max_days=max_days
        )
        outcomes: dict[str, int] = {}
        for day in targets:
            # return_state: a raised exception fails that date's task only, the
            # same as the CLI's per-date try/except — one bad date must not
            # stop the run.
            state = process_date(
                client, http, day, force=force, keep_nc=keep_nc, return_state=True
            )
            outcome = state.name.lower() if state.is_completed() else "failed"
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

    summary = cli.run_summary(outcomes, len(targets))
    print(summary)
    if outcomes.get("failed"):
        return Failed(message=summary)
    return Completed(message=summary)


if __name__ == "__main__":
    # Serve the flow as imported from its package, not the one this `__main__`
    # module just defined: the deployment's entrypoint is recorded from the
    # flow's module, and `__main__.daily_run` is not importable by the process
    # that later executes a run. `CRW/flows.py:daily_run` would be, but loading
    # by file path puts CRW/ itself on sys.path, making its modules importable a
    # second time as top-level `config`, `status`, ...
    from prefect.deployments.runner import EntrypointType

    from CRW.flows import daily_run as served

    served.serve(
        name="daily",
        cron=os.environ.get("RUN_CRON", DEFAULT_CRON),
        paused=_bool_env("RUN_SCHEDULE_PAUSED"),
        parameters={"keep_nc": _bool_env("RUN_KEEP_NC")},
        limit=1,
        entrypoint_type=EntrypointType.MODULE_PATH,
    )
