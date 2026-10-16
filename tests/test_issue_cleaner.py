"""Which OPEN issue a merged PR already implemented — and whether closing it is right (#325).

The decision runs through `gh`, stubbed on `PATH` here (the repo's allowance for an external CLI), so
the *logic* runs for real against controlled API answers. The cases that matter are the ones a naive
cleaner gets wrong:

  * a merged PR whose body closed its issue — nothing to do, the linkage held;
  * a merged PR that implemented a still-open issue — the stale-open this bot exists to close;
  * a merged PR whose `Not covered` names the issue — a tracked REMAINDER, left open (the #344/#256
    case: #344 implemented #256 and named #339-#343 as out of its scope; a cleaner that closed those
    would close work still being tracked);
  * a merged PR that names no issue at all — ignored, loudly.

`--dry` must mutate nothing; `--apply` must post the evidence comment and close.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import issue_cleaner as cleaner  # noqa: E402

OWNER = "asimov-agent"


# --------------------------------------------------------------------------------------- pure logic

def test_not_covered_reads_its_section_and_stops_at_the_next_heading():
    body = (
        "## Goal\n\nImplement #256.\n\n"
        "## Not covered\n\n"
        "- #339 — the product-code half\n"
        "- #340, #341, #342, #343 — the guard halves\n\n"
        "## Provenance\n\nSplit out of #324.\n"
    )
    assert cleaner.not_covered(body) == {339, 340, 341, 342, 343}


def test_not_covered_is_empty_without_the_section():
    # A PR with no `Not covered` declares no remainder: every issue it names, it meant to close.
    assert cleaner.not_covered("## Goal\n\nImplement #256.\n") == set()
    assert cleaner.not_covered(None) == set()


def test_not_covered_does_not_swallow_a_later_section():
    body = "## Not covered\n\nnothing here\n\n## Follow-up\n\n- #999 — filed separately\n"
    assert cleaner.not_covered(body) == set()


def test_implemented_issue_prefers_the_merge_commit_then_the_title():
    commit = {"message": "fix(hub): retry once\n\nIssue: #256\n"}
    assert cleaner.implemented_issue(
        {"number": 344, "title": "x (#999)", "body": "", "mergeCommit": commit}
    ) == (256, "the merge commit's `Issue:` line")
    assert cleaner.implemented_issue(
        {"number": 344, "title": "x (#256)", "body": "", "mergeCommit": {"message": "no ref"}}
    ) == (256, "the title's trailing `(#n)`")


def test_implemented_issue_is_none_when_the_body_closed_it():
    # closingIssuesReferences non-empty means GitHub closed the issue at merge: not this bot's business.
    pr = {"number": 1, "title": "x (#256)", "body": "closes #256",
          "closingIssuesReferences": [{"number": 256}], "mergeCommit": {"message": "Issue: #256"}}
    assert cleaner.implemented_issue(pr) is None


def test_implemented_issue_is_none_when_nothing_names_an_issue():
    assert cleaner.implemented_issue(
        {"number": 1, "title": "chore: tidy", "body": "", "mergeCommit": {"message": "chore"}}
    ) is None


def test_decide_closes_a_stale_open_issue():
    pr = {"number": 344, "title": "x (#256)", "body": "## Goal\n\nretry\n",
          "mergeCommit": {"message": "test(hub-probe): retry\n\nIssue: #256\n"}}
    d = cleaner.decide(pr, {256: {"number": 256, "title": "test-unit is red on clean main"}})
    assert d is not None and d["action"] == "close" and d["issue"] == 256 and d["pr"] == 344
    assert "no closing reference" in d["reason"]


def test_decide_leaves_a_remainder_open():
    body = "## Goal\n\nretry (#256)\n\n## Not covered\n\n- #339 — product code\n"
    pr = {"number": 344, "title": "x (#256)", "body": body,
          "mergeCommit": {"message": "Issue: #256"}}
    d = cleaner.decide(pr, {256: {"number": 256, "title": "t"}, 339: {"number": 339, "title": "u"}})
    # #256 is the implemented issue and #339 the remainder; the same PR cannot decide both here,
    # so the implemented issue wins the finding — the remainder is only reachable when IT is named.
    assert d["action"] == "close" and d["issue"] == 256
    pr2 = {"number": 344, "title": "x (#339)", "body": body,
           "mergeCommit": {"message": "Issue: #339"}}
    d2 = cleaner.decide(pr2, {339: {"number": 339, "title": "u"}})
    assert d2["action"] == "remainder" and d2["issue"] == 339
    assert "left open" in d2["reason"]


def test_decide_ignores_an_issue_that_is_already_closed():
    pr = {"number": 344, "title": "x (#256)", "body": "",
          "mergeCommit": {"message": "Issue: #256"}}
    assert cleaner.decide(pr, {}) is None


# ------------------------------------------------------------------------------- end to end via gh

def gh_stub(tmp_path: Path, merged: list[dict], issues: list[dict]) -> Path:
    """A `gh` that answers the two shapes the cleaner uses, and logs every mutation."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"merged": merged, "issues": issues}))
    log = tmp_path / "gh-calls"
    log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
