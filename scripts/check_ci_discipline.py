#!/usr/bin/env python3
"""CI discipline: only the weekly engine/registry lane keeps cron; the main pipeline is tests-only;
Hermes appears only in agent-image engine/registry legs; the agent never starts CI manually (issue #2702).

Owner policy stated 2026-11-15, measured against main `dcfb96b7` (#2702): of 37 workflow files, 26
declared an `on.schedule:` key (30 cron blocks), and eight of them were autonomous bot/trigger lanes
that run LLM/agent work or re-trigger the CI pipeline on a clock. This guard encodes and ENFORCES the
repo law AGENTS.md now carries in its durable CI-discipline section:

1. **Schedule allow-list.** A `schedule:` trigger key may appear only in an explicit 18-file
   allow-list, each entry carrying a one-line rationale (the weekly engine lane `engine-bump.yml`,
   the weekly models/registry fetch `registry-sync.yml`, the weekly test battery `all-pipelines.yml`,
   the non-agent security/liveness monitors, and the merge/monitoring plumbing). A non-allow-listed
   workflow declaring a `schedule:` is a finding naming the file.
2. **No allow-list rot.** An allow-listed file that loses its `schedule:` is a finding — removing the
   clock from a sanctioned weekly lane must be a deliberate edit to the workflow AND the allow-list,
   not a silent drift (the same shape `check-main-ruleset` uses for its pinned contexts).
3. **Main pipeline is tests-only.** The test-pipeline files `ci.yml` and `pipeline.yml` may carry no
   agent-leg (`./.github/actions/agent-leg`) and no agent-image (`agent-image-ref`, `make agent-image`,
   `fix-loop-image`) job. A job in either that references them is a finding.
4. **Agent-leg allow-list.** A workflow that uses `./.github/actions/agent-leg` must be in the
   agent-leg allow-list — the dispatch-only bot lanes (architecture-bot, fix-bot, issue-bot,
   issue-refiner, rebase-bot, registry-sync-review). An agent-leg user outside the list is a finding.
5. **AGENTS.md carries the durable section.** AGENTS.md must state the CI-discipline section; its
   deletion is a finding, so the repo law cannot be silently removed.

Commands (driven by make, never by hand):

    check_ci_discipline.py check [--root ROOT]    exit 1 on any violation, naming each offending file
    check_ci_discipline.py report [--root ROOT]   print the allow-list and per-file verdict, exit 0

Stdlib only — it runs on a bare host in `ci-unit` and `lane-preflight` with no PyYAML, the same
reason `check_workflows.py` is stdlib only (its `schedule` and agent-leg readers are textual, exactly
how `check_workflows._on_triggers` reads triggers without a YAML library).

The 18-file schedule allow-list below is the ONE sanctioned state — adding a scheduled lane means
editing this list deliberately with a rationale (reviewable), or the gate reddens CI.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
AGENTS = "AGENTS.md"

#: The main pipeline's test-only files. They may run NO agent work at all (issue #2702, requirement 3).
TEST_PIPELINE = ("ci.yml", "pipeline.yml")

#: The composite action that runs the ordered agent-leg preflight (issue #798, used by every bot leg).
AGENT_LEG = "./.github/actions/agent-leg"

#: Agent-image references. `agent-image-ref` prints the :latest ref; `make agent-image` ensures it;
#: `fix-loop-image` is the image loop helper. Any of these in a test-pipeline file is agent work.
AGENT_IMAGE_REFS = re.compile(r"agent-image-ref|\bmake agent-image\b|fix-loop-image")

#: A `schedule:` trigger key indented under `on:` — 2 spaces, the trigger-column this guard reads
#: (the same way `check_workflows` reads `on:`-nested trigger keys). Only column-two `schedule:` is a
#: top-level trigger; a deeper mention (e.g. inside a `run:` script) is not a job's event.
SCHEDULE_KEY = re.compile(r"^  schedule:\s*(?:#.*)?$")

#: The durable AGENTS.md section heading — its presence (and the sentence below) is asserted as a
#: whole so the repo law cannot be reduced to a paragraph, mirroring `check-main-ruleset`'s shape.
AGENTS_SECTION = "## CI discipline (MANDATORY, durable)"
AGENTS_SENTENCE = "the agent never starts a CI pipeline manually"

#: The 18 files that may declare `on.schedule:`, each with a one-line rationale. The weekly engine lane
#: (`engine-bump.yml`), the weekly models/registry fetch (`registry-sync.yml`), the weekly test battery
#: (`all-pipelines.yml`), the non-agent security/liveness monitors, and the merge/monitoring plumbing
#: the owner's auto-merge/auto-approve mandate relies on. Measured on main `dcfb96b7` (#2702).
SCHEDULE_ALLOWLIST: dict[str, dict[str, str]] = {
    "engine-bump.yml":          {"rationale": "weekly engine lane — bumps engines + builds images + fetches latest models"},
    "registry-sync.yml":        {"rationale": "weekly models/registry fetch — vendors the trending store"},
    "all-pipelines.yml":        {"rationale": "weekly test battery — drives the full CI matrix on a schedule"},
    "arms.yml":                 {"rationale": "merge/monitoring plumbing the auto-approve mandate relies on"},
    "auto-merge.yml":           {"rationale": "merge recheck sweep the auto-merge/auto-approve mandate depends on"},
    "holds.yml":                {"rationale": "merge/monitoring plumbing — holds on headed runs"},
    "queued-alarm.yml":         {"rationale": "monitoring plumbing — alarms on runs queued too long"},
    "engine-bump-rebase.yml":   {"rationale": "merge/monitoring plumbing — rebases the engine bump PR"},
    "ci-frozen-reaper.yml":     {"rationale": "merge/monitoring plumbing — reaps frozen CI runs"},
    "stale-branch-cleanup.yml": {"rationale": "merge/monitoring plumbing — prunes stale PR branches"},
    "main-ruleset.yml":         {"rationale": "monitoring plumbing — re-checks the main ruleset"},
    "ci-hf-live.yml":           {"rationale": "non-agent liveness monitor — probes the model host"},
    "registry-liveness.yml":    {"rationale": "non-agent liveness monitor — probes the registry store"},
    "security-scan.yml":        {"rationale": "non-agent security scan"},
    "security-images.yml":      {"rationale": "non-agent security scanner image publish"},
    "security-bot.yml":         {"rationale": "non-agent security tracker"},
    "semgrep-rules-refresh.yml":{"rationale": "non-agent security scanner rules refresh"},
    "code-review-bot.yml":      {"rationale": "deterministic scanner (no agent-leg/agent-image job in it)"},
}

#: The workflows allowed to use `./.github/actions/agent-leg` — the dispatch-only bot lanes (issue
#: #2702 requirement 4). A user outside this list (e.g. a scheduled or test-pipeline workflow) is a
#: finding: Hermes in CI is limited to agent-image engine/registry legs.
AGENT_LEG_ALLOWLIST: dict[str, dict[str, str]] = {
    "architecture-bot.yml":     {"rationale": "dispatch-only bot lane — scans the tree for architecture gaps"},
    "fix-bot.yml":              {"rationale": "manual-only job that repairs a red CI run on a human dispatch"},
    "issue-bot.yml":            {"rationale": "dispatch-only bot lane — implements one issue per run"},
    "issue-refiner.yml":        {"rationale": "dispatch-only bot lane — restates one issue body per run"},
    "rebase-bot.yml":           {"rationale": "dispatch-only bot lane — rebases stale PRs when dispatched"},
    "registry-sync-review.yml": {"rationale": "dispatch-only bot lane — reviews a green registry-sync PR"},
}


def workflow_files(root: Path = REPO_ROOT) -> list[Path]:
    return sorted((root / WORKFLOWS).glob("*.yml"))


def read_lines(path: Path) -> list[str]:
    return path.read_text().splitlines()


def has_schedule(lines: list[str]) -> bool:
    """A top-level (column-two) `schedule:` trigger key inside the `on:` block.

    Reads the `on:` block's direct children only — a column-two key immediately beneath `on:` — so
    a mention deeper in the file (e.g. inside a `run:` script or a nested mapping) is never a
    workflow's clock, the same way `check_workflows` reads trigger keys textually.
    """
    for i, line in enumerate(lines):
        if not re.match(r"^on:", line):
            continue
        for j in range(i + 1, len(lines)):
            l = lines[j]
            if not l.strip():
                continue
            if l.startswith("  ") and l[2:3] not in (" ", "\t"):
                if SCHEDULE_KEY.match(l):
                    return True
            elif not l.startswith(" "):
                break                           # past the on: block
        return False
    return False


def uses_agent_leg(text: str) -> bool:
    return AGENT_LEG in text


def uses_agent_image(text: str) -> bool:
    return AGENT_IMAGE_REFS.search(text) is not None


def agents_section_present(root: Path) -> bool:
    path = root / AGENTS
    if not path.exists():
        return False
    text = path.read_text()
    return AGENTS_SECTION in text and AGENTS_SENTENCE in text


def check(root: Path = REPO_ROOT) -> list[dict]:
    """Every CI-discipline finding; [] means the repo obeys the policy."""
    out: list[dict] = []
    files = workflow_files(root)

    # 1+2. schedule allow-list both directions.
    present = {p.name: has_schedule(read_lines(p)) for p in files}
    for name, has in sorted(present.items()):
        where = f"{WORKFLOWS}/{name}"
        if has and name not in SCHEDULE_ALLOWLIST:
            out.append({
                "key": f"ci-discipline-schedule-extra/{where}",
                "title": f"ci: {where} declares an `on.schedule:` outside the CI-discipline allow-list",
                "evidence": (
                    f"`{where}` carries a `schedule:` trigger. Owner policy 2026-11-15 (#2702): only "
                    f"the weekly engine/registry lane keeps cron; every other scheduled lane was "
                    f"deactivated. Add it to the SCHEDULE_ALLOWLIST with a one-line rationale (a "
                    f"deliberate, reviewable decision), or remove the schedule — the cron minute "
                    f"budget is already exhausted (`zero-job-pending.yml:14-16`)."
                ),
                "where": where,
            })
        elif not has and name in SCHEDULE_ALLOWLIST:
            out.append({
                "key": f"ci-discipline-schedule-lost/{where}",
                "title": f"ci: allow-listed {where} lost its `schedule:` — the allow-list is stale",
                "evidence": (
                    f"`{where}` is in the CI-discipline schedule allow-list ({SCHEDULE_ALLOWLIST[name]['rationale']}) "
                    f"but no longer declares a `schedule:`. \"Removing a scheduled lane\" must be a "
                    f"deliberate edit to the workflow AND the allow-list together, not a silent drift: "
                    f"an allow-listed file that lost its schedule is a stale allow-list, the same "
                    f"class of defect as a host-only-wiring or git-identity exception that rots."
                ),
                "where": where,
            })

    # 3. the main pipeline is tests-only.
    for name in TEST_PIPELINE:
        path = root / WORKFLOWS / name
        if not path.exists():
            continue
        text = path.read_text()
        where = f"{WORKFLOWS}/{name}"
        if uses_agent_leg(text):
            out.append({
                "key": f"ci-discipline-agent-in-test-pipeline/{where}",
                "title": f"ci: {where} carries an agent-leg job — the main pipeline is tests-only",
                "evidence": (
                    f"`{where}` references the agent-leg composite action `{AGENT_LEG}`. Issue #2702 "
                    f"policy: the main CI pipeline runs tests only, no LLM; Hermes in CI is limited to "
                    f"agent-image engine/registry legs. Remove the agent job from the test pipeline."
                ),
                "where": where,
            })
        if uses_agent_image(text):
            out.append({
                "key": f"ci-discipline-agent-image-in-test-pipeline/{where}",
                "title": f"ci: {where} carries an agent-image job — the main pipeline is tests-only",
                "evidence": (
                    f"`{where}` references the agent image (agent-image-ref / make agent-image / "
                    f"fix-loop-image). Issue #2702 policy: the main CI pipeline runs tests only; "
                    f"agent-image work belongs in the engine/registry legs. Remove it from the test "
                    f"pipeline."
                ),
                "where": where,
            })

    # 4. agent-leg users are inside the agent-leg allow-list.
    for p in files:
        text = p.read_text()
        if not uses_agent_leg(text):
            continue
        if p.name in AGENT_LEG_ALLOWLIST:
            continue
        where = f"{WORKFLOWS}/{p.name}"
        out.append({
            "key": f"ci-discipline-agent-leg-outside/{where}",
            "title": f"ci: {where} uses the agent leg outside the agent-leg allow-list",
            "evidence": (
                f"`{where}` references `{AGENT_LEG}` but is not in AGENT_LEG_ALLOWLIST. Owner policy "
                f"2026-11-15 (#2702): Hermes in CI is limited to agent-image engine/registry legs and "
                f"the dispatch-only bot lanes; a workflow using the agent leg must be listed here "
                f"with its rationale, or use none."
            ),
            "where": where,
        })

    # 5. the durable AGENTS.md section is present.
    if not agents_section_present(root):
        where = AGENTS
        out.append({
            "key": f"ci-discipline-agents-section/{where}",
            "title": f"ci: {where} lacks the durable CI-discipline section",
            "evidence": (
                f"`{where}` must carry `{AGENTS_SECTION}` stating that only the weekly engine/registry "
                f"lane keeps cron, the main pipeline is tests-only, Hermes appears only in agent-image "
                f"engine/registry legs, and {AGENTS_SENTENCE}. The section deletion is a finding, so "
                f"the repo law cannot be silently removed (the same shape check-main-ruleset uses)."
            ),
            "where": where,
        })

    return out


def render(items: list[dict]) -> str:
    if not items:
        return ("[ci-discipline] OK: only the 18 allow-listed workflows declare a schedule; the main "
                "pipeline (ci.yml/pipeline.yml) carries no agent-leg or agent-image job; every "
                "agent-leg user is in the allow-list; and AGENTS.md carries the durable "
                "CI-discipline section")
    lines = [f"[ci-discipline] {len(items)} violation(s)"]
    for f in items:
        lines += ["", f"- {f['title']}", f"  where: {f['where']}", f"  {f['evidence']}"]
    return "\n".join(lines)


def report(root: Path = REPO_ROOT) -> str:
    files = workflow_files(root)
    lines = [f"[ci-discipline] {len(files)} workflow file(s); schedule allow-list: "
             f"{len(SCHEDULE_ALLOWLIST)} file(s), agent-leg allow-list: {len(AGENT_LEG_ALLOWLIST)} file(s)"]
    lines.append("[ci-discipline] allowed to declare a schedule:")
    for name, d in sorted(SCHEDULE_ALLOWLIST.items()):
        lines.append(f"  - {name} — {d['rationale']}")
    lines.append("[ci-discipline] allowed to use the agent leg:")
    for name, d in sorted(AGENT_LEG_ALLOWLIST.items()):
        lines.append(f"  - {name} — {d['rationale']}")
    for f in findings(root):
        lines += ["", f"- {f['title']}", f"  where: {f['where']}"]
    lines += ["", render(findings(root))]
    return "\n".join(lines)


def findings(root: Path = REPO_ROOT) -> list[dict]:
    return check(root)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_ci_discipline", description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--root", default=str(REPO_ROOT))
    args = p.parse_args(argv)
    if not args.cmd:
        p.error("need a command: check | report")
    root = Path(args.root)
    if args.cmd == "report":
        print(report(root))
        return 0
    items = findings(root)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
