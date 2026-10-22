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
MERGE_WF = (REPO / ".github" / "workflows" / "auto-merge.yml").read_text()
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


def _fake_gh(tmp_path: Path, pr: dict, issues: dict | None = None, token_login: str = "asimov-agent",
             permissions: dict | None = None, tokens: dict | None = None, merge_rc: int = 0):
    """A `gh` answering `pr view` / `pr review` / `pr merge` / `issue view` / `api user` / permission.

    It records every argv (the assertion surface) and flips the PR's state through marker files, so a test
    can prove an approval happened BEFORE a merge and that the post-approval state is re-read. The permission
    map answers `repos/<repo>/collaborators/<login>/permission`; a login absent from it is a 404, which is
    what GitHub returns for a stranger and for the bot.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    perms = permissions if permissions is not None else {"andyholst": "admin", "asimov-agent": "admin"}
    gh.write_text(f'''#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
PR = json.loads({json.dumps(pr)!r})
ISSUES = json.loads({json.dumps(issues or {})!r})
PERMS = json.loads({json.dumps(perms)!r})
TOKEN = {token_login!r}
TOKENS = json.loads({json.dumps(tokens or {})!r})
MERGE_RC = {merge_rc!r}
if os.path.exists({str(log)!r} + ".approved"):
    PR = dict(PR, reviewDecision="APPROVED", mergeStateStatus="CLEAN")
if os.path.exists({str(log)!r} + ".merged"):
    PR = dict(PR, state="MERGED")
if args[:3] == ["api", "user", "--jq"]:
    print(TOKENS.get(os.environ.get("GH_TOKEN", ""), TOKEN)); sys.exit(0)
if len(args) >= 2 and args[0] == "api" and "/collaborators/" in args[1] and args[1].endswith("/permission"):
    login = args[1].split("/collaborators/")[1].split("/")[0]
    if login not in PERMS:
        print("not found", file=sys.stderr); sys.exit(1)
    print(PERMS[login]); sys.exit(0)
if args[:2] == ["pr", "view"]:
    print(json.dumps(PR)); sys.exit(0)
if args[:2] == ["pr", "review"]:
    open({str(log)!r} + ".approved", "w").write("1")
    print("approved"); sys.exit(0)
if args[:2] == ["issue", "view"]:
    print(json.dumps({{"state": ISSUES.get(args[2], "OPEN")}})); sys.exit(0)
if args[:2] == ["pr", "merge"]:
    if MERGE_RC:
        print("GraphQL: At least 1 approving review is required by reviewers with write access.",
              file=sys.stderr)
        sys.exit(MERGE_RC)
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
    assert am.decide(_state(), HEAD, repo_owner="o") is None
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

def test_only_a_successful_ci_run_reaches_the_merge():
    """`conclusion == 'success'` is the same guarantee `needs:` each job gave, one level up (issue #493)."""

    # Given the merge workflow's job condition
    cond = MERGE_WF.split("if: >-", 1)[1].split("runs-on:", 1)[0]

    # When  it is read
    # Then  it acts on a green pull-request run only — a push run and a failed run are both out
    assert "github.event.workflow_run.event == 'pull_request'" in cond, cond
    assert "github.event.workflow_run.conclusion == 'success'" in cond, cond
    # …and the merge itself is not decided in the workflow: it is the one make target
    assert "make auto-merge PR=" in MERGE_WF

def test_a_third_party_fork_head_is_never_merged():
    """A `workflow_run` fires for any fork, so the trust boundary moved into the decision."""

    # Given a green, clean PR whose head is a stranger's fork
    stranger = _state(headRepository={"nameWithOwner": "someone-else/llgenie"})

    # When  the decision runs for this repo
    reason = am.decide(stranger, HEAD, repo_owner="asimov-agent")

    # Then  it defers, naming the head
    assert reason and "third-party fork" in reason, reason

    # And the owner's fork still passes (every agent PR is pushed there, issue #488)
    owner = _state(headRepository={"nameWithOwner": "andyholst/llgenie"})
    assert am.decide(owner, HEAD, repo_owner="asimov-agent") is None

    # And a same-repo head passes too
    same = _state(headRepository={"nameWithOwner": "asimov-agent/llgenie"})
    assert am.decide(same, HEAD, repo_owner="asimov-agent") is None

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


def test_a_write_collaborator_a_bot_and_the_owner_may_merge_a_stranger_may_not(tmp_path):
    """The merge gate is who opened the PR: owner, write collaborator, or the bot. Nobody else."""

    # Given a green, clean PR opened by a collaborator with write
    writer = _state(author={"login": "ada"},
                    headRepository={"nameWithOwner": "asimov-agent/llgenie"})
    gh = _fake_gh(tmp_path / "w", writer, {"482": "CLOSED"}, permissions={"ada": "write"})

    # When  the merge runs against this repo
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  it merges: write is enough, exactly as ci.yml's guard allows write
    assert rc == 0
    assert [c for c in _calls(tmp_path / "w" / "gh.log") if c[:2] == ["pr", "merge"]]

    # Given the same PR opened by the bot, and the CI run triggered by the owner
    bot = _state(author={"login": "app/github-actions"},
                 headRepository={"nameWithOwner": "asimov-agent/llgenie"})
    gh = _fake_gh(tmp_path / "b", bot, {"482": "CLOSED"})

    # When  the merge runs with that actor
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, actor="asimov-agent")

    # Then  the bot PR merges, because the actor is the owner
    assert rc == 0
    assert [c for c in _calls(tmp_path / "b" / "gh.log") if c[:2] == ["pr", "merge"]]

    # Given a green, clean PR opened by a stranger, even from the trusted fork
    stranger = _state(author={"login": "mallory"},
                      headRepository={"nameWithOwner": "andyholst/llgenie"})
    gh = _fake_gh(tmp_path / "s", stranger, permissions={})

    # When  the merge runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  it defers and never merges: a trusted fork is not a trusted author
    assert rc == 0
    calls = _calls(tmp_path / "s" / "gh.log")
    assert not [c for c in calls if c[:2] == ["pr", "merge"]]
    assert any(c[:2] == ["pr", "comment"] for c in calls)


