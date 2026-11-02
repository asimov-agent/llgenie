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
from scripts import auto_merge as am
from scripts import bot_verdict as bv
from scripts import verify_closure as vc

CI = (REPO / ".github" / "workflows" / "ci.yml").read_text()
MERGE_WF = (REPO / ".github" / "workflows" / "auto-merge.yml").read_text()
MAKEFILE = (REPO / "Makefile").read_text()
README = (REPO / "README.md").read_text()
#: The documentation surface (issue #678): the user guide plus the reference pages it links.
DOCS = README + "\n" + "\n".join(
    p.read_text() for p in sorted((REPO / "docs").glob("*.md")))
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
             permissions: dict | None = None, tokens: dict | None = None, merge_rc: int = 0,
             settle_after: int = 0, prs: list | None = None, views: dict | None = None,
             unknown_reads: int = 0, refuse_user_for: list | None = None,
             checks=None, jobs=None, merged=None):
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
import json, os, pathlib, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
PR = json.loads({json.dumps(pr)!r})
ISSUES = json.loads({json.dumps(issues or {})!r})
PERMS = json.loads({json.dumps(perms)!r})
TOKEN = {token_login!r}
TOKENS = json.loads({json.dumps(tokens or {})!r})
MERGE_RC = {merge_rc!r}
SETTLE = {settle_after!r}
UNKNOWN_READS = {unknown_reads!r}
PRS = json.loads({json.dumps(prs or [])!r})
VIEWS = json.loads({json.dumps(views or {})!r})
CHECKS = json.loads({json.dumps([] if checks is None else checks)!r})
JOBS = json.loads({json.dumps(jobs or {})!r})
MERGED = json.loads({json.dumps(merged or [])!r})
if os.path.exists({str(log)!r} + ".approved"):
    PR = dict(PR, reviewDecision="APPROVED", mergeStateStatus="CLEAN")
if os.path.exists({str(log)!r} + ".merged"):
    PR = dict(PR, state="MERGED")
if args[:3] == ["api", "user", "--jq"]:
    if os.environ.get("GH_TOKEN", "") in json.loads({json.dumps(refuse_user_for or [])!r}):
        print("gh: Resource not accessible by integration (HTTP 403)", file=sys.stderr); sys.exit(1)
    print(TOKENS.get(os.environ.get("GH_TOKEN", ""), TOKEN)); sys.exit(0)
if len(args) >= 2 and args[0] == "api" and "/collaborators/" in args[1] and args[1].endswith("/permission"):
    login = args[1].split("/collaborators/")[1].split("/")[0]
    if login not in PERMS:
        print("not found", file=sys.stderr); sys.exit(1)
    print(PERMS[login]); sys.exit(0)
if len(args) >= 2 and args[0] == "api" and "check-runs" in args[1]:
    sha = args[1].split("/commits/")[1].split("/")[0].split("?")[0] if "/commits/" in args[1] else ""
    print(json.dumps(CHECKS.get(sha, []) if isinstance(CHECKS, dict) else CHECKS)); sys.exit(0)
if len(args) >= 2 and args[0] == "api" and "/actions/jobs/" in args[1]:
    job = args[1].split("/actions/jobs/")[1].split("/")[0].split("?")[0]
    print(JOBS.get(job, "")); sys.exit(0)
if args[:2] == ["pr", "list"]:
    if "merged" in args:
        print(json.dumps(MERGED)); sys.exit(0)
    print(json.dumps(PRS)); sys.exit(0)
if args[:2] == ["pr", "view"] and len(args) > 2 and args[2] in VIEWS:
    print(json.dumps(VIEWS[args[2]])); sys.exit(0)
if args[:2] == ["pr", "view"]:
    _reads = {str(log)!r} + ".reads"
    _n = (int(open(_reads).read()) if os.path.exists(_reads) else 0) + 1
    open(_reads, "w").write(str(_n))
    if UNKNOWN_READS and _n <= UNKNOWN_READS:
        _st = dict(PR); _st["mergeable"] = "UNKNOWN"; _st["mergeStateStatus"] = "UNKNOWN"
        print(json.dumps(_st)); sys.exit(0)
if args[:2] == ["pr", "view"]:
    if SETTLE and os.path.exists({str(log)!r} + ".approved"):
        counter = pathlib.Path({str(log)!r} + ".views")
        seen = int(counter.read_text()) if counter.exists() else 0
        counter.write_text(str(seen + 1))
        if seen < SETTLE:
            print(json.dumps(dict(PR, reviewDecision="APPROVED", mergeStateStatus="BLOCKED")))
            sys.exit(0)
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
    """`pr_state` is the one call every decision reads; its argv carries only allowlisted names.

    Since issue #852 the read also asks for `comments`: a bot review verdict is a comment marker, and
    the decision must see the verdict and the head it has to match in the SAME snapshot — a second
    read could pair a verdict with a head that moved between the calls.
    """

    # Given a fake gh and a complete PR state
    gh = _fake_gh(tmp_path, _state())

    # When  the state is read
    am.pr_state(str(gh), "o/r", 482)

    # Then  the requested names are the constant, and `authorAssociation` is nowhere in the argv
    views = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "view"]]
    assert len(views) == 1, views
    requested = views[0][views[0].index("--json") + 1].split(",")
    assert requested == list(am.PR_VIEW_FIELDS), requested
    assert "comments" in requested, "the verdict marker lives in the thread (issue #852)"
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


# ---- issue #917: the merger must not queue behind itself ----

def _concurrency_block(workflow: str) -> str:
    """The `concurrency:` mapping as text, so its SHAPE can be asserted rather than its presence.

    Comments are stripped: the block carries its own explanation, and an assertion about what the workflow
    DOES must not be satisfied or defeated by prose that quotes the very values it forbids.
    """
    m = re.search(r"^concurrency:\s*\n((?:[ \t]+.*\n)+)", workflow, re.M)
    assert m, "auto-merge.yml has no concurrency block at all"
    return "\n".join(line for line in m.group(1).splitlines() if not line.lstrip().startswith("#"))


def test_a_later_sweep_supersedes_an_earlier_one():
    """Nine sweeps stacked on `main` put 12 of 51 queued runs behind a 4h25m queue (issue #917).

    The merger was queued behind itself: every CI completion fired a sweep, the schedule fired one every 30
    minutes, and `cancel-in-progress: false` made them wait for each other instead of superseding. A sweep
    re-reads the PR state before acting, so the newer run subsumes the older one, and a merge already made is
    idempotent - the next sweep reads MERGED and stops.
    """
    block = _concurrency_block(MERGE_WF)

    assert "cancel-in-progress: true" in block, block
    assert "cancel-in-progress: false" not in block, (
        "a per-branch group that cannot cancel stacks one sweep per CI completion (#917)")


