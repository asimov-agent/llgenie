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

#: Below this a slow-but-healthy job would be killed; above it the default is effectively still in force.
MIN_MINUTES = 5
MAX_MINUTES = 300


def _jobs() -> dict:
    return yaml.safe_load(PIPELINE.read_text())["jobs"]


def test_every_pipeline_job_declares_a_timeout():
    """A job that inherits the 360-minute default cannot tell a hang from work."""

    missing = [name for name, job in _jobs().items() if "timeout-minutes" not in job]

    assert not missing, (
        "these jobs would run for GitHub's 360-minute default before anything notices a hang "
        f"(#846): {missing}")


def test_every_timeout_is_a_hang_ceiling_and_not_a_budget():
    """Too small kills a healthy job; too large is the default wearing a number."""

    out_of_range = {name: job["timeout-minutes"] for name, job in _jobs().items()
                    if not MIN_MINUTES <= int(job["timeout-minutes"]) <= MAX_MINUTES}

    assert not out_of_range, (f"timeouts must be {MIN_MINUTES}-{MAX_MINUTES} minutes (#846): "
                              f"{out_of_range}")


def test_the_unit_gate_has_the_tightest_ceiling_of_the_long_jobs():
    """`unit` is the gate every PR needs, so its hang is the most expensive one to hide."""

    jobs = _jobs()

    assert int(jobs["unit"]["timeout-minutes"]) <= 60, jobs["unit"]
    # and it is never *tighter* than the long install path, which legitimately pulls images
    assert int(jobs["unit"]["timeout-minutes"]) < int(jobs["install"]["timeout-minutes"]), (
        "the unit suite should not be given a longer ceiling than install")
