#!/usr/bin/env python3
"""The reconcile guard answers "is this PR still reconcilable?" before a lane acts (issue #1749).

The defect class, measured 2026-11-05: a lane was handed a PR-numbered red by a post-merge
straggler run or a state-blind board search and described reconcile work for a PR the API says
already merged — "open #1742 at head 8482c24b, failing guard job 126996060863, pending amend"
while #1742 had merged at 02:33:51Z (squash `ebabd9f1`, branch
`fix/ci-verdict-skip-merged-pr-stragglers` deleted, run 41951437719 all-green, zero amend/guard
comments). The guard is the reconcile trigger's own read: `pulls/<n>` state/merged/mergeCommit,
one verdict line, and a failed read blocks the reconcile rather than guessing a verdict.

These cases run the REAL script against a REAL fake `gh` binary on disk (the repo's pattern: no
mock of the product, only the external API is a stand-in), plus the Makefile target and the
host-only wiring registration that make it the fleet's one code path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
from scripts import pr_reconcile_guard as guard

MERGED_1742 = {
    "state": "MERGED",
    "mergedAt": "2026-11-05T02:33:51Z", "closedAt": "2026-11-05T02:33:51Z",
    "mergeCommit": {"oid": "ebabd9f12ea808c927122e858cae35fbc06e4a05"},
    "headRefOid": "8482c24b6803f483ae962256267a62817aa59690",
    "headRefName": "fix/ci-verdict-skip-merged-pr-stragglers",
    "mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN",
}
OPEN_PR = {
    "state": "OPEN", "mergedAt": None, "closedAt": None, "mergeCommit": None,
    "headRefOid": "df4c0ff47b62fbf70c21c2778c68c58183fd7f17",
    "headRefName": "feat/hermes-model-chain",
    "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
}
CLOSED_UNMERGED = {
    "state": "CLOSED", "mergedAt": None,
    "closedAt": "2026-11-18T10:11:12Z", "mergeCommit": None,
    "headRefOid": "0a0b0c0d0e0f1011121314151617181920212223",
    "headRefName": "chore/superseded-duplicate",
    "mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN",
}


def _fake_gh(tmp_path: Path, name: str, view_stdout: str = "", view_exit: int = 0) -> Path:
    """A `gh` answering `pr view` with the given body/exit, recording every argv it received."""
    log = tmp_path / f"{name}.log"
    gh = tmp_path / f"gh-{name}"
    gh.write_text(f'''#!{sys.executable}
import json, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "view"]:
    sys.stdout.write({view_stdout!r})
    raise SystemExit({view_exit})
raise SystemExit(f"unexpected gh argv: {{args}}")
''')
    gh.chmod(0o755)
    return gh


def _calls(tmp_path: Path, name: str) -> list[list[str]]:
    log = tmp_path / f"{name}.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_merged_pr_answers_read_only_with_the_merge_commit(tmp_path):
    """The phantom shape itself: #1742 merged — the guard says `merged, read-only`, never `red`."""
    gh = _fake_gh(tmp_path, "merged", json.dumps(MERGED_1742))
    rc = guard.main(["--pr", "1742", "--repo", "asimov-agent/llgenie", "--gh", str(gh)])
    returncode = rc
    assert returncode == 0
    # `main` prints to stdout: capture through the verdict function for the exact line, then pin
    # the CLI produced exit 0 above.
    line = guard.verdict("asimov-agent/llgenie", 1742, str(gh))
    assert line is not None
    assert line.startswith("#1742 merged, read-only")
    assert "mergeCommit ebabd9f12e" in line
    assert "merged 2026-11-05T02:33:51Z" in line
    assert "head 8482c24b68" in line
    assert "actionable" not in line


