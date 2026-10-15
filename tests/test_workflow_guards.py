"""Every workflow a human can dispatch carries the same trigger guard (issue #295).

A `workflow_dispatch` workflow is started by a person, so each one must refuse anyone who is not the
owner or a collaborator with WRITE access — checked for `github.actor` AND `github.triggering_actor`,
before any secret is read. The audit that produced this file found the rules drifting: `queued-alarm.yml`
had **no** guard at all, four workflows used an older `curl` form that accepted ANY collaborator level
(`GET /collaborators/<user>` answers 204 for read and triage too), and `fix-bot.yml`'s step-level guard
ignored `triggering_actor` and `maintain`.

GitHub itself refuses `workflow_dispatch` from a user without write access, so this is the second line of
defence — it is what covers the non-dispatch paths (`issues: [labeled]`, a fork-side run, a re-run by
someone else) and what keeps the rule visible in the file. A convention without a guard drifts, so the
shared shape is pinned here: ONE guard body (byte-identical in all eleven guard sites — the ten
dispatchable workflows plus `ci.yml`, which is guarded though no human dispatches it), one rule, one test.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

#: The permission levels the guard accepts: anything a collaborator can do to a branch or an image.
ALLOWED_PERMISSIONS = ("admin", "maintain", "write")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _on(wf: dict) -> dict:
    """The triggers. YAML 1.1 reads the bare key `on` as the boolean True; a list form is possible."""
    on = wf.get("on") or wf.get(True)
    if isinstance(on, list):
        return {str(k): None for k in on}
    return on if isinstance(on, dict) else {}


def _dispatchable() -> list[Path]:
    return [p for p in sorted(WF.glob("*.yml")) if "workflow_dispatch" in _on(_load(p))]


def _runs(wf: dict) -> list[tuple[str, str]]:
    """(job name, its steps' run text) for every job with steps."""
    out = []
    for name, job in (wf.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        text = "\n".join(str(s.get("run") or "") for s in (job.get("steps") or [])
                         if isinstance(s, dict))
        if text.strip():
            out.append((name, text))
    return out


def _is_guard(text: str) -> bool:
    return "/collaborators/" in text and "permission" in text


def test_every_dispatchable_workflow_has_the_guard():
    """A workflow a human can start by hand states who may start it."""
    missing = []
    for path in _dispatchable():
        wf = _load(path)
        if not any(_is_guard(text) for _, text in _runs(wf)):
            missing.append(path.name)
    assert not missing, (
        "these workflows are dispatchable and carry no actor guard (issue #295): " + ", ".join(missing))


def test_the_guard_checks_both_actors_and_a_write_level():
    """`github.actor` alone is not enough (a re-run is someone else), and any-collaborator is not a
    write level: `GET /collaborators/<user>` answers 204 for read/triage collaborators too."""
    weak = []
    for path in _dispatchable():
        wf = _load(path)
        text = path.read_text()
        guards = [t for _, t in _runs(wf) if _is_guard(t)]
        assert guards, path.name
        joined = "\n".join(guards)
        if not all(level in joined for level in ALLOWED_PERMISSIONS):
            weak.append(f"{path.name}: accepted levels are not exactly {ALLOWED_PERMISSIONS}")
        if "triggering_actor" not in text:
            weak.append(f"{path.name}: checks `github.actor` only, not `github.triggering_actor`")
        if "204" in joined:
            weak.append(f"{path.name}: still uses the curl-204 form (any collaborator level)")
    assert not weak, "\n  ".join(["weak guards:"] + weak)


def _guard_steps() -> list[tuple[Path, dict]]:
    """(workflow path, step) for every step whose run text is the guard."""
    out = []
    for path in sorted(WF.glob("*.yml")):
        for job in (_load(path).get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if isinstance(step, dict) and _is_guard(str(step.get("run") or "")):
                    out.append((path, step))
    return out


def test_every_guard_step_is_byte_identical():
    """One guard body means ONE body: a rule fixed in one workflow cannot miss the other ten, and a
    reviewer reads one script instead of diffing eleven near-copies (issue #295)."""
    groups: dict[str, list[str]] = {}
    for path, step in _guard_steps():
        body = yaml.safe_dump({"name": step.get("name"), "env": step.get("env") or {},
                               "run": step.get("run")}, sort_keys=True)
        groups.setdefault(body, []).append(path.name)

    # Then there is exactly one body, and it is the one every guard site carries
    assert len(groups) == 1, (
        "the guard is not byte-identical everywhere — these bodies differ:\n"
        + "\n".join(f"  {', '.join(sorted(names))}" for names in groups.values()))
    assert len(next(iter(groups.values()))) == 11, next(iter(groups.values()))


def test_the_guard_actually_gates_the_work():
    """A guard nothing depends on is decoration: the guarded job needs it (or the guarding step sits
    in the job itself, and that job can only start from a dispatch)."""
    unguarded = []
    for path in _dispatchable():
        wf = _load(path)
        jobs = wf.get("jobs") or {}
        guard_job = jobs.get("guard")
        if isinstance(guard_job, dict):
            consumers = []
            for name, job in jobs.items():
                if name == "guard" or not isinstance(job, dict):
                    continue
                needs = job.get("needs")
                needs = [needs] if isinstance(needs, str) else list(needs or [])
                if "guard" in needs:
                    consumers.append(name)
            if not consumers:
                unguarded.append(f"{path.name}: a `guard` job nothing needs")
            continue
        # step-level guard (fix-bot.yml): the guarded job must be dispatch-only
        step_guarded = [name for name, text in _runs(wf) if _is_guard(text)]
        if not step_guarded:
            unguarded.append(f"{path.name}: neither a `guard` job nor a guarded step")
            continue
        for name in step_guarded:
            if str((jobs.get(name) or {}).get("if") or "") != "github.event_name == 'workflow_dispatch'":
                unguarded.append(f"{path.name}: job `{name}` has a guard step but can also run on "
                                 f"another event")
    assert not unguarded, "\n  ".join(["ungated guards:"] + unguarded)


def test_no_guard_declares_an_output_nobody_reads():
    """ci.yml declared `outputs.allowed` and wrote `allowed=true|false`, while nothing consumed it —
    the refusal was the step's non-zero exit all along (issue #295). A declared, unread output is how
    a reviewer comes to believe a value is consulted."""
    dead = []
    # EVERY workflow, not just the dispatchable ones: the finding was in ci.yml, which no human
    # dispatches (it runs on pull_request/push) and which the dispatchable filter therefore misses.
    for path in sorted(WF.glob("*.yml")):
        wf = _load(path)
        text = path.read_text()
        guard = (wf.get("jobs") or {}).get("guard")
        for key in sorted(((guard or {}).get("outputs") or {})):
            if f"guard.outputs.{key}" not in text:
                dead.append(f"{path.name}: `jobs.guard.outputs.{key}` is never consumed")
    assert not dead, "\n  ".join(["dead guard outputs:"] + dead)


def test_every_guarded_workflow_is_covered_by_this_file():
    """The list of guarded workflows is read from the tree, so a NEW dispatchable workflow cannot
    ship without one: it appears here the moment it exists."""
    assert len(_dispatchable()) >= 8, [p.name for p in _dispatchable()]
    assert "queued-alarm.yml" in [p.name for p in _dispatchable()], (
        "queued-alarm.yml is the workflow the audit found unguarded — it must stay dispatchable AND "
        "guarded, not made undispatchable to pass")
