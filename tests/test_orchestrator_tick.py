#!/usr/bin/env python3
"""The orchestrator tick's producer keeps a lost delivery (issue #1125).

The tick dispatched work that had merged hours earlier (#919, #1049/#1050, #885), and every receiving
lane spent a turn proving it stale. The mechanism is an order of operations: the producer advanced its
durable state before the side effect that consumes its output, so when delivery failed (`queue_full`
is measured on that job) the delta existed nowhere and the next pass re-sent a task list from memory.

These tests drive the REAL script (a `gh` stub on PATH is the repository's allowance for an external
CLI — the production code that builds every request still runs) and assert the four properties:

  * a delivery that was lost is re-emitted from the outbox, byte-identical, with the ORIGINAL
    measurement time;
  * the outbox is durable when the state write fails, so the ordering is proven rather than declared;
  * a subject whose PR merged or whose issue closed is not emitted at emit time;
  * a second pass over unchanged state emits nothing and leaves the outbox byte-identical — the
    delta key is the fact, never the run time.

Each test carries `# Given / # When / # Then` markers so it can be read against
`openspec/changes/orchestrator-tick-outbox/specs/orchestrator-tick/spec.md` scenario by scenario.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "orchestrator_tick.py"
REPO_SLUG = "asimov-agent/llgenie"

from scripts import orchestrator_tick as tick  # noqa: E402  (the real module, not a copy)

#: A `gh` that answers the four reads this producer makes, out of the fixture file `$TICK_FIXTURE`.
#: `$TICK_FAIL=1` makes every call fail, which is how the loud-read test drives the real error path.
GH_STUB = '''#!__PYTHON__
import json, os, sys

try:
    fixture = json.loads(open(os.environ["TICK_FIXTURE"], encoding="utf-8").read())
except Exception as exc:                                        # noqa: BLE001 - the stub must be loud
    print(f"stub: unreadable fixture: {exc}", file=sys.stderr)
    raise SystemExit(9)

if os.environ.get("TICK_FAIL"):
    print("stub: refused (TICK_FAIL=1)", file=sys.stderr)
    raise SystemExit(1)

args = sys.argv[1:]
if len(args) < 2:
    print(f"stub: unexpected gh {' '.join(args)}", file=sys.stderr)
    raise SystemExit(2)
cmd, sub = args[0], args[1]

if cmd == "pr" and sub == "list":
    print(json.dumps(fixture.get("prs", [])))
elif cmd == "issue" and sub == "list":
    print(json.dumps(fixture.get("issues", [])))
elif cmd == "pr" and sub == "view":
    num = args[2]
    print(json.dumps((fixture.get("pr_view") or {}).get(num, {"state": "OPEN", "mergedAt": None})))
elif cmd == "issue" and sub == "view":
    num = args[2]
    print(json.dumps((fixture.get("issue_view") or {}).get(num, {"state": "OPEN"})))
else:
    print(f"stub: unexpected gh {' '.join(args)}", file=sys.stderr)
    raise SystemExit(2)
'''

PR_919 = {"number": 919, "headRefName": "fix/919-lint", "headRefOid": "e21e7b22aa55bb66",
          "mergeStateStatus": "DIRTY"}
ISSUE_1049 = {"number": 1049, "title": "an implementable issue", "comments": []}


def stub(tmp_path: Path, fixture: dict) -> tuple[Path, Path]:
    """A `gh` on PATH plus the fixture it reads. Returns (bindir, fixture path)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(GH_STUB.replace("__PYTHON__", sys.executable), encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    path = tmp_path / "gh-fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    return bindir, path


def write_fixture(path: Path, fixture: dict) -> None:
    path.write_text(json.dumps(fixture), encoding="utf-8")


def run(tmp_path: Path, bindir: Path, fixture_path: Path, *args: str,
        discard: bool = False, fail: bool = False) -> subprocess.CompletedProcess:
    """One real CLI call: the script, the stub, a scratch state and outbox."""
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["TICK_FIXTURE"] = str(fixture_path)
    if fail:
        env["TICK_FAIL"] = "1"
    argv = [sys.executable, str(SCRIPT), *args,
            "--repo", REPO_SLUG,
            "--state", str(tmp_path / "state.json"),
            "--outbox", str(tmp_path / "outbox.log")]
    return subprocess.run(argv, text=True, env=env, encoding="utf-8",
                          stdout=subprocess.DEVNULL if discard else subprocess.PIPE,
                          stderr=subprocess.PIPE)


def outbox_lines(tmp_path: Path) -> list[dict]:
    path = tmp_path / "outbox.log"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def state(tmp_path: Path) -> dict:
    path = tmp_path / "state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def test_a_lost_delivery_reemits_the_same_lines(tmp_path):
    """The acceptance case: stdout thrown away (a `queue_full`) must not lose the dispatch."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})

    # Given a repository whose only fact is a conflicted PR, and a state/outbox that do not exist
    assert not (tmp_path / "state.json").exists()

    # When  the producer emits and its stdout is LOST (discarded) and it acknowledges nothing
    lost = run(tmp_path, bindir, fixture_path, "emit", "--no-ack",
               "--now", "2026-10-30T21:14:07Z", discard=True)
    assert lost.returncode == 0, lost.stderr
    records = outbox_lines(tmp_path)
    assert len(records) == 1, records

    # Then  the next pass re-emits the SAME line, from the outbox, with the first run's stamp
    again = run(tmp_path, bindir, fixture_path, "emit", "--no-ack", "--now", "2026-10-30T21:31:52Z")
    assert again.returncode == 0, again.stderr
    assert again.stdout.strip() == records[0]["line"]
    assert again.stdout.strip() == (
        "REBASE-NEEDED   #919 @e21e7b22  mergeStateStatus=DIRTY  [measured 21:14:07Z]")
    assert len(outbox_lines(tmp_path)) == 1, "the re-emit must not append a duplicate"


def test_the_outbox_is_written_before_the_state_advances(tmp_path):
    """The ordering is the fix, so prove it: the state write fails and the record already exists."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})
    (tmp_path / "blocked").write_text("not a directory", encoding="utf-8")
    unwritable = tmp_path / "blocked" / "state.json"

    # Given a state path that cannot be written (its parent is a regular file)
    # When  the producer emits a new fact through the real CLI
    broken = subprocess.run(
        [sys.executable, str(SCRIPT), "emit", "--repo", REPO_SLUG,
         "--state", str(unwritable), "--outbox", str(tmp_path / "outbox.log"), "--no-ack"],
        capture_output=True, text=True,
        env={**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
             "TICK_FIXTURE": str(fixture_path)})

    # Then  the outbox already carries the record, the exit is loud, and the next pass emits it once
    assert broken.returncode == tick.EXIT_READ, broken.stderr
    records = outbox_lines(tmp_path)
    assert len(records) == 1
    assert "READ-FAILED" in broken.stderr and "blocked" in broken.stderr

    after = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T22:00:00Z")
    assert after.returncode == 0, after.stderr
    assert after.stdout.strip() == records[0]["line"]
    assert len(outbox_lines(tmp_path)) == 1, "a durable record must not be appended twice"


def test_a_reemitted_line_carries_the_measurement_time_of_the_fact(tmp_path):
    """A late dispatch must LOOK late: the stamp is the fact's, not the run's."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})

    # Given a 21:14:07Z measurement whose delivery was lost
    run(tmp_path, bindir, fixture_path, "emit", "--no-ack",
        "--now", "2026-10-30T21:14:07Z", discard=True)

    # When  the next pass runs the clock forward
    again = run(tmp_path, bindir, fixture_path, "emit", "--no-ack", "--now", "2026-10-30T23:59:59Z")

    # Then  it still reports the measurement time of the fact it reports
    assert "[measured 21:14:07Z]" in again.stdout
    assert "23:59:59Z" not in again.stdout


def test_a_merged_pull_request_is_not_emitted(tmp_path):
    """Already-merged work: the live state at EMIT time decides, not the remembered queue."""
    bindir, fixture_path = stub(tmp_path, {
        "prs": [PR_919],
        "pr_view": {"919": {"state": "MERGED", "mergedAt": "2026-10-30T20:51:19Z"}},
    })

    # Given a PR measured as open and DIRTY
    # When  the same subject reports MERGED at emit time
    first = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:18:00Z")

    # Then  stdout is empty, the fact is recorded as suppressed, and no later pass emits it
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == ""
    assert len(outbox_lines(tmp_path)) == 1
    assert state(tmp_path)["suppressed"] == ["REBASE-NEEDED #919 @e21e7b22 mergeStateStatus=DIRTY"]

    later = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-31T00:03:00Z")
    assert later.stdout.strip() == ""


def test_a_closed_issue_is_not_emitted(tmp_path):
    """An issue that closed between measurement and emit is not a dispatch either."""
    bindir, fixture_path = stub(tmp_path, {
        "issues": [ISSUE_1049],
        "issue_view": {"1049": {"state": "CLOSED"}},
    })

    # Given an agent:implement issue measured while it was open
    # When  the same subject reports CLOSED at emit time
    first = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:18:00Z")

    # Then  it is never emitted, and it is recorded as suppressed
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == ""
    assert state(tmp_path)["suppressed"] == ["IMPLEMENT-READY #1049 no live claim"]


def test_a_second_pass_over_unchanged_state_is_silent_and_the_outbox_is_byte_identical(tmp_path):
    """Idempotence: the delta key is the fact set, so an unchanged state is a delta of nothing."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919], "issues": [ISSUE_1049]})

    # Given a first emit that delivered and acknowledged two facts
    first = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:18:00Z")
    assert first.returncode == 0, first.stderr
    assert len(first.stdout.strip().splitlines()) == 2
    before = (tmp_path / "outbox.log").read_bytes()

    # When  the producer runs again over the same measured facts
    second = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:45:00Z")

    # Then  it emits nothing, appends nothing, and the outbox is byte-identical
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == ""
    assert (tmp_path / "outbox.log").read_bytes() == before


def test_the_delta_key_is_the_fact_set_never_the_run_time(tmp_path):
    """A different clock is not a different fact."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})
    facts = lambda: state(tmp_path)["facts"]  # noqa: E731 - the durable state's own keys

    # Given a fact already emitted and acknowledged
    run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:18:00Z")
    sealed = facts()
    assert sealed == ["REBASE-NEEDED #919 @e21e7b22 mergeStateStatus=DIRTY"]

    # When  the producer runs again at a different time
    again = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-31T04:04:04Z")

    # Then  nothing is emitted because the key carries the fact and not the time
    assert again.stdout.strip() == ""
    assert facts() == sealed


def test_a_failed_read_fails_loud_and_leaves_the_outbox_and_state_untouched(tmp_path):
    """A read that failed must never look like "no change"."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})
    run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:18:00Z")
    outbox_before = (tmp_path / "outbox.log").read_bytes()
    state_before = (tmp_path / "state.json").read_bytes()

    # Given an outbox and a state from an earlier pass
    # When  gh fails
    broken = run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:45:00Z", fail=True)

    # Then  the exit is loud and both files are byte-identical
    assert broken.returncode == tick.EXIT_READ
    assert "READ-FAILED" in broken.stderr
    assert (tmp_path / "outbox.log").read_bytes() == outbox_before
    assert (tmp_path / "state.json").read_bytes() == state_before


def test_a_failed_delivery_leaves_the_line_pending(tmp_path):
    """A print that raises is a `queue_full`: the record stays pending and the caller exits non-zero."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})
    os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"
    os.environ["TICK_FIXTURE"] = str(fixture_path)

    class Refuses:
        def write(self, _text):
            raise OSError("queue_full")

        def flush(self):
            raise OSError("queue_full")

    # Given a new fact and a delivery channel that refuses it
    try:
        # When  the producer emits into that channel
        tick.emit(REPO_SLUG, tmp_path / "state.json", tmp_path / "outbox.log", ack=True, out=Refuses())
    except tick.DeliveryError as exc:
        # Then  it says so and acknowledges nothing, so the line is still pending
        assert "stay pending" in str(exc)
    else:  # pragma: no cover - the refusal must not pass silently
        raise AssertionError("a refused delivery must raise DeliveryError")

    assert state(tmp_path)["acked"] == []
    pending, dead = tick.pending_records(REPO_SLUG, tmp_path / "outbox.log", state(tmp_path))
    assert [rec["key"] for rec in pending] == ["REBASE-NEEDED #919 @e21e7b22 mergeStateStatus=DIRTY"]
    assert dead == []


def test_pending_prints_without_acknowledging(tmp_path):
    """The recovery read: what a lost delivery would have said, and it consumes nothing."""
    bindir, fixture_path = stub(tmp_path, {"prs": [PR_919]})
    run(tmp_path, bindir, fixture_path, "emit", "--no-ack",
        "--now", "2026-10-30T21:14:07Z", discard=True)
    before = (tmp_path / "outbox.log").read_bytes()

    # Given an outbox holding one unacknowledged record
    # When  pending runs twice
    first = run(tmp_path, bindir, fixture_path, "pending")
    second = run(tmp_path, bindir, fixture_path, "pending")

    # Then  both print the same line and the record is still unacknowledged
    assert first.stdout.strip() == second.stdout.strip() != ""
    assert "[measured 21:14:07Z]" in first.stdout
    assert (tmp_path / "outbox.log").read_bytes() == before
    assert state(tmp_path)["acked"] == []


def test_report_counts_the_outbox_without_emitting(tmp_path):
    """The numbers an operator asks for after a failed delivery, and no dispatch line."""
    bindir, fixture_path = stub(tmp_path, {
        "prs": [PR_919],
        "issues": [ISSUE_1049],
        "pr_view": {"919": {"state": "MERGED", "mergedAt": "2026-10-30T20:51:19Z"}},
    })
    run(tmp_path, bindir, fixture_path, "emit", "--now", "2026-10-30T23:18:00Z")

    # Given one suppressed record (the merged PR) and one acknowledged record (the issue)
    # When  report runs
    out = run(tmp_path, bindir, fixture_path, "report")

    # Then  it prints the counts, exits 0, and carries no dispatch line on stdout
    assert out.returncode == 0, out.stderr
    assert "records=2" in out.stdout
    assert "acknowledged=2" in out.stdout
    assert "suppressed=1" in out.stdout
    assert "REBASE-NEEDED" not in out.stdout and "IMPLEMENT-READY" not in out.stdout
