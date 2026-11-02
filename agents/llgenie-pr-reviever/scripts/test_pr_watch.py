"""Tests for the llgenie PR-watch fingerprint used as this profile's cron `monitor`.

The monitor is the thing that decides whether the agent wakes at all, so its contract is tested
rather than trusted: identical state must render identical bytes (else every tick fires), the
hold guard must fire on an approval that has no `do-not-merge`, and the printed stream and the
hashed stream must be the same code path (a divergence would make `--fingerprint` lie).

Run:  pytest -q scripts/test_pr_watch.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_watch  # noqa: E402


def _pr(**kw) -> dict:
    base = {
        "number": 1,
        "title": "a title",
        "headRefOid": "a" * 40,
        "baseRefName": "main",
        "isDraft": False,
        "reviewDecision": "REVIEW_REQUIRED",
        "mergeStateStatus": "BLOCKED",
        "mergeable": "MERGEABLE",
        "labels": [],
        "statusCheckRollup": [],
    }
    base.update(kw)
    return base


def _review(state="APPROVED", login="andyholst", at="2026-10-28T13:13:40Z") -> dict:
    return {"author": {"login": login}, "state": state, "submittedAt": at}


def test_rendering_is_stable_for_identical_state():
    pr = _pr(statusCheckRollup=[
        {"name": "linux / unit", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "macos / unit", "status": "IN_PROGRESS", "conclusion": ""},
    ])
    first = pr_watch.render(pr, 2, [_review("APPROVED", at="2026-10-28T09:00:00Z")])
    again = pr_watch.render(pr, 2, [_review("APPROVED", at="2026-10-28T09:00:00Z")])
    assert first == again, "the monitor must hash stable bytes or every tick looks changed"


def test_a_held_approval_does_not_warn():
    lines = pr_watch.render(_pr(reviewDecision="APPROVED", labels=[{"name": pr_watch.HOLD}]),
                            0, [_review()])
    assert not any("WARN" in line for line in lines)


def test_an_approval_with_no_hold_warns_and_names_the_approver():
    lines = pr_watch.render(_pr(reviewDecision="APPROVED"), 0, [_review()])
    warn = [line for line in lines if "WARN" in line]
    assert len(warn) == 1
    assert "andyholst" in warn[0] and pr_watch.HOLD in warn[0]


def test_failing_and_pending_checks_are_named_not_just_counted():
    lines = pr_watch.render(_pr(statusCheckRollup=[
        {"name": "linux / unit", "status": "COMPLETED", "conclusion": "FAILURE"},
        {"name": "macos / unit", "status": "IN_PROGRESS", "conclusion": ""},
    ]), 0, [])
    assert any("FAILING: linux / unit" in line for line in lines)
    assert any("PENDING: macos / unit" in line for line in lines)
    assert "fail=1" in lines[0] and "pending=1" in lines[0]


def test_skipped_is_not_a_failure_but_action_required_is():
    lines = pr_watch.render(_pr(statusCheckRollup=[
        {"name": "test-published-${{ matrix.engine }}", "status": "COMPLETED", "conclusion": "SKIPPED"},
        {"name": "macos / install", "status": "COMPLETED", "conclusion": "ACTION_REQUIRED"},
    ]), 0, [])
    assert not any("test-published" in line for line in lines)
    assert any("FAILING: macos / install" in line for line in lines)


def test_a_cancelled_check_is_reported_but_not_counted_as_a_failure():
    """A cancelled run cancels its sibling jobs; that must not read as a red PR on the board."""
    lines = pr_watch.render(_pr(statusCheckRollup=[
        {"name": "linux / unit", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "macos / unit", "status": "COMPLETED", "conclusion": "CANCELLED"},
        {"name": "macos / lint", "status": "COMPLETED", "conclusion": "CANCELLED"},
    ]), 0, [])
    assert "fail=0" in lines[0] and "cancel=2" in lines[0]
    assert any("CANCELLED: macos / unit" in line for line in lines)
    assert not any(line.startswith("    FAILING:") for line in lines)


def _fake_gh(prs, workflows=(("CI", "active"), ("auto-merge", "disabled_manually")),
             reviews=None, comments=0, runs=None):
    """A `gh` stub: `api …/workflows`, `run list`, `pr list`, `pr view … comments,reviews`."""
    reviews = reviews or []

    def _gh(*args):
        if args and args[0] == "api":
            path = args[1] if len(args) > 1 else ""
            if "actions/runs" in path:
                return json.dumps({"workflow_runs": runs or []})
            return json.dumps({"workflows": [{"name": n, "state": s} for n, s in workflows]})
        if args and args[0] == "run":
            return json.dumps(runs or [])
        if "list" in args:
            return json.dumps(prs)
        return json.dumps({"comments": [{"body": "x"}] * comments, "reviews": reviews})

    return _gh


def test_the_line_carries_every_run_id_a_verdict_must_cite(monkeypatch):
    """A verdict cites the run id at the head, and one head carries a run per workflow."""
    # the API shape (`id` / `name`), which `runs_at` normalises to databaseId / workflowName
    runs = [
        {"id": 40721356864, "name": "CI", "status": "queued", "conclusion": None},
        {"id": 40721356874, "name": "scope", "status": "completed", "conclusion": "success"},
        {"id": 40721356865, "name": "docs", "status": "completed", "conclusion": "success"},
    ]
    monkeypatch.setattr(pr_watch, "gh", _fake_gh([], runs=runs))
    assert [r["databaseId"] for r in pr_watch.runs_at("a" * 40)] == [40721356864, 40721356874,
                                                                  40721356865]
    line = pr_watch.render(_pr(), 0, [], pr_watch.runs_at("a" * 40))[0]
    assert "runs=CI:40721356864:queued/-" in line
    assert "|scope:40721356874:completed/success" in line
    assert "|docs:40721356865:completed/success" in line
    # the long ` — subtitle` is cut so one PR still fits on one line
    sub = pr_watch.run_fields([{"databaseId": 1, "workflowName": "scope — which CI jobs select",
                                "status": "completed", "conclusion": "success"}])
    assert sub == "runs=scope:1:completed/success", sub


def test_no_run_at_the_head_says_so_rather_than_lying(monkeypatch):
    monkeypatch.setattr(pr_watch, "gh", _fake_gh([]))
    assert pr_watch.runs_at("a" * 40) == []
    assert "runs=none" in pr_watch.render(_pr(), 0, [], None)[0]
    assert "runs=none" in pr_watch.render(_pr(), 0, [], [])[0]


def test_workflow_states_names_the_disabled_workflows(monkeypatch):
    """The pause is 20 disabled workflows; a resume moves this line, and the NAMES say which.

    A count alone cannot answer "did the ones my work depends on come back", so the slugs are in
    the line. The delta is not: it would depend on the previous run and make every tick differ.
    """
    monkeypatch.setattr(pr_watch, "gh", _fake_gh([]))
    assert pr_watch.workflow_states() == (
        "workflows: active=1 (CI) disabled=1 (auto-merge)")
    # a resume must change the bytes, or the monitor would sleep through it
    monkeypatch.setattr(pr_watch, "gh", _fake_gh([], workflows=(("CI", "active"),
                                                               ("auto-merge", "active"))))
    assert pr_watch.workflow_states() == (
        "workflows: active=2 (CI,auto-merge) disabled=0 ()")


def test_a_failing_unheld_pr_raises_an_action_line():
    """A red PR with no hold can slip green later with nobody having reviewed it (#838)."""
    red = [{"name": "linux / unit", "status": "COMPLETED", "conclusion": "FAILURE"}]
    unheld = pr_watch.render(_pr(statusCheckRollup=red), 0, [])
    held = pr_watch.render(_pr(statusCheckRollup=red, labels=[{"name": pr_watch.HOLD}]), 0, [])
    assert any("ACTION: failing and unheld" in ln for ln in unheld)
    assert not any("ACTION:" in ln for ln in held)
    # a cancellation is not "failing", so it must not raise the action either
    cancelled = pr_watch.render(_pr(statusCheckRollup=[
        {"name": "macos / unit", "status": "COMPLETED", "conclusion": "CANCELLED"}]), 0, [])
    assert not any("ACTION:" in ln for ln in cancelled)


def test_queue_state_names_the_backlog(monkeypatch):
    """A stuck runner queue is what stalls every verdict while the alarm workflow is paused."""
    runs = {"workflow_runs": [
        {"id": 1, "name": "CI", "status": "queued", "conclusion": None,
         "created_at": "2026-10-28T16:10:47Z", "run_started_at": None},
        {"id": 2, "name": "CI", "status": "in_progress", "conclusion": None,
         "created_at": "2026-10-28T15:56:25Z", "run_started_at": "2026-10-28T15:57:00Z"},
        {"id": 3, "name": "docs", "status": "completed", "conclusion": "success",
         "created_at": "2026-10-28T15:00:00Z", "run_started_at": "2026-10-28T15:00:05Z"},
    ]}

    def _gh(*args):
        return json.dumps(runs)

    monkeypatch.setattr(pr_watch, "gh", _gh)
    # one of the two pending runs was accepted but never handed to a runner
    assert pr_watch.queue_state() == (
        "queue: 2 pending, unstarted=1, oldest=2026-10-28T15:56:25Z")

    # a queue of ONE, unstarted, is the "no runner granted" signature — not a backlog
    runs["workflow_runs"] = [r for r in runs["workflow_runs"] if r["id"] == 1]
    assert pr_watch.queue_state() == (
        "queue: 1 pending, unstarted=1, oldest=2026-10-28T16:10:47Z")

    runs["workflow_runs"] = []
    assert pr_watch.queue_state() == "queue: none pending"


def test_zero_checks_is_reported_as_unverified_not_calm():
    """A non-main base gets no workflow, so 0 checks reads like health unless it is called out (#836)."""
    bare = pr_watch.render(_pr(), 0, [], [])
    assert any("UNVERIFIED: 0 checks and no run" in ln for ln in bare)
    # a PR with real checks must NOT carry the marker
    busy = pr_watch.render(_pr(statusCheckRollup=[
        {"name": "linux / unit", "status": "COMPLETED", "conclusion": "SUCCESS"}]), 0, [], [])
    assert not any("UNVERIFIED" in ln for ln in busy)


def test_the_printed_and_hashed_stream_are_the_same_code_path(monkeypatch, capsys):
    pr = _pr(reviewDecision="APPROVED")
    fake = _fake_gh([pr], reviews=[_review("APPROVED", at="2026-10-28T13:13:40Z")], comments=1)
    monkeypatch.setattr(pr_watch, "gh", fake)
    assert pr_watch.main([]) == 0
    printed = capsys.readouterr().out

    monkeypatch.setattr(pr_watch, "gh", fake)
    assert pr_watch.main(["--fingerprint"]) == 0
    digest = capsys.readouterr().out.strip()

    import hashlib
    assert digest == hashlib.sha256(printed.encode()).hexdigest()


def test_no_open_prs_is_one_line_after_the_workflow_line(monkeypatch, capsys):
    monkeypatch.setattr(pr_watch, "gh", _fake_gh([]))
    assert pr_watch.main([]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith("workflows: active="), lines
    # The baseline comes before the queue: a PR's red is only meaningful against main (#892).
    assert lines[1].startswith("main: "), lines
    assert lines[2].startswith("queue: "), lines
    assert lines[3] == f"{pr_watch.REPO}: no open PRs"
    assert len(lines) == 4


def test_selftest_passes():
    assert pr_watch.selftest() == 0


def test_a_cancelled_ci_run_at_the_head_says_no_verdict(monkeypatch):
    """21 of 31 PRs sat with a cancelled latest run: the line must say 'no verdict', not look calm."""
    runs = [{"workflowName": "CI — full matrix", "databaseId": 40734476022,
             "status": "completed", "conclusion": "cancelled"}]
    lines = pr_watch.render(_pr(statusCheckRollup=[]), 0, [], runs=runs)
    assert any("NO VERDICT:" in ln for ln in lines), lines
    assert not any("ACTION:" in ln for ln in lines), "a cancellation is not a red to act on"


def test_a_successful_or_running_ci_run_does_not_claim_no_verdict():
    ok = [{"workflowName": "CI", "databaseId": 1, "status": "completed", "conclusion": "success"}]
    running = [{"workflowName": "CI", "databaseId": 2, "status": "in_progress", "conclusion": None}]
    for runs in (ok, running, None):
        lines = pr_watch.render(_pr(statusCheckRollup=[]), 0, [], runs=runs)
        assert not any("NO VERDICT:" in ln for ln in lines), (runs, lines)


def test_main_state_names_a_red_main_and_its_failing_jobs(monkeypatch):
    """A PR's red means nothing without the baseline: name main's sha, conclusion and failing jobs."""
    calls = {"n": 0}

    def fake_gh(*args):
        calls["n"] += 1
        if calls["n"] == 1:
            return "0ddfda8b168430051ed7fd8467d8134f4370ae2f\n"
        if calls["n"] == 2:
            return "40747172915 completed/failure\n"
        return "linux / unit,linux / install\n"

    monkeypatch.setattr(pr_watch, "gh", fake_gh)
    line = pr_watch.main_state()
    assert line.startswith("main: 0ddfda8b")
    assert "completed/failure" in line
    assert "FAILED:linux / unit,linux / install" in line


def test_a_cancelled_main_run_says_no_verdict(monkeypatch):
    seq = iter(["fba8c872" + "0" * 32 + "\n", "40746943024 completed/cancelled\n"])
    monkeypatch.setattr(pr_watch, "gh", lambda *a: next(seq))
    line = pr_watch.main_state()
    assert "cancelled" in line and "no verdict" in line


def test_a_null_run_id_does_not_request_jobs(monkeypatch):
    """An empty workflow row must not become actions/runs/null/jobs (issue #1037)."""
    assert pr_watch.usable_run_id("null") is False
    assert pr_watch.usable_run_id("") is False
    assert pr_watch.usable_run_id("123") is True
    calls: list[tuple[str, ...]] = []

    def fake_gh(*args):
        calls.append(tuple(args))
        if len(calls) == 1:
            return "ac09527cf1a8199393955fc6e47cac99453b01a1\n"
        return "null null/-\n"

    monkeypatch.setattr(pr_watch, "gh", fake_gh)
    line = pr_watch.main_state()
    assert line == "main: ac09527c no CI run", line
    assert all("actions/runs/null/jobs" not in " ".join(call) for call in calls)
    assert len(calls) == 2


def _fake_git(wiki: int, notes: int, preflight: bool):
    """`git` stand-in: `ls-tree` answers with N .md paths, `cat-file -e` only for the preflight note."""
    def fake(*args, cwd=None):
        if args[0] == "ls-tree":
            path = args[-1]
            n = wiki if path == "agent-wiki" else notes
            return "".join(f"{path}/{i}.md\n" for i in range(n))
        if args[0] == "cat-file":
            ok = preflight and "2026-10-28-bot-preflight.md" in args[-1]
            if not ok:
                raise RuntimeError("cat-file: not found")
            return ""
        if args[0] == "merge-base":
            return "5a367d42" + "0" * 32 + "\n"
        raise AssertionError(args)
    return fake


def test_changes_index_state_names_a_missing_dir_base(monkeypatch):
    """A branch with no docs/changes.d at all is a pre-directory base, not an author's mistake."""
    monkeypatch.setattr(pr_watch, "git", _fake_git(wiki=220, notes=0, preflight=False))
    line = pr_watch.changes_index_state(["deadbeef"])[0]
    assert "wiki=220 notes=0" in line and "preflight=no" in line
    assert "MISSING-DIR" in line and "do not hand-add" in line
    assert "base=5a367d42" in line


def test_changes_index_state_counts_a_short_pair(monkeypatch):
    """The 221-vs-222 shape: the wiki file exists, its note does not."""
    monkeypatch.setattr(pr_watch, "git", _fake_git(wiki=222, notes=221, preflight=False))
    line = pr_watch.changes_index_state(["ca85c385"])[0]
    assert "wiki=222 notes=221" in line and "SHORT by 1 note(s)" in line


def test_changes_index_state_calls_an_indexed_head_indexed(monkeypatch):
    monkeypatch.setattr(pr_watch, "git", _fake_git(wiki=223, notes=223, preflight=True))
    line = pr_watch.changes_index_state(["origin/main"])[0]
    assert "preflight=yes" in line and line.endswith("verdict=indexed")


def test_changes_index_state_is_stable_for_identical_refs(monkeypatch):
    """The monitor hashes bytes: the same ref must render the same line twice."""
    monkeypatch.setattr(pr_watch, "git", _fake_git(wiki=220, notes=0, preflight=False))
    first = pr_watch.changes_index_state(["abc12345"])
    second = pr_watch.changes_index_state(["abc12345"])
    assert first == second


def _fake_soul_git(bodies: dict[str, str]):
    """`git` stand-in for the rule census: `ls-tree` lists lanes, `show` returns each SOUL body."""
    def fake(*args, cwd=None):
        if args[0] == "ls-tree":
            return "".join(f"agents/{lane}/SOUL.md\n" for lane in bodies)
        if args[0] == "show":
            lane = args[1].split("/")[1]
            return bodies[lane]
        raise AssertionError(args)
    return fake


ALL_THREE = ("- never hold a PR without a remedy\n"
             "- announce the work where the work lives\n"
             "- start from a fresh upstream main\n")


def test_soul_rules_state_flags_absent_rules(monkeypatch):
    """fea316d8: six of eight lanes carried 0/0/0 — absence is its own verdict, not 'not measured'."""
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({
        "good": ALL_THREE,
        "empty": "nothing here\n",
    }))
    lines = pr_watch.soul_rules_state("fea316d8")
    by_lane = {ln.split()[1]: ln for ln in lines}
    assert "verdict=ok" in by_lane["good"]
    assert "r13=0 r14=0 r15=0" in by_lane["empty"]
    assert "verdict=ABSENT r13,r14,r15" in by_lane["empty"]


def test_soul_rules_state_flags_a_duplicated_rule(monkeypatch):
    """4fb3bf3a: a rule stated twice has two texts that can drift (#922)."""
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({
        "dup": ALL_THREE + "- announce the work where the work lives (again)\n",
    }))
    line = pr_watch.soul_rules_state("4fb3bf3a")[0]
    assert "r14=2" in line and "verdict=DUPLICATED r14" in line


