#!/usr/bin/env python3
"""The ci-network workflow obeys the owner's directive for the HF tests (issue #1000).

The owner: "the hf network tests must be part of another ci pipeline … they can't be part of ci unit
anymore." This pins that at the workflow-file level, in this lane's own test:

- `ci-network.yml` triggers ONLY from `schedule` + `workflow_dispatch` — it must never have a
  `push:` or `pull_request:` trigger (a live-Hub flake must never red a PR or a push to main).
- The job runs the liveness gate FIRST (`make check-model-links LIVE=1 LIMIT=25`: a dead committed
  model/GGUF link is a named message before any test), then the seam `make test-unit-network`
  (the `@pytest.mark.network` ownership set), never the hermetic unit gate.
- Its schedule minute is odd and its own (issue #275).

Hermetic: pure file reads, no network.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci-network.yml"


def _text() -> str:
    assert WORKFLOW.exists(), f"ci-network.yml missing at {WORKFLOW}"
    return WORKFLOW.read_text()


def test_ci_network_has_the_required_trigger_surface():
    """Schedule + workflow_dispatch only; never push, never pull_request (issue #1000)."""

    # Given the committed workflow body
    text = _text()

    # Then it schedules and can be dispatched by hand, and NEVER triggers on push / PR
    assert re.search(r"^\s+schedule:", text, re.M), "ci-network.yml must have a schedule"
    assert "workflow_dispatch" in text, "ci-network.yml must be manually dispatchable"
    assert "use: push" not in text, "ci-network.yml must not run on push"
    assert re.search(r"^\s+push:", text, re.M) is None, "ci-network.yml must not trigger on push"
    assert re.search(r"^\s+pull_request:", text, re.M) is None, \
        "a live-Hub test must never gate a pull request (issue #1000)"


def test_ci_network_runs_the_liveness_gate_then_the_seam():
    """The dedicated pipeline first proves the links resolve, then runs the network-owned set."""

    # Given the committed workflow body
    text = _text()

    # Then the job gates with the liveness check and then the seam — never the hermetic unit gate
    assert "make check-model-links LIVE=1 LIMIT=25" in text, \
        "the liveness gate (bounded) must come before any test (issue #1000)"
    assert "make test-unit-network" in text, \
        "the network-owned @pytest.mark.network set must run via the seam (issue #1000)"
    assert re.search(r"make test-unit(?!-network)", text.split("jobs:", 1)[1]) is None, \
        "the hermetic unit gate must never run in the network pipeline (issue #1000)"
    # compare order only inside the JOB body (the header prose names them out of order, so a
    # whole-file first-occurrence comparison is the wrong witness)
    job = text.split("jobs:", 1)[1]
    gate = job.index("make check-model-links LIVE=1 LIMIT=25")
    seam = job.index("make test-unit-network")
    assert gate < seam, "liveness gate must precede the seam in the job (a dead link fails first)"


def test_ci_network_schedule_is_an_odd_own_minute():
    """Issue #275: no bot shares a slot; GitHub drops top-of-hour runs, so the minute is odd."""

    # Given the committed workflow body
    text = _text()

    # Then the cron uses an odd minute
    m = re.search(r"cron:\s*\"([0-9]+) ([0-9]+) \* \* \*\"", text)
    assert m, "ci-network.yml must declare a daily schedule cron"
    minute = int(m.group(1))
    assert minute % 2 == 1, f"ci-network cron minute {minute} is not odd (issue #275)"
