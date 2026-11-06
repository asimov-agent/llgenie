"""(#1865, #1250-class) Every engine/build job declares a maximum runtime — a step never runs unbounded.

The #1696 zombies (runs 42191808660 / 42191768249, started 09:00Z, still in_progress at
`a90fb89aec` 3h35m later) stalled every push=true run behind the engine-build concurrency gate
until a human noticed. A job with no `timeout-minutes` is that failure mode waiting to happen: the
job-level `if:` that GitHub evaluates before scheduling cannot bound a step that started, and a
hung cell with no bound reads identically to a legitimately long build. This suite pins the
standing rule (issue #1865): every job in the engine-build workflows declares a maximum runtime.

The negative control is `test_every_engine_build_job_declares_a_runtime_bound`: drop the
`timeout-minutes` from any engine-build job and it reds.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

#: The workflows whose jobs must every declare a maximum runtime. The trigger is the concurrency-
#: gate holder whose own unbounded wait is the #1860/#1863/#1696 stall; the builder is the cells.
ENGINE_BUILD_WORKFLOWS = ("engine-build.yml", "engine-build-pr-trigger.yml")

#: Every job of those workflows must carry a `timeout-minutes`. A helper spits a job name per line
#: when the series of whitespace-indented `name:` keys under `jobs:` meets its `timeout-minutes:`.
JOB = re.compile(r"^  ([a-zA-Z0-9_-]+):\s*$")
TIMEOUT = re.compile(r"^\s*timeout-minutes:\s*")


def _jobs_and_timeout(workflow: str) -> dict[str, bool]:
    """{job name: has a `timeout-minutes`} for one workflow's `jobs:` mapping."""
    text = (WF / workflow).read_text(encoding="utf-8")
    in_jobs = False
    out: dict[str, bool] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        m = JOB.match(line)
        if m:
            current = m.group(1)
            if current is not None:
                out[current] = False
            continue
        if current is not None and TIMEOUT.match(line):
            out[current] = True
    return out


def test_every_engine_build_job_declares_a_runtime_bound():
    """Every job in the engine-build workflows carries `timeout-minutes` (#1865).

    A step that exceeds its declared bound must be surfaced (the #1860 stall-watchdog names the
    concurrency-gate holder on overrun) and a step with no bound can never be surfaced because it
    has no bound to exceed. Each job here is one of: the owner-guard (10m), the matrix solver
    (bounds the make call that builds the include list), the build/verify cell (240m, rocm 360m —
    issue #1818), or the push-trigger wait (250m, the #1860 fix's own window).
    """
    missing: list[str] = []
    for wf in ENGINE_BUILD_WORKFLOWS:
        jobs = _jobs_and_timeout(wf)
        assert jobs, f"{wf}: no jobs parsed (workflow shape changed?)"
        for job, bounded in jobs.items():
            if not bounded:
                missing.append(f"{wf}::{job}")
    assert not missing, (
        "engine-build jobs missing a `timeout-minutes` (#1865: a step never runs unbounded): "
        + ", ".join(missing)
    )
