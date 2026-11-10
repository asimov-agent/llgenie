from __future__ import annotations

import sys
from pathlib import Path

from scripts.check_pr_acceptance import (
    main as run_cli,
    pr_body_acceptance_findings as findings_of,
)

REPO = Path(__file__).resolve().parents[1]

# The REAL engine-bump PR #2267 body — its own `## Acceptance criteria` section, verbatim, with all
# four boxes `- [ ]`. Merged 2026-11-09T05:49:50Z via armed auto-merge with `ci-verdict` SUCCESS and
# the published-pin criterion false at the head; this is the exact defect issue #2352 measures. The
# tests drive the REAL script with this REAL PR payload — no mock of the decision.
BUMP_UNTICKED = """# chore(engine): bump llama.cpp to master@7d7f0287

## Problem

The llama.cpp skill pins a release tag that is behind the chrome; bump to the current master.

## How we fix it

1. derive at master@7d7f0287
2. regenerate params + Dockerfiles
3. open this bump PR with its own acceptance checklist

## Acceptance criteria

A pin bump is accepted when the new pin's cells are built, published and served as committed:
- [ ] the engine's `make build-engine` cells for each committed variant build and verify green at the new pin (reviewer reads the engine-build run)
- [ ] the new pin's exact image tag resolves a GHCR manifest for each committed variant (`check-engine-pins-published` / registry-liveness green)
- [ ] the re-derived params + Dockerfiles + SKILL.md are committed and `check-engine-params` passes
- [ ] the pinned change-note + agent-wiki note for this bump ride the PR (`make check-docs` green)

These criteria are ticked by the reviewer from run evidence, not by the bump bot.
"""


def _ticked_variant() -> str:
    """BUMP_UNTICKED with every `- [ ]` → `- [x] (proven: … run=<id>)` (the #1858 evidence form)."""
    out = []
    for i, line in enumerate(BUMP_UNTICKED.splitlines()):
        if line.startswith("- [ ]"):
            tail = line[5:].strip()
            out.append(f"- [x] {tail}  (proven: reviewer=engine-bump-ci comment={i} "
                       "head=7d7f0287 run=42191377162)")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "pr-body.md"
    path.write_text(text)
    return path


# --- acceptance-body-unchecked: a sole-vehicle bump PR with unticked boxes is RED at its head -----

def test_engine_bump_all_four_boxes_unticked_is_RED():
    """The #2352 measured shape: a bump PR closes no issue, so its body checklist is the SOLE
    acceptance record, and four unticked boxes must be RED."""
    # Given an engine-bump PR body with four `- [ ]` boxes that closes no issue
    body = BUMP_UNTICKED

    # When  the body-gate evaluates it (sole vehicle: the close set is empty)
    findings = findings_of(body, closed=set())

    # Then  it reports 4 acceptance-body-unchecked findings, all blocking
    assert len(findings) == 4, [f["key"] for f in findings]
    assert all(f["key"] == "acceptance-body-unchecked" for f in findings)
    assert all(f["blocking"] for f in findings)


def test_cli_body_engine_bump_all_unticked_is_RED(tmp_path):
    """Drive the REAL CLI with the real #2267 payload file — exit non-zero."""
    # Given a real bump PR payload file on disk
    path = _write(tmp_path, BUMP_UNTICKED)

    # When  the real script runs `body` on it
    rc = run_cli(["body", "--body-file", str(path)])

    # Then  it is RED (the #2267 class can no longer merge while 0/4 is ticked)
    assert rc != 0


# --- acceptance-body green: all boxes ticked with run ids ---------------------------------------

def test_engine_bump_all_boxes_ticked_with_run_ids_is_GREEN(tmp_path):
    """A correct implementation — every box ticked and each tick naming a CI run id — passes, so the
    gate does not reject a correct bump (#2352 acceptance: negative control)."""
    # Given the same bump body, each criterion ticked `- [x]` naming a `run=<id>`
    body = _ticked_variant()
    path = _write(tmp_path, body)

    # When  the real script evaluates it
    rc = run_cli(["body", "--body-file", str(path)])

    # Then  it is GREEN
    assert rc == 0
    # And   the pure function reports zero blocking findings
    assert findings_of(body, closed=set()) == []


def test_engine_bump_tick_with_no_evidence_is_RED():
    """A `- [x]` that names no run id and no command+rc+sha is the #1858 self-tick class on the body
    side — unprovable by definition, so the sole-vehicle bump stays red."""
    # Given a bump body whose boxes are ticked with no re-producible evidence
    import re as _re
    body = _re.sub(r"\s*\(proven:.*?\)\s*$", "", _ticked_variant(), flags=_re.M)
    # After stripping the whole `(proven: …)` suffix the box text names no run=
    assert "run=42191377162" not in body

    # When  the pure function evaluates it
    findings = findings_of(body, closed=set())

    # Then  every ticked-but-unprovable box is a blocking tick-unprovable finding
    assert findings and all(f["key"] == "acceptance-body-tick-unprovable" for f in findings)
    assert all(f["blocking"] for f in findings)


# --- sole-vehicle scoping: a PR that closes an issue is NOT held by the body gate ----------------

def test_a_PR_that_closes_an_issue_is_skipped():
    """#1644's issue-body write-back path and the issue-side gate own a PR that closes an issue: its
    body checklist is NOT the sole vehicle, so an unticked body box here must not red this gate (the
    #1792 check-pr-acceptance verifies the linked issue instead). Existing issue-side tests are
    unchanged."""
    # Given a PR body that closes #2091 and carries partly-unticked `## Acceptance criteria`
    body = ("## What and why\n\ncloses #2091\n\n## Acceptance criteria\n\n"
            "- [ ] dispatch with github.token\n- [ ] marker in the log\n")

    # When  the body-gate evaluates it AND the close set is non-empty (issue-side gate owns it)
    findings = findings_of(body, closed={2091})

    # Then  it is skipped (no acceptance-body-* finding)
    assert findings == []


def test_cli_body_PR_that_closes_an_issue_is_GREEN(tmp_path):
    """CLI control: the same closing PR through the real script exits 0 because it closes an issue."""
    # Given a PR body closing an issue, on disk
    path = _write(tmp_path, "## What and why\n\ncloses #2091\n\n## Acceptance criteria\n\n- [ ] box\n")

    # When  the real script runs `body` on it
    rc = run_cli(["body", "--body-file", str(path)])

    # Then  it is GREEN — the issue-side gate owns the close
    assert rc == 0


# --- the gate is in the judged set ---------------------------------------------------------------

def test_the_gate_step_is_in_the_judged_ci_guard_job():
    """The body-gate must be a step of the ci.yml `guard` job — a row of the ci-scope judged job table
    (`ci_scope.JOBS`), read from the workflow/table at the fixing head, never a grep-for-a-string."""
    from scripts import ci_scope  # the judged job table, live from the tree
    # Given the judged ci-scope job table
    judged = [name for name, _stages in ci_scope.JOBS]
    # When  we resolve the gate's home in the tree
    ci = (REPO / ".github/workflows/ci.yml").read_text()
    guard_block = ci.split("\n  guard:\n", 1)[1].split("\n  ci-images:", 1)[0]
    # Then  `guard` is a judged job and the ci.yml guard job runs the body-gate step
    assert "guard" in judged
    assert "make check-pr-acceptance-body" in guard_block
    # And   the verdict judges ci.yml (its roster is the judged set)
    from scripts import verdict_roster as vr
    assert "ci.yml" in vr.judged_files(REPO)