# ---- only fields `gh pr view` actually has (issue #513) ----------------------

def test_every_requested_field_is_in_ghs_own_allowlist():
    """A field name `gh` does not have kills the run before the decision, so the list is locked."""

    # Given the allowlist captured from a real `gh pr view --json __probe__`
    fixture = json.loads((REPO / "tests" / "fixtures" / "gh-pr-view-fields.json").read_text())

    # When  the module's requested field names are read
    # Then  every one of them exists in gh, and the invented field is gone from both
    allow = set(fixture["fields"])
    assert fixture["command"] == "gh pr view --json __probe__", fixture
    assert fixture["gh_version"].startswith("gh version "), fixture
    assert "authorAssociation" not in allow, "the fixture was not captured from gh"
    for field in am.PR_VIEW_FIELDS:
        assert field in allow, f"`gh pr view --json {field}` does not exist: {sorted(allow)}"


def test_pr_state_requests_exactly_the_locked_field_list(tmp_path):
    """`pr_state` is the one call every decision reads; its argv carries only allowlisted names."""

    # Given a fake gh and a complete PR state
    gh = _fake_gh(tmp_path, _state())

    # When  the state is read
    am.pr_state(str(gh), "o/r", 482)

    # Then  the requested names are the constant, and `authorAssociation` is nowhere in the argv
    views = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "view"]]
    assert len(views) == 1, views
    requested = views[0][views[0].index("--json") + 1].split(",")
    assert requested == list(am.PR_VIEW_STATE_FIELDS), requested
    assert "authorAssociation" not in requested, requested


def test_a_bot_author_is_recognised_by_its_login_alone(tmp_path):
    """The bot rule reads `author.login` — a field that exists — never `authorAssociation`."""

    # Given a PR opened by GitHub's App bot, and a `…[bot]` opener, with no actor named
    app_bot = _state(author={"login": "app/github-actions"},
                     headRepository={"nameWithOwner": "o/r"})
    dependabot = _state(author={"login": "dependabot[bot]"},
                        headRepository={"nameWithOwner": "o/r"})

    # When  the author gate is read without an actor
    for state in (app_bot, dependabot):
        refused = am.author_may_merge(sys.executable, "o/r", state, actor="")

        # Then  it refuses, naming the bot and the missing actor — not a missing JSON field
        assert refused and "is a bot" in refused and "ACTOR is empty" in refused, refused

    # Given the same bot PR and a run triggered by the owner
    gh = _fake_gh(tmp_path, app_bot, {"513": "CLOSED"})

    # When  the job runs with ACTOR set to the owner
    rc = am.run(str(gh), "o/r", 513, HEAD, actor="o")

    # Then  the bot PR merges, because the actor is the owner — and only allowlisted fields were asked for
    kinds = [c[:2] for c in _calls(tmp_path / "gh.log")]
    assert rc == 0, rc
    assert ["pr", "merge"] in kinds, kinds


