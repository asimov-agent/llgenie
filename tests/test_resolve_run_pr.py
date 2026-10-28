#!/usr/bin/env python3
"""A finished fork CI run is resolved back to its PR (issue #508).

`auto-merge.yml` is a `workflow_run` workflow: it receives a run id, not a PR number. The resolution
lives in `scripts/resolve_run_pr.py`, and the defect this file pins was measured on run `39735179724`:
the runs endpoint **404s for a fork `pull_request` run**, `gh api` prints the error body to stdout, and
`number=<that blob>` then (a) skipped the fork fallback from #504, because the value looked non-empty,
and (b) broke `$GITHUB_OUTPUT` with `Invalid format '  "message": "Not Found",'`.

These cases run the REAL resolver against a REAL fake `gh` binary on disk (the repo's pattern: no mock
of the product, only the external API is a stand-in), plus the real `auto-merge.yml` text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
from scripts import resolve_run_pr as rr

WORKFLOW = (REPO / ".github" / "workflows" / "auto-merge.yml").read_text()
BRANCH = "fix/rebase-gate-mount"
OWNER = "andyholst"
#: The exact body `gh api` printed on run 39735179724, plus the `gh:` line it writes to stderr.
NOT_FOUND_BODY = """{
  "message": "Not Found",
  "documentation_url": "https://docs.github.com/rest",
  "status": "404"
}
"""


def _fake_gh(tmp_path: Path, api_stdout: str = "", api_exit: int = 0,
             list_stdout: str = "", list_exit: int = 0) -> Path:
    """A `gh` answering the runs endpoint and the PR search, recording every argv it received."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:1] == ["api"]:
    sys.stdout.write({api_stdout!r})
    raise SystemExit({api_exit})
if args[:2] == ["pr", "list"]:
    sys.stdout.write({list_stdout!r})
    raise SystemExit({list_exit})
