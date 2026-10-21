#!/usr/bin/env python3
"""A green, conflict-free PR is merged by CI; nothing else is (issue #482).

The decision lives in `scripts/auto_merge.py` and is read from ONE `gh pr view`:
`mergeStateStatus == CLEAN` is the whole "green and no merge conflicts" rule (`DIRTY` is a conflict,
`BEHIND` is a stale branch, `BLOCKED` is a required check or review still pending), the head must still be
the commit the run validated, and `do-not-merge` is the human hold. The merge itself is
`gh pr merge --squash --delete-branch --match-head-commit`, with the owner PAT, followed by a closure check.

These cases run the REAL decision against a REAL fake `gh` binary (the repo's pattern: no mocks of the
product, only the external API is a stand-in), plus the real `ci.yml`, `Makefile`, `README.md` and
`AGENTS.md` text.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import auto_merge as am  # noqa: E402
import verify_closure as vc  # noqa: E402

CI = (REPO / ".github" / "workflows" / "ci.yml").read_text()
MAKEFILE = (REPO / "Makefile").read_text()
README = (REPO / "README.md").read_text()
AGENTS = (REPO / "AGENTS.md").read_text()

HEAD = "1234567890abcdef1234567890abcdef12345678"


def _state(**kw) -> dict:
    """A `gh pr view` answer with every field the decision reads."""
    base = {"state": "OPEN", "isDraft": False, "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN", "headRefOid": HEAD, "labels": [],
            "headRepository": {"nameWithOwner": "o/r"},
            "author": {"login": "andyholst"}, "reviewDecision": None,
            "comments": []}
    base.update(kw)
    return base


def _fake_gh(tmp_path: Path, pr: dict, issues: dict | None = None, token_login: str = "asimov-agent"):
    """A `gh` answering `pr view` / `pr review` / `pr merge` / `issue view` / `api user`.

    It records every argv (the assertion surface) and flips the PR's state through marker files, so a test
    can prove an approval happened BEFORE a merge and that the post-approval state is re-read.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
PR = json.loads({json.dumps(pr)!r})
ISSUES = json.loads({json.dumps(issues or {})!r})
TOKEN = {token_login!r}
if os.path.exists({str(log)!r} + ".approved"):
    PR = dict(PR, reviewDecision="APPROVED", mergeStateStatus="CLEAN")
if os.path.exists({str(log)!r} + ".merged"):
    PR = dict(PR, state="MERGED")
if args[:3] == ["api", "user", "--jq"]:
    print(TOKEN); sys.exit(0)
if args[:2] == ["pr", "view"]:
    print(json.dumps(PR)); sys.exit(0)
if args[:2] == ["pr", "review"]:
    open({str(log)!r} + ".approved", "w").write("1")
    print("approved"); sys.exit(0)
if args[:2] == ["issue", "view"]:
    print(json.dumps({{"state": ISSUES.get(args[2], "OPEN")}})); sys.exit(0)
if args[:2] == ["pr", "merge"]:
    open({str(log)!r} + ".merged", "w").write("1")
    print("merged"); sys.exit(0)
if args[:2] == ["pr", "comment"]:
    print("commented"); sys.exit(0)