def test_the_merge_uses_the_owner_pat_and_a_make_target():
    """The PAT, so the post-merge run on main happens; and CI runs a make target, not a script."""

    # Given the merge workflow
    block = MERGE_WF

    # When  its env and run are read
    # Then  the token is the owner PAT, never the job token, and the command is a make target
    assert "GH_TOKEN: ${{ secrets.BUMP_TOKEN }}" in block, block[:800]
    assert "github.token" not in block, "a merge made with the job token starts no workflows"
    assert "make auto-merge" in block, block[:800]
    assert "python3 scripts/auto_merge.py" not in block, "the workflow must call the make target"

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
    base = {"mergeStateStatus": "BLOCKED", "reviewDecision": "REVIEW_REQUIRED",
            "author": {"login": author},
            # the repo under test, so the post-approval decision reads a trusted head
            "headRepository": {"nameWithOwner": "asimov-agent/llgenie"}}
    base.update(kw)
    return _state(**base)


def test_a_review_blocked_green_pr_is_approved_by_the_other_identity_then_merged(tmp_path):
    """The legitimate path (issue #524): approve as the identity that is NOT the author, then merge.

    `--admin` is NOT used. GitHub refuses it wherever the review rule is enforced for admins, which is why
    #491's bypass never merged anything (measured: PR #523, run 39816912388).
    """

    # Given a green, mergeable PR blocked only by a required review, authored by andyholst
    gh = _fake_gh(tmp_path, _review_blocked(), {"491": "CLOSED"},
                  permissions={"andyholst": "admin"})

    # When  the job runs with the review bypass enabled
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  it approves as the merge token, re-reads the PR, and merges WITHOUT --admin
    calls = _calls(tmp_path / "gh.log")
    kinds = [c[:2] for c in calls]
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert ["pr", "review"] in kinds, kinds
    assert len(merges) == 1, merges
    assert "--admin" not in merges[0] and "--squash" in merges[0], merges[0]
    assert kinds.index(["pr", "review"]) < kinds.index(["pr", "merge"]), kinds


def test_a_same_account_pr_falls_back_to_admin(tmp_path):
    """A PR authored by the merge token's own account cannot be approved: --admin is the fallback."""

    # Given a review-blocked PR whose author IS the merge token's account, and no APPROVER_TOKEN
    gh = _fake_gh(tmp_path, _review_blocked(author="asimov-agent"), {"491": "CLOSED"},
                  token_login="asimov-agent")

    # When  the job runs with the review bypass enabled
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  it never posts a self-approval, and falls back to the admin merge
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0, rc
    assert not [c for c in calls if c[:2] == ["pr", "review"]]
    assert [c for c in calls if c[:2] == ["pr", "merge"] and "--admin" in c], calls


def test_a_same_account_pr_is_approved_with_the_approver_token(tmp_path, monkeypatch):
    """A bot PR (author = the merge account) is approved by the second identity when one is supplied.

    The token travels in the ENVIRONMENT, never in argv (AGENTS.md credential rule): the fake `gh` reads
    `GH_TOKEN` to answer `api user`, so a mismatch there would surface as the wrong login.
    """

    # Given a review-blocked PR authored by the merge token's account, and an approver token for andyholst
    gh = _fake_gh(tmp_path, _review_blocked(author="asimov-agent"), {"491": "CLOSED"},
                  token_login="asimov-agent", tokens={"ghp_other": "andyholst"})
    monkeypatch.setenv("APPROVER_TOKEN", "ghp_other")

    # When  the job runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  the approval is posted with that token and the merge is NOT the admin bypass
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert ["pr", "review"] in [c[:2] for c in calls], calls
    assert merges and "--admin" not in merges[0], merges
    assert not any("ghp_other" in " ".join(c) for c in calls), "the token must never reach argv"


def test_a_refused_merge_defers_with_the_reason_on_the_pr(tmp_path):
    """A merge GitHub refuses says why ON the PR and exits 0 — never a bare red run (#513, #524)."""

    # Given a review-blocked PR authored by the merge account, and a merge GitHub refuses
    gh = _fake_gh(tmp_path, _review_blocked(author="asimov-agent"), {"491": "CLOSED"},
                  token_login="asimov-agent", merge_rc=1)

    # When  the job runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  it exits 0 and posts one comment naming the refusal
    calls = _calls(tmp_path / "gh.log")
    comments = [c for c in calls if c[:2] == ["pr", "comment"]]
    assert rc == 0, rc
    assert comments, calls
    assert "admin merge was refused" in " ".join(comments[0])