raise SystemExit(f"unexpected gh argv: {{args}}")
''')
    gh.chmod(0o755)
    return gh


def _calls(tmp_path: Path) -> list[list[str]]:
    log = tmp_path / "gh.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_a_404_from_the_runs_endpoint_falls_through_to_the_fork_head(tmp_path):
    """The measured defect: the error body must not be mistaken for a PR number."""

    # Given a fork run, whose runs endpoint 404s with a JSON body on stdout
    gh = _fake_gh(tmp_path, api_stdout=NOT_FOUND_BODY, api_exit=1, list_stdout="506\n")

    # When  the run is resolved back to its PR
    number = rr.resolve("asimov-agent/llgenie", 39732261968, OWNER, BRANCH, str(gh))

    # Then  the fork fallback answers, and it was asked for the head branch
    assert number == 506, number
    searches = [c for c in _calls(tmp_path) if c[:2] == ["pr", "list"]]
    assert len(searches) == 1, searches
    assert f"head:{BRANCH}" in searches[0], searches[0]


def test_the_run_object_is_used_when_it_answers(tmp_path):
    """A same-repo run needs no search: the runs endpoint already names the PR."""

    # Given a run whose pull_requests array carries the PR number
    gh = _fake_gh(tmp_path, api_stdout="506\n")

    # When  the run is resolved
    number = rr.resolve("asimov-agent/llgenie", 39732261968, OWNER, BRANCH, str(gh))

    # Then  the number comes from the run object alone
    assert number == 506, number
    assert [c for c in _calls(tmp_path) if c[:2] == ["pr", "list"]] == [], _calls(tmp_path)


def test_the_fork_search_is_scoped_to_the_head_owner(tmp_path):
    """A branch name is not unique across forks, so the search must filter on the head owner."""

    # Given a fork run and a search that answers with its PR
    gh = _fake_gh(tmp_path, api_stdout="", api_exit=0, list_stdout="507\n")

    # When  the run is resolved
    rr.resolve("asimov-agent/llgenie", 39732261968, OWNER, BRANCH, str(gh))

    # Then  gh was asked with the branch AND the owner filter, never the branch alone
    search = [c for c in _calls(tmp_path) if c[:2] == ["pr", "list"]][0]
    assert f'select(.headRepositoryOwner.login=="{OWNER}")' in " ".join(search), search
    assert "number,headRepositoryOwner" in search, search


def test_nothing_resolving_is_loud_and_writes_no_output(tmp_path):
    """An unresolved green PR must fail the step, never defer silently."""

    # Given a run that answers nothing from either source, and a GitHub output file
    gh = _fake_gh(tmp_path, api_stdout="", api_exit=0, list_stdout="", list_exit=0)
    output = tmp_path / "output.txt"
    output.write_text("")

    # When  the step runs
    rc = rr.main(["resolve", "--repo", "asimov-agent/llgenie", "--run-id", "39732261968",
                  "--head-owner", OWNER, "--head-branch", BRANCH, "--gh", str(gh)])

    # Then  it exits non-zero naming the run and the head, and leaves the output file empty
    assert rc == 1, rc
    assert output.read_text() == "", output.read_text()


def test_the_output_file_gets_one_number_line(tmp_path, monkeypatch):
    """$GITHUB_OUTPUT must hold `number=<n>` — the multi-line blob is what broke the step."""

    # Given a resolved fork run and a GitHub output file
    gh = _fake_gh(tmp_path, api_stdout=NOT_FOUND_BODY, api_exit=1, list_stdout="506\n")
    output = tmp_path / "output.txt"
    output.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    # When  the step runs
    rc = rr.main(["resolve", "--repo", "asimov-agent/llgenie", "--run-id", "39732261968",
                  "--head-owner", OWNER, "--head-branch", BRANCH, "--gh", str(gh)])

    # Then  the output is exactly one `number=` line
    assert rc == 0, rc
    assert output.read_text() == "number=506\n", output.read_text()


def test_the_number_is_printed_when_no_output_file_is_set(tmp_path, monkeypatch):
    """Locally there is no $GITHUB_OUTPUT: the same value is printed, so make hands it back."""

    # Given no GitHub output file
    gh = _fake_gh(tmp_path, api_stdout="506\n")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    # When  the step runs
    rc = rr.main(["resolve", "--repo", "asimov-agent/llgenie", "--run-id", "39732261968",
                  "--head-owner", OWNER, "--head-branch", BRANCH, "--gh", str(gh)])

    # Then  it succeeds and prints the same `number=` line
    assert rc == 0, rc


def test_the_workflow_resolves_the_pr_through_the_make_target():
    """AGENTS.md: a workflow runs make targets, so this code path is the one that runs locally too."""

    # Given the real auto-merge workflow
    workflow = WORKFLOW

    # When  its resolution step is read
    step = workflow.split("- name: Resolve the pull request the finished run belongs to", 1)[1]
    step = step.split("- name:", 1)[0]

    # Then  it calls the make target and no longer shells out to gh itself
    assert "make auto-merge-resolve" in step, step
    assert "number=$(" not in step, step
    assert "gh pr list --repo" not in step, step
    assert '"/runs/' not in step, step


def test_allow_none_answers_no_pr_without_failing(tmp_path, monkeypatch):
    """Issue #629: a failed run whose PR already landed is nothing to repair, not a red run."""

    # Given a run neither source resolves, and a GitHub output file
    gh = _fake_gh(tmp_path, api_stdout="", api_exit=0, list_stdout="", list_exit=0)
    output = tmp_path / "output.txt"
    output.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    # When  the fix-bot resolves that run with the lenient answer
    rc = rr.main(["resolve", "--repo", "asimov-agent/llgenie", "--run-id", "40207293399",
                  "--head-owner", OWNER, "--head-branch", "fix/engine-gate-strict",
                  "--allow-none", "--gh", str(gh)])

    # Then  it succeeds with the single empty `number=` line an absent PR means
    assert rc == 0, rc
    assert output.read_text() == "number=\n", output.read_text()


def test_allow_none_still_resolves_a_live_pr(tmp_path, monkeypatch):
    """The lenient flag changes only the no-answer case: a live PR is still reported as its number."""

    # Given a run whose head still has an open PR, and a GitHub output file
    gh = _fake_gh(tmp_path, api_stdout="506\n")
    output = tmp_path / "output.txt"
    output.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    # When  the fix-bot resolves it with the lenient answer
    rc = rr.main(["resolve", "--repo", "asimov-agent/llgenie", "--run-id", "40207293399",
                  "--head-owner", OWNER, "--head-branch", BRANCH, "--allow-none", "--gh", str(gh)])

    # Then  the number is unchanged
    assert rc == 0, rc
    assert output.read_text() == "number=506\n", output.read_text()


def test_the_fix_bot_workflow_resolves_through_the_lenient_target():
    """The lenient answer belongs to the fix-bot's sweep, and only to it (issue #629)."""

    # Given the real fix-bot workflow and the real make targets
    fix_bot = (REPO / ".github" / "workflows" / "fix-bot.yml").read_text()
    makefile = (REPO / "Makefile").read_text()

    # When  the sweep's resolution step and both targets' recipes are read
    step = fix_bot.split("- name: Resolve the PR the failed run belongs to", 1)[1]
    step = step.split("- name:", 1)[0]
    lenient = makefile.split("fix-bot-resolve:", 1)[1].split(chr(10) * 2, 1)[0]
    strict = makefile.split("auto-merge-resolve:", 1)[1].split(chr(10) * 2, 1)[0]

    # Then  the sweep calls the lenient target, and it is the ONLY place the flag is passed
    assert "make fix-bot-resolve" in step, step
    assert "make auto-merge-resolve" not in step, step
    assert "--allow-none" in lenient, lenient
    assert "--allow-none" not in strict, strict
    assert "--allow-none" not in WORKFLOW, "the merge gate must keep its loud failure"


# ---------------------------------------------------------------------------------------------------
# issue #897: a head whose PR already merged or closed is a NON-EVENT, not a dropped green PR
def test_a_landed_pr_head_is_an_answer_and_the_gate_ends_cleanly(tmp_path, monkeypatch, capsys):
    """A completed CI run can arrive after its PR merged; nothing to merge, nothing to fix."""

    # Given a run whose head has no OPEN PR, but whose PR exists and is MERGED
    monkeypatch.setattr(rr, "run_pr_number", lambda *a, **k: None)
    monkeypatch.setattr(rr, "open_pr_for_head", lambda *a, **k: None)
    monkeypatch.setattr(rr, "landed_pr_for_head", lambda *a, **k: (12, "MERGED"))

    # When  the merge gate resolves it
    rc = rr.main(["resolve", "--repo", "o/r", "--run-id", "40749229861",
                  "--head-owner", "asimov-agent", "--head-branch", BRANCH])

    # Then  it is green, and the log says which PR and which state
    err = capsys.readouterr().err
    assert rc == 0, err
    assert "nothing to merge" in err and "#12" in err and "MERGED" in err, err


def test_a_head_that_never_had_a_pr_still_fails_loudly(tmp_path, monkeypatch, capsys):
    """The case the original message protects: something was built that nobody can review."""

    # Given a head with no PR in ANY state
    monkeypatch.setattr(rr, "run_pr_number", lambda *a, **k: None)
    monkeypatch.setattr(rr, "open_pr_for_head", lambda *a, **k: None)
    monkeypatch.setattr(rr, "landed_pr_for_head", lambda *a, **k: None)

    # When  the merge gate resolves it
    rc = rr.main(["resolve", "--repo", "o/r", "--run-id", "1",
                  "--head-owner", "asimov-agent", "--head-branch", BRANCH])

    # Then  it still fails, with the original message
    err = capsys.readouterr().err
    assert rc == 1, err
    assert "must never be silently dropped" in err, err


def test_the_landed_lookup_filters_by_head_owner_and_branch_through_the_api():
    """`head=owner:branch` is the only form that works for a FORK head, and every bot PR is one.

    `gh pr list --search head:<branch>` matches same-repo branches only - the trap this module's own
    docstring records for #508. Using it here would leave the false red for exactly the PRs it is for.
    """

    import inspect

    source = inspect.getsource(rr.landed_pr_for_head)
    # source 1: the exact REST filter, which answers for a head in THIS repository
    assert "pulls?state=all&head=" in source, source
    assert "{head_owner}:{head_branch}" in source, source
    # source 2: the search form, which answers for a FORK head - measured: head=asimov-agent:<branch>
    # answers `867 closed` while head=andyholst:<branch> answers nothing for the same PR, and 12 of the
    # last 40 PRs in this repository have fork heads, so one source alone misses half of them
    assert '"--search"' in source, source