with open("{log}", "a") as fh:
    print(" ".join(a), file=fh)
if a[:2] == ["pr", "list"]:
    print(json.dumps(sc["merged"]))
elif a[:2] == ["issue", "list"]:
    print(json.dumps(sc["issues"]))
elif a[:2] == ["issue", "comment"] or a[:2] == ["issue", "close"]:
    pass
else:
    sys.exit(f"unexpected gh call: {{a}}")
""")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return log


def run_cleaner(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    return subprocess.run([sys.executable, str(REPO / "scripts" / "issue_cleaner.py"),
                           "--repo", f"{OWNER}/llgenie", *args],
                          capture_output=True, text=True, env=env, timeout=120)


def test_dry_run_reports_the_close_and_mutates_nothing(tmp_path):
    gh_stub(tmp_path,
            [{"number": 344, "title": "test(hub-probe): retry (#256)", "body": "## Goal\n\nretry\n",
              "mergedAt": "2026-10-16T09:04:00Z", "closingIssuesReferences": [],
              "mergeCommit": {"message": "test(hub-probe): retry\n\nIssue: #256\n"}}],
            [{"number": 256, "title": "test-unit is red on clean main"}])
    r = run_cleaner(tmp_path, "--dry")
    assert r.returncode == 0, r.stderr
    assert "stale-open #256" in r.stdout and "would be closed" in r.stdout
    calls = (tmp_path / "gh-calls").read_text()
    assert "issue close" not in calls and "issue comment" not in calls


def test_apply_posts_the_evidence_and_closes(tmp_path):
    gh_stub(tmp_path,
            [{"number": 344, "title": "test(hub-probe): retry (#256)", "body": "## Goal\n\nretry\n",
              "mergedAt": "2026-10-16T09:04:00Z", "closingIssuesReferences": [],
              "mergeCommit": {"message": "test(hub-probe): retry\n\nIssue: #256\n"}}],
            [{"number": 256, "title": "test-unit is red on clean main"}])
    r = run_cleaner(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "closed #256" in r.stdout
    calls = (tmp_path / "gh-calls").read_text()
    assert "issue comment 256" in calls
    assert "issue close 256" in calls
    assert "--reason completed" in calls


def test_a_remainder_is_reported_and_never_closed(tmp_path):
    body = "## Goal\n\nretry\n\n## Not covered\n\n- #339 — product code\n"
    gh_stub(tmp_path,
            [{"number": 344, "title": "x (#339)", "body": body, "mergedAt": "2026-10-16T09:04:00Z",
              "closingIssuesReferences": [], "mergeCommit": {"message": "Issue: #339\n"}}],
            [{"number": 339, "title": "hf_auth.hub_open raises on the first Hub 5xx"}])
    r = run_cleaner(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "remainder #339" in r.stdout and "nothing to close" in r.stdout
    calls = (tmp_path / "gh-calls").read_text()
    assert "issue close" not in calls


def test_a_pr_that_closed_its_issue_is_silent(tmp_path):
    gh_stub(tmp_path,
            [{"number": 1, "title": "x (#5)", "body": "closes #5", "mergedAt": "2026-10-16T09:04:00Z",
              "closingIssuesReferences": [{"number": 5}], "mergeCommit": {"message": "Issue: #5"}}],
            [{"number": 5, "title": "already closed"}])
    r = run_cleaner(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "nothing to close" in r.stdout
    assert "issue close" not in (tmp_path / "gh-calls").read_text()


def test_json_mode_emits_the_findings(tmp_path):
    gh_stub(tmp_path,
            [{"number": 344, "title": "x (#256)", "body": "", "mergedAt": "2026-10-16T09:04:00Z",
              "closingIssuesReferences": [], "mergeCommit": {"message": "Issue: #256"}}],
            [{"number": 256, "title": "t"}])
    r = run_cleaner(tmp_path, "--json", "--dry")
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert rows[0]["action"] == "close" and rows[0]["issue"] == 256
