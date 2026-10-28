"""Every job in `pipeline.yml` must carry an explicit `timeout-minutes` (issue #846, incident #767).

A job without one inherits GitHub's **360-minute** default, so a hang is invisible for six hours. Measured
on 2026-10-28: `macos / unit` sat inside `make ci-unit` at **105 minutes** on a PR whose other 27 jobs were
green; the owner of that PR had to cancel the run and re-run one job, because a run that is still open
cannot be `gh run rerun --job`'d. The cancellations that follow are how a green matrix loses its verdict —
exactly the failure #846's healer exists to undo.

The ceiling is a hang detector, not a budget: `unit` measures minutes on `ubuntu-latest` and gets 60,
while `install` legitimately pulls large images and gets 120. The bound asserted here is wide on purpose —
it catches "no timeout at all" and absurd values, and leaves the per-job number a judgement call that a
reviewer can see in the diff.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / ".github" / "workflows" / "pipeline.yml"
#: Every workflow the PR path actually runs. `pipeline.yml` holds the stages, but `ci.yml` decides whether
#: they run at all and `published.yml` is reached from it - a job in either of those that inherits the
#: 360-minute default is the same invisible stall, one level further out (#846, incident #767).
WORKFLOWS = tuple(REPO / ".github" / "workflows" / name
                  for name in ("ci.yml", "pipeline.yml", "published.yml"))

#: Below this a slow-but-healthy job would be killed; above it the default is effectively still in force.
MIN_MINUTES = 5
MAX_MINUTES = 300


def _jobs(workflow: Path) -> dict:
    return yaml.safe_load(workflow.read_text())["jobs"]


def _run_jobs(workflow: Path) -> dict:
    """The jobs that run steps. A `uses:` caller cannot declare a ceiling at all - GitHub refuses the
    whole file when one carries a job-level key - so it is not a job that can hold a timeout."""
    return {name: job for name, job in _jobs(workflow).items() if "uses" not in job}


def test_every_pipeline_job_declares_a_timeout():
    """A job that inherits the 360-minute default cannot tell a hang from work."""

    missing = {w.name: [name for name, job in _run_jobs(w).items() if "timeout-minutes" not in job]
               for w in WORKFLOWS}
    missing = {k: v for k, v in missing.items() if v}

    assert not missing, (
        "these jobs would run for GitHub's 360-minute default before anything notices a hang "
        f"(#846): {missing}")


def test_every_timeout_is_a_hang_ceiling_and_not_a_budget():
    """Too small kills a healthy job; too large is the default wearing a number."""

    out_of_range = {f"{w.name}:{name}": job["timeout-minutes"] for w in WORKFLOWS
                    for name, job in _jobs(w).items()
                    if "timeout-minutes" in job
                    and not MIN_MINUTES <= int(job["timeout-minutes"]) <= MAX_MINUTES}

    assert not out_of_range, (f"timeouts must be {MIN_MINUTES}-{MAX_MINUTES} minutes (#846): "
                              f"{out_of_range}")


def test_the_unit_gate_has_the_tightest_ceiling_of_the_long_jobs():
    """`unit` is the gate every PR needs, so its hang is the most expensive one to hide."""

    jobs = _jobs(PIPELINE)

    assert int(jobs["unit"]["timeout-minutes"]) <= 60, jobs["unit"]
    # and it is never *tighter* than the long install path, which legitimately pulls images
    assert int(jobs["unit"]["timeout-minutes"]) < int(jobs["install"]["timeout-minutes"]), (
        "the unit suite should not be given a longer ceiling than install")


def test_a_caller_ceiling_is_illegal_and_the_ceiling_lives_in_the_called_job():
    """`ci.yml` calls two reusable workflows, and a caller cannot carry a ceiling at all.

    GitHub refuses the WHOLE file when a `uses:` job carries a job-level key - the run arrives
    `completed/failure` with zero jobs - so a caller's timeout is not a too-tight guard, it is a
    workflow that never loads. The ceiling therefore has to live on the job that runs steps, inside
    the called workflow, and that job must declare one (issue #846).
    """
    ci = _jobs(REPO / ".github" / "workflows" / "ci.yml")
    callers = {name: job for name, job in ci.items()
               if (job.get("uses") or "").startswith("./.github/workflows/")}

    assert callers, "ci.yml is expected to call the reusable workflows"

    illegal = {name: job["timeout-minutes"] for name, job in callers.items()
               if "timeout-minutes" in job}
    assert not illegal, (
        f"a `uses:` job cannot declare a ceiling; GitHub rejects the file (#846): {illegal}")

    uncovered = {}
    for name, job in callers.items():
        called = _run_jobs(REPO / job["uses"].removeprefix("./"))
        bare = [n for n, j in called.items() if "timeout-minutes" not in j]
        if bare:
            uncovered[f"{name} -> {job['uses']}"] = bare
    assert not uncovered, (
        f"the called workflow must hold the ceiling a caller cannot (#846): {uncovered}")
