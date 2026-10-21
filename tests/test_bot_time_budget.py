"""A bot must be allowed to finish the work it started (issues #222/#248).

Both bots hand a long task to an agent and then re-run the repo's own gates. If the job's
`timeout-minutes` is smaller than that work, GitHub kills the job mid-round and the run ends
as CANCELLED — which reads as an infrastructure hiccup rather than the loop's own verdict
("still failing after N attempts"), and loses the agent's work. This pins the budget to the
work: the check's measured runtime plus a repair, times the loop's own default round count.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

# Measured on a linux runner in this repo: `make ci-unit` (the default check) is 11-20
# minutes depending on container pulls. A repair that reads AGENTS.md, edits and re-runs the
# gates is 10-30. The floors below are the conservative end of both.
CHECK_MINUTES = 20
AGENT_MINUTES = 30
#: The least a bot job may allow: an hour of agent work, which is what the bots are for.
FLOOR_MINUTES = 60
#: How a job that runs an agent is recognised (the step commands that hand work to Hermes).
AGENT_RUN = re.compile(r"(make (implement-issue|fix-loop|issue-bot-)|scripts/fix_loop\.sh|hermes )")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _rounds() -> int:
    """The loop's OWN default round count, read from scripts/fix_loop.sh (not a copy)."""
    text = (REPO / "scripts" / "fix_loop.sh").read_text()
    m = re.search(r'ROUNDS="\$\{FIX_ROUNDS:-([0-9]+)\}', text)
    assert m, "scripts/fix_loop.sh no longer sets ROUNDS from FIX_ROUNDS"
    return int(m.group(1))


def _agent_jobs(wf: dict) -> dict:
    """Jobs with a step that hands work to the agent."""
    out = {}
    for name, job in (wf.get("jobs") or {}).items():
        runs = [s.get("run", "") for s in (job.get("steps") or []) if isinstance(s, dict)]
        if any(AGENT_RUN.search(r) for r in runs):
            out[name] = job
    return out


def _bot_workflows() -> list[Path]:
    found = [p for p in (WF / "fix-bot.yml", WF / "issue-bot.yml") if p.exists()]
    assert found, "neither bot workflow exists: the bots were removed, not merely moved"
    return found


def test_every_bot_job_that_runs_an_agent_allows_an_hour():
    for path in _bot_workflows():
        jobs = _agent_jobs(_load(path))
        assert jobs, f"{path.name}: no job runs the agent any more"
        for name, job in jobs.items():
            allowed = job.get("timeout-minutes")
            assert isinstance(allowed, int), f"{path.name}/{name}: no timeout-minutes"
            assert allowed >= FLOOR_MINUTES, (
                f"{path.name}/{name} allows {allowed} min; an agent task needs at least "
                f"{FLOOR_MINUTES} (it may run an hour)"
            )
            assert allowed <= 360, f"{path.name}/{name}: {allowed} exceeds GitHub's ceiling"


def test_the_fix_job_fits_the_rounds_it_may_run():
    """rounds x (check + repair), not a round and a half — that is how a run gets cancelled."""
    job = _load(WF / "fix-bot.yml")["jobs"]["fix"]
    rounds = _rounds()
    needed = rounds * (CHECK_MINUTES + AGENT_MINUTES)
    assert job["timeout-minutes"] >= needed, (
        f"the fix job allows {job['timeout-minutes']} min but {rounds} rounds x "
        f"({CHECK_MINUTES} min check + {AGENT_MINUTES} min repair) = {needed} min"
    )


def test_no_step_caps_a_bot_round_below_the_job():
    """A step-level timeout would silently cut a long agent round short before the job would."""
    for path in _bot_workflows():
        for name, job in _agent_jobs(_load(path)).items():
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                cap = step.get("timeout-minutes")
                if cap is not None:
                    assert cap >= FLOOR_MINUTES, (
                        f"{path.name}/{name}: step {step.get('name')!r} caps at {cap} min"
                    )


def test_the_short_jobs_still_fail_fast():
    """The guard/sweep half only decides WHICH PR, so it must not inherit the agent budget."""
    for path in _bot_workflows():
        for name, job in (_load(path).get("jobs") or {}).items():
            if name in _agent_jobs(_load(path)):
                continue
            allowed = job.get("timeout-minutes")
            assert allowed is not None, f"{path.name}/{name}: no timeout-minutes (can hang)"
            assert allowed <= 30, f"{path.name}/{name}: {allowed} min for a decision-only job"


def test_the_fix_loop_imposes_no_hidden_per_round_cap():
    """The loop is the other place a cap could hide: it must not wrap the agent in `timeout`."""
    text = (REPO / "scripts" / "fix_loop.sh").read_text()
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    assert not re.search(r"\btimeout\b", body), (
        "scripts/fix_loop.sh caps a round with `timeout`; the workflow budget is then not "
        "the effective one"
    )


# ------------------------- the implement leg has its own budget and salvages (#476)


def _issue_bot() -> dict:
    return _load(WF / "issue-bot.yml")


def test_the_implement_step_has_a_budget_below_the_job():
    """A leg that can outlive the job needs its own, smaller ceiling."""
    wf = _issue_bot()
    job = wf["jobs"]["implement"]
    step = next(s for s in job["steps"] if s.get("id") == "impl")

    # Then it declares a budget that leaves time to salvage the tree afterwards
    assert "timeout-minutes" in step, "the implement step has no budget of its own"
    budget = int(step["timeout-minutes"])
    assert FLOOR_MINUTES <= budget < int(job["timeout-minutes"]), (budget, job["timeout-minutes"])


def test_a_timed_out_implementation_still_salvages_the_tree():
    """Detection and the push must run even when the implementation failed or timed out."""
    steps = {s.get("id"): s for s in _issue_bot()["jobs"]["implement"]["steps"] if s.get("id")}

    # Then both the change detection and the push are unconditional-on-outcome
    assert "always()" in str(steps["diff"].get("if", "")), steps["diff"].get("if")
    assert "always()" in str(steps["push"].get("if", "")), steps["push"].get("if")


def test_the_budget_failure_is_named():
    """The run says it ran out of budget, and what survived, instead of dying at the job cap."""
    steps = _issue_bot()["jobs"]["implement"]["steps"]
    named = [s for s in steps if "impl.outcome" in str(s.get("if", ""))]
    assert named, "no step names the implement step's outcome"
    body = "\n".join(str(s.get("run", "")) for s in named)
    assert "budget" in body.lower() and "90" in body
    assert "pushed" in body and "tree=" in body