print("unexpected: " + " ".join(args)); sys.exit(1)
''')
    gh.chmod(0o755)
    return gh


def _calls(log: Path) -> list[list[str]]:
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


# ---- the decision ------------------------------------------------------------

def test_only_a_clean_merge_state_is_merged():
    """CLEAN is the only mergeable state; DIRTY, BEHIND and BLOCKED each name their reason."""

    # Given a green run and a PR in each merge state
    # When  the decision is read
    # Then  only CLEAN merges, and each other state is named
    assert am.decide(_state(), HEAD) is None
    for status, needle in (("DIRTY", "conflict"), ("BEHIND", "behind"), ("BLOCKED", "blocked"),
                           ("UNKNOWN", "mergeStateStatus")):
        reason = am.decide(_state(mergeStateStatus=status), HEAD)
        assert reason and needle.lower() in reason.lower(), (status, reason)


def test_a_draft_a_closed_pr_and_a_moved_head_are_deferred():
    """The three ways a PR is not the thing this run validated."""

    # Given a draft PR, a closed PR, and a head that moved after the run started
    # When  the decision is read
    # Then  each is deferred with a reason, and none can reach the merge
    assert "draft" in am.decide(_state(isDraft=True), HEAD).lower()
    assert am.decide(_state(state="MERGED"), HEAD)
    moved = am.decide(_state(headRefOid="deadbeef" + HEAD[8:]), HEAD)
    assert moved and "head moved" in moved.lower(), moved


def test_do_not_merge_holds_the_pr():
    """A green, clean PR is still held while the label is on it."""

    # Given a green, CLEAN PR carrying the human hold
    held = _state(labels=[{"name": "do-not-merge"}])

    # When  the decision is read
    reason = am.decide(held, HEAD)

    # Then  the hold is named, and it wins over a clean state
    assert reason and "do-not-merge" in reason, reason


# ---- the merge itself --------------------------------------------------------

def test_the_merge_is_squash_head_pinned_and_branch_deleted(tmp_path):
    """The argv is the policy: squash, delete the branch, and pin the validated commit."""

    # Given a green, clean PR and a fake gh
    gh = _fake_gh(tmp_path, _state(), {"482": "CLOSED"})

    # When  the merge runs
    rc = am.run(str(gh), "o/r", 482, HEAD)

    # Then  it squash-merges exactly that commit, deletes the branch, and verifies the closure
    merges = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert len(merges) == 1, merges
    argv = merges[0]
    for flag in ("--squash", "--delete-branch"):
        assert flag in argv, argv
    assert argv[argv.index("--match-head-commit") + 1] == HEAD, argv


def test_a_deferred_pr_never_calls_merge(tmp_path):
    """A conflicted PR is left for a human, and nothing is merged."""

    # Given a PR with merge conflicts
    gh = _fake_gh(tmp_path, _state(mergeStateStatus="DIRTY"))

    # When  the merge runs
    rc = am.run(str(gh), "o/r", 482, HEAD)

    # Then  it exits 0 (a deferral is not a failure) and never calls `pr merge`
    assert rc == 0
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]
    assert am.decide(_state(mergeStateStatus="DIRTY"), HEAD)


def test_dry_run_decides_but_never_merges(tmp_path):
    """`DRY=1` shows the decision without touching the PR."""

    # Given a green, clean PR
    gh = _fake_gh(tmp_path, _state())

    # When  the dry run executes
    rc = am.run(str(gh), "o/r", 482, HEAD, dry=True)

    # Then  it reports what it would do and merges nothing
    assert rc == 0
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]


# ---- the closure proof -------------------------------------------------------

def test_verify_closure_passes_for_a_closed_reference(tmp_path):
    """A merged PR whose closing reference is closed is green."""

    # Given a merged PR that closes #482, and #482 is CLOSED
    pr = {"state": "MERGED", "closingIssuesReferences": [{"number": 482}], "mergeCommit": {"oid": "x"}}
    gh = _fake_gh(tmp_path, pr, {"482": "CLOSED"})

    # When  the closure is verified
    rc = vc.verify(str(gh), "o/r", 1)

    # Then  it passes
    assert rc == 0


def test_verify_closure_fails_for_an_open_reference(tmp_path):
    """An unbound closing keyword is a red run naming the issue."""

    # Given a merged PR whose claimed issue is still OPEN
    pr = {"state": "MERGED", "closingIssuesReferences": [{"number": 482}], "mergeCommit": {"oid": "x"}}
    gh = _fake_gh(tmp_path, pr, {"482": "OPEN"})

    # When  the closure is verified
    rc = vc.verify(str(gh), "o/r", 1)

    # Then  it fails
    assert rc == 1


def test_verify_closure_is_quiet_on_a_chore_with_no_reference(tmp_path):
    """A PR that closes nothing legitimately verifies as nothing to check."""

    # Given a merged PR with no closing reference
    pr = {"state": "MERGED", "closingIssuesReferences": [], "mergeCommit": {"oid": "x"}}
    gh = _fake_gh(tmp_path, pr, {})

    # When  the closure is verified
    rc = vc.verify(str(gh), "o/r", 1)

    # Then  it passes (a chore says so in `Issue:`, AGENTS.md)
    assert rc == 0


# ---- the workflow, the policy and the wiring ---------------------------------

def test_the_job_needs_every_pr_relevant_job():
    """The merge job cannot run before the pipeline it depends on."""

    # Given ci.yml
    block = CI.split("  auto-merge:", 1)[1].split("\n  # ---", 1)[0]

    # When  its needs list is read
    needs = re.search(r"needs:\s*\[([^\]]+)\]", block).group(1)

    # Then  every PR-relevant job is in it
    for job in ("guard", "ci-images", "linux", "macos", "engine-base", "engine-matrix",
                "engine-image", "linux-published"):
        assert job in needs, (job, needs)
    # …and the push-only job is deliberately absent (it is skipped on a PR)
    assert "engine-published-test" not in needs, needs

    # And "green" means every need SUCCEEDED: a skipped job is not a passed job, and merging on
    # "nothing failed" would land a PR whose linux or macos job never ran.
    cond = block.split("if: >-", 1)[1].split("runs-on:", 1)[0]
    for job in ("guard", "ci-images", "linux", "macos", "engine-base", "engine-matrix",
                "engine-image", "linux-published"):
        assert f"needs.{job}.result == 'success'" in cond, (job, cond)


def test_the_workflow_accepts_the_owners_fork_and_no_other():
    """A head in the base repo OR in the owner's fork; a draft or a `main` head never."""

    # Given the auto-merge job's `if:`
    block = CI.split("  auto-merge:", 1)[1]
    cond = block.split("if: >-", 1)[1].split("runs-on:", 1)[0]

    # When  it is read
    # Then  both accepted heads are there — the fork is where every agent PR is pushed (issue #488)
    assert "github.event.pull_request.head.repo.full_name == github.repository" in cond, cond
    assert "github.event.pull_request.head.repo.owner.login == 'andyholst'" in cond, cond
    # …only THAT owner: no wildcard, and no negation that would let any fork through
    assert "head.repo.owner.login !=" not in cond, cond
    assert "head.repo.fork == false" not in cond, cond

    # And the other refusals and the failure guards are unchanged
    for needle in ("always()", "!failure()", "!cancelled()", "github.event_name == 'pull_request'",
                   "github.event.pull_request.draft == false", "github.head_ref != 'main'"):
        assert needle in cond, (needle, cond)


def test_a_fork_head_merges_without_deleting_the_branch(tmp_path):
    """The base token cannot delete a fork branch, so a fork merge asks for no deletion."""

    # Given a green, clean PR whose head is the owner's fork
    fork = _state(headRepository={"nameWithOwner": "andyholst/llgenie"})
    gh = _fake_gh(tmp_path, fork, {"482": "CLOSED"})

    # When  the merge runs
    rc = am.run(str(gh), "o/r", 482, HEAD)

    # Then  it merges the same-squash, head-pinned way, without --delete-branch
    merges = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert len(merges) == 1, merges
    argv = merges[0]
    assert "--squash" in argv and "--delete-branch" not in argv, argv
    assert argv[argv.index("--match-head-commit") + 1] == HEAD, argv


def test_the_merge_uses_the_owner_pat_and_a_make_target():
    """The PAT, so the post-merge run on main happens; and CI runs a make target, not a script."""

    # Given the auto-merge job's merge step
    block = CI.split("  auto-merge:", 1)[1]

    # When  its env and run are read
    # Then  the token is the owner PAT, never the job token, and the command is a make target
    assert "GH_TOKEN: ${{ secrets.BUMP_TOKEN }}" in block, block[:800]
    assert "github.token" not in block, "a merge made with the job token starts no workflows"
    assert "make auto-merge" in block, block[:800]
    assert "scripts/auto_merge.py" not in block, "the workflow must call the make target"


def test_the_targets_are_phony_and_documented():
    """`auto-merge` and `verify-closure` exist, are phony, and are in the README."""

    # Given the Makefile and the README
    phony = MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # When  the two targets are looked for
    # Then  both are declared, both recipes exist, and the README documents them
    for target in ("auto-merge", "verify-closure"):
        assert f"\n{target}:" in MAKEFILE, target
        assert target in phony, target
        assert target in README, target


def test_agents_md_states_the_new_policy():
    """The policy is stated once, and the old unconditional rule is gone."""

    # Given AGENTS.md
    # When  the merge policy is read
    # Then  it names the job, the CLEAN rule, the hold and the PAT, and the old wording is gone
    for needle in ("auto-merge", "mergeStateStatus", "do-not-merge", "make verify-closure",
                   "Never run `gh pr merge`"):
        assert needle in AGENTS, needle
    assert "Merging needs an approval — the agent NEVER merges" not in AGENTS
    assert "gh pr merge <N> --merge --delete-branch" not in AGENTS


# ---- a review-blocked green PR: approve with the other identity, then merge (issue #491) ------

def _review_blocked(author: str = "andyholst", **kw) -> dict:
    return _state(mergeStateStatus="BLOCKED", reviewDecision="REVIEW_REQUIRED",
                  author={"login": author}, **kw)


def test_a_review_blocked_green_pr_is_approved_then_merged(tmp_path):
    """The one procedural block a bot may clear: an approval from the OTHER allowed identity."""

    # Given a green, mergeable PR blocked only by a required review, authored by andyholst
    gh = _fake_gh(tmp_path, _review_blocked(), {"491": "CLOSED"})

    # When  the job runs with approval enabled
    rc = am.run(str(gh), "o/r", 482, HEAD, approve_when_review_required=True)

    # Then  it approves first (as the well-known token account), re-reads, then merges
    kinds = [c[:2] for c in _calls(tmp_path / "gh.log")]
    assert rc == 0, rc
    assert kinds.index(["pr", "review"]) < kinds.index(["pr", "merge"]), kinds
    review = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "review"]][0]
    assert "--approve" in review, review
    body = review[review.index("--body") + 1]
    assert "auto-merge" in body and "491" in body, body


def test_a_same_account_pr_is_never_self_approved(tmp_path):
    """GitHub refuses a self-approval, so a PR authored by the token's own account defers."""

    # Given a review-blocked PR whose author IS the merge token's account
    gh = _fake_gh(tmp_path, _review_blocked(author="asimov-agent"), token_login="asimov-agent")

    # When  the job runs with approval enabled
    rc = am.run(str(gh), "o/r", 482, HEAD, approve_when_review_required=True)

    # Then  it never approves, never merges, and says so on the PR
    kinds = [c[:2] for c in _calls(tmp_path / "gh.log")]
    assert rc == 0
    assert ["pr", "review"] not in kinds and ["pr", "merge"] not in kinds, kinds
    assert ["pr", "comment"] in kinds, kinds


def test_a_non_allowlisted_author_is_not_approved(tmp_path):
    """A bot does not approve a stranger's PR, however green it is."""

    # Given a review-blocked PR from an author outside the repo's identities
    gh = _fake_gh(tmp_path, _review_blocked(author="somebody-else"))

    # When  the job runs with approval enabled
    rc = am.run(str(gh), "o/r", 482, HEAD, approve_when_review_required=True)

    # Then  no approval is posted and the PR is deferred
    kinds = [c[:2] for c in _calls(tmp_path / "gh.log")]
    assert rc == 0
    assert ["pr", "review"] not in kinds and ["pr", "merge"] not in kinds, kinds


def test_no_approval_for_any_other_blocker(tmp_path):
    """Only the review state is actionable this way: conflicts and staleness are not."""

    # Given a PR with conflicts, and one behind main
    for state in (_state(mergeStateStatus="DIRTY"), _state(mergeStateStatus="BEHIND")):
        calls_before = None
        gh = _fake_gh(tmp_path / state["mergeStateStatus"], state)

        # When  the job runs with approval enabled
        rc = am.run(str(gh), "o/r", 482, HEAD, approve_when_review_required=True)

        # Then  it never approves
        kinds = [c[:2] for c in _calls(tmp_path / state["mergeStateStatus"] / "gh.log")]
        assert rc == 0
        assert ["pr", "review"] not in kinds, kinds


def test_a_deferral_is_commented_once_per_head(tmp_path):
    """The reason is on the PR, and not repeated run after run for the same head."""

    # Given a conflicted PR and the job running twice for the same head
    gh = _fake_gh(tmp_path, _state(mergeStateStatus="DIRTY"))
    am.run(str(gh), "o/r", 482, HEAD)
    first = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]

    # A second run on the same head: the fake answers `pr view` with the same empty comment list, so the
    # dedupe is asserted on the marker the product builds rather than on a re-read fixture.
    marker = am.DEFERRAL_MARKER.format(HEAD[:40])
    assert len(first) == 1, first
    body = first[0][first[0].index("--body") + 1]
    assert marker in body and "Not auto-merged" in body, body

    # When  the PR already carries that marker, nothing new is posted
    already = _fake_gh(tmp_path / "again", _state(mergeStateStatus="DIRTY",
                                                  comments=[{"body": marker + "\nold"}]))
    am.run(str(already), "o/r", 482, HEAD)

    # Then  no second comment is posted
    assert not [c for c in _calls(tmp_path / "again" / "gh.log") if c[:2] == ["pr", "comment"]]


def test_explain_prints_the_verdict_and_writes_nothing(tmp_path, capsys):
    """The same decision, for a human, with no writes at all."""

    # Given a complete PR state
    gh = _fake_gh(tmp_path, _state())

    # When  explain runs
    rc = am.explain(str(gh), "o/r", 482)

    # Then  it prints the verdict and calls nothing that writes
    out = capsys.readouterr().out
    assert rc == 0
    assert "verdict: would merge" in out, out
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] in (["pr", "merge"], ["pr", "review"],
                                                                   ["pr", "comment"])]


def test_the_workflow_enables_the_approval_with_the_pat():
    """The job turns the approval on, and still merges with the owner PAT."""

    # Given the auto-merge job's merge step
    block = CI.split("  auto-merge:", 1)[1]

    # When  its env is read
    # Then  approval is enabled and the token is the PAT
    assert 'APPROVE: "1"' in block, block[:1200]
    assert "GH_TOKEN: ${{ secrets.BUMP_TOKEN }}" in block, block[:1200]


def test_the_explain_target_is_phony_and_documented():
    """`auto-merge-explain` exists, is phony, and is in the README."""

    # Given the Makefile and the README
    phony = MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # When  the target is looked for
    # Then  it is declared, has a recipe, and the README documents it
    assert "\nauto-merge-explain:" in MAKEFILE
    assert "auto-merge-explain" in phony
    assert "auto-merge-explain" in README
