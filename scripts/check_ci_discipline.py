#!/usr/bin/env python3
"""Enforce the CI discipline the owner set on 2026-11-15 (issue #2701).

The rule has four faces, and every one of them is a MEASURE, not a comment:

1. SCHEDULE SURFACE. Only the allow-listed lanes below may declare an
   `on.schedule:` trigger. The weekly engine lane (`engine-bump.yml`), the
   weekly latest-models/inference-servers fetch (`registry-sync.yml`), the
   weekly test battery (`all-pipelines.yml`), the non-agent security and
   liveness monitors, and the merge/monitoring plumbing the owner's
   auto-merge/auto-approve mandate depends on. Everything else keeps a clock
   only by being added to the allow-list WITH a rationale, in review.
   A lane that loses its declared schedule while staying in the allow-list is
   ALSO a finding: the list must describe reality, in both directions.

2. TESTS-ONLY MAIN PIPELINE. `ci.yml` and `pipeline.yml` (the PR/push lanes)
   and `all-pipelines.yml` (the scheduled battery) may not run a Hermes agent
   leg: no `./.github/actions/agent-leg` use, no agent image reference, no
   `make agent-*` / `make search-smoke` agent seam. The main pipeline runs
   tests, no LLM.

3. AGENT-LEG SCOPE. Hermes/LLM usage in CI lives in the allow-listed lanes
   whose purpose is fetching the latest engine servers, syncing the registry,
   updating the engine list with new engines, and updating existing engines'
   Dockerfiles — plus the bot lanes #2701 left dispatch-only. A NEW workflow
   that uses the agent-leg action outside that list is a finding. None of the
   agent-lane files may declare a schedule (issue #2701 deactivated them).

4. AGENTS.md CARRIES THE RULE. The durable section named by SECTION markers
   below must exist; a gate nobody wrote into the rules drifts.

Commands (driven by make, never by hand):

    check [--root DIR]    exit 1 on any finding; 2 when an input is unreadable
    report [--root DIR]   print the measured surface, always exit 0

Findings name the file and the rule; values (cron strings) are echoed only
for allow-listed lanes, where they are part of the record.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Every workflow that may declare `on.schedule:` -> why it keeps a clock.
#: The list is the decision; adding a lane here is a review act (issue #2701).
SCHEDULE_ALLOW: dict[str, str] = {
    "engine-bump.yml": "the owner's weekly lane: engine bumps, engine image builds, latest models/inference servers (ADDENDUM: the only weekly lane besides the registry fetch it feeds)",
    "engine-bump-rebase.yml": "rebase plumbing for the branches the weekly engine lane opens",
    "registry-sync.yml": "the weekly trending-store fetch (latest models and inference servers) that feeds the engine lane",
    "all-pipelines.yml": "the weekly scheduled test battery: tests only, no agent job (the gate checks it)",
    "arms.yml": "arms auto-merge/auto-approve for green PRs (the owner's landing mandate)",
    "auto-merge.yml": "merges green, CLEAN PRs on its slot (the owner's landing mandate)",
    "holds.yml": "monitors do-not-merge holds so auto-merge defers to reviewers",
    "queued-alarm.yml": "queue alarm: files issues for runs that never got a runner; it never reruns one",
    "ci-frozen-reaper.yml": "cancels frozen/undeliverable queue entries; cancelling is not starting a pipeline",
    "stale-branch-cleanup.yml": "prunes merged/stale branches — landing plumbing, never a pipeline start",
    "main-ruleset.yml": "re-measures the main ruleset's required-check floor (issue #1400)",
    "ci-hf-live.yml": "live HF model-availability monitors; a red lane files an issue, it starts no pipeline",
    "registry-liveness.yml": "registry liveness monitors; same shape as ci-hf-live",
    "security-scan.yml": "scheduled deterministic scanner (no agent-leg use; the gate checks it)",
    "security-images.yml": "rebuilds the scanner images (deterministic; issue #744 pipeline)",
    "security-bot.yml": "picks security findings into issues (deterministic producers; no agent-leg use)",
    "semgrep-rules-refresh.yml": "refreshes semgrep rules monthly",
    "code-review-bot.yml": "deterministic PR scanner (no agent-leg/agent-image job in it)",
}

#: Lanes that may use the Hermes agent leg or the agent image at all.
#: engine-bump.yml reaches its agent review legs through the make seam
#: (engine-params-review*), not the action, and is covered by SCHEDULE_ALLOW.
#: The seven deactivated lanes stay dispatch-only (issue #2701, #2703).
AGENT_LANES: dict[str, str] = {
    "architecture-bot.yml": "dispatch-only since issue #2701: scans the tree for architecture gaps",
    "fix-bot.yml": "implements auto-fixable findings with the agent leg",
    "issue-bot.yml": "dispatch-only since issue #2701: implements issue-labeled work",
    "issue-refiner.yml": "dispatch-only since issue #2701: restates issue bodies into the six-section shape",
    "publish-agent-image.yml": "the lane that BUILDS/PUSHES the Hermes agent image every agent lane pulls (#222/#238/#248); on-demand dispatch only",
    "rebase-bot.yml": "dispatch-only since issue #2701: rebases open PRs (agents rebase their own branches meanwhile)",
    "registry-sync-review.yml": "dispatch-only since issue #2701: agent review of registry-sync proposals",
    "search-smoke.yml": "dispatch-only since issue #2701: the loud proof the agent's web-reach key works, via the one sanctioned agent-fetch leg",
}

#: The main pipeline files that must stay tests-only.
TESTS_ONLY_PIPELINES = ("ci.yml", "pipeline.yml", "all-pipelines.yml")

#: Text fragments that mark a Hermes agent job in a pipeline file.
AGENT_MARKERS = ("actions/agent-leg", "containers/agent", "agent-image-ref", "make agent-image", "fix-loop-image", "make search-smoke", "make engine-params-review")

#: The durable AGENTS.md section this gate pins (issue #2701). The gate fails
#: when the section or any pin phrase disappears.
AGENTS_SECTION_HEADER = "## CI pipeline discipline: weekly engine/registry lane only, tests-only main pipeline, Hermes in agent-image lanes only (mandatory, durable)"
AGENTS_PIN_PHRASES = (
    "owner, a collaborator, and GitHub itself",
    "gh run rerun",
    "verifies locally with `make`",
    "test a workflow that is failing",
    "tests only",
    "agent-image",
    "weekly",
)


def _on_block(wf: dict) -> dict:
    # YAML 1.1 parses a bare `on:` key as boolean True; workflows here use both spellings.
    return wf.get("on") or wf.get(True) or {}


def _load_workflows(root: pathlib.Path) -> tuple[dict[str, dict], list[str]]:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        raise FileNotFoundError(f"no workflows directory at {wf_dir}")
    out: dict[str, dict] = {}
    bad: list[str] = []
    for path in sorted(wf_dir.glob("*.yml")):
        try:
            doc = yaml.safe_load(path.read_text())
        except (yaml.YAMLError, OSError):
            bad.append(path.name)
            continue
        if isinstance(doc, dict):
            out[path.name] = doc
    return out, bad


def _schedules(wf: dict) -> list[str]:
    return [str(slot.get("cron")) for slot in _on_block(wf).get("schedule") or []]


def _uses_agent(wf: dict) -> list[str]:
    """Name the jobs whose steps reference an agent leg/image seam."""
    hits: list[str] = []
    for job_name, job in (wf.get("jobs") or {}).items():
        text = yaml.dump(job)
        for marker in AGENT_MARKERS:
            if marker in text:
                hits.append(f"{job_name}:{marker}")
    return hits


def check(root: pathlib.Path) -> list[str]:
    findings: list[str] = []
    try:
        workflows, bad = _load_workflows(root)
    except FileNotFoundError as exc:
        print(f"unreadable: {exc}", file=sys.stderr)
        sys.exit(2)
    for name in bad:
        findings.append(f"{name}: YAML does not parse — the schedule discipline cannot be measured on it")

    scheduled = {name for name, wf in workflows.items() if _schedules(wf)}
    for name in sorted(scheduled - set(SCHEDULE_ALLOW)):
        findings.append(f"{name}: declares `on.schedule:` ({_schedules(workflows[name])}) outside the allow-list — add it to SCHEDULE_ALLOW with a rationale in review, or remove the clock (issue #2701)")
    for name, why in SCHEDULE_ALLOW.items():
        wf = workflows.get(name)
        if wf is None:
            findings.append(f"{name}: allow-listed as scheduled but the workflow file is gone — the allow-list is stale (issue #2701)")
        elif not _schedules(wf):
            findings.append(f"{name}: allow-listed as scheduled but declares no `schedule:` any more — stale allow-list entry (rationale on record: {why!r})")
    for name, why in AGENT_LANES.items():
        wf = workflows.get(name)
        if wf is None:
            findings.append(f"{name}: allow-listed as an agent lane but the workflow file is gone — the lane list is stale")
        elif _schedules(wf):
            findings.append(f"{name}: a deactivated agent lane declares a `schedule:` again ({_schedules(wf)}) — issue #2701 left it dispatch-only")

    agent_users = {name for name, wf in workflows.items() if _uses_agent(wf)}
    for name in sorted(agent_users - set(AGENT_LANES) - set(SCHEDULE_ALLOW)):
        findings.append(f"{name}: uses the Hermes agent leg outside the agent-lane allow-list — Hermes in CI is limited to the engine/registry agent-image lanes and the allow-listed bot lanes (issue #2701)")
    for name in TESTS_ONLY_PIPELINES:
        wf = workflows.get(name)
        if wf is None:
            continue
        for hit in _uses_agent(wf):
            findings.append(f"{name}: the main pipeline is tests-only, but job {hit.split(':', 1)[0]} carries an agent marker {hit.split(':', 1)[1]!r} (issue #2701)")

    agents_md = root / "AGENTS.md"
    if not agents_md.is_file():
        findings.append("AGENTS.md: missing — the CI discipline rule must live in the repo rules (issue #2701)")
    else:
        text = agents_md.read_text()
        if AGENTS_SECTION_HEADER not in text:
            findings.append("AGENTS.md: the durable CI-discipline section is missing (issue #2701 wrote it; removing it re-opens the drift)")
        else:
            section = text.split(AGENTS_SECTION_HEADER, 1)[1].split("\n## ", 1)[0]
            for phrase in AGENTS_PIN_PHRASES:
                if phrase not in section:
                    findings.append(f"AGENTS.md: the CI-discipline section lost its pin phrase {phrase!r}")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or __name__).splitlines()[0])
    ap.add_argument("command", choices=("check", "report"))
    ap.add_argument("--root", default=str(REPO))
    args = ap.parse_args()
    root = pathlib.Path(args.root)

    findings = check(root)

    if args.command == "report":
        try:
            workflows, _bad = _load_workflows(root)
        except FileNotFoundError as exc:
            print(f"unreadable: {exc}", file=sys.stderr)
            return 2
        scheduled = {n: _schedules(w) for n, w in workflows.items() if _schedules(w)}
        print(f"workflows: {len(workflows)}; scheduled lanes: {len(scheduled)} (allow-list {len(SCHEDULE_ALLOW)})")
        for name in sorted(scheduled):
            mark = "allow-listed" if name in SCHEDULE_ALLOW else "FINDING"
            print(f"  {name}: {scheduled[name]} [{mark}]")
        agent_users = sorted(n for n, w in workflows.items() if _uses_agent(w))
        print(f"agent-leg/agent-image users: {agent_users}")
        print(f"tests-only pipelines: {list(TESTS_ONLY_PIPELINES)}")
        print(f"findings: {len(findings)} (report always exits 0)")
        return 0

    for finding in findings:
        print(f"FINDING: {finding}", file=sys.stderr)
    if findings:
        print(f"check-ci-discipline: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("check-ci-discipline: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