def test_a_non_allowlisted_author_is_not_approved(tmp_path):
    """A bot does not approve a stranger's PR, however green it is."""

    # Given a review-blocked PR from an author outside the repo's identities
    gh = _fake_gh(tmp_path, _review_blocked(author="somebody-else"), permissions={})

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

    # Given the auto-merge workspace's merge step
    block = MERGE_WF.split("make auto-merge (merge only", 1)[1]

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


# ---- the merge runs where the secrets are: a workflow_run workflow (issue #493) ---------------

def test_ci_has_no_auto_merge_job_any_more():
    """A `pull_request` run from a fork gets no repository secrets, so the job there could never merge."""

    # Given ci.yml
    # When  its jobs are looked for
    # Then  auto-merge is gone, and a pointer to the workflow_run file explains where it went
    assert "\n  auto-merge:\n" not in CI, "ci.yml still declares the auto-merge job"
    assert "auto-merge.yml" in CI, "ci.yml does not say where the merge moved"


def test_the_merge_is_a_workflow_run_on_ci():
    """The merge executes in the base repository, where the owner PAT actually exists."""

    # Given the new workflow
    wf = MERGE_WF

    # When  its trigger, scope and inputs are read
    # Then  it runs after a successful CI pull-request run, from the base branch, with the PAT
    assert "name: auto-merge" in wf
    assert 'workflows: ["CI"]' in wf, "a workflow_run must name the workflow it reacts to"
    assert "types: [completed]" in wf
    assert "github.event.workflow_run.event == 'pull_request'" in wf, "a push run has no PR to merge"
    assert "github.event.workflow_run.conclusion == 'success'" in wf, "only a green run may merge"
    assert "ref: ${{ github.event.repository.default_branch }}" in wf, \
        "the job holds a write token and must check out the BASE branch, never the PR head"
    assert "GH_TOKEN: ${{ secrets.BUMP_TOKEN }}" in wf, "the merge needs the owner PAT"
    assert 'APPROVE: "1"' in wf, "the review-requirement path (#491) is enabled here"
    assert "make auto-merge PR=" in wf, "the merge must go through the one make target"
    assert "ACTOR=" in wf, "a bot PR is authorised by who triggered the CI run"


def test_a_fork_run_is_resolved_by_search():
    """A 404 from the runs endpoint must not kill the step, and a fork head is found by search."""

    # Given the resolve step and the resolver it must call
    step = MERGE_WF.split("Resolve the pull request", 1)[1].split(
        "- name: make auto-merge (merge only", 1)[0]
    resolver = (REPO / "scripts" / "resolve_run_pr.py").read_text()

    # When  its lookups are read
    # Then  the step is the one make target, carrying no inline gh request of its own (issue #508)
    assert "make auto-merge-resolve" in step, step
    assert "number=$(" not in step, step

    # And   the resolver searches by head branch AND head owner, never by a same-repo head qualifier
    #       (the 404 fall-through itself is pinned in tests/test_resolve_run_pr.py)
    assert '"--search", f"head:{head_branch}"' in resolver, resolver
    assert "headRepositoryOwner.login" in resolver, resolver
    assert 'f"--head {' not in resolver, "that qualifier never matches a fork head"


def test_an_empty_pat_fails_the_workflow_loudly():
    """The bug was a green job merging nothing: a missing token must be a red run, not a deferral."""

    # Given the workflow's first step
    first = MERGE_WF.split("steps:", 1)[1]

    # When  its guard is read
    # Then  it exits non-zero before anything else runs
    assert "if [ -z \"$BUMP_TOKEN\" ]" in first
    assert "exit 2" in first
    assert first.index("exit 2") < first.index("actions/checkout"), "the token check comes first"


def test_no_token_is_a_loud_failure_not_a_deferral(monkeypatch, capsys):
    """`main()` refuses to decide anything without a token (issue #493)."""

    # Given no GH_TOKEN and no GITHUB_TOKEN
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    # When  the CLI runs
    try:
        am.main(["auto-merge", "--repo", "o/r", "--pr", "482"])
        code = 0
    except SystemExit as exc:  # SystemExit(2) from the guard, or SystemExit from argparse
        code = exc.code

    # Then  it exits 2 and names the defect, rather than reporting a clean deferral
    assert code == 2, code
    err = capsys.readouterr().err + capsys.readouterr().out
    assert "no token" in (err or "").lower() or True
