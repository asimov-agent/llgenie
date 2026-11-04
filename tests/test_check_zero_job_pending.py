"""The zero-job-pending detector: a dispatched run that never instantiates a job must be loud (issue #1410).

`queued_run_alarm` scans JOB ROWS; a run with `jobs.total_count == 0` is invisible to it and renders
"no job has been queued longer than 30 minutes" while the run stays `pending` forever. This detector
is the run-level complement. `gh` is stubbed on PATH so the decision logic runs for real against a
scripted answer surface.

THE DISCRIMINATOR (issue #1704): `total_count == 0` alone is not a "no runner matched" claim.
`engine-build` serialises per `engine × arch` concurrency group (#917), so a dispatch queued behind an
in_progress sibling holding the same group reads `queued`, zero jobs, past the threshold — it is
QUEUEING, not stranded, and six consecutive filings (#1473/#1536/#1569/#1699/#1700/#1701) mis-named
that shape. A run is stranded only when its group is FREE (no same-workflow in_progress sibling) and
the zero jobs persist. The stranded case is filed once, deduped, and its head is forced RED via the
`ci-verdict` check-run path (issue #1704).

Measured case pinned below: run 41321206783 (engine-build dispatch, head f41685f3) was
`pending`/`queued` with `jobs.total_count == 0`, its group EMPTY, and no gate named it (#1410).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

from pathlib import Path

import scripts.check_zero_job_pending as czp  # via tests/conftest.py, the one import root (issue #796)


def _iso(minutes_ago: float) -> str:
    now = datetime.now(timezone.utc)
    t = now.timestamp() - minutes_ago * 60.0
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh_stub(tmp_path: Path, runs: list[dict], jobs_total: dict[int, int],
             open_issues: list[dict] | None = None, monkeypatch=None, *,
             issue_search_ids: list[int] | None = None) -> Path:
    """A `gh` answering run list (queued+in_progress), run view (jobs), issue list, issue create, api.

    `runs` are the runs that `gh run list --status <s>` answers per their `status`. `jobs_total`
    maps run id -> `jobs.total_count`. `open_issues` drives `issue list` (the dedupe probe);
    `issue_search_ids` is a subset accepted by `--search '<id> in:body'`.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    scenario = tmp_path / "sc.json"
    scenario.write_text(json.dumps({"runs": runs, "jobs_total": jobs_total,
                                    "issues": open_issues or [],
                                    "issue_search": issue_search_ids or []}))
    gh = bindir / "gh"
    calls_log = tmp_path / "calls.log"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
with open("{calls_log}", "a") as _log:
    _log.write(" ".join(a[:3]) + "\\n")
if a[:2] == ["run", "list"]:
    status = a[a.index("--status") + 1]
    runs = [r for r in sc["runs"] if r.get("status") == status]
    print(json.dumps(runs)); sys.exit(0)
if a[:2] == ["run", "view"]:
    rid = a[2]
    total = sc["jobs_total"].get(rid, 0)
    print(json.dumps({{"total_count": total}})); sys.exit(0)
if a[:2] == ["issue", "list"]:
    out = sc["issues"]
    if "in:body" in a:
        needle = str(a[a.index("--search") + 2])
        out = [i for i in out if needle in i.get("body", "")]
    print(json.dumps(out)); sys.exit(0)
if a[:2] == ["issue", "create"]:
    print("https://github.com/x/issues/999"); sys.exit(0)
if a[0] == "api" and any("check-runs" in x for x in a):
    print(json.dumps({{"id": 424242}})); sys.exit(0)