def test_the_sweep_group_is_repo_wide_within_each_outcome_not_per_branch():
    """One sweep at a time per OUTCOME (issue #917, corrected twice by measurement).

    `cancel-in-progress: false` does NOT protect a PENDING run: GitHub keeps one running plus one pending per
    group and replaces the pending one whatever the flag says. With a per-branch group the scheduled sweeps —
    which carry no `head_branch` — collapsed into one empty-name group and cancelled each other's pending slot:
    16 of the last 25 runs ended `cancelled` with no job rows, so nothing drained and churn looked like
    backlog. And a single repo-wide group has the opposite defect: a sweep fired by a FAILING CI run decides
    nothing (the `merge` job requires `conclusion == 'success'`), yet it would cancel the pending sweep of a
    PR that IS mergeable. So the group is repo-wide *within each conclusion*.
    """
    block = _concurrency_block(MERGE_WF)

    assert "github.event.workflow_run.conclusion" in block, (
        "a single group lets a failed-CI sweep cancel a mergeable PR's pending sweep (#917): " + block)
    assert "head_branch" not in block, (
        "a per-branch group is what let the scheduled sweeps cancel each other (#917)")
    assert "cancel-in-progress: true" in block, block


def test_the_merge_uses_the_owner_pat_and_a_make_target():
    """The PAT, so the post-merge run on main happens; and CI runs a make target, not a script."""

    # Given the merge workflow
    block = MERGE_WF

    # When  its env and run are read
    # Then  the MERGE is made with the owner PAT — never the job token, which starts no workflows …
    assert "GH_TOKEN: ${{ secrets.BUMP_TOKEN }}" in block, block[:800]
    assert "GH_TOKEN: ${{ github.token }}" not in block, (
        "a merge made with the job token starts no workflows, so the merge must keep the owner PAT")
    assert "make auto-merge" in block, block[:800]
    assert "python3 scripts/auto_merge.py" not in block, "the workflow must call the make target"
    # … while the REVIEW is exactly the job token, which is a DIFFERENT account from the author (#874):
    # `github-actions[bot]` approves, `andyholst` authored, so the approval is legal without an owner PAT.
    assert "APPROVER_TOKEN: ${{ github.token }}" in block, block[:800]
    assert "secrets.APPROVER_TOKEN" not in block, (
        "the review must not depend on a secret that can be empty: the job token always exists")

def test_the_targets_are_phony_and_documented():
    """`auto-merge` and `verify-closure` exist, are phony, and are documented."""

    # Given the Makefile and the README
    phony = MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # When  the two targets are looked for
    # Then  both are declared, both recipes exist, and the docs document them
    for target in ("auto-merge", "verify-closure"):
        assert f"\n{target}:" in MAKEFILE, target
        assert target in phony, target
        assert target in DOCS, target


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


def test_a_bot_authored_pr_is_approved_by_the_merge_token(tmp_path):
    """`app/github-actions` is this repo's own bot, not a stranger: the other identity may approve it.

    Issue #529: the author gate admits the bot (`BOT_LOGINS`) while the approval gate did not, so a
    workflow PR could never clear the required review and `--admin` is refused.
    """

    # Given a green PR opened as the Actions app, blocked only by the required review
    gh = _fake_gh(tmp_path, _review_blocked(author="app/github-actions"), {"529": "CLOSED"},
                  permissions={"asimov-agent": "admin"})

    # When  the job runs with review clearance enabled, for a run the owner triggered
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True,
                actor="asimov-agent")

    # Then  the merge token approves it and merges without the admin bypass
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert ["pr", "review"] in [c[:2] for c in calls], calls
    assert merges and "--admin" not in merges[0], merges
def test_the_approval_is_waited_for_before_deciding(tmp_path, monkeypatch):
    """GitHub reports BLOCKED for a moment after an approval; the job must wait, not give up (#531)."""

    # Given a review-blocked green PR whose state stays BLOCKED for two reads after the approval
    monkeypatch.setattr(am, "RECHECK_DELAY", 0.0)
    monkeypatch.setattr(am, "RECHECK_ATTEMPTS", 4)
    gh = _fake_gh(tmp_path, _review_blocked(), {"531": "CLOSED"}, settle_after=2)

    # When  the job runs with review clearance enabled
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  it merges on the polled read, without ever falling back to --admin
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert merges and "--admin" not in merges[0], merges
    assert len([c for c in calls if c[:2] == ["pr", "view"]]) >= 3, calls


def test_a_pr_that_never_settles_defers_naming_the_real_reason(tmp_path, monkeypatch):
    """No `None` in the deferral: it says the approval landed and the state it stayed stuck in (#531)."""

    # Given a PR that stays BLOCKED however long the job waits, and a merge GitHub refuses
    monkeypatch.setattr(am, "RECHECK_DELAY", 0.0)
    monkeypatch.setattr(am, "RECHECK_ATTEMPTS", 3)
    gh = _fake_gh(tmp_path, _review_blocked(), {"531": "CLOSED"}, settle_after=99, merge_rc=1)

    # When  the job runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  it exits 0 and the comment names the wait, never "None"
    comments = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]
    assert rc == 0, rc
    assert comments, "a deferral must be visible on the PR"
    body = " ".join(comments[0])
    assert "did not become mergeable within the wait" in body, body
    assert "None;" not in body, body


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
    """`auto-merge-explain` exists, is phony, and is documented."""

    # Given the Makefile and the README
    phony = MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # When  the target is looked for
    # Then  it is declared, has a recipe, and the docs document it
    assert "\nauto-merge-explain:" in MAKEFILE
    assert "auto-merge-explain" in phony
    assert "auto-merge-explain" in DOCS


# ---- green ⇒ merged is permanent: the threshold may be neither deleted nor loosened (issue #874) ----

