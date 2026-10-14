"""The issue-refiner's eligible-pick, spare-capacity and review logic (issue #263).

Only the GitHub API is a stand-in: a `gh` on PATH records its argv and answers the queries, so
every assertion is about the EXACT request the product builds. `count`, `pick`, `render`,
`parse_review` and `apply_review` are the real code under test.

The two rules this file exists to protect: the refiner runs on the implementer's spare capacity
(so it never races it for an issue), and it opens NO PR — ever.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import bot_claims as bc  # noqa: E402
import issue_refiner as ir  # noqa: E402

OWNER, NAME = "asimov-agent", "llgenie"


def _fake_gh(tmp_path: Path, opts: dict | None = None):
    """`gh` that records every argv as one JSON line and answers what the refiner asks."""
    opts = opts or {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    refined_today = opts.get("refined_today", [])
    queued = opts.get("queued", {})          # label -> issue numbers waiting for the implementer
    prs_today = opts.get("prs_today", [1, 2, 3])          # the implementer is busy by default
    issues = opts.get("issues", [])
    views = opts.get("views", {})
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
args = sys.argv[1:]
REFINED = {json.dumps(refined_today)}
QUEUED = json.loads({json.dumps(__import__("json").dumps(queued))})
PRS = {json.dumps(prs_today)}
ISSUES = {json.dumps(issues)}
VIEWS = {json.dumps(views)}
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["issue", "list"] and "--label" in args:
    lab = args[args.index("--label") + 1]
    nums = REFINED if lab == "agent:refined" else QUEUED.get(lab, [])
    print(json.dumps([{{"number": n}} for n in nums]))
elif args[:2] == ["issue", "list"]:
    print(json.dumps(ISSUES))
elif args[:2] == ["search", "prs"]:
    print(json.dumps([{{"number": n}} for n in PRS]))
elif args[:2] == ["issue", "view"]:
    print(json.dumps(VIEWS.get(args[2], {{"number": int(args[2]), "title": "t", "body": "b",
                                          "state": "open", "author": {{"login": "a"}},
                                          "labels": [], "comments": [],
                                          "closedByPullRequestsReferences": []}})))
elif args[:2] == ["issue", "comment"]:
    print("Comment created.")
elif args[:2] == ["issue", "edit"]:
    print("Issue updated.")
elif args[:2] == ["pr", "create"]:
    print("https://example.invalid/pull/1")
else:
    print("[]")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


def _issue(num, title="Fix the thing", labels=(), created="2026-10-01T00:00:00Z"):
    return {"number": num, "title": title, "createdAt": created,
            "labels": [{"name": n} for n in labels]}


def test_count_reads_the_labels_it_applies_today(tmp_path):
    """The refiner's budget is its own: issues it labelled agent:refined, updated today."""
    gh, log = _fake_gh(tmp_path, {"refined_today": [4, 5]})
    assert ir.count(str(gh), f"{OWNER}/{NAME}", today="2026-10-14") == 2
    q = _calls(log)[0]
    assert q[:2] == ["issue", "list"] and ir.REFINED_LABEL in q
    assert "--search" in q and "updated:>=2026-10-14" in q


def test_it_yields_while_an_issue_is_waiting_for_the_implementer(tmp_path, capsys):
    """The one race to avoid: an issue queued for the implementer with no PR yet."""
    gh, log = _fake_gh(tmp_path, {"queued": {"agent:implement": [21]}})
    r = ir.pick(str(gh), f"{OWNER}/{NAME}", out_path=tmp_path / "refine-in.md")
    assert r["action"] == "busy" and r["issue"] is None
    assert "yielding to the implementer" in capsys.readouterr().out
    # it asked who is queued, and never went on to build candidates
    assert [c for c in _calls(log) if c[:2] == ["issue", "list"] and "agent:implement" in c]
    assert not [c for c in _calls(log) if c[:2] == ["issue", "list"] and "--label" not in c]


def test_a_labelled_issue_that_already_has_a_pr_does_not_block_the_refiner(tmp_path):
    """Work already started is not waiting for anyone, so hourly runs stay useful."""
    gh, _log = _fake_gh(tmp_path, {
        "queued": {"agent:implement": [21], "agent:ready": [22]},
        "issues": [_issue(30, "oldest clean", created="2026-09-01T00:00:00Z")],
        "views": {"21": {"number": 21, "title": "started", "body": "b", "state": "open",
                         "author": {"login": "a"}, "labels": [], "comments": [],
                         "closedByPullRequestsReferences": [{"number": 90}]},
                  "22": {"number": 22, "title": "started too", "body": "b", "state": "open",
                         "author": {"login": "a"}, "labels": [], "comments": [],
                         "closedByPullRequestsReferences": [{"number": 91}]},
                  "30": {"number": 30, "title": "oldest clean", "body": "b", "state": "open",
                         "author": {"login": "a"}, "labels": [], "comments": [],
                         "closedByPullRequestsReferences": []}},
    })
    r = ir.pick(str(gh), f"{OWNER}/{NAME}", out_path=tmp_path / "refine-in.md")
    assert r["issue"] == 30, r


