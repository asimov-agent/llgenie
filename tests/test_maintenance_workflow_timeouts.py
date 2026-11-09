"""(#2291, #1865 blanket) Every maintenance step job declares a maximum runtime — never unbounded.

The scheduled engine/registry maintenance workflows (`engine-bump`, `engine-bump-rebase`,
`registry-sync`) each render a live GitHub PR on every run, behind a `concurrency` group. A step job
with no `timeout-minutes` inherits GitHub's **360-minute default**, so a hang (a stuck `git fetch`, a
Hub that stops answering) is invisible for six hours while it blocks the whole weekly/daily slot and
the PR it edits. Measured at `main@5c7f4020` (2026-11-09): the four step jobs (`plan`, `bump`,
`rebase`, `sync`) all carried NO `timeout-minutes`, and `make check-workflows` passed.

This is the standing rule #1865 in its maintenance form: the existing
`tests/test_engine_build_timeouts.py` pins the engine-build workflows and
`tests/test_pipeline_timeouts.py` pins `ci.yml`/`pipeline.yml`, neither covers the maintenance
workloads. This suite extends the #1865 net to them with the same general every-steph-job rule
`test_pipeline_timeouts.py` uses: every non-`uses` job must declare a `timeout-minutes`.

The negative control is `test_every_maintenance_step_job_declares_a_timeout`: drop the bound from any
of `plan`/`bump`/`rebase`/`sync` and it reds, naming the workflow and the job.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

#: The three scheduled engine/registry maintenance workflows whose step jobs must every declare a
#: maximum runtime (#1865 maintenance blanket, issue #2291). `engine-build*` is pinned by
#: `test_engine_build_timeouts.py`; `ci.yml`/`pipeline.yml` by `test_pipeline_timeouts.py`.
MAINTENANCE_WORKFLOWS = ("engine-bump.yml", "engine-bump-rebase.yml", "registry-sync.yml")

#: The four step jobs that carried no bound at `main@5c7f4020`. A `uses:` caller cannot declare a
#: ceiling at all (GitHub refuses the whole file when one carries a job-level key), so the ceiling
#: lives on the job that runs steps — these.
STEP_JOBS = {
    "engine-bump.yml": ("plan", "bump"),
    "engine-bump-rebase.yml": ("rebase",),
    "registry-sync.yml": ("sync",),
}

#: Below this a slow-but-healthy job would be killed; above it the default is effectively still in
#: force (the same band `test_pipeline_timeouts.py` asserts).
MIN_MINUTES = 5
MAX_MINUTES = 300


def _jobs(workflow: str) -> dict:
    return yaml.safe_load((WF / workflow).read_text(encoding="utf-8"))["jobs"]


def _run_jobs(workflow: str) -> dict:
    """The jobs that run steps. A `uses:` caller cannot hold a timeout (issue #846)."""
    return {name: job for name, job in _jobs(workflow).items() if "uses" not in job}


def test_every_maintenance_step_job_declares_a_timeout():
    """The four #2291 step jobs each carry a `timeout-minutes`, and it is a hang ceiling (#1865).

    A step that exceeds its declared bound is surfaced as a `timeout`; a step with no bound can never
    be surfaced because it has no bound to exceed — it is GitHub's 360-minute zombie, blocking the
    maintenance `concurrency` slot. Each clamps to a wide-but-bounded ceiling: `plan`/`rebase` 30,
    `bump`/`sync` 120.
    """

    missing = {
        f"{wf}::{name}": job
        for wf, names in STEP_JOBS.items()
        for name in names
        if (job := _run_jobs(wf).get(name)) is None
        or "timeout-minutes" not in job
    }

    assert not missing, (
        "maintenance step jobs missing a `timeout-minutes` (#1865: a step never runs unbounded, "
        f"#2291): {list(missing)}")

    out_of_range = {
        f"{wf}::{name}": job["timeout-minutes"]
        for wf, names in STEP_JOBS.items()
        for name in names
        if (job := _run_jobs(wf).get(name))
        and "timeout-minutes" in job
        and not MIN_MINUTES <= int(job["timeout-minutes"]) <= MAX_MINUTES
    }
    assert not out_of_range, (
        f"maintenance step timeouts must be {MIN_MINUTES}-{MAX_MINUTES} minutes (#846/#2291): "
        f"{out_of_range}")


def test_every_maintenance_job_declares_a_timeout():
    """Every non-`uses` job in the maintenance workflows is bound, not just the four named.

    A future edit that adds a new unbounded step job to any of the three workflows reds here,
    before the added job ever inherits the 360-minute default (#1865 blanket).
    """

    missing = {
        wf: [name for name, job in _run_jobs(wf).items() if "timeout-minutes" not in job]
        for wf in MAINTENANCE_WORKFLOWS
    }
    missing = {k: v for k, v in missing.items() if v}

    assert not missing, (
        "maintenance workflow jobs would run for GitHub's 360-minute default before anything "
        f"notices a hang (#1865/#2291): {missing}")