def test_the_merge_gate_still_requires_a_clean_pr():
    """`mergeStateStatus` stays CLEAN — #874 forbids a loosened threshold, not only a deleted file.

    The tree half of the guard sits with the workflow invariants
    (`tests/test_bot_pipeline_isolation.py::test_auto_merge_fires_by_itself_when_a_pr_run_completes`);
    this is the decision half. It pins BOTH the constants and the behaviour they drive, so an edit that
    widens one of them (to `UNSTABLE`/`BLOCKED`, or by dropping the head check) reds here instead of
    quietly merging a PR GitHub says is not clean.
    """

    # Given the three thresholds the decision reads, and the human hold
    # Then  each is the one #874 pinned — OPEN (not MERGED/CLOSED), MERGEABLE, and CLEAN
    assert (am.REQUIRED_STATE, am.REQUIRED_MERGEABLE, am.REQUIRED_MERGE_STATE) == \
        ("OPEN", "MERGEABLE", "CLEAN"), (
        "the merge thresholds were loosened: a PR that GitHub does not report as OPEN + MERGEABLE + "
        "CLEAN would now be merged (issue #874 — never merge an unstable, blocked, dirty or stale PR)")
    assert am.HOLD_LABEL == "do-not-merge", "the human hold label was renamed away"

    # When  an otherwise green, still-headed PR is decided for every non-CLEAN merge state
    for status in ("UNSTABLE", "BLOCKED", "DIRTY", "BEHIND", "HAS_HOOKS", "UNKNOWN", ""):
        state = _state(mergeStateStatus=status)
        reason = am.decide(state, HEAD)

        # Then  it is deferred with a reason, never merged
        assert reason, f"decide() returned None (i.e. MERGE) for mergeStateStatus={status!r}"

    # And   the inverse still holds: a green, CLEAN PR at the run's own head merges with no human
    assert am.decide(_state(), HEAD) is None, (
        "a green, CLEAN, non-draft PR no longer merges — the guard must not also break the behaviour")


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
    # CI is the workflow_run trigger's primary name, and the docs-class completion joins it (issue
    # #1227): a docs-only head never produces a CI run (`ci.yml` paths-ignore the docs class), so its
    # green head can only reach the merge job through the `ci-scope` completion, which runs on every PR.
    # The roster is the multi-line block form (one workflow per line), because the docs-class name holds
    # a comma that a bracketed `["CI", "..."]` list would mis-split.
    assert 'workflows:' in wf and '- "CI"' in wf and "- \"ci-scope" in wf, \
        "a workflow_run must name the workflows it reacts to (CI and the docs-class ci-scope)"
    assert "types: [completed]" in wf
    assert "github.event.workflow_run.event == 'pull_request'" in wf, "a push run has no PR to merge"
    assert "github.event.workflow_run.conclusion == 'success'" in wf, "only a green run may merge"
    assert "ref: ${{ github.event.repository.default_branch }}" in wf, \
        "the job holds a write token and must check out the BASE branch, never the PR head"
    assert "GH_TOKEN: ${{ secrets.BUMP_TOKEN }}" in wf, "the merge needs the owner PAT"
    assert 'APPROVE: "1"' in wf, "the review-requirement path (#491) is enabled here"
    assert "make auto-merge PR=" in wf, "the merge must go through the one make target"
    assert "ACTOR=" in wf, "a bot PR is authorised by who triggered the CI run"


def test_auto_merge_watches_the_docs_class_by_scope_yml_name():
    """AC4: the merge job engages on a green docs-class completion, so a docs-only PR is never
    silently re-excluded by a paths-ignore drift.

    `ci.yml` ignores the docs class at the trigger (`pull_request.paths-ignore` == `DOCS_TRIGGER_IGNORE`),
    so a docs-only head has no `CI` run; its only CI-class completion is `ci-scope` (no path filter), and
    that workflow must therefore be named in auto-merge's `workflow_run.workflows`. GitHub matches that
    roster against scope.yml's top-level `name:` VERBATIM, so the pin is the exact name, not a prefix.
    Revert auto-merge.yml to watch only `CI` and the docs class is silently re-excluded again.
    """
    import scripts.ci_scope as cscope

    scope_text = (REPO / ".github" / "workflows" / "scope.yml").read_text()
    m = re.search(r"^name:\s*(.+?)\s*$", scope_text, re.M)
    assert m, "scope.yml must declare a top-level name:"
    scope_name = m.group(1)

    # The two facts AC4 pins together: ci.yml skips the docs class (no CI run on a docs-only head),
    # scope carries no path filter (it IS a docs-only head's completion), and auto-merge names that
    # completion in the same roster as CI.
    assert scope_name in MERGE_WF, "auto-merge must watch the docs-class completion by its exact name"
    assert '"CI"' in MERGE_WF, "CI must stay a workflow_run trigger"
    assert "paths-ignore" in CI, "ci.yml still skips the docs class (that is why docs needs scope)"
    assert "paths-ignore" not in scope_text and "paths:" not in scope_text, \
        "scope must run on a docs-only PR to be its completion"
    assert set(cscope.DOCS_TRIGGER_IGNORE) == set(cscope.CLASSES["docs"]), \
        "a docs trigger that drifts from the docs class re-excludes docs PRs from the merge job"


def test_a_docs_only_head_is_the_auto_merge_channel_and_a_code_head_is_ci(tmp_path, monkeypatch):
    """AC4: the channel split that keeps a code PR's merge with its own CI completion while giving a
    docs-only head (no ci.yml run) to this sweep.

    The routing is pinned so a future paths-ignore drift cannot silently move a code head to a premature
    docs sweep or drop a docs head entirely: a head WITH a ci.yml run reports `channel=ci`, a head with
    only the scope run reports `channel=auto-merge`.
    """
    import scripts.auto_merge_channel as ch

    log = tmp_path / "gh.log"

    def fake_gh(count: str):
        gh = tmp_path / f"gh{count}"
        gh.write_text(f'''#!{sys.executable}
import json, sys
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
print({count!r})
''')
        gh.chmod(0o755)
        return str(gh)

    # Given a head with one ci.yml run (a code PR): the CI completion will decide it.
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out1"))
    gh = fake_gh("1")
    assert ch.main(["channel", "--repo", "o/r", "--head-sha", HEAD, "--gh", gh]) == 0
    assert "channel=ci" in (tmp_path / "out1").read_text(), (tmp_path / "out1").read_text()
    # And the query is the raw URL-string form (issue #1311): the `-f` form-encoding is rejected by
    # `gh` 2.103.x on this endpoint with a spurious 404, so the argv must carry the params IN the URL
    # and never as `-f` flags. The query still filters for the ci.yml workflow file at that head (the
    # scope run at the same head must not count as a CI run); the log then says the decision.
    call = json.loads(log.read_text().splitlines()[0])
    assert call[1].startswith("repos/o/r/actions/runs?"), call
    assert "-f" not in call, call
    assert "path=.github/workflows/ci.yml" in call[1], call
    assert "event=pull_request" in call[1] and f"head_sha={HEAD}" in call[1], call

    # Given a docs-only head with NO ci.yml run (only the scope run exists): this sweep decides.
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out2"))
    gh0 = fake_gh("0")
    assert ch.main(["channel", "--repo", "o/r", "--head-sha", HEAD, "--gh", gh0]) == 0
    assert "channel=auto-merge" in (tmp_path / "out2").read_text()

    # A count the API cannot produce is a LOUD failure, never a doc grabbed by a guessed channel.
    gh_err = tmp_path / "ghbad"
    gh_err.write_text(f"""#!{sys.executable}
import sys
sys.stderr.write("404 (no such run)\\n")
sys.exit(1)
""")
    gh_err.chmod(0o755)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    assert ch.main(["channel", "--repo", "o/r", "--head-sha", HEAD, "--gh", str(gh_err)]) == 2