def test_it_picks_the_oldest_issue_that_is_not_decided_claimed_or_implemented(tmp_path):
    """Eligibility: skip decided, skip labelled-for-implementation, skip one with a bot PR."""
    gh, log = _fake_gh(tmp_path, {
        "refined_today": [],
        "issues": [_issue(10, "already refined", labels=["agent:refined"]),
                   _issue(11, "claimed by the implementer", labels=["agent:implement"], created="2026-09-01T00:00:00Z"),
                   _issue(12, "oldest clean", created="2026-09-02T00:00:00Z"),
                   _issue(13, "has a bot PR", created="2026-09-03T00:00:00Z")],
        "views": {"12": {"number": 12, "title": "oldest clean", "body": "b", "state": "open",
                         "author": {"login": "a"}, "labels": [], "comments": [],
                         "closedByPullRequestsReferences": []},
                  "13": {"number": 13, "title": "has a bot PR", "body": "b", "state": "open",
                         "author": {"login": "a"}, "labels": [], "comments": [],
                         "closedByPullRequestsReferences": [{"number": 99}]}},
    })
    r = ir.pick(str(gh), f"{OWNER}/{NAME}", out_path=tmp_path / "refine.md")
    assert r["issue"] == 12, r


def test_a_pick_writes_the_thread_and_the_review_instruction(tmp_path):
    """The agent reviews the issue AND its comments, and is told never to implement."""
    comments = [{"author": {"login": "andyholst"}, "createdAt": "2026-10-02T09:00:00Z",
                 "body": "we said CPU only here"}]
    gh, _log = _fake_gh(tmp_path, {"refined_today": [], "issues": [_issue(12)],
                                   "views": {"12": {"number": 12, "title": "oldest clean",
                                                    "body": "add --foo", "state": "open",
                                                    "author": {"login": "a"}, "labels": [],
                                                    "comments": comments,
                                                    "closedByPullRequestsReferences": []}}})
    out = tmp_path / "refine.md"
    ir.pick(str(gh), f"{OWNER}/{NAME}", out_path=out)
    text = out.read_text()
    assert "add --foo" in text and "we said CPU only here" in text
    assert "andyholst · 2026-10-02T09:00:00Z" in text
    assert "## Review it, do not implement it" in text
    for v in ("REFINE: refined", "REFINE: already-clear"):
        assert v in text, v


def test_the_review_grammar_and_its_refusal():
    v = ir.parse_review("REFINE: refined\nRESTATED:\n- [ ] --foo on CPU\nREASON: criteria missing\n")
    assert v["verdict"] == "refined" and "--foo on CPU" in v["restated"]
    assert ir.parse_review("REFINE: already-clear\nREASON: explicit already\n")["verdict"] == "already-clear"
    for bad in ("", "looks fine to me", "REFINE: maybe\n"):
        with pytest.raises(SystemExit):
            ir.parse_review(bad)


def test_a_refined_verdict_without_a_restatement_is_refused(tmp_path):
    gh, log = _fake_gh(tmp_path)
    with pytest.raises(SystemExit):
        ir.apply_review(str(gh), f"{OWNER}/{NAME}", 12, "REFINE: refined\nREASON: unclear\n")
    assert _calls(log) == [], "a refused review must not comment or label"


def test_applying_a_review_posts_it_closes_its_claim_labels_and_never_opens_a_pr(tmp_path):
    """The protocol: the review comment carries a `done` marker, which is what releases the claim
    the run opened in `pick` - otherwise the issue stays occupied for every other bot until the
    claim expires. It still never opens a PR."""
    gh, log = _fake_gh(tmp_path, {"refined_today": [], "queued": {}, "prs_today": []})
    ir.apply_review(str(gh), f"{OWNER}/{NAME}", 7,
                    "REFINE: already-clear\nREASON: acceptance criteria are explicit\n", dry=False)
    calls = _calls(log)
    comments = [c for c in calls if c[:2] == ["issue", "comment"]]
    assert len(comments) == 1, f"one comment: the review that closes the claim ({comments})"
    assert "acceptance criteria are explicit" in " ".join(comments[0])
    assert "bot-done: refiner" in " ".join(comments[0]), "the review must release the claim"
    assert any(c[:2] == ["issue", "edit"] and "agent:refined" in c for c in calls)
    assert not any(c[:2] == ["pr", "create"] for c in calls)

def _claim(bot, at, work="refine"):
    return {"body": f"<!-- bot-claim: {bot} {at} {work} -->\ntaking this one"}


def test_a_fresh_claim_by_another_bot_occupies_the_issue():
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    why = bc.occupied([_claim("implementer", "2026-10-14T11:30:00Z", "implement")],
                      bc.REFINER, now)
    assert why and "implementer" in why and "30 min" in why


