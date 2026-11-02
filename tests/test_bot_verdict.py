#!/usr/bin/env python3
"""A bot review verdict is a comment MARKER, not a GitHub approval (issue #852).

Every bot pushes with the owner's token, so `gh pr review --approve` on its own PR is refused and
`reviewDecision` can never leave `REVIEW_REQUIRED`. The verdict therefore has to be machine-readable in
a place that DOES accept a bot's write — the PR thread — and must name the head it reviewed so a stale
one can never clear the merge gate.

These cases run the REAL module against a REAL fake `gh` binary (the repo's pattern: the product is
never mocked, only the external API is a stand-in).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import auto_merge as am  # noqa: E402
import bot_verdict as bv  # noqa: E402

HEAD = "1234567890abcdef1234567890abcdef12345678"
OLD = "0" * 40
RUN = "42796343593"
BOTS = (REPO / "docs" / "BOTS.md").read_text()


def _fake_gh(tmp_path: Path, existing: "list[dict] | None" = None):
    """A `gh` that answers `pr view` (with comments) and records `pr comment` in a log.

    A posted comment is APPENDED to the thread the next `pr view` returns, so the producer's
    idempotence is measured against a real second read rather than a static fixture.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    thread = tmp_path / "thread.json"
    thread.write_text(json.dumps(existing or []))
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
THREAD = {str(thread)!r}
if args[:2] == ["pr", "view"]:
    print(json.dumps({{"headRefOid": {HEAD!r}, "comments": json.load(open(THREAD))}})); sys.exit(0)
if args[:2] == ["pr", "comment"]:
    body = args[args.index("--body") + 1]
    comments = json.load(open(THREAD))
    comments.append({{"author": {{"login": "asimov-agent"}}, "body": body}})
    open(THREAD, "w").write(json.dumps(comments))
    print("commented"); sys.exit(0)
