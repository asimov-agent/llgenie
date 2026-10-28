#!/usr/bin/env python3
"""The FAST repository gates the issue-bot re-checks before it pushes (issue #475).

The implement leg's agent runs the slow gates while it writes the change (`make test-unit`, 11-20
minutes), and until this guard existed nothing re-checked the fast ones between "the tree changed"
and "the branch is pushed". CI then discovered the bookkeeping reds a full round trip later: the run
that implemented #407 opened six PRs (#443-#448) that were functionally green and red only on an
unticked `- [ ]` in `tasks.md`, a stale README target list and a wiring count - each detectable in
seconds on the host, each worth a CI run plus up to an hour of the hourly `fix-bot`.

`issue-bot-gates` therefore runs a small, ordered list of host-side gates and stops at the first
failure, naming it. It deliberately does NOT run `make test-unit`: the agent already did, and a
second 11-20 minute run inside a 90-minute leg would buy nothing.

Two commands:

  run [--root DIR] [--gates G ...]   run the gates in order, stop at the first failure, name it
  check [--root DIR]                 static lock on the wiring (exit 1 on a finding)

`check` is the part that cannot rot. It reads the REAL files and fails when:

- a gate `ci-unit` runs is classified neither as FAST (`FAST_GATES`, run here) nor in `DEFERRED`
  (with the reason it is not re-checked before the push) - so a new gate added to `ci-unit` reds
  `make test-unit` until someone decides which side it belongs on;
- a `DEFERRED` entry is stale (not a `ci-unit` gate any more) or contradicts `FAST_GATES`;
- a FAST gate is not a make target, is not declared `.PHONY`, or no `ci-*` job runs it (a gate the
  pipeline never reaches proves nothing);
- `make issue-bot-gates` no longer runs this script (the target became a green no-op);
- `.github/workflows/issue-bot.yml` no longer runs `make issue-bot-gates` BETWEEN
  `Detect what the implementation changed` and `Commit + push the feature branch`, or has lost the
  `changed == 'true'` condition (a refine/close run has nothing to gate).

Stdlib only: `ci-unit` runs it on a bare host, exactly like `scripts/check_workflows.py`.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = "Makefile"
WORKFLOW = ".github/workflows/issue-bot.yml"
#: The step the gate must follow, and the step it must precede (issue #475).
STEP_AFTER = "Detect what the implementation changed"
STEP_BEFORE = "Commit + push the feature branch"
GATE_TARGET = "issue-bot-gates"
RUNNER = "scripts/issue_bot_gates.py"

#: The fast gates, in the order they run. `lint` first: it is the cheapest and the most common red
#: (a missing trailing newline). Named here, not in the Makefile, so there is ONE list to compare
#: `ci-unit`'s roster against.
FAST_GATES: tuple[str, ...] = (
    "lint",
    "check-workflows",
    "check-wiring",
    "check-docs",
    "check-pr-hygiene",
    "openspec-tasks-check",
)

#: Every OTHER gate `ci-unit` runs, and why the bot does not re-run it before pushing. A gate in
#: `ci-unit` that appears in NEITHER this mapping nor `FAST_GATES` is a finding (issue #475): a new
#: gate has to be classified, so it cannot be silently skipped here.
DEFERRED: dict[str, str] = {
    "check-issue-bodies": "reads the seven issue producers and the issue skills plus AGENTS.md: a producer/rule change moves it, ci-unit already catches it on the bot's own PR, and FAST_GATES is the fixed #475 list (widening it is that issue's follow-up, not this one)",
    "check-security-bot": "reads the bot's select labels and pin sources against the issue roster: a security-tracker change moves it, not the issue-bot's own PR",
    "check-security-issues": "reads the issue label roster and the scan policy: a security-tracker change moves it, not the issue-bot's own PR",
    "check-security-scan": "reads data/security-policy.json and the scan digests: a security-pipeline change moves it, not the issue-bot's own PR",
    "check-security-bumps": "reads tools/security-floors.in against the compiled pins: a security-pipeline change moves it, and a stale floor fails here rather than in the bot's PR",
    "check-scanner-images": "reads the scanner Dockerfiles and digests.json: a static gate a scan-pipeline change moves, not the issue-bot's own PR",
    "check-actions": "a static read of the workflow files: the change that would float an Action is a workflow edit, and the PR the bot opens is re-checked by the pin gate in ci-unit",
    "check-module-names": "a static read of every live file for one retired module name: the change that would reintroduce it is a text edit ci-unit re-checks on the bot's own PR, and #475 names a fixed FAST list (widening it is that issue's follow-up, not this one)",
    "check-renovate": "a static read of renovate.json and ci.yml's trigger: a dependency-bot config change is not something the issue-bot's own PR can introduce",
    "test-unit": "the agent already ran the whole hermetic suite while writing the change (11-20 minutes); a second run would not fit the leg's budget",
    "skills-validate": "reads every engine skill against the registry; minutes, and the agent's test-unit run reads the same files",
    "check-registry": "re-validates the vendored registry shape; the agent's test-unit run covers the registry tests it drives",
    "check-strata-models": "compares the vendored Strata data with the catalog; slow and not touched by a bookkeeping change",
    "check-quant-catalog": "renders the quant catalog from the registry; slow",
    "check-trend-list-matrix": "renders the README trend matrix; slow",
    "check-engine-skill-gap": "walks every registry engine against the skills; slow",
    "check-engine-params": "regenerates the engine params and Dockerfiles and compares them; slow",
    "check-engine-coverage": "a static read of the skills and the committed params: ci-unit re-checks the issue-bot's own PR, which is where a new skill and its params land, and widening FAST_GATES past the #475 six is that issue's follow-up",
    "check-engine-source": "reads every engine's upstream source at its pin; network-bound",
    "check-engine-launchers": "reads this host's ~/bin launchers against the committed params: a host-local file the bot's PR cannot change, and ci-unit (where the bot's own PR is re-checked) has no launchers at all, so it is informational there by design (issue #842)",
    "check-secret-output": "compares SECRET_VARS with AGENT_SHELL_KEYS; fast, but #475 names a fixed list and widening it is that issue's follow-up, not this one",
    "check-dispatch-forms": "reads the dispatchable workflows' input forms; fast, but not in #475's list (follow-up issue, not this change)",
    "check-pr-authors": "reads the PR's commit range, which does not exist before the push",
    "check-agent-skills": "validates every bot leg's prompt against its project skill; fast, but not in #475's list (follow-up issue, not this change)",
    "check-agent-model": "compares the pinned model snapshot with the two files carrying it; fast, but not in #475's list (follow-up issue, not this change)",
}

_MAKE_CALL = re.compile(r"(?:\$\(MAKE\)|\bmake)\s+(?:-(?!C\s)\S+\s+)*([a-z0-9][a-z0-9._-]*)")

#: The guard's OWN targets. `ci-unit` runs them too (that is how the check itself stays green), and
#: they are not gates over the change: one runs FAST_GATES, the other asserts this file's wiring.
#: Classifying them as fast or deferred would be a category error - they ARE the guard.
GATE_CHECK = "issue-bot-gates-check"
SELF_TARGETS = frozenset({GATE_TARGET, GATE_CHECK})


def _recipes(text: str) -> dict[str, str]:
    """`{target: its recipe text}`, computed from the real Makefile (the same shape check_wiring
    reads, kept local so this gate stays one stdlib file)."""
    spans = [(m.group(1), m.start()) for m in re.finditer(r"^([a-z0-9][a-z0-9._-]*):", text, re.M)]
    out: dict[str, str] = {}
    for i, (name, start) in enumerate(spans):
        end = spans[i + 1][1] if i + 1 < len(spans) else len(text)
        out[name] = text[start:end]
    return out


def _make_calls(recipe: str) -> list[str]:
    """The make targets a recipe calls, in order, deduplicated."""
    seen: list[str] = []
    for name in _MAKE_CALL.findall(recipe):
        if name not in seen:
            seen.append(name)
    return seen


def _phony(text: str) -> set[str]:
    """Every name declared `.PHONY` (the declaration is one list with line continuations)."""
    out: set[str] = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith(".PHONY:"):
            continue
        chunk = [line.split(":", 1)[1]]
        j = i
        while chunk[-1].rstrip().endswith("\\") and j + 1 < len(lines):
            j += 1
            chunk.append(lines[j])
        out |= set(re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]*",
                              " ".join(c.rstrip().rstrip("\\") for c in chunk)))
    return out


def _steps(text: str) -> list[str]:
    """Every step block of every job in a workflow, in file order, as raw text.

    Read textually on purpose: `ci-unit` runs its gates on a bare host with no PyYAML, the same
    reason `scripts/check_workflows.py` is stdlib only."""
    lines = text.splitlines()
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "steps:":
            i += 1
            continue
        indent = len(lines[i]) - len(lines[i].lstrip())
        item = " " * (indent + 2) + "- "
        cur: list[str] | None = None
        j = i + 1
        while j < len(lines):
            line = lines[j]
            stripped = line.strip()
            if stripped and (len(line) - len(line.lstrip())) <= indent:
                break  # back to the job's own keys: this steps list ended
            if line.startswith(item):
                if cur is not None:
                    blocks.append("\n".join(cur))
                cur = [line[len(item):]]
            elif cur is not None:
                cur.append(line)
            j += 1
        if cur is not None:
            blocks.append("\n".join(cur))
        i = j if j > i else i + 1
    return blocks


def _step_name(block: str) -> str:
    for line in block.splitlines():
        m = re.match(r"^\s*name:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip("'\"")
    return ""


def check(root: Path = REPO) -> list[str]:
    """Every finding about the gate's own wiring, from the real files (empty means wired)."""
    errors: list[str] = []
    makefile = root / MAKEFILE
    if not makefile.exists():
        return [f"{MAKEFILE} is missing: the gate has nothing to read"]
    text = makefile.read_text()
    recipes = _recipes(text)
    calls = {t: _make_calls(r) for t, r in recipes.items()}

    # 1. Every gate `ci-unit` runs is classified: fast (run here) or deferred (with a reason).
    unit = calls.get("ci-unit")
    if unit is None:
        errors.append(f"`make ci-unit` is gone: the gate has no roster to check {GATE_TARGET} against")
        unit = []
    for gate in unit:
        if gate in SELF_TARGETS or gate in FAST_GATES:
            continue
        if gate in DEFERRED:
            if not DEFERRED[gate].strip():
                errors.append(f"DEFERRED[{gate!r}] carries no reason; say why the bot does not "
                              f"re-run it before the push")
            continue
        errors.append(f"`ci-unit` runs `make {gate}` and neither FAST_GATES nor DEFERRED classifies "
                      f"it: add it to FAST_GATES (so {GATE_TARGET} re-checks it before the push) or "
                      f"to DEFERRED with the reason it is not re-checked")
    for gate in DEFERRED:
        if gate in FAST_GATES:
            errors.append(f"{gate} is classified twice (FAST_GATES and DEFERRED): keep one")
        elif gate not in unit:
            errors.append(f"DEFERRED[{gate!r}] is stale: `ci-unit` does not run `make {gate}` any more "
                          f"(- delete the entry)")

    # 2. Each fast gate is a real, phony target a CI job actually reaches.
    if len(set(FAST_GATES)) != len(FAST_GATES):
        errors.append(f"FAST_GATES names a gate twice: {list(FAST_GATES)}")
    phony = _phony(text)
    ci_jobs = {t: c for t, c in calls.items() if t.startswith("ci-")}
    for gate in FAST_GATES:
        if gate not in recipes:
            errors.append(f"FAST_GATES names `make {gate}`, which is not a target in {MAKEFILE}")
            continue
        if gate not in phony:
            errors.append(f"`make {gate}` is a fast gate but not declared .PHONY: a file named "
                          f"{gate!r} shadows it and it runs nothing while reporting success")
        if not any(gate in targets for targets in ci_jobs.values()):
            errors.append(f"no `ci-*` job runs `make {gate}`: a gate the pipeline never reaches "
                          f"proves nothing (add it to ci-lint/ci-unit)")

    # 2b. `ci-unit` reaches both the runner and its own check: a target nobody calls is dead code
    #     that reports nothing, and the bot's gate would then be checked by no pipeline job at all.
    for target in (GATE_TARGET, GATE_CHECK):
        if target not in unit:
            errors.append(f"`ci-unit` does not run `make {target}`: the bot's gate (or the check that "
                          f"keeps it honest) is reached by no pipeline job, so it can rot unnoticed")

    # 3. The target still runs this script, and its help line says what it does.
    recipe = recipes.get(GATE_TARGET)
    if recipe is None:
        errors.append(f"`make {GATE_TARGET}` is not a target in {MAKEFILE}: the issue-bot has "
                      f"nothing to run before it pushes")
    elif RUNNER not in recipe:
        errors.append(f"`make {GATE_TARGET}` does not run {RUNNER}: the target is a no-op that "
                      f"reports success without checking anything")
    elif GATE_TARGET not in phony:
        errors.append(f"`make {GATE_TARGET}` is not declared .PHONY: a file named {GATE_TARGET!r} "
                      f"would shadow it and the gate would verify nothing")

    # 4. The issue-bot runs it BETWEEN the change detection and the push.
    wf = root / WORKFLOW
    if not wf.exists():
        return errors + [f"{WORKFLOW} is missing: the gate is wired into no job"]
    steps = _steps(wf.read_text())
    names = [_step_name(b) for b in steps]
    gate_idx = [i for i, b in enumerate(steps) if re.search(rf"make\s+{GATE_TARGET}\b", b)]
    if not gate_idx:
        errors.append(f"{WORKFLOW} has no step running `make {GATE_TARGET}`: the fast gates are "
                      f"checked by nothing before the push")
        return errors
    if len(gate_idx) > 1:
        errors.append(f"{WORKFLOW} runs `make {GATE_TARGET}` in {len(gate_idx)} steps: one is the gate")
    idx = gate_idx[0]
    after = [i for i, n in enumerate(names) if n == STEP_AFTER]
    before = [i for i, n in enumerate(names) if n == STEP_BEFORE]
    if not after:
        errors.append(f"{WORKFLOW} lost its `{STEP_AFTER}` step: the gate must follow it")
    elif idx < after[0]:
        errors.append(f"{WORKFLOW}: `make {GATE_TARGET}` runs BEFORE `{STEP_AFTER}` - there is "
                      f"nothing to check yet")
    if not before:
        errors.append(f"{WORKFLOW} lost its `{STEP_BEFORE}` step: the gate must precede it")
    elif idx > before[0]:
        errors.append(f"{WORKFLOW}: `make {GATE_TARGET}` runs AFTER `{STEP_BEFORE}` - the red "
                      f"change is already pushed and the guard bought nothing")
    block = steps[idx]
    if "changed == 'true'" not in block:
        errors.append(f"{WORKFLOW}: the `make {GATE_TARGET}` step lost its `changed == 'true'` "
                      f"condition - a run that changed nothing has nothing to gate")
    # `lint` runs inside llgenie/test (the same path `ci-lint` uses), and a fresh runner has no such
    # tag: without an earlier `make test-image`/`make test-env` the gate dies on the runtime before
    # it checks anything. Measured: `docker: Unable to find image 'llgenie/test:latest' locally`.
    prep = [i for i, b in enumerate(steps[:idx]) if re.search(r"make\s+(test-image|test-env)\b", b)]
    if not prep:
        errors.append(f"{WORKFLOW}: no step before `make {GATE_TARGET}` runs `make test-image` or "
                      f"`make test-env` - the fast gates' container (llgenie/test) is not on a "
                      f"fresh runner, so the first gate fails on the runtime, not on the change")
    return errors


