"""Which PR the fix-bot sweep picks, and what it refuses (issue #222).

The sweep decides through `gh`, which is stubbed on PATH here (the repo's allowance for an
external CLI), so the *decision logic* runs for real against controlled API answers: fork and
draft PRs, `main`, green PRs and branches already at the attempt cap are refused with a reason,
and only a genuinely red same-repo PR is dispatched — with the argv the workflow needs.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SWEEP = REPO / "scripts" / "fix_bot_sweep.py"
sys.path.insert(0, str(REPO / "scripts"))
import fix_bot_sweep as sweep  # noqa: E402

OWNER = "asimov-agent"


def gh_stub(tmp_path: Path, prs, checks: dict, commits: dict) -> Path:
    """A `gh` that answers the three shapes the sweep uses, and logs a dispatch."""
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"prs": prs, "checks": checks, "commits": commits}))
    log = tmp_path / "gh-calls"
    log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, os, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
with open("{log}", "a") as fh:
    print(" ".join(a), file=fh)
if a[:2] == ["pr", "list"]:
    print(json.dumps(sc["prs"]))
elif a[:2] == ["pr", "checks"]:
    print(json.dumps(sc["checks"].get(a[2], [])))
elif a[:2] == ["pr", "view"]:
    print(json.dumps({{"commits": [{{"messageHeadline": m}} for m in sc["commits"].get(a[2], [])]}}))
elif a[:2] == ["workflow", "run"]:
    pass
else:
    sys.exit(f"unexpected gh call: {{a}}")
""")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return log


def run_sweep(tmp_path: Path, args: list[str]):
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    return subprocess.run([sys.executable, str(SWEEP), *args], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, timeout=60)


def pr(num, branch="feat/x", owner=OWNER, draft=False, updated="2026-10-14T01:00:00Z"):
    return {"number": num, "title": f"PR {num}", "isDraft": draft, "headRefName": branch,
            "headRepositoryOwner": {"login": owner}, "updatedAt": updated}


RED = [{"name": "linux / unit", "state": "FAILURE", "bucket": "fail"}]
GREEN = [{"name": "linux / unit", "state": "SUCCESS", "bucket": "pass"}]


def test_a_red_same_repo_pr_is_chosen_and_dispatched(tmp_path):
    log = gh_stub(tmp_path, [pr(252)], {"252": RED}, {"252": []})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "252" in r.stdout and "dispatched the fix-bot" in r.stdout
    dispatch = [l for l in log.read_text().splitlines() if l.startswith("workflow run")]
    assert len(dispatch) == 1 and "pr_number=252" in dispatch[0] and "branch=feat/x" in dispatch[0]
    assert "rounds=3" in dispatch[0] and "fix-bot.yml" in dispatch[0]


def test_a_fork_draft_or_main_pr_is_refused_with_a_reason(tmp_path):
    gh_stub(tmp_path, [pr(1, owner="someone-else"), pr(2, draft=True), pr(3, branch="main")],
            {"1": RED, "2": RED, "3": RED}, {})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 0
    assert "nothing to fix" in r.stdout
    assert "a fork (someone-else)" in r.stdout and "draft" in r.stdout and "the base branch" in r.stdout


def test_a_green_pr_is_refused(tmp_path):
    gh_stub(tmp_path, [pr(10)], {"10": GREEN}, {"10": []})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert "no failing check" in r.stdout and "nothing to fix" in r.stdout


def test_the_attempt_cap_is_respected_and_reported(tmp_path):
    """Three `fix(bot):` commits already on the branch: the bot does not run again."""
    gh_stub(tmp_path, [pr(11)], {"11": RED}, {"11": ["fix(bot): one", "fix(bot): two", "fix(bot): three"]})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert "the cap (3/3 attempts)" in r.stdout and "nothing to fix" in r.stdout


def test_the_oldest_updated_red_pr_wins(tmp_path):
    """One PR per sweep: the oldest-updated red PR is repaired, and the sweep stops there."""
    log = gh_stub(tmp_path, [pr(20, updated="2026-10-14T05:00:00Z"), pr(21, updated="2026-10-14T02:00:00Z")],
                  {"20": RED, "21": RED}, {})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert "dispatched the fix-bot for #21" in r.stdout
    dispatches = [l for l in log.read_text().splitlines() if l.startswith("workflow run")]
    assert len(dispatches) == 1, "one dispatch per sweep"
    assert "pr_number=20" not in dispatches[0], "the newer red PR waits for the next sweep"


def test_dry_run_dispatches_nothing(tmp_path):
    log = gh_stub(tmp_path, [pr(30)], {"30": RED}, {})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--dry"])
    assert "--dry: nothing dispatched" in r.stdout
    assert not [l for l in log.read_text().splitlines() if l.startswith("workflow run")]


def test_the_attempt_counter_only_counts_the_bot(tmp_path, monkeypatch):
    gh_stub(tmp_path, [pr(40)], {"40": RED},
            {"40": ["feat: mine", "fix(bot): a", "docs: theirs", "fix(bot): b"]})
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    assert sweep.bot_attempts(f"{OWNER}/llgenie", 40) == 2


def test_the_cap_is_a_parameter(tmp_path):
    gh_stub(tmp_path, [pr(50)], {"50": RED}, {"50": ["fix(bot): a"]})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--max-attempts", "1"])
    assert "the cap (1/1 attempts)" in r.stdout