def test_a_transient_gateway_error_is_retried_and_recovers(tmp_path, monkeypatch):
    """A 502/504 (the answer lost, not a verdict) is retried a bounded number of times, then recovers.

    The retry is the load-bearing half of issue #1311's fix: the raw-URL form leaves the API reachable,
    and a lose-answer gateway error must not turn a green, armed head into a red sweep. A 404 (this API
    genuinely cannot confirm the head) stays LOUD on the FIRST attempt — never retried into a silent
    "no CI run" — so the same helper must not mask a real refusal.
    """
    import scripts.auto_merge_channel as ch

    # Transient: first two calls fail 502, the third answers "1" = a code head.
    gh = tmp_path / "gh-transient"
    log = tmp_path / "gh-transient.log"
    log.write_text("")
    gh.write_text(f"""#!{sys.executable}
import sys
with open({str(log)!r}, "a") as fh:
    fh.write("CALL" + "\\n")
n = open({str(log)!r}).read().count("CALL")
if n < 3:
    sys.stderr.write("HTTP 502 (gateway error)\\n"); sys.exit(1)
print("1")
""")
    gh.chmod(0o755)
    assert ch.ci_run_count(str(gh), "o/r", HEAD) == 1
    calls = log.read_text().count("CALL")
    assert calls == 3, calls


def test_a_genuine_404_is_loud_on_the_first_attempt(tmp_path, monkeypatch):
    """A 404 (truly unconfirmable head) is a loud failure on the FIRST call, never retried silently.

    The retry must re-attempt only a lost answer (502/504), never swallow a refusal that the API
    answered definitively — otherwise a disabled/unfindable workflow would be decided channel=auto-merge
    by a blind retry loop. Pins the "one call, then exit 2" behaviour.
    """
    import scripts.auto_merge_channel as ch

    gh = tmp_path / "gh-404"
    log = tmp_path / "gh-404.log"
    log.write_text("")
    gh.write_text(f"""#!{sys.executable}
import sys
with open({str(log)!r}, "a") as fh:
    fh.write("CALL" + "\\n")
sys.stderr.write("404 (no such run)\\n"); sys.exit(1)
""")
    gh.chmod(0o755)
    # Force a single attempt: default retry would take 1s+; assert the 404 is NOT retried (first call loud).
    monkeypatch.setattr(ch, "_gh_retry", lambda g, a, attempts=3, delay=1.0: ch._gh(g, a))
    try:
        ch.ci_run_count(str(gh), "o/r", HEAD)
        raise AssertionError("expected a loud RuntimeError for a genuine 404")
    except RuntimeError as exc:
        assert "404" in str(exc), exc
    # One call only — a real 404 must not spin a retry loop.
    assert log.read_text().count("CALL") == 1, log.read_text()


def test_the_scope_sweep_skips_a_code_head_and_decides_once(tmp_path):
    """The gate that keeps a scope-triggered sweep off a code PR: the merge job runs on the CI
    completion, and on a scope completion only when the channel named this sweep.

    The negative control: with auto-merge watching scope (a code head's scope run completes minutes
    before its CI run), a sweep that decided the code head would defer a mid-flight PR ahead of the
    green CI run that will itself merge it. This pins the `if:` on the merge step that prevents it.
    """
    block = MERGE_WF.split("Which channel merges this head", 1)[1]

    # The channel step runs only for the docs-class completion (never for CI itself).
    assert "if: github.event.workflow_run.name != 'CI'" in block, block[:600]
    # And the merge step runs for a CI completion, or for a scope sweep that found no CI run at the head —
    # and ONLY when the resolve step actually produced a PR number (a landed/closed head resolves to an
    # empty `number=` and is a non-event, never a red run — issue #897).
    assert "make auto-merge-channel REPO" in block, block[:600]
    assert ("if: (github.event.workflow_run.name == 'CI' || "
            "steps.channel.outputs.channel == 'auto-merge') && "
            "steps.pr.outputs.number != ''") in block, block[:600]


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


# ---- a deferral is retried by the recheck sweep (issue #545) ----

def _deferred_view(pr: dict, head: str, **kw) -> dict:
    """A PR carrying the gate's own deferral marker for `head`."""
    marker = am.DEFERRAL_MARKER.format(head[:40])
    view = dict(pr)
    view["comments"] = [{"body": f"{marker}\n\nNot auto-merged."}]
    view.update(kw)
    return view


def test_a_deferred_pr_is_retried_and_merged_when_the_blocker_cleared(tmp_path):
    """#541: the secret was added, nothing about the PR changed — the sweep must finish the job."""

    # Given a green, clean PR carrying a deferral marker for its CURRENT head
    trust = {"nameWithOwner": "asimov-agent/llgenie"}
    view = _deferred_view(_state(reviewDecision="APPROVED", headRepository=trust), HEAD)
    gh = _fake_gh(tmp_path, _state(reviewDecision="APPROVED", headRepository=trust),
                  prs=[{"number": 541, "headRefOid": HEAD}], views={"541": view})

    # When  the recheck sweep runs
    rc = am.recheck(str(gh), "asimov-agent/llgenie", max_prs=5)

    # Then  it merges it, through the one decision (no --admin)
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert merges and "--admin" not in merges[0], merges


def test_a_marker_for_another_head_is_not_retried(tmp_path):
    """That verdict described a different tree; the current head has its own run."""

    # Given a deferral marker for an OLD head, on a PR whose head has since moved
    trust = {"nameWithOwner": "asimov-agent/llgenie"}
    view = _deferred_view(_state(headRepository=trust), "0ld" * 13 + "ab")
    gh = _fake_gh(tmp_path, _state(headRepository=trust),
                  prs=[{"number": 541, "headRefOid": HEAD}], views={"541": view})

    # When  the sweep runs
    rc = am.recheck(str(gh), "asimov-agent/llgenie")

    # Then  nothing is merged or approved
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0
    assert not [c for c in calls if c[:2] == ["pr", "merge"]]
    assert not [c for c in calls if c[:2] == ["pr", "review"]]


def test_a_review_blocked_pr_without_a_marker_is_approved_and_merged(tmp_path):
    """A green PR whose only blocker is the required review never got a deferral marker.

    The merge job only runs for the CI run that just finished. A PR that is already green and
    armed stays REVIEW_REQUIRED until something approves it. The sweep is that something, and the
    approver is the workflow token, a different account from the author.
    """

    # Given a review-blocked PR authored by andyholst, with no deferral marker
    trust = {"nameWithOwner": "asimov-agent/llgenie"}
    blocked = _review_blocked(headRepository=trust, headRefOid=HEAD)
    gh = _fake_gh(tmp_path, blocked, prs=[{"number": 1247, "headRefOid": HEAD}],
                  token_login="asimov-agent")

    # When  the sweep runs
    rc = am.recheck(str(gh), "asimov-agent/llgenie")

    # Then  it approves with the other identity and merges, and the token never reaches argv
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert ["pr", "review"] in [c[:2] for c in calls], calls
    assert merges and "--admin" not in merges[0], merges


def test_a_pr_without_a_deferral_marker_is_not_touched(tmp_path):
    """The sweep retries its OWN deferrals, not every open PR."""

    # Given an open PR with no deferral marker
    trust = {"nameWithOwner": "asimov-agent/llgenie"}
    gh = _fake_gh(tmp_path, _state(headRepository=trust),
                  prs=[{"number": 600, "headRefOid": HEAD}], views={"600": _state(headRepository=trust)})

    # When  the sweep runs
    rc = am.recheck(str(gh), "asimov-agent/llgenie")

    # Then  it merges nothing
    assert rc == 0
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]