def run(root: Path = REPO, gates: tuple[str, ...] = FAST_GATES) -> int:
    """Run the gates in order, print each, and stop at the first failure naming it."""
    total = len(gates)
    for i, gate in enumerate(gates, 1):
        print(f"[issue-bot-gates] {i}/{total} make {gate}", flush=True)
        proc = subprocess.run(["make", gate], cwd=str(root))
        if proc.returncode != 0:
            print(f"[issue-bot-gates] FAIL `make {gate}` (exit {proc.returncode}): the branch is NOT "
                  f"pushed; fix the file this gate names and re-run `make {GATE_TARGET}`",
                  file=sys.stderr, flush=True)
            return proc.returncode or 1
    print(f"[issue-bot-gates] OK: {total} fast gate(s) passed - the branch may be pushed", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The fast gates the issue-bot re-checks before it "
                                             "pushes (issue #475)")
    ap.add_argument("cmd", choices=("run", "check"))
    ap.add_argument("--root", default=str(REPO), help="the checkout to read/run in (default: this repo)")
    ap.add_argument("--gates", nargs="+", default=list(FAST_GATES),
                    help="the gates `run` executes, in order (default: FAST_GATES)")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.cmd == "run":
        return run(root, tuple(a.gates))
    errors = check(root)
    for e in errors:
        print(f"[issue-bot-gates] {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"[issue-bot-gates] OK: {len(FAST_GATES)} fast gate(s) run before the push, "
          f"{len(DEFERRED)} deferred with a reason, wired into the issue-bot between the change "
          f"detection and the push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
