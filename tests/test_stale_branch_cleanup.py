"""The stale-branch-cleanup actor is only safe when the pipeline asserts itself.

Issue #1344: the repo accumulates non-`main` branches; most are squash-merged PR branches (tip is NOT
an ancestor of main — the #1317 lesson) or unmerged bot branches. Deleting by age alone would destroy
in-flight and squash-delivered work. The workflow and its script are governed by the repo's
workflow-hygiene gates (guard, dispatch-form, wiring), and THIS file proves the deletion decision is
gated on the safety predicate — never on age alone.

The script's output is real: each test drives the real `scripts/stale_branch_cleanup.py` with a fake
`gh` on PATH answering the exact API calls the production code makes (pr-list, compare, branch list,
dates). A pure-read fake — the script's own subprocess calls hit the fake binary, so the decision logic
is exercised end to end. Applies check_dispatch_forms-style fixture isolation: the guard/hygiene gates
run over the repo's real workflow file; deletion-safety is proven here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

from scripts import stale_branch_cleanup as sbc


def _run(argv: list[str], gh_env: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = gh_env + ":" + env.get("PATH", "/usr/bin:/bin")
    return subprocess.run([sys.executable, str(sbc.__file__), *argv],
                          capture_output=True, text=True, env=env)


def _write_gh(tmp_path: Path, script_body: str) -> str:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text("#!/usr/bin/env python3\n" + script_body)
    gh.chmod(0o755)
    return str(bindir)


def _newer_sha() -> str:
    return "a" * 40


def _old_days_ago() -> str:
    return (datetime.now(timezone.utc).replace(tzinfo=None)
            - __import__("datetime").timedelta(days=10)).isoformat()


def _fake_gh_script(branches: list[dict], prs: dict[str, str],
                    compare_status: str = "behind",
                    default: str = "main") -> str:
    """A `gh` answering exactly the calls stale_branch_cleanup makes."""
    bf = json.dumps(branches)
    old_date = (datetime.now(timezone.utc).replace(tzinfo=None)
                - __import__("datetime").timedelta(days=10)).isoformat()
    return ("import json, sys\n"
            "def out(x): print(x); sys.exit(0)\n"
            f"DEFAULT = {default!r}\n"
            f"B = {bf}\n"
            f"PRS = {json.dumps(prs)}\n"
            f"CSTAT = {compare_status!r}\n"
            f"OLD_DATE = {old_date!r}\n"
            "args = sys.argv[1:]\n"
            "if args[:2] == ['repo', 'view']:\n"
            "    out(DEFAULT) if '--jq' in args else out('{\"defaultBranchRef\": {\"name\": \"' + DEFAULT + '\"}}')\n"
            "if args[:2] == ['pr', 'list']:\n"
            "    head_branch = args[args.index('--head')+1]\n"
            "    st = PRS.get(head_branch, 'NONE')\n"
            "    stq = args[args.index('--state')+1]\n"
            "    if stq == 'open':\n"
            "        out('[{\"number\": 1, \"state\": \"OPEN\"}]') if st == 'OPEN' else out('[]')\n"
            "    else:\n"
            "        out(json.dumps([{'number': 1, 'state': st}])) if st in ('MERGED','CLOSED') else out('[]')\n"
            "if args[:1] == ['api']:\n"
            "    ep = next(a for a in args[1:] if a.startswith('repos/'))\n"
            "    if 'branches?' in ep:\n"
            "        out(json.dumps(B))\n"
            "    if '/branches/' in ep and '/protection' in ep:\n"
            "        sys.stderr.write('gh: Not Found (HTTP 404)\\n'); sys.exit(1)\n"
            "    if '/commits/' in ep and '/compare/' not in ep:\n"
            "        out(OLD_DATE)\n"
            "    if 'compare/' in ep:\n"
            "        out(CSTAT)\n"
            "    sys.exit(0)\n"
            "sys.exit(1)\n")


def _tree_with_repo(tmp_path: Path, branches: list[dict], prs: dict[str, str],
                    compare: str = "behind", default: str = "main") -> tuple[str, Path]:
    bindir = _write_gh(tmp_path, _fake_gh_script(branches, prs, compare, default))
    return bindir, tmp_path


def test_report_only_never_calls_delete(tmp_path):
    """A branch that is old, delivered, with no open PR is REPORTED as would-delete but NOT deleted."""
    branches = [{"name": "fix/123-old-delivered", "commit": {"sha": _newer_sha()}}]
    bindir, _ = _tree_with_repo(tmp_path, branches, {"fix/123-old-delivered": "MERGED"},
                                compare="behind")
    out = _run(["--repo", "asimov-agent/llgenie", "--age-days", "3"], bindir)
    assert out.returncode == 0, out.stderr
    assert "report-only" in out.stdout
    assert "WOULD-DELETE fix/123-old-delivered" in out.stdout
    assert "DELETED" not in out.stdout, out.stdout
    assert "applied:" not in out.stdout


def test_open_pr_branch_is_never_deleted_even_with_APPLY(tmp_path):
    """A branch with an open PR is KEPT even when APPLY is passed."""
    branches = [{"name": "fix/123-open-pr", "commit": {"sha": _newer_sha()}}]
    bindir, _ = _tree_with_repo(tmp_path, branches, {"fix/123-open-pr": "OPEN"})
    out = _run(["--repo", "asimov-agent/llgenie", "--apply"], bindir)
    assert out.returncode == 0, out.stderr
    assert "KEEP fix/123-open-pr" in out.stdout
    assert "live vehicle (OPEN) — kept" in out.stdout
    assert "applied: 0 deleted" in out.stdout
    assert "WOULD-DELETE" not in out.stdout


def test_unreachable_commits_are_reported_not_deleted(tmp_path):
    """A branch whose tip is ahead of main (commits not delivered) and has no merged PR is kept."""
    branches = [{"name": "fix/456-unmerged", "commit": {"sha": _newer_sha()}}]
    bindir, _ = _tree_with_repo(tmp_path, branches, {"fix/456-unmerged": "NONE"},
                                compare="ahead")
    out = _run(["--repo", "asimov-agent/llgenie", "--apply"], bindir)
    assert out.returncode == 0, out.stderr
    assert "KEEP fix/456-unmerged" in out.stdout
    assert "unreachable" in out.stdout
    assert "applied: 0 deleted" in out.stdout


def test_merged_pr_squash_branch_is_deleted_under_APPLY(tmp_path):
    """A squash-merged PR branch (tip NOT an ancestor) is recognised as delivered via PR MERGED."""
    branches = [{"name": "fix/789-squash-merged", "commit": {"sha": _newer_sha()}}]
    bindir, _ = _tree_with_repo(tmp_path, branches, {"fix/789-squash-merged": "MERGED"},
                                compare="ahead")
    out = _run(["--repo", "asimov-agent/llgenie", "--apply"], bindir)
    assert out.returncode == 0, out.stderr
    assert "DELETED fix/789-squash-merged" in out.stdout
    assert "applied: 1 deleted" in out.stdout


def test_default_branch_never_touched(tmp_path):
    """`main` and the default branch are never candidates even if present in the list."""
    branches = [{"name": "main", "commit": {"sha": _newer_sha()}},
                {"name": "develop", "commit": {"sha": _newer_sha()}}]
    bindir, _ = _tree_with_repo(tmp_path, branches, {"main": "MERGED", "develop": "MERGED"},
                                default="develop")
    out = _run(["--repo", "asimov-agent/llgenie", "--apply"], bindir)
    assert out.returncode == 0, out.stderr
    assert "main" not in out.stdout or "KEEP" in out.stdout
    assert "WOULD-DELETE main" not in out.stdout
    assert "applied: 0 deleted" in out.stdout