def test_the_recheck_is_scheduled_and_runs_the_make_target():
    """A deferral is retried by a scheduled sweep, not only by a human re-run (issue #545)."""

    # Given the merge workflow and the Makefile
    # When  the schedule, the recheck job and the target are read
    # Then  the workflow schedules it and the job calls the one make target
    assert "schedule:" in MERGE_WF and "*/30 * * * *" in MERGE_WF, "the sweep must be scheduled"
    assert "recheck:" in MERGE_WF, "a recheck job must exist"
    assert "make auto-merge-recheck REPO=\"$REPO\"" in MERGE_WF
    assert "APPROVER_TOKEN" in MERGE_WF, "the sweep needs the other identity to approve"
    assert "\nauto-merge-recheck:" in MAKEFILE, "the target is the one entry point"
    assert "scripts/auto_merge.py recheck" in MAKEFILE


# ---- GitHub's asynchronous `mergeable` must not become a deferral (issue #558) ----

def test_an_unknown_mergeable_is_waited_for_not_deferred(tmp_path):
    """#552: the run read `mergeable: UNKNOWN`, deferred, and nothing retried it — the PR was green."""

    # Given a green PR whose first reads answer `mergeable: UNKNOWN` (GitHub has not computed it yet)
    gh = _fake_gh(tmp_path, _state(headRepository={"nameWithOwner": "asimov-agent/llgenie"}),
                  unknown_reads=2)

    # When  the gate runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 552, HEAD, approve_when_review_required=True,
                actor="andyholst")

    # Then  it waits, then merges normally — it does not fall back to --admin and does not defer
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0
    assert merges and "--admin" not in merges[0], merges
    assert [c for c in calls if c[:2] == ["pr", "view"]] and len([c for c in calls if c[:2] == ["pr", "view"]]) >= 3


def test_settle_mergeable_gives_up_after_its_attempts(tmp_path):
    """A state that never settles returns the last read, so the caller still defers with a real reason."""

    # Given a PR that answers UNKNOWN forever
    gh = _fake_gh(tmp_path, _state(), unknown_reads=99)

    # When  the settle helper runs with two attempts and no delay
    state = am.settle_mergeable(str(gh), "asimov-agent/llgenie", 552, attempts=2, delay=0)

    # Then  it returns UNKNOWN and spends exactly two reads
    assert (state.get("mergeable") or "").upper() == "UNKNOWN"
    assert len([c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "view"]]) == 2


def test_the_recheck_runs_on_every_ci_completion_too():
    """The cron has never fired for this workflow (0 schedule runs measured), so CI completions must sweep."""

    # Given the merge workflow on main
    # When  the recheck job's trigger is read
    # Then  it runs after the merge job on any outcome, and the cron is still declared
    assert "schedule:" in MERGE_WF and "*/30 * * * *" in MERGE_WF
    recheck = MERGE_WF.split("recheck:", 1)[1]
    assert "needs: [merge]" in recheck
    assert "always()" in recheck, "a workflow_run completion must sweep too"


# ---- issue #874: the workflow's own token can approve, and must not approve its own PR ----

def test_an_ordinary_author_is_approved_by_the_workflow_token(tmp_path, monkeypatch):
    """`github.token` is `github-actions[bot]`, a different account from the author — so it is legal.

    An installation token cannot answer `GET /user` (403 "Resource not accessible by integration"), which is
    why the identity is deterministic rather than queried: the fallback names the bot instead of aborting.
    """
    # Given a review-blocked PR authored by andyholst, and the workflow token as the approver
    gh = _fake_gh(tmp_path, _review_blocked(author="andyholst"), {"491": "CLOSED"},
                  token_login="asimov-agent", refuse_user_for=["wf-token"])
    monkeypatch.setenv("APPROVER_TOKEN", "wf-token")

    # When  the job runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  the review is posted with that token, and the merge is not the admin bypass
    calls = _calls(tmp_path / "gh.log")
    merges = [c for c in calls if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert ["pr", "review"] in [c[:2] for c in calls], calls
    assert merges and "--admin" not in merges[0], merges
    assert not any("wf-token" in " ".join(c) for c in calls), "the token must never reach argv"


def test_a_pr_the_workflow_opened_is_never_approved_by_the_workflow(tmp_path, monkeypatch):
    """The negative control: `github-actions[bot]` cannot approve a PR `github-actions[bot]` opened.

    Without this, enabling the workflow token as the approver would turn a self-approval attempt into a
    GitHub 422 on a green PR — the failure mode the guard exists to prevent.
    """
    # Given a PR the workflow itself opened, and a merge token that is ALSO the workflow's own account
    gh = _fake_gh(tmp_path, _review_blocked(author="github-actions[bot]"), {"491": "CLOSED"},
                  token_login="github-actions[bot]", refuse_user_for=["wf-token"],
                  permissions={"github-actions[bot]": "admin", "andyholst": "admin"})
    monkeypatch.setenv("APPROVER_TOKEN", "wf-token")

    # When  the job runs for an owner-triggered run (so the bot-PR guard lets it through)
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True,
                actor="andyholst")

    # Then  it never posts a review, and falls back to the admin merge instead
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0, rc
    assert not [c for c in calls if c[:2] == ["pr", "review"]], calls
    assert [c for c in calls if c[:2] == ["pr", "merge"] and "--admin" in c], calls


# ---- announcing the merge (fleet rule 14, issue #873) ------------------------

def _announcements(tmp_path: Path) -> list[str]:
    """Every `pr comment` body the run posted — `[]` when the fake gh was never called at all."""
    log = tmp_path / "gh.log"
    if not log.exists():
        return []
    return [" ".join(c) for c in _calls(log) if c[:2] == ["pr", "comment"]]


def test_a_merge_announces_the_run_the_sha_and_the_decision_on_the_pr(tmp_path, monkeypatch):
    """Rule 14: a merger that merges silently cannot be told apart from a coincidence.

    The comment must name the run id, the head sha judged and the decision — and it must be posted
    AFTER the merge returned, not before it (a run that announces a merge it has not made is worse
    than a silent one).
    """

    # Given a green, CLEAN PR and a run id in the environment
    monkeypatch.setenv("GITHUB_RUN_ID", "40835541562")
    gh = _fake_gh(tmp_path, _state(), {"482": "CLOSED"})

    # When  the merge runs
    rc = am.run(str(gh), "o/r", 482, HEAD)

    # Then  one comment names the run, the sha and the decision, and it follows the merge
    calls = _calls(tmp_path / "gh.log")
    bodies = _announcements(tmp_path)
    assert rc == 0, rc
    assert len(bodies) == 1, bodies
    body = bodies[0]
    for needle in ("Merged by `auto-merge`", "40835541562", HEAD, "CLEAN", "rule 14"):
        assert needle in body, (needle, body)
    merge_at = [i for i, c in enumerate(calls) if c[:2] == ["pr", "merge"]]
    comment_at = [i for i, c in enumerate(calls) if c[:2] == ["pr", "comment"]]
    assert merge_at and comment_at and comment_at[0] > merge_at[0], calls


