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
from scripts import issue_cleaner as cleaner

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


def test_a_pr_merged_off_main_is_ignored(tmp_path):
    """A stack-branch merge must not close an issue on the default branch."""

    # Given two merged PRs, one into a stack branch and one into main
    gh_stub(tmp_path,
            [{"number": 1032, "title": "paths (#973)", "body": "", "mergedAt": "2026-10-30T17:28:13Z",
              "baseRefName": "feat/agent-profile-implementer-skill", "closingIssuesReferences": [],
              "mergeCommit": {"message": "Issue: #973"}},
             {"number": 952, "title": "holds (#948)", "body": "", "mergedAt": "2026-10-29T17:04:03Z",
              "baseRefName": "main", "closingIssuesReferences": [],
              "mergeCommit": {"message": "no issue line"}}],
            [{"number": 973, "title": "paths"}, {"number": 948, "title": "holds"}])

    # When the cleaner applies
    r = run_cleaner(tmp_path)

    # Then only the main PR's issue is closed, and the list asked for main
    assert r.returncode == 0, r.stderr
    assert "closed #948" in r.stdout
    assert "closed #973" not in r.stdout
    calls = (tmp_path / "gh-calls").read_text()
    assert "--base main" in calls
    assert "issue close 973" not in calls
    assert "issue close 948" in calls


def test_two_title_only_prs_leave_the_tracking_issue_open(tmp_path):
    """Several title-only PRs name a vehicle. Measured #1079 via #1310 and #1319."""

    # Given two merged-to-main PRs whose titles both end with the same issue
    gh_stub(tmp_path,
            [{"number": 1310, "title": "version the fold tool (#1079)", "body": "lands the tool",
              "mergedAt": "2026-11-01T12:07:00Z", "baseRefName": "main", "closingIssuesReferences": [],
              "mergeCommit": {"message": "version the fold tool"}},
             {"number": 1319, "title": "wire the fold target (#1079)", "body": "wires the target",
              "mergedAt": "2026-11-01T12:16:08Z", "baseRefName": "main", "closingIssuesReferences": [],
              "mergeCommit": {"message": "wire the fold target"}}],
            [{"number": 1079, "title": "lanes record lessons in live profile skills"}])

    # When the cleaner applies
    r = run_cleaner(tmp_path)

    # Then the issue is reported as a vehicle and not closed
    assert r.returncode == 0, r.stderr
    assert "vehicle #1079" in r.stdout
    assert "nothing to close" in r.stdout
    assert "issue close" not in (tmp_path / "gh-calls").read_text()


def test_an_idle_audit_title_is_left_open(tmp_path):
    """An idle-audit record is not the implementation. Measured #1377 for #1282."""

    # Given a merged-to-main PR whose title is an idle-audit record
    gh_stub(tmp_path,
            [{"number": 1377, "title": "docs(security): record own-domain idle audit (#1282)",
              "body": "option 2 of the dispatch", "mergedAt": "2026-11-01T15:09:40Z",
              "baseRefName": "main", "closingIssuesReferences": [],
              "mergeCommit": {"message": "record the audit"}}],
            [{"number": 1282, "title": "engine install-string pins"}])

    # When the cleaner applies
    r = run_cleaner(tmp_path)

    # Then the issue is reported as an audit and not closed
    assert r.returncode == 0, r.stderr
    assert "audit #1282" in r.stdout
    assert "nothing to close" in r.stdout
    assert "issue close" not in (tmp_path / "gh-calls").read_text()

    # And a title with words between idle and audit is the same record (#1274 / #1245)
    d = cleaner.decide(
        {"number": 1274, "title": "docs(architect): add fleet idle continuous-improvement audit contract (#1245)",
         "body": "", "closingIssuesReferences": [], "mergeCommit": {"message": "audit contract"}},
        {1245: {"number": 1245, "title": "role split"}},
    )
    assert d["action"] == "audit" and d["issue"] == 1245


def test_an_issue_line_still_closes_when_another_title_names_it(tmp_path):
    """The merge commit's Issue line is the implementation, even beside a title-only sibling."""

    # Given one PR that states Issue: #256 and another that only titles it
    gh_stub(tmp_path,
            [{"number": 344, "title": "retry (#999)", "body": "", "mergedAt": "2026-10-16T09:04:00Z",
              "baseRefName": "main", "closingIssuesReferences": [],
              "mergeCommit": {"message": "Issue: #256\n"}},
             {"number": 345, "title": "notes (#256)", "body": "", "mergedAt": "2026-10-16T10:04:00Z",
              "baseRefName": "main", "closingIssuesReferences": [],
              "mergeCommit": {"message": "notes only"}}],
            [{"number": 256, "title": "test-unit is red on clean main"}])

    # When the cleaner applies
    r = run_cleaner(tmp_path)

    # Then the Issue-line PR closes it, and the title-only sibling is demoted only when it is a close
    assert r.returncode == 0, r.stderr
    assert "closed #256" in r.stdout
    calls = (tmp_path / "gh-calls").read_text()
    assert "issue close 256" in calls


def test_the_stale_branch_workflow_runs_the_closer():
    """The daily branch pipeline is the schedule. It calls the make target, not the script."""

    # Given the stale-branch cleanup workflow
    text = (REPO / ".github" / "workflows" / "stale-branch-cleanup.yml").read_text()

    # When its close job is read
    job = text.split("close-implemented:", 1)[1]

    # Then it runs the apply target and can write issues, and it never calls the script directly
    assert "make issue-cleaner-apply" in job
    assert "python3 scripts/issue_cleaner.py" not in text
    assert "issues: write" in job
    assert 'cron: "39 3 * * *"' in text


def test_json_mode_emits_the_findings(tmp_path):
    gh_stub(tmp_path,
            [{"number": 344, "title": "x (#256)", "body": "", "mergedAt": "2026-10-16T09:04:00Z",
              "closingIssuesReferences": [], "mergeCommit": {"message": "Issue: #256"}}],
            [{"number": 256, "title": "t"}])
    r = run_cleaner(tmp_path, "--json", "--dry")
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert rows[0]["action"] == "close" and rows[0]["issue"] == 256