def test_soul_rules_state_catches_the_gate_blind_spot(monkeypatch):
    """A duplication the repo gate cannot see: both copies state `never merge`, so check_agent_profiles
    greps the manifest strings and passes while a rule is stated twice — the #919@5baca03a shape."""
    dup = ("- **Never hold a PR without a remedy.** `do-not-merge` means never this lane would rather not\n"
           "- **Never hold a PR without a remedy** `do-not-merge` means never this lane would rather not\n"
           "- **You never merge, and you never approve.**\n")
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({"doc": dup}))
    line = pr_watch.soul_rules_state("5baca03a")[0]
    assert "r13=2" in line and "verdict=DUPLICATED r13" in line
    # the repo gate greps `never merge` and passes; the census counts statements and reds — the blind spot
    assert "verdict=ok" not in line and "ABSENT" not in line





def test_soul_rules_state_says_when_there_is_no_tree(monkeypatch):
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({}))
    assert pr_watch.soul_rules_state("origin/main") == ["origin/main: no agents/*/SOUL.md"]


def test_soul_shrink_state_flags_a_live_longer_file(monkeypatch, tmp_path):
    """4fb3bf3a: five live-longer findings — the sync would delete live instruction (issue #791)."""
    body = "x" * 50
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({"lane": body}))
    live = tmp_path / "lane" / "SOUL.md"
    live.parent.mkdir(parents=True)
    live.write_text("y" * 80)
    line = pr_watch.soul_shrink_state("4fb3bf3a", profile_root=str(tmp_path))[0]
    assert "tree=50 live=80" in line and "verdict=LIVE-LONGER" in line


def test_soul_shrink_state_distinguishes_absent_from_shorter(monkeypatch, tmp_path):
    """`live=absent` is not `live=0`: one is a missing profile, the other a real shrink."""
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({"lane": "x" * 10}))
    line = pr_watch.soul_shrink_state("deadbeef", profile_root=str(tmp_path))[0]
    assert "live=absent" in line and "verdict=LIVE-MISSING" in line


def test_soul_shrink_state_is_ok_when_the_tree_is_not_shorter(monkeypatch, tmp_path):
    body = "x" * 40
    monkeypatch.setattr(pr_watch, "git", _fake_soul_git({"lane": body}))
    live = tmp_path / "lane" / "SOUL.md"
    live.parent.mkdir(parents=True)
    live.write_text(body)
    line = pr_watch.soul_shrink_state("abc", profile_root=str(tmp_path))[0]
    assert "tree=40 live=40" in line and "verdict=ok" in line