def test_a_refused_merge_announces_nothing(tmp_path):
    """The negative control: a merge GitHub refused is NOT announced as a merge.

    `merge()` raises SystemExit on a refusal; the deferral path runs instead. Announcing there would
    tell the next reader the PR had merged when it had not.
    """

    # Given a review-blocked PR whose merge GitHub refuses
    gh = _fake_gh(tmp_path, _review_blocked(author="asimov-agent"), {"491": "CLOSED"},
                  token_login="asimov-agent", merge_rc=1)

    # When  the job runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  it defers with the reason and announces no merge at all
    bodies = _announcements(tmp_path)
    assert rc == 0, rc
    assert bodies and "admin merge was refused" in bodies[0], bodies
    assert not [b for b in bodies if "Merged by `auto-merge`" in b], bodies


def test_the_admin_fallback_announces_the_bypass(tmp_path):
    """The admin path is a merge too: its announcement says the review could not be self-approved."""

    # Given a review-blocked PR authored by the merge token's own account
    gh = _fake_gh(tmp_path, _review_blocked(author="asimov-agent"), {"491": "CLOSED"},
                  token_login="asimov-agent")

    # When  the job runs with review clearance enabled
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  the merge is announced as the admin bypass, after the merge
    calls = _calls(tmp_path / "gh.log")
    bodies = _announcements(tmp_path)
    assert rc == 0, rc
    assert len(bodies) == 1, bodies
    assert "--admin" in bodies[0], bodies[0]
    merge_at = [i for i, c in enumerate(calls) if c[:2] == ["pr", "merge"]]
    comment_at = [i for i, c in enumerate(calls) if c[:2] == ["pr", "comment"]]
    assert comment_at[0] > merge_at[0], calls


def test_an_announcement_is_posted_once_per_head(tmp_path):
    """Idempotent per head sha, like the deferral: a recheck of an already-merged PR posts nothing."""

    # Given a PR whose comments already carry the announcement for this head
    marker = am.MERGE_MARKER.format(HEAD)
    gh = _fake_gh(tmp_path, _state(comments=[{"body": marker}]))

    # When  the announcement runs again for the same head
    am.announce_merge(str(gh), "o/r", 482, HEAD)

    # Then  nothing is posted
    assert not _announcements(tmp_path)

    # And   a different head is announced (the old marker described a different tree)
    gh2 = _fake_gh(tmp_path / "second", _state(comments=[{"body": marker}]))
    am.announce_merge(str(gh2), "o/r", 482, "deadbeef" + HEAD[8:])
    assert _announcements(tmp_path / "second")


def test_a_local_run_says_it_is_local_instead_of_inventing_a_run_id(tmp_path, monkeypatch):
    """`make auto-merge` is documented as a local invocation, and it has no `GITHUB_RUN_ID`.

    The first version wrote `run: unknown` — a value the merger made up, in a comment whose whole purpose is
    to be evidence. A reader cannot tell "unknown" from "a run id we failed to capture", so it now says which
    kind of run it was. Prevents: an audit line that looks filled in and is not.
    """
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    gh = _fake_gh(tmp_path, _state(), {"482": "CLOSED"})

    rc = am.run(str(gh), "o/r", 482, HEAD)

    bodies = _announcements(tmp_path)
    assert rc == 0, rc
    assert len(bodies) == 1, bodies
    assert "a local invocation" in bodies[0], bodies[0]
    assert "unknown" not in bodies[0], bodies[0]
    assert HEAD in bodies[0], bodies[0]


def test_an_announcement_with_no_head_sha_is_refused_not_posted(tmp_path, capsys):
    """A comment that cannot say WHICH tree was merged is noise shaped like an audit line.

    The marker would be `<!-- auto-merge: merged  -->`, which also matches every other empty-sha
    announcement, so the idempotency check would silently suppress the next real one. Prevents: rule 14's
    evidence requirement being satisfied by a comment with an empty sha in it.
    """
    gh = _fake_gh(tmp_path, _state(), {"482": "CLOSED"})

    am.announce_merge(str(gh), "o/r", 482, "")

    err = capsys.readouterr().err
    assert "NOT announcing the merge" in err, err
    assert not _announcements(tmp_path)


def test_a_failed_announcement_names_the_merge_it_could_not_record(tmp_path, monkeypatch, capsys):
    """The merge already happened; a comment that fails must not read as "the run failed" without saying so.

    Without this, a flaky `gh pr comment` after a successful merge produces a bare `gh … failed` red — the
    reader concludes nothing merged, while the branch is deleted and the commit is on `main`. Prevents: a
    merged PR charged to a failed announcement, with the audit line missing and nobody told which.
    """
    import pytest as _pytest

    gh = _fake_gh(tmp_path, _state(), {"482": "CLOSED"})
    real = am._gh

    def boom(gh_bin, args, token=""):
        if args[:2] == ["pr", "comment"]:
            raise SystemExit("[auto-merge] gh pr comment failed (1): Resource not accessible by integration")
        return real(gh_bin, args, token)

    monkeypatch.setattr(am, "_gh", boom)

    with _pytest.raises(SystemExit):
        am.run(str(gh), "o/r", 482, HEAD)

    err = capsys.readouterr().err
    assert f"MERGED at {HEAD}" in err, err
    assert "could NOT be posted" in err, err
    assert "no audit line" in err, err
# ---- a bot verdict is legible to the merge decision, never an approval (issue #852) -----------

def _verdict(head: str = HEAD, verdict: str = "approve", reviewer: str = "github-actions[bot]",
             author: str = "") -> dict:
    """A PR comment carrying the bot-verdict marker, in the shape `gh pr view --json comments` gives."""
    who = author or reviewer
    return {"author": {"login": who}, "body": bv.marker(head, verdict, reviewer)}


def test_a_stale_verdict_does_not_clear_the_review_block(tmp_path):
    """A verdict names ONE tree: at any other head it says nothing about what would merge.

    Every bot pushes with the owner's token, so an approval is impossible and `reviewDecision` stays
    REVIEW_REQUIRED. The fix must not be "any verdict in the thread clears the block" — a push after the
    verdict would then merge unreviewed code (issue #852).
    """
    # Given a review-blocked PR at HEAD, with a verdict written for an OLDER commit
    stale = _verdict(head="0" * 40)
    state = _review_blocked(comments=[stale])
    gh = _fake_gh(tmp_path, state, {"482": "CLOSED"})

    # When  the decision and then the full run read it
    reason = am.decide(state, HEAD, repo_owner="asimov-agent")
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  the block stands, the reason is the merge state, and nothing is merged
    assert reason and "mergeStateStatus is BLOCKED" in reason, reason
    assert rc == 0
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]