print("unexpected: " + " ".join(args)); sys.exit(1)
''')
    gh.chmod(0o755)
    return gh


def _calls(log: Path) -> "list[list[str]]":
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()] if log.exists() else []


def test_the_marker_round_trips():
    """The producer writes exactly what the parser reads — no second format to rot."""
    # Given a verdict
    text = bv.marker(HEAD, RUN, "approve", "asimov-agent")

    # When  it is parsed back
    got = bv.parse(f"some prose\n{text}\nmore prose")

    # Then  every field survives, and the verdict is normalised to lowercase
    assert got == {"head": HEAD, "run": RUN, "verdict": "approve", "reviewer": "asimov-agent"}, got
    assert bv.parse("no marker here") is None


def test_the_round_trip_refuses_a_marker_without_a_run_id():
    """A verdict that names only a sha cannot be audited (#1551): the run slot is REQUIRED.

    `head` alone is not enough — two heads could carry a marker for the same sha and no record of
    what was measured. So a marker with the run slot missing does not parse as a verdict at all.
    """
    # When  a marker in the old shape (no `run=`) is parsed
    got = bv.parse("<!-- bot-verdict: head=1234567890abcdef1234567890abcdef12345678 "
                   "verdict=approve reviewer=asimov-agent -->")
    # Then  it is NOT a verdict — it cannot clear the merge gate
    assert got is None, got


def test_only_a_verdict_at_the_named_head_is_returned():
    """The head IN the marker is the whole staleness rule."""
    # Given a thread with a verdict written for an older commit, then one for the current head
    comments = [
        {"author": {"login": "asimov-agent"}, "body": bv.marker(OLD, RUN, "approve", "asimov-agent")},
        {"author": {"login": "asimov-agent"}, "body": bv.marker(HEAD, RUN, "approve", "asimov-agent")},
    ]

    # When  the verdict for HEAD is read
    got = bv.verdict_for_head(comments, HEAD)

    # Then  it is the current-head one — and an unknown head answers nothing
    assert got and got["head"] == HEAD and got["author"] == "asimov-agent", got
    assert bv.verdict_for_head([comments[0]], HEAD) is None
    assert bv.verdict_for_head(comments, "") is None


def test_the_newest_verdict_at_a_head_wins():
    """A reviewer that changes its mind posts again; the thread order decides."""
    # Given an `approve` followed by a `changes` for the SAME head
    comments = [
        {"author": {"login": "github-actions[bot]"}, "body": bv.marker(HEAD, RUN, "approve", "github-actions[bot]")},
        {"author": {"login": "github-actions[bot]"}, "body": bv.marker(HEAD, RUN, "changes", "github-actions[bot]")},
    ]

    # When  the verdict is read
    got = bv.verdict_for_head(comments, HEAD)

    # Then  the newest one is the verdict
    assert got and got["verdict"] == "changes", got


def test_the_verdict_author_allowlist_cannot_drift_from_the_merge_gate():
    """Two lists of "this repo's identities" would rot apart; they must be the same set."""
    assert set(bv.TRUSTED_VERDICT_AUTHORS) == set(am.ALLOWED_AUTHORS)
    assert set(bv.BOT_LOGINS) == set(am.BOT_LOGINS)


def test_the_marker_is_not_an_approval_and_the_docs_say_so():
    """The rule lives in `docs/BOTS.md`, and the producer never posts a review."""
    # Given the module source and the documentation of record
    source = (REPO / "scripts" / "bot_verdict.py").read_text()

    # When  the write path is read
    # Then  it comments (never `pr review --approve`), and the doc states the rule
    assert '"pr", "comment"' in source, source
    assert '"pr", "review"' not in source
    assert "never an approval" in BOTS
    assert "bot-verdict" in BOTS


def test_post_writes_one_comment_and_is_idempotent(tmp_path):
    """One verdict per (head, verdict): a repeated run is quiet, not a second comment."""
    # Given a PR with no verdict yet
    gh = _fake_gh(tmp_path)
    log = tmp_path / "gh.log"

    # When  the same verdict is posted twice
    rc1 = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, RUN, "approve", "asimov-agent",
                  note="read the diff")
    rc2 = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, RUN, "approve", "asimov-agent",
                  note="read the diff")

    # Then  exactly ONE `pr comment` was made, and the body carries the marker
    comments = [c for c in _calls(log) if c[:2] == ["pr", "comment"]]
    assert (rc1, rc2) == (0, 0)
    assert len(comments) == 1, comments
    body = comments[0][comments[0].index("--body") + 1]
    assert bv.marker(HEAD, RUN, "approve", "asimov-agent") in body, body


def test_post_refuses_a_short_sha(tmp_path):
    """A short sha would let a stale verdict read as current: the producer refuses it."""
    # Given a 7-character sha
    gh = _fake_gh(tmp_path)

    # When  a verdict is posted for it
    rc = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD[:7], RUN, "approve", "asimov-agent")

    # Then  it is refused and nothing is written
    assert rc == 2
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]


def test_post_refuses_an_unknown_verdict(tmp_path):
    """Only an accepting or a blocking verdict exists; anything else is a typo, not a decision."""
    # Given a verdict value the gate would not understand
    gh = _fake_gh(tmp_path)

    # When  it is posted
    rc = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, RUN, "looks-fine", "asimov-agent")

    # Then  it is refused
    assert rc == 2
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]


def test_post_refuses_a_missing_run_id(tmp_path):
    """A verdict that names only a sha cannot be audited (#1551): the producer refuses to post it."""
    # Given a PR with no verdict yet
    gh = _fake_gh(tmp_path)

    # When  a verdict is posted with no run id
    rc = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, "", "approve", "asimov-agent")

    # Then  it is refused, the marker is never written, and nothing is commented
    assert rc == 2
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]


# ---------------------------------------------------------------------------
# the wiring guard (issue #1550): the producer ships, but a future producer must
# never again exist with NO caller. At least one lane behaviour or one workflow
# must run `make bot-verdict VERDICT=... HEAD=... RUN=... REPO=... PR=...`.
# ---------------------------------------------------------------------------
import re as _re

import yaml as _yaml

#: A caller runs the producer with every argument the make target requires. The head is a full 40-hex
#: sha and the run is the id that measured it (#1551), never a placeholder.
_CALLER = _re.compile(
    r"make\s+bot-verdict\s+(?=[^#]*(?:VERDICT|verdict))(?=[^#]*(?:HEAD|head))\s*"
    r"(?=[^#]*(?:RUN|run))(?=[^#]*(?:PR|pr))",
    _re.M)


def _caller_files(root: "Path") -> "list[Path]":
    """The workflow and lane files that invoke `make bot-verdict` (derived, never hand-listed)."""
    return sorted(
        [p for p in (root / ".github" / "workflows").glob("*.yml") if _CALLER.search(p.read_text())]
        + [p for p in (root / "agents").rglob("*.md") if _CALLER.search(p.read_text())]
        + [p for p in (root / "scripts").glob("*.py") if _CALLER.search(p.read_text())])


def _caller_job_lacks_checkout(root: "Path") -> "list[tuple[str, str]]":
    """(workflow, job) for every WORKFLOW caller whose invoking job has no checkout step (#1565).

    The text-probe above proves a file *calls* `make bot-verdict`, but a workflow that runs the make
    in an empty workspace still fails ("No rule to make target 'bot-verdict'") — the call alone does
    not make the producer runnable online. A workflow caller is runnable only when the JOB that
    invokes `make bot-verdict` first checks out the repo (a SHA-pinned `actions/checkout` step).
    Parsed from the workflow's own steps, never an assumed job name.
    """
    bad: "list[tuple[str, str]]" = []
    for p in (root / ".github" / "workflows").glob("*.yml"):
        if not _CALLER.search(p.read_text()):
            continue
        wf = _yaml.safe_load(p.read_text())
        for job_name, job in (wf.get("jobs") or {}).items():
            job_steps = job.get("steps") or []
            if not any("make bot-verdict" in str(s.get("run", "")) for s in job_steps):
                continue            # not the job that invokes the producer
            if not any(str(s.get("uses", "")).startswith("actions/checkout@") for s in job_steps):
                bad.append((p.name, job_name))
    return sorted(bad)


def test_the_producer_has_at_least_one_caller_on_the_real_tree():
    """`make bot-verdict` is not definition-only: a workflow or lane actually runs it (issue #1550).

    #852 shipped the producer, consumer, docs and tests — and no caller. Everyone agreed the verdict
    must reach the merge decision, and nothing ever wrote it. This is the pin: if every caller is
    deleted, this test fails by construction (proved below against a tree without the caller).
    """
    assert _caller_files(REPO), (
        "the bot-verdict producer has no caller anywhere under .github/workflows/, agents/ or "
        "scripts/ - a producer without a caller is a control that does not exist (issue #1550). "
        "Wire one: a lane or workflow must run `make bot-verdict VERDICT=... HEAD=<sha> RUN=<id> "
        "REPO=... PR=<n>` for the review verdict at the exact head judged."
    )


def test_the_wiring_guard_fails_when_the_caller_is_removed(tmp_path):
    """Removing the callers reds the guard: the wiring is pinned, not just the parser (#1550).

    The real-tree test above passes because a caller exists. Deleting every caller (as a future edit
    could) must flip it to RED — this proves the guard reads the callers rather than a fact it was
    told. A tree WITHOUT the caller is a tree `test_the_producer_has_at_least_one_caller` is MISSING;
    running its own assertion against that tree must raise.
    """
    # Given a copy of this repo's workflows with every `make bot-verdict` caller removed
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "agents").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    for p in (REPO / ".github" / "workflows").glob("*.yml"):
        if _CALLER.search(p.read_text()):
            continue                        # remove every caller
        (root / ".github" / "workflows" / p.name).write_text(p.read_text())

    # When  the guard's own assertion runs against that caller-less tree
    raised = False
    try:
        assert _caller_files(root), (
            "the bot-verdict producer has no caller - a producer without a caller is a control "
            "that does not exist (issue #1550)."
        )
    except AssertionError:
        raised = True
    assert raised, "the guard did not fail on a tree with every caller removed"


def test_a_workflow_caller_job_checks_out_before_make_bot_verdict():
    """A workflow caller must check out the repo in the SAME job that runs `make bot-verdict` (#1565).

    The tree-probe above proves a caller *exists*, but review-verdict's `record` job ran make in an
    empty workspace — no checkout — and failed with `No rule to make target 'bot-verdict'` on every
    same-repo review (run 41418832262, PR #1563). A caller whose job does not check out the tree is
    exactly as dead as no caller at all: the marker it was built to write is never written. This pin
    holds the runtime: the WORKFLOW caller's invoking job must carry a checkout step.
    """
    assert not _caller_job_lacks_checkout(REPO), (
        "a workflow caller runs `make bot-verdict` in a job that has no checkout step — `make` runs "
        "in an empty workspace and dies with 'No rule to make target' on every event (issue #1565). "
        "Add a SHA-pinned `actions/checkout` step to that job before the make step."
    )


def test_the_checkout_guard_reds_when_a_workflow_caller_job_lacks_checkout(tmp_path):
    """Removing the checkout from a caller's invoking job reds the guard (#1565).

    The real-tree test passes because review-verdict's `record` job now checks out first. Deleting the
    checkout from that job (leaving the make call intact — a future edit could do exactly this) must
    flip it to RED, so the guard reads the job's steps rather than a fact the test was told alongside.
    """
    # Given a copy of the workflows with every `make bot-verdict` caller's checkout step removed
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    for p in (REPO / ".github" / "workflows").glob("*.yml"):
        if not _CALLER.search(p.read_text()):
            (root / ".github" / "workflows" / p.name).write_text(p.read_text())
            continue
        wf = _yaml.safe_load(p.read_text())
        for job in (wf.get("jobs") or {}).values():
            steps = job.get("steps") or []
            if not any("make bot-verdict" in str(s.get("run", "")) for s in steps):
                continue
            job["steps"] = [
                s for s in steps
                if not str(s.get("uses", "")).startswith("actions/checkout@")
            ]                                       # remove the checkout, keep the make call
        (root / ".github" / "workflows" / p.name).write_text(_yaml.safe_dump(wf, sort_keys=False))

    # When  the guard runs against that checkout-less tree
    bad = _caller_job_lacks_checkout(root)

    # Then  it names the caller whose job lost its checkout
    assert bad, (
        "the checkout guard did not fail on a workflow caller whose invoking job had its checkout "
        "removed — the wiring pin must hold the runtime, not just the call (issue #1565)."
    )