def test_closed_unmerged_pr_answers_read_only(tmp_path):
    gh = _fake_gh(tmp_path, "closed", json.dumps(CLOSED_UNMERGED))
    assert guard.main(["--pr", "2916", "--gh", str(gh)]) == 0
    line = guard.verdict(guard.DEFAULT_REPO, 2916, str(gh))
    assert line is not None and line.startswith("#2916 closed, read-only")
    assert "closed 2026-11-18T10:11:12Z" in line


def test_open_pr_stays_actionable_and_names_the_merge_state(tmp_path):
    gh = _fake_gh(tmp_path, "open", json.dumps(OPEN_PR))
    assert guard.main(["--pr", "2937", "--gh", str(gh)]) == 0
    line = guard.verdict(guard.DEFAULT_REPO, 2937, str(gh))
    assert line is not None and line.startswith("#2937 open, actionable")
    assert "mergeState=CLEAN" in line and "mergeable=true" in line
    assert "head df4c0ff47b" in line


def test_a_failed_read_is_not_a_verdict(tmp_path):
    """404 / gh failure: exit non-zero, print no verdict line — an unevidenced reconcile stays blocked."""
    gh = _fake_gh(tmp_path, "fail404", '{"message": "Not Found", "status": "404"}', view_exit=1)
    assert guard.main(["--pr", "999999", "--gh", str(gh)]) == 1
    assert guard.verdict(guard.DEFAULT_REPO, 999999, str(gh)) is None

    # A zero-exit non-JSON answer is the same no-answer (a gh complaint on stdout).
    gh2 = _fake_gh(tmp_path, "garbage", "unknown flag: --json\n")
    assert guard.main(["--pr", "1", "--gh", str(gh2)]) == 1
    assert guard.verdict(guard.DEFAULT_REPO, 1, str(gh2)) is None


def test_the_read_asks_for_state_and_merged(tmp_path):
    """The guard's whole contract is the state triple: pin that the gh call requests it."""
    gh = _fake_gh(tmp_path, "fields", json.dumps(MERGED_1742))
    guard.verdict("asimov-agent/llgenie", 1742, str(gh))
    calls = _calls(tmp_path, "fields")
    assert calls, "the guard made no gh call"
    argv = calls[0]
    assert argv[:2] == ["pr", "view"]
    joined = " ".join(argv)
    for field in ("state", "mergedAt", "mergeCommit", "headRefOid"):
        assert field in joined, f"the read does not request {field}"


def test_the_fleet_path_is_the_target_and_the_registration_lands():
    """One code path: mk/bots.mk wires the target to the script (lanes run it from their
    terminal; no CI job reconciles PRs, and the help line says no CI coverage), the unit
    battery proves the script, and package-layers states the module with its proc edge."""
    bots = (REPO / "mk" / "bots.mk").read_text()
    assert "lane-reconcile-guard:" in bots
    recipe_block = bots.split("lane-reconcile-guard:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/pr_reconcile_guard.py" in recipe_block
    assert "$(GH_REPO)" in recipe_block and "$(REPO)" not in recipe_block, \
        "the recipe must take the slug form; a checkout path never belongs in --repo (issues #343/#434)"

    fixture = json.loads((REPO / "tests" / "fixtures" / "host-only-wiring.json").read_text())
    assert "scripts/pr_reconcile_guard.py" not in fixture["documents"], \
        "the guard is proven in the unit battery, so a host-only document is stale"
    assert "lane-reconcile-guard" not in fixture["targets"], \
        "the help line claims no CI coverage, so a host-only target record is stale"

    layers = json.loads((REPO / "scripts" / "package-layers.json").read_text())
    assert "pr_reconcile_guard" in layers["groups"]["Bots and automation"]
    edges = {(e["from"], e["to"]) for e in layers["allowed_edges"]}
    assert ("pr_reconcile_guard", "proc") in edges


def test_the_make_phony_roster_lists_the_target():
    makefile = (REPO / "Makefile").read_text()
    assert "lane-reconcile-guard" in makefile.split(".PHONY:", 1)[1]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