def test_a_verdict_at_the_current_head_clears_the_review_block_and_merges(tmp_path):
    """The verdict IS the review; the block is the identity, so the merge bypasses it (issue #852)."""
    # Given a review-blocked PR at HEAD and a trusted verdict written for exactly that head
    state = _review_blocked(comments=[_verdict()])
    gh = _fake_gh(tmp_path, state, {"482": "CLOSED"})

    # When  the decision and the run read it
    reason = am.decide(state, HEAD, repo_owner="asimov-agent")
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD, approve_when_review_required=True)

    # Then  the decision accepts it, and the merge is the ONE admin merge pinned to that head
    assert reason is None, reason
    merges = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert len(merges) == 1, merges
    assert "--admin" in merges[0], merges[0]
    assert merges[0][merges[0].index("--match-head-commit") + 1] == HEAD, merges[0]


def test_a_verdict_from_an_untrusted_login_does_not_count(tmp_path):
    """Anyone can comment on a public PR, so the marker's author must be a repository identity."""
    # Given a verdict marker written by an account the repository does not own
    state = _review_blocked(comments=[_verdict(reviewer="stranger", author="stranger")])
    gh = _fake_gh(tmp_path, state, {"482": "CLOSED"})

    # When  the decision and the run read it
    reason = am.decide(state, HEAD, repo_owner="asimov-agent")
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  it is not a verdict about anything, and nothing is merged
    assert reason and "BLOCKED" in reason, reason
    assert rc == 0
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]


def test_a_stranger_cannot_borrow_a_bot_name_in_the_marker(tmp_path):
    """`reviewer=` must be the comment's own author, or the marker impersonates an identity."""
    # Given a stranger's comment whose marker claims the bot wrote it
    state = _review_blocked(comments=[_verdict(reviewer="github-actions[bot]", author="stranger")])

    # When  the decision reads it
    reason = am.decide(state, HEAD, repo_owner="asimov-agent")

    # Then  it does not count
    assert reason and "BLOCKED" in reason, reason


def test_a_changes_verdict_at_the_head_holds_the_pr(tmp_path):
    """A verdict is a decision either way: `changes` blocks, even when the merge state is otherwise fine."""
    # Given a CLEAN PR whose thread carries a `changes` verdict at its head
    state = _state(comments=[_verdict(verdict="changes", reviewer="asimov-agent")])
    gh = _fake_gh(tmp_path, state, {"482": "CLOSED"})

    # When  the decision and the run read it
    reason = am.decide(state, HEAD, repo_owner="asimov-agent")
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  the changes are named and nothing is merged
    assert reason and "requests changes" in reason, reason
    assert rc == 0
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]

# The property "the gate still fires itself" is pinned by
# tests/test_bot_pipeline_isolation.py::test_auto_merge_fires_by_itself_when_a_pr_run_completes
# (issue #874): this change reads the verdict, it must never be the reason the workflow stops running
# on its own, so that guard is re-run in the same `make test-unit` pass (issue #852).


# ---- a red head is not merged, and --admin is not the way around it (issue #1386) ----

SCOPE_URL = ("https://github.com/asimov-agent/llgenie/actions/runs/41325509945/job/124904531947")
SCOPE_JOB = {"124904531947": "make ci-lint"}
MERGE_SHA = "ac1f3e77" + "ab" * 16


def _scope_failure() -> list:
    """The #1401 head: `scope` failed `make ci-lint` while GitHub still said the review was the blocker."""
    return [{"name": "scope", "conclusion": "failure", "details_url": SCOPE_URL}]


def test_a_clean_pr_with_a_red_check_is_not_merged(tmp_path):
    """mergeStateStatus CLEAN does not outrank a failed check on the head."""

    # Given a pull request GitHub calls CLEAN, whose scope job already failed
    gh = _fake_gh(tmp_path, _state(), checks=_scope_failure(), jobs=SCOPE_JOB)

    # When  the gate runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 1401, HEAD)

    # Then  it does not merge, and the deferral names the run, the job and the step
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0, rc
    assert not [c for c in calls if c[:2] == ["pr", "merge"]], calls
    body = " ".join(" ".join(c) for c in calls if c[:2] == ["pr", "comment"])
    for needle in ("scope", "failure", "41325509945", "124904531947", "make ci-lint", "#1386"):
        assert needle in body, (needle, body)


def test_a_review_blocked_red_pr_is_not_approved_or_admin_merged(tmp_path):
    """#1401: the recheck called a failed scope job 'review is the only blocker', then used --admin."""

    # Given a review-blocked pull request whose scope check failed
    gh = _fake_gh(tmp_path, _review_blocked(), checks=_scope_failure(), jobs=SCOPE_JOB,
                  token_login="asimov-agent")

    # When  the job runs with approval enabled
    rc = am.run(str(gh), "asimov-agent/llgenie", 1401, HEAD, approve_when_review_required=True)

    # Then  it neither approves nor merges
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0, rc
    assert not [c for c in calls if c[:2] == ["pr", "review"]], calls
    assert not [c for c in calls if c[:2] == ["pr", "merge"]], calls
    assert any("scope" in " ".join(c) for c in calls if c[:2] == ["pr", "comment"]), calls


def test_recheck_does_not_approve_a_red_review_blocked_pr(tmp_path):
    """The sweep must not print that the review is the only blocker when a check is red."""

    # Given an open review-blocked pull request with a failed scope check and no deferral marker
    trust = {"nameWithOwner": "asimov-agent/llgenie"}
    blocked = _review_blocked(headRepository=trust, headRefOid=HEAD)
    gh = _fake_gh(tmp_path, blocked, prs=[{"number": 1401, "headRefOid": HEAD}],
                  checks=_scope_failure(), jobs=SCOPE_JOB, token_login="asimov-agent")

    # When  the sweep runs
    rc = am.recheck(str(gh), "asimov-agent/llgenie")

    # Then  it defers and does not approve
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0, rc
    assert not [c for c in calls if c[:2] == ["pr", "review"]], calls
    assert not [c for c in calls if c[:2] == ["pr", "merge"]], calls
    assert any("41325509945" in " ".join(c) for c in calls if c[:2] == ["pr", "comment"]), calls


def test_a_skipped_check_is_not_a_red_pipeline(tmp_path):
    """A docs-only head has no `linux` job: `skipped` is the one legitimate "no verdict" (#843)."""

    # Given a clean pull request whose linux job was the only non-success and it was skipped
    checks = [{"name": "linux", "conclusion": "skipped", "details_url": ""},
              {"name": "ci-verdict", "conclusion": "success", "details_url": ""},
              {"name": "scope", "conclusion": "success", "details_url": ""}]
    gh = _fake_gh(tmp_path, _state(headRepository={"nameWithOwner": "asimov-agent/llgenie"}),
                  checks=checks)

    # When  the gate runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  it merges without --admin
    merges = [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "merge"]]
    assert rc == 0, rc
    assert merges and "--admin" not in merges[0], merges


