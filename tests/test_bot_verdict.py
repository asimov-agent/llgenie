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
    text = bv.marker(HEAD, "approve", "asimov-agent")

    # When  it is parsed back
    got = bv.parse(f"some prose\n{text}\nmore prose")

    # Then  every field survives, and the verdict is normalised to lowercase
    assert got == {"head": HEAD, "verdict": "approve", "reviewer": "asimov-agent"}, got
    assert bv.parse("no marker here") is None


def test_only_a_verdict_at_the_named_head_is_returned():
    """The head IN the marker is the whole staleness rule."""
    # Given a thread with a verdict written for an older commit, then one for the current head
    comments = [
        {"author": {"login": "asimov-agent"}, "body": bv.marker(OLD, "approve", "asimov-agent")},
        {"author": {"login": "asimov-agent"}, "body": bv.marker(HEAD, "approve", "asimov-agent")},
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
        {"author": {"login": "github-actions[bot]"}, "body": bv.marker(HEAD, "approve", "github-actions[bot]")},
        {"author": {"login": "github-actions[bot]"}, "body": bv.marker(HEAD, "changes", "github-actions[bot]")},
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
    rc1 = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, "approve", "asimov-agent",
                  note="read the diff")
    rc2 = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, "approve", "asimov-agent",
                  note="read the diff")

    # Then  exactly ONE `pr comment` was made, and the body carries the marker
    comments = [c for c in _calls(log) if c[:2] == ["pr", "comment"]]
    assert (rc1, rc2) == (0, 0)
    assert len(comments) == 1, comments
    body = comments[0][comments[0].index("--body") + 1]
    assert bv.marker(HEAD, "approve", "asimov-agent") in body, body


def test_post_refuses_a_short_sha(tmp_path):
    """A short sha would let a stale verdict read as current: the producer refuses it."""
    # Given a 7-character sha
    gh = _fake_gh(tmp_path)

    # When  a verdict is posted for it
    rc = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD[:7], "approve", "asimov-agent")

    # Then  it is refused and nothing is written
    assert rc == 2
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]


def test_post_refuses_an_unknown_verdict(tmp_path):
    """Only an accepting or a blocking verdict exists; anything else is a typo, not a decision."""
    # Given a verdict value the gate would not understand
    gh = _fake_gh(tmp_path)

    # When  it is posted
    rc = bv.post(str(gh), "asimov-agent/llgenie", 852, HEAD, "looks-fine", "asimov-agent")

    # Then  it is refused
    assert rc == 2
    assert not [c for c in _calls(tmp_path / "gh.log") if c[:2] == ["pr", "comment"]]
