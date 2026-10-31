"""Issue #902 — the 2026-10-28 bot pause is recorded as data, gated, and has a restore measure.

Every rule is exercised through the REAL modules (scripts/all_pipelines.py, scripts/bots_restore_health.py,
bots/pause.toml), with the GitHub API standing in as a local stub `gh` binary — the allowed external
stand-in, exactly like all_pipelines' `ALL_PIPELINES_GH` and ci_requeue's `CI_REQUEUE_GH` — never a
mock of the product logic.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip. `bots/pause.toml` MUST exist
and MUST contain the never_pause + restore keys; a guard that reads a hand-kept list instead would
rot the moment the tree changed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import tomllib
from scripts import all_pipelines as ap
from scripts import bots_restore_health as brh

REPO = Path(__file__).resolve().parent.parent
TOML = (REPO / "bots" / "pause.toml")


def _load_toml() -> dict:
    return tomllib.loads(TOML.read_text())


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    for name, text in files.items():
        (root / ".github" / "workflows" / name).write_text(text)
    return root


DISPATCHABLE = "name: a-bot — does one thing\non:\n  workflow_dispatch:\n\njobs:\n  go:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"


# ---- the record is present, complete, and derived ----------------------------------------------

def test_the_pause_record_exists_and_names_a_decision():
    """`bots/pause.toml` is the source of truth: it names the paused set, the reason, the order."""
    cfg = _load_toml()
    assert len(cfg["paused"]) >= 14, cfg["paused"]          # the pause was real and broad
    assert set(cfg["paused"]) >= {"fix-bot", "issue-bot", "security-bot", "registry-sync"}
    assert "auto-merge.yml" in cfg["never_pause"], "the merge path must be in the never-pause set"
    assert set(cfg["never_pause"]) >= {"ci.yml", "pipeline.yml", "published.yml"}
    assert "runner_starvation" in cfg["pause_reason"], "the reason is recorded, not guessed"
    assert brh.restore_order(), "the restore order must not be empty"


def test_never_pause_is_derived_not_hand_kept():
    """The sweep reads `_NEVER_PAUSE` from the same toml, so a new merge-path workflow is protected
    the moment it is recorded in the data — the roster-defect fix of issue #301."""
    assert frozenset(_load_toml()["never_pause"]) == ap._NEVER_PAUSE


# ---- the never-pause half of the #874 guard ----------------------------------------------------

def test_a_never_pause_workflow_disabled_manually_is_a_hard_failure(tmp_path):
    """`auto-merge.yml` in `disabled_manually` is FORBIDDEN, not a benign DISABLED: the sweep must
    fail loudly and say so, because a green PR has no path to a merged one (#874, #902)."""
    root = _tree(tmp_path, {"all-pipelines.yml": DISPATCHABLE, "auto-merge.yml": DISPATCHABLE})
    states = {"auto-merge.yml": {"state": "disabled_manually", "active": False}}

    rows = ap.classify(root, states)
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file["auto-merge.yml"] == "forbidden_disabled", by_file

    report, code = ap.render_report(rows, {}, "abc123")
    assert "FORBIDDEN DISABLED" in report
    assert "`auto-merge.yml`" in report
    assert code == 1, "a never-pause workflow disabled must fail the sweep"


def test_an_ordinary_paused_bot_is_still_a_benign_disabled(tmp_path):
    """The guard does NOT overreach: a bot in the allowed paused set (fix-bot) staying paused is
    DISABLED (owner re-enable), excluded from ok/failed, and does not itself fail the sweep."""
    root = _tree(tmp_path, {"all-pipelines.yml": DISPATCHABLE, "fix-bot.yml": DISPATCHABLE})
    states = {"fix-bot.yml": {"state": "disabled_manually", "active": False}}
    rows = ap.classify(root, states)
    by_file = {r["file"]: r["role"] for r in rows}
    assert by_file["fix-bot.yml"] == "disabled", by_file
    report, code = ap.render_report(rows, {}, "abc123")
    assert "DISABLED (owner re-enable required)" in report
    assert "FORBIDDEN DISABLED" not in report
    assert code == 0


def test_the_delete_half_still_exists_in_the_tree_guard():
    """Deleting auto-merge.yml entirely is already refused by the #874 tree half
    (`tests/test_bot_pipeline_isolation.py`); the API-state half here is additive, not a replacement.
    The tree file must still be present for that guard to apply at all."""
    assert list(REPO.joinpath(".github/workflows").glob("auto-merge.yml")), "auto-merge.yml deleted"


# ---- the restore measurement -------------------------------------------------------------------

def _stub_gh(tmp_path: Path, runs: list[dict]) -> Path:
    gh = tmp_path / "gh"
    runs_json = json.dumps(runs)
    body = (
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"RUNS = {runs_json}\n"
        "args = sys.argv[1:]\n"
        "if args[0] == 'api' and args[1].endswith('/actions/runs'):\n"
        "    for r in RUNS:\n"
        "        sys.stdout.write(json.dumps({'workflow': r['workflow'], 'id': str(r['id']),\n"
        "                                     'status': r.get('status', 'completed'),\n"
        "                                     'created_at': r.get('created_at')}))\n"
        "        sys.stdout.write('\\x0a')\n"
        "    sys.exit(0)\n"
        "sys.exit(9)\n"
    )
    gh.write_text(body)
    gh.chmod(0o755)
    return gh


def test_restore_order_comes_from_the_record():
    first, after = _load_toml()["restore_first"], _load_toml()["restore_after"]
    assert brh.restore_order() == list(first) + list(after)
    # the cheap common bots wake early; the heaviest last
    assert brh.restore_order().index("fix-bot") < brh.restore_order().index("security-scan")


def test_a_stuck_queued_run_makes_a_reading_unhealthy(tmp_path):
    run = {"workflow": "CI", "id": 1, "status": "queued",
           "created_at": "2026-10-31T08:00:00+00:00"}
    gh = _stub_gh(tmp_path, [run])
    healthy, problems = brh.sample_queue("a/b", str(gh), in_progress_within_minutes=10,
                                         now="2026-10-31T10:00:00+00:00")
    assert healthy is False
    assert problems, "a stuck queued run must be named"


def test_an_in_progress_run_is_not_a_problem(tmp_path):
    # A run that reached `in_progress` (status != queued) is the queue working, not stuck — even if
    # old, it was picked up.
    run = {"workflow": "CI", "id": 1, "status": "in_progress",
           "created_at": "2026-10-31T08:00:00+00:00"}
    gh = _stub_gh(tmp_path, [run])
    healthy, problems = brh.sample_queue("a/b", str(gh), in_progress_within_minutes=10,
                                         now="2026-10-31T10:00:00+00:00")
    assert healthy is True
    assert problems == []


def test_a_recent_queued_run_is_not_yet_a_problem(tmp_path):
    # Within `in_progress_within_minutes` of creation, a queued run is not stuck yet.
    run = {"workflow": "CI", "id": 1, "status": "queued",
           "created_at": "2026-10-31T09:55:00+00:00"}
    gh = _stub_gh(tmp_path, [run])
    healthy, problems = brh.sample_queue("a/b", str(gh), in_progress_within_minutes=10,
                                         now="2026-10-31T10:00:00+00:00")
    assert healthy is True
    assert problems == []