def test_its_own_claim_does_not_block_it():
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    assert bc.occupied([_claim("refiner", "2026-10-14T11:59:00Z")], bc.REFINER, now) is None


def test_a_stale_claim_locks_nothing_so_a_crashed_run_frees_the_issue():
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    old = (now - bc.CLAIM_TTL - dt.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert bc.occupied([_claim("implementer", old, "implement")], bc.REFINER, now) is None


def test_the_newest_claim_wins_and_junk_is_ignored():
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    why = bc.occupied([{"body": "<!-- bot-claim: nonsense -->"}, {"body": "no marker"},
                       _claim("implementer", "2026-10-14T09:00:00Z", "implement"),
                       _claim("fix-bot", "2026-10-14T11:45:00Z")], bc.REFINER, now)
    assert "fix-bot" in why


def test_the_claim_comment_carries_a_marker_another_bot_can_read():
    at = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    body = bc.claim_comment(bc.REFINER, "refine", at)
    assert bc.claims([{"body": body}]) == [{"bot": "refiner", "at": at, "work": "refine"}]
    assert bc.occupied([{"body": body}], bc.IMPLEMENTER, now=at) is not None, \
        "the implementer sees it while the claim is fresh"


def test_an_issue_claimed_by_the_implementer_is_skipped_not_yielded(tmp_path):
    """End to end through the sweep: #1 is claimed, so the refiner takes #2 - it does not stand
    down for the whole run, which is what makes an hourly cadence safe."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh, log = _fake_gh(tmp_path, {
        "refined_today": [], "queued": {}, "prs_today": [],
        "issues": [{"number": 1, "title": "one", "createdAt": "2026-09-01T00:00:00Z", "labels": []},
                   {"number": 2, "title": "two", "createdAt": "2026-09-02T00:00:00Z", "labels": []}],
        "views": {"1": {"number": 1, "title": "one", "body": "b", "state": "open", "labels": [],
                        "author": {"login": "u"},
                        "comments": [_claim("implementer", now, "implement")],
                        "closedByPullRequestsReferences": []},
                  "2": {"number": 2, "title": "two", "body": "b", "state": "open", "labels": [],
                        "author": {"login": "u"}, "comments": [],
                        "closedByPullRequestsReferences": []}},
    })
    r = ir.pick(str(gh), f"{OWNER}/{NAME}", out_path=tmp_path / "refine-in.md")
    assert r["issue"] == 2, r


def test_refining_claims_the_issue_first(tmp_path):
    """The claim must be posted BEFORE the agent runs, or the other bot sees nothing."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh, log = _fake_gh(tmp_path, {
        "refined_today": [], "queued": {}, "prs_today": [],
        "issues": [{"number": 7, "title": "seven", "createdAt": "2026-09-01T00:00:00Z", "labels": []}],
        "views": {"7": {"number": 7, "title": "seven", "body": "b", "state": "open", "labels": [],
                        "author": {"login": "u"}, "comments": [],
                        "closedByPullRequestsReferences": []}},
    })
    ir.pick(str(gh), f"{OWNER}/{NAME}", out_path=tmp_path / "refine-in.md")
    claims = [c for c in _calls(log) if c[:2] == ["issue", "comment"]]
    assert claims, "no claim comment was posted"
    assert "bot-claim: refiner" in " ".join(claims[0])


def test_a_done_that_means_pr_open_still_occupies_the_issue():
    """`done` says WHICH kind: refined/closed/merged release the issue, but an implemented PR that
    is not approved yet must not be implemented a second time."""
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    at = "2026-10-14T11:30:00Z"
    pending = [{"body": f"<!-- bot-done: implementer {at} pr-open -->\nPR #12 is up for review"}]
    why = bc.occupied(pending, bc.REFINER, now)
    assert why and "not merged" in why, why
    closed = [{"body": f"<!-- bot-done: implementer {at} closed -->\nmerged and closed"}]
    assert bc.occupied(closed, bc.REFINER, now) is None
    refined = [{"body": f"<!-- bot-done: refiner {at} refined -->\nrestated"}]
    assert bc.occupied(refined, bc.IMPLEMENTER, now) is None, "a refined issue frees the implementer"


def test_the_refiner_gates_the_run_on_jev():
    """The rule for every bot: the job does not start when the JEV engine is off. The refiner passed
    no JEV env at all before this, so its agent ran unsupervised."""
    repo = Path(__file__).resolve().parent.parent
    text = (repo / ".github/workflows/issue-refiner.yml").read_text()
    gate = text.index("JEV engine is active")
    review = text.index("Review the issue (Hermes reads refine-in.md")
    assert gate < review, "the gate must run before the agent"
    assert "NERVE_REQUIRE=1" in text, "the gate must be ARMED"
    mk = (repo / "Makefile").read_text()
    recipe = mk[mk.index("issue-refiner:"):mk.index("_issue-refiner:")]
    assert "TYPESAFE_API_KEY" in recipe, "the key must reach the container at run time"