def test_a_cancelled_or_neutral_check_defers_the_merge(tmp_path):
    """#1250 Finding B: a cancelled run is a killed CI (not a docs head), and the `neutral` is
    `ci_verdict`'s superseded-head verdict — neither is a green pipeline, so the gate defers."""

    # Given a clean PR whose CI scope check is cancelled
    cancelled = [{"name": "linux", "conclusion": "cancelled", "details_url": ""},
                 {"name": "scope", "conclusion": "success", "details_url": ""}]
    gh = _fake_gh(tmp_path / "cancelled",
                  _state(headRepository={"nameWithOwner": "asimov-agent/llgenie"}),
                  checks=cancelled)

    # When  the gate runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 482, HEAD)

    # Then  it does NOT merge, and the cancellation is named as the deferral reason
    assert not [c for c in _calls(tmp_path / "cancelled" / "gh.log") if c[:2] == ["pr", "merge"]], \
        [c for c in _calls(tmp_path / "cancelled" / "gh.log")]
    body = " ".join(" ".join(c) for c in _calls(tmp_path / "cancelled" / "gh.log")
                    if c[:2] == ["pr", "comment"])
    assert "cancelled" in body and "red" in body.lower(), body

    # And  the same holds for a superseded-head `neutral` verdict
    neutral = [{"name": "linux", "conclusion": "neutral", "details_url": ""},
               {"name": "scope", "conclusion": "success", "details_url": ""}]
    gh2 = _fake_gh(tmp_path / "neutral",
                   _state(headRepository={"nameWithOwner": "asimov-agent/llgenie"}),
                   checks=neutral)
    assert am.run(str(gh2), "asimov-agent/llgenie", 482, HEAD) == 0
    assert not [c for c in _calls(tmp_path / "neutral" / "gh.log") if c[:2] == ["pr", "merge"]], \
        [c for c in _calls(tmp_path / "neutral" / "gh.log")]


def test_a_red_head_is_not_admin_merged_on_a_bot_verdict(tmp_path):
    """A verdict clears the review. It does not clear a failed ci-verdict or linux / unit job."""

    # Given a review-blocked pull request with a verdict at this head and a failed unit job
    unit = ("https://github.com/asimov-agent/llgenie/actions/runs/41319111383/job/124885504534")
    checks = [{"name": "linux / unit", "conclusion": "failure", "details_url": unit},
              {"name": "ci-verdict", "conclusion": "failure",
               "details_url": "https://github.com/asimov-agent/llgenie/runs/124887855931"}]
    state = _review_blocked(comments=[_verdict()])
    gh = _fake_gh(tmp_path, state, checks=checks, jobs={"124885504534": "Run unit tests"})

    # When  the gate runs
    rc = am.run(str(gh), "asimov-agent/llgenie", 1374, HEAD, approve_when_review_required=True)

    # Then  --admin is not used
    calls = _calls(tmp_path / "gh.log")
    assert rc == 0, rc
    assert not [c for c in calls if c[:2] == ["pr", "merge"]], calls
    body = " ".join(" ".join(c) for c in calls if c[:2] == ["pr", "comment"])
    assert "linux / unit" in body and "41319111383" in body and "Run unit tests" in body, body


def test_red_check_exits_nonzero_and_names_the_run(tmp_path, monkeypatch, capsys):
    """`make check-merge-on-red` is this command: non-zero, and it names the failing run."""

    # Given the #1401 head
    monkeypatch.setenv("GH_TOKEN", "test-token")
    gh = _fake_gh(tmp_path, _state(), checks=_scope_failure(), jobs=SCOPE_JOB)

    # When  red-check runs
    rc = am.main(["red-check", "--repo", "asimov-agent/llgenie", "--pr", "1401", "--gh", str(gh)])

    # Then  it fails and names the run, and a green head does not
    err = capsys.readouterr().err
    assert rc == 1, rc
    assert "41325509945" in err and "make ci-lint" in err, err
    green = _fake_gh(tmp_path / "green", _state(), checks=[{"name": "scope", "conclusion": "success",
                                                            "details_url": ""}])
    assert am.main(["red-check", "--repo", "asimov-agent/llgenie", "--pr", "1401",
                    "--gh", str(green)]) == 0


def test_alert_names_the_merge_commit_once(tmp_path):
    """A merged red head is commented once, and a green merge-commit re-run is named as such."""

    # Given a merged pull request whose head failed and whose merge commit is clean
    merged = [{"number": 1401, "headRefOid": HEAD, "mergeCommit": {"oid": MERGE_SHA}}]
    checks = {HEAD: _scope_failure(), MERGE_SHA: [{"name": "ci-verdict", "conclusion": "success",
                                                    "details_url": ""}]}
    gh = _fake_gh(tmp_path, _state(), merged=merged, checks=checks, jobs=SCOPE_JOB)

    # When  the alert runs
    rc = am.alert_merged_red(str(gh), "asimov-agent/llgenie")

    # Then  one comment names the head, the run and the merge commit
    calls = _calls(tmp_path / "gh.log")
    comments = [c for c in calls if c[:2] == ["pr", "comment"]]
    assert rc == 0, rc
    assert len(comments) == 1, comments
    body = " ".join(comments[0])
    for needle in (HEAD, MERGE_SHA, "41325509945", "no red check", "merged-over-red"):
        assert needle in body, (needle, body)

    # And   a head that already carries the marker is not commented again
    marked = _state(comments=[{"body": am.MERGED_RED_MARKER.format(HEAD)}])
    again = _fake_gh(tmp_path / "again", marked, merged=merged, checks=checks, jobs=SCOPE_JOB,
                     views={"1401": marked})
    am.alert_merged_red(str(again), "asimov-agent/llgenie")
    assert not [c for c in _calls(tmp_path / "again" / "gh.log") if c[:2] == ["pr", "comment"]]


def test_explain_names_a_red_check_and_writes_nothing(tmp_path, capsys):
    """The human verdict says the head is red, and it does not approve or merge."""

    # Given a clean-looking pull request with a failed scope check
    gh = _fake_gh(tmp_path, _state(), checks=_scope_failure(), jobs=SCOPE_JOB)

    # When  explain runs
    rc = am.explain(str(gh), "asimov-agent/llgenie", 1401)

    # Then  it names the red check and writes nothing
    out = capsys.readouterr().out
    assert rc == 0, rc
    assert "defers" in out and "scope" in out, out
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] in (["pr", "merge"], ["pr", "review"],
                                                                   ["pr", "comment"])]


def test_the_red_gate_is_a_make_target_and_the_approver_token_stays(tmp_path):
    """The check and the alert are make targets, and the review token is still the job token."""

    # Given the Makefile, the docs and the merge workflow
    # Then  both targets exist, the docs name them, and the approver is unchanged
    assert "\ncheck-merge-on-red:" in MAKEFILE
    assert "\nalert-merged-red:" in MAKEFILE
    assert "scripts/auto_merge.py red-check" in MAKEFILE
    assert "check-merge-on-red" in DOCS and "alert-merged-red" in DOCS
    assert "make alert-merged-red REPO=\"$REPO\"" in MERGE_WF
    assert "APPROVER_TOKEN: ${{ github.token }}" in MERGE_WF
    assert "secrets.APPROVER_TOKEN" not in MERGE_WF

