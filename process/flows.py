"""The ocean and land `run`s, as two Prefect flows on schedules.

    python -m flows            # serve: register both deployments, poll for runs

This is the only module that imports Prefect, so `python -m CRW.cli ...` and
`python -m CPC.cli ...` keep working with no server. It adds a scheduler and a
UI and nothing else. For the ocean, which dates a run covers is
`CRW.cli.run_targets()` and what happens to one date is
`CRW.cli._process_date()`; for land, the whole job is `CPC.cli.run()`. A second
copy of any of them here would be a second definition of the job.

It sits beside the two packages rather than inside either: it serves both, and
a land flow inside `CRW` would be the misnaming `CPC` exists to avoid.

### Hourly, because both runs are cheap when there is nothing new

Neither product publishes at a fixed hour, so both fire hourly and the first
run after a publication picks it up. An ocean run with nothing new is the HEADs
of its recheck window; a land run is six HEADs (`CPC.cli.run`'s version check).

### What the UI shows

`osta-ocean-run`: one flow run per firing, and inside it **one task run per
date**, named after the date. Its final state is the date's outcome —
`Ingested`, `Skipped`, `Unpublished` or `Failed` — so the thirty revision
rechecks that are no-ops on a normal day read as `Skipped` rather than as thirty
indistinguishable greens.

`osta-land-run`: one flow run per firing, ending `Unchanged` (most hours),
`Completed` or `Failed`.

The pipelines' own `logging` lines (download, ingest, imaging, regions,
shared.*) land in the run's logs through `PREFECT_LOGGING_EXTRA_LOGGERS`.

### Choices worth not undoing

- **Dates run sequentially**, never `.submit()`ed: the ClickHouse client is not
  safe across threads and ingest is disk-bound, so parallel dates would contend
  for the same disk rather than finish sooner.
- **`limit=1`, across both deployments.** Two overlapping runs are the failure
  `repartition` hit once — every per-date count agreeing while a year held
  duplicate rows. Ocean and land never overlap either: both are disk-bound and
  render through the same pool.
- **No retries.** Each run picks up whatever the last one did not, so the next
  firing is the retry by design; a retry here would only re-hit a NOAA outage
  sooner.
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

from CPC import cli as land_cli
from CRW import cli, download

# Hourly, the land run half an hour after the ocean one so their downloads and
# renders do not queue behind each other on the hour (`limit=1` would hold the
# second until the first finished).
DEFAULT_CRON = "0 * * * *"
DEFAULT_LAND_CRON = "30 * * * *"

# The pipelines' loggers. PREFECT_LOGGING_EXTRA_LOGGERS attaches the API handler
# but sets no level, so these would inherit the root's WARNING and every INFO
# line — which is all of them — would be dropped before reaching the UI.
LOGGERS = ("CRW", "CPC", "shared")


def _log_to_ui() -> None:
    for name in LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)


@task(
    name="osta-process-date",
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


# Flows, task, deployments and tag are all prefixed with the project: in prod the
# server is shared with other projects' flows (pipelines.cioospacific.ca), and a
# bare `ocean-run` or `land` would sit beside theirs under one name. OSTA, not
# the repo's old `enso`, since that is the name a reader of the shared UI knows.
@flow(name="osta-ocean-run", log_prints=True)
def ocean_run(
    date: dt.date | None = None,
    recheck_days: int = 30,
    max_days: int | None = None,
    keep_nc: bool = False,
    force: bool = False,
) -> State:
    """CoralTemp SST and the MHW category: download, ingest and render every
    date from the last ingested through yesterday, plus a revision recheck of
    the recent tail. Pass `date` for one day only. `keep_nc` skips the
    retention prune."""
    _log_to_ui()
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


@flow(name="osta-land-run", log_prints=True)
def land_run(
    product: str | None = None,
    recheck_days: int = 14,
    keep_nc: bool = False,
    force: bool = False,
) -> State:
    """NOAA CPC land temperature and precipitation: if a year file has changed
    since the last run, fetch it, ingest the new days plus a revision recheck
    of the recent tail, and re-render. `product` is `temp` or `precip` for one
    only; `force` runs even when nothing changed; `keep_nc` skips the prune."""
    _log_to_ui()
    ensure_schema()

    outcome = land_cli.run(
        product=product, recheck_days=recheck_days, keep_nc=keep_nc, force=force
    )
    if outcome == "failed":
        return Failed(message="land run: failed, see the logs")
    return Completed(name=outcome.capitalize(), message=f"land run: {outcome}")


if __name__ == "__main__":
    # Serve the flows as imported from their module, not the ones this
    # `__main__` module just defined: a deployment's entrypoint is recorded
    # from the flow's module, and `__main__.ocean_run` is not importable by the
    # process that later executes a run. `flows.ocean_run` is.
    from prefect import serve
    from prefect.deployments.runner import EntrypointType

    import flows

    common = {
        "tags": ["osta"],
        "paused": _bool_env("RUN_SCHEDULE_PAUSED"),
        "parameters": {"keep_nc": _bool_env("RUN_KEEP_NC")},
        "entrypoint_type": EntrypointType.MODULE_PATH,
    }
    serve(
        flows.ocean_run.to_deployment(
            name="osta-ocean", cron=os.environ.get("RUN_CRON", DEFAULT_CRON), **common
        ),
        flows.land_run.to_deployment(
            name="osta-land", cron=os.environ.get("LAND_RUN_CRON", DEFAULT_LAND_CRON), **common
        ),
        limit=1,
    )