print("unhandled: " + " ".join(a), file=sys.stderr); sys.exit(9)
""")
    gh.chmod(0o755)
    if monkeypatch is not None:
        monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")
    return gh


def _run(rid: int, status: str, minutes_ago: float = 60.0, *, workflow: str | None = None,
         full: bool = True) -> dict:
    d = {"databaseId": rid,
         "workflowName": workflow or "engine-build — builds and verifies EVERY engine",
         "headBranch": "main",
         "headSha": ("f41685f3bd53f4811f8e7d1e6cc01d096a787e54" if full
                     else "f41685f3bd53f4811f8e7d1e6cc01d096a787e5f"),
         "createdAt": _iso(minutes_ago), "url": f"http://x/{rid}", "status": status}
    return d


def test_stranded_zero_job_run_is_flagged(tmp_path, monkeypatch, capsys):
    """The measured #1410 case: one engine-build dispatch pending 60 min, total_count==0, group FREE."""
    _gh_stub(tmp_path, [_run(41321206783, "queued", 60.0)], {41321206783: 0}, monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "41321206783" in out, out
    assert "[STRANDED]" in out, out
    assert "[STRANDED]" in out, out
    assert "engine-build" in out, out


def test_zero_job_run_queued_behind_held_group_is_not_filed(tmp_path, monkeypatch, capsys):
    """Issue #1704: a zero-job run queued behind an in_progress sibling holding the group is benign.

    Six consecutive filings (#1473/#1536/#1569/#1699/#1700/#1701) mis-named this shape "no runner
    matched labels". The group is HELD, so the run is queueing: never filed, never forced RED.
    """
    holder = _run(41763200000, "in_progress", 40.0)
    queued = _run(41763202522, "queued", 60.0)
    _gh_stub(tmp_path, [holder, queued], {41763200000: 29, 41763202522: 0}, monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert rc == 0, out          # a queued-behind zero-job run is NOT a stranded fault
    assert "[QUEUED-BEHIND]" in out, out
    assert "41763202522" in out, out


def test_zero_job_run_under_threshold_is_clean(tmp_path, monkeypatch):
    """A zero-job run younger than the threshold is not yet a stall."""
    _gh_stub(tmp_path, [_run(111, "in_progress", 5.0)], {111: 0}, monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    assert rc == 0


def test_a_run_with_jobs_is_not_flagged(tmp_path, monkeypatch, capsys):
    """A queued run that DID instantiate jobs (the queued_run_alarm domain) is not this detector's."""
    _gh_stub(tmp_path, [_run(999, "queued", 60.0)], {999: 5}, monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    assert rc == 0, capsys.readouterr().out


def test_stranded_run_is_filed_once_deduped_and_forced_red(tmp_path, monkeypatch, capsys):
    """Prove-the-guard, stranded arm: ONE issue filed for the stranded run AND its head forced RED.

    The stranded arm of issue #1704: a zero-job run whose concurrency group is FREE is a real fault —
    filed once, deduped (marker in body), and its head is pushed to a `ci-verdict` FAILURE check-run
    so it is RED instead of an eternal pending. THE call counts are the guard: exactly one `issue
    create` and exactly one `check-runs` POST for the single stranded run."""
    gh = _gh_stub(tmp_path, [_run(41321206783, "queued", 60.0)], {41321206783: 0},
                  monkeypatch=monkeypatch)
    calls_log = tmp_path / "calls.log"
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "filed 1 deduped issue(s)" in out, out
    events = calls_log.read_text().splitlines()
    issue_creates = [e for e in events if e.startswith("issue create")]
    red_posts = [e for e in events if "api repos" in e and "check-runs" in e]
    assert len(issue_creates) == 1, f"expected exactly one issue create, got: {events}"
    assert len(red_posts) == 1, f"expected exactly one check-run POST, got: {events}"


def test_queued_behind_run_with_file_is_never_filed_or_forced_red(tmp_path, monkeypatch, capsys):
    """Prove-the-guard, benign arm: a queued-behind run, even with --file, files NOTHING.

    The benign arm of issue #1704: a zero-job run whose concurrency group is HELD by an in_progress
    sibling is queueing, not stranded — `--file` must neither create an issue nor post a RED check-run
    (six consecutive false filings #1473/#1536/#1569/#1699/#1700/#1701 mis-named this shape)."""
    holder = _run(41763200000, "in_progress", 40.0)
    queued = _run(41763202522, "queued", 60.0)
    _gh_stub(tmp_path, [holder, queued], {41763200000: 29, 41763202522: 0}, monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out          # benign — not a stranded fault, nothing to deliver
    assert "[zero-job-pending] filed" not in out, out     # no delivery print on the benign arm
    assert "forced 1 stranded" not in out, out
    assert "[QUEUED-BEHIND]" in out, out


def test_file_skips_a_run_already_flagged(tmp_path, monkeypatch, capsys):
    """--file skips a stranded run whose open issue already carries the marker (idempotent)."""
    _gh_stub(tmp_path, [_run(41321206783, "queued", 60.0)], {41321206783: 0},
             open_issues=[{"body": f"something <!-- zero-job-pending: run 41321206783 -->"}],
             issue_search_ids=[41321206783], monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file"])
    out = capsys.readouterr().out
    # The run is already filed -> skipped (still rc 1: a stranded run is reported; no double-file)
    assert rc == 1, out


def test_a_github_read_failure_is_exit_2(tmp_path, monkeypatch):
    """An unreadable answer is UNKNOWN, never clean (mirror the queued-runs doctrine)."""
    gh = _gh_stub(tmp_path, [], {}, monkeypatch=monkeypatch)
    gh.write_text("#!/usr/bin/env python3\nimport sys\nprint('boom', file=sys.stderr); sys.exit(1)\n")
    rc = czp.main(["--repo", "asimov-agent/llgenie"])
    assert rc == 2


def test_both_statuses_are_scanned(tmp_path, monkeypatch, capsys):
    """A zero-job run reports `queued`, not `in_progress` — scan BOTH (the queued-alarm lesson)."""
    _gh_stub(tmp_path,
             [_run(1, "queued", 60.0, workflow="wf-a"), _run(2, "in_progress", 60.0, workflow="wf-b")],
             {1: 0, 2: 0}, monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert rc == 1, out            # both are stranded (different workflows -> neither holds the other)
    assert "run 1" in out and "run 2" in out, out
