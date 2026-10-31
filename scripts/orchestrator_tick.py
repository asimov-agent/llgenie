#!/usr/bin/env python3
"""The orchestrator tick's dispatch producer: the OUTBOX is written before the state (issue #1125).

The tick kept dispatching work that had already merged — `#919` as "rebase it, head e21e7b22" 2.5 h
after it merged, `#1049`/`#1050` and `#885` after theirs — and every receiving lane spent a turn
proving the dispatch stale. A stale dispatch is **indistinguishable from a fresh one**, so the cost
is not the message: the receiver must re-measure GitHub to tell them apart.

The mechanism was never a stale queue. It is the ORDER of two operations: the producer advanced its
**durable state** (what it had already said) before the side effect that consumes its output (the
delivered message). When the delivery failed — `queue_full` is measured on this job — the in-memory
delta was gone; the next pass diffed against the already-advanced state, found nothing new, and
re-sent a task list from memory that still looked current. A lost delivery was not late, it was
unrecoverable.

This module encodes the shape the rebase lane proved in its own delta reporter (`tally-delta.py`:
append-only outbox + `[measured HH:MM:SSZ]` + a delta keyed on the fact), with the ordering fixed:

  1. **the OUTBOX is append-only and is written and `fsync`ed BEFORE the state advances**, so a lost
     delivery is retried from the file instead of vanishing;
  2. **every emitted line carries the measurement time of the fact it reports**, persisted in the
     record — a re-emitted line is visibly old instead of looking fresh;
  3. **at emit time** the subject's live state is asked (`gh pr view <n> --json state,mergedAt` /
     `gh issue view <n> --json state`); a subject whose PR merged or whose issue closed is dropped
     and recorded as suppressed, so it is never emitted again;
  4. **the delta key is the fact set** (`REBASE-NEEDED #919 @e21e7b22 mergeStateStatus=DIRTY`),
     never the run time — a second pass over unchanged state emits nothing and writes nothing.

Facts are the two things the tick dispatches: a PR that is `DIRTY`/`CONFLICTING` (dispatch the rebase
bot) and an open `agent:implement` issue with no live claim (dispatch an implementer). A third kind is
another branch in `measure()`; nothing else in this file changes.

Commands (stdlib only, no LLM):
  emit     measure -> append the delta to the outbox -> advance state -> print the pending lines and
           acknowledge them. `--no-ack` prints the same lines and acknowledges nothing (the exact
           shape of a delivery that was lost).
  pending  print the lines the outbox still holds undelivered, acknowledging nothing: what a lost
           delivery would have said, with the measurement time of each fact.
  report   the outbox/state numbers, exit 0, no dispatch line on stdout.

The GitHub API is reached ONLY through a `gh` on PATH (`--gh` selects another), so the tests drive the
real code against a `gh` stub, the repository's allowance for an external CLI.

Exit: 0 emitted or nothing to emit; 2 a read/state failure (never a silent "no change"); 3 the lines
could not be delivered — they stay pending.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot_claims  # the shared claim protocol: one subject, one bot (issues #261/#279/#292)

DEFAULT_REPO = "asimov-agent/llgenie"
#: A bot's own state, never the tree: `~/.llgenie` is where the other host tools keep theirs.
STATE_FILE = Path.home() / ".llgenie" / "tick" / "state.json"
OUTBOX_FILE = Path.home() / ".llgenie" / "tick" / "outbox.log"

#: The fact kinds. The name IS the dispatch verb, so a reader needs no mapping table.
REBASE = "REBASE-NEEDED"
IMPLEMENT = "IMPLEMENT-READY"
#: `mergeStateStatus` values that mean "no CI run will ever happen unless someone rebases it".
REBASE_STATES = {"DIRTY", "CONFLICTING"}
IMPLEMENT_LABEL = "agent:implement"
#: The reader of claims in this module's role. It never writes one, so no marker is "its own" and
#: ANY live claim holds the subject — which is the rule the tick needs.
TICK = "orchestrator-tick"

EXIT_READ = 2
EXIT_DELIVERY = 3


class TickError(RuntimeError):
    """A failed read or a failed state write. Never "no change" (issue #1125)."""


class DeliveryError(RuntimeError):
    """The lines could not be printed: they stay pending and the caller exits non-zero."""


def gh(*args: str, gh_cmd: str = "gh") -> str:
    """One `gh` call, its stdout. A failure raises — a read that failed is not an empty answer."""
    proc = subprocess.run([gh_cmd, *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise TickError(f"gh {' '.join(args)} rc={proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _json(text: str):
    try:
        return json.loads(text or "null")
    except json.JSONDecodeError as exc:
        raise TickError(f"gh answered unparsable JSON: {exc}") from None


def stamp(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).strftime("%H:%M:%SZ")


def _record(kind: str, subject: int, detail: str, measured: str, line: str) -> dict:
    return {"key": f"{kind} #{subject} {detail}", "kind": kind, "subject": subject,
            "detail": detail, "measured": measured, "line": line}


def measure(repo: str, now: dt.datetime, gh_cmd: str = "gh") -> dict[str, dict]:
    """`{fact key: record}` for every fact the tick would dispatch, each stamped with NOW.

    The key carries the fact — kind, subject and the measured condition (a PR's head sha and merge
    state) — and never the run time, so an unchanged second pass is a delta of nothing (issue #1125).
    A new head sha IS a new fact: it is a fresh measurement of a PR that is still conflicted.
    """
    measured = stamp(now)
    facts: dict[str, dict] = {}

    prs = _json(gh("pr", "list", "--repo", repo, "--state", "open", "--limit", "200",
                   "--json", "number,headRefName,headRefOid,mergeStateStatus", gh_cmd=gh_cmd)) or []
    for pr in prs:
        state = (pr.get("mergeStateStatus") or "").upper()
        if state not in REBASE_STATES:
            continue
        num, sha = int(pr["number"]), (pr.get("headRefOid") or "")[:8]
        detail = f"@{sha} mergeStateStatus={state}"
        rec = _record(REBASE, num, detail, measured,
                      f"{REBASE:<15} #{num} @{sha}  mergeStateStatus={state}  [measured {measured}]")
        facts[rec["key"]] = rec

    issues = _json(gh("issue", "list", "--repo", repo, "--state", "open", "--label", IMPLEMENT_LABEL,
                      "--limit", "200", "--json", "number,title,comments", gh_cmd=gh_cmd)) or []
    for issue in issues:
        num = int(issue["number"])
        comments = issue.get("comments") or []
        if bot_claims.occupied(comments, TICK, now):
            continue  # somebody is already on it; a claimed subject is not work to dispatch
        detail = "no live claim"
        rec = _record(IMPLEMENT, num, detail, measured,
                      f"{IMPLEMENT:<15} #{num}  no live claim  [measured {measured}]")
        facts[rec["key"]] = rec
    return facts


def still_open(repo: str, record: dict, gh_cmd: str = "gh") -> bool:
    """The subject's LIVE state at emit time — not the state from when it was measured.

    This is the half that stops already-merged work being dispatched: the measurement is a memory,
    and a memory of an open PR is exactly what the four measured dispatches carried (#919 and friends).
    """
    kind, num = record.get("kind"), int(record["subject"])
    if kind == REBASE:
        data = _json(gh("pr", "view", str(num), "--repo", repo, "--json", "state,mergedAt",
                        gh_cmd=gh_cmd)) or {}
        return data.get("state") == "OPEN" and not data.get("mergedAt")
    data = _json(gh("issue", "view", str(num), "--repo", repo, "--json", "state",
                    gh_cmd=gh_cmd)) or {}
    return data.get("state") == "OPEN"


def read_outbox(path: Path) -> list[dict]:
    """Every record ever written, oldest first. One JSON object per line; a corrupt line is loud."""
    if not path.exists():
        return []
    out: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TickError(f"{path}:{lineno} is not a record ({exc}); refusing to guess") from None
        if "key" not in rec or "line" not in rec:
            raise TickError(f"{path}:{lineno} carries no key/line; refusing to guess")
        out.append(rec)
    return out


def append_outbox(path: Path, records: list[dict]) -> None:
    """Append + fsync. The durability is the point: this happens BEFORE the state advances."""
    if not records:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise TickError(f"could not append to the outbox at {path} ({exc}); nothing was "
                        f"acknowledged") from None


def read_state(path: Path) -> dict:
    if not path.exists():
        return {"facts": [], "acked": [], "suppressed": [], "updated": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except OSError as exc:
        raise TickError(f"could not read the state at {path} ({exc})") from None
    except json.JSONDecodeError as exc:
        raise TickError(f"{path} is not JSON ({exc}); refusing to guess") from None
    if not isinstance(data, dict):
        raise TickError(f"{path} is not a state object")
    for key in ("facts", "acked", "suppressed"):
        data.setdefault(key, [])
    return data


def write_state(path: Path, state: dict) -> None:
    """Atomic rewrite: a half-written state file would read as "nothing was ever dispatched"."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        raise TickError(f"could not write the state at {path} ({exc}); the outbox still holds "
                        f"every record") from None


def pending_records(repo: str, outbox: Path, state: dict,
                    gh_cmd: str = "gh") -> tuple[list[dict], list[str]]:
    """(records still to deliver, keys that are no longer a subject) from the outbox + live state."""
    acked = set(state.get("acked") or [])
    live: list[dict] = []
    dead: list[str] = []
    for rec in read_outbox(outbox):
        if rec["key"] in acked:
            continue
        if still_open(repo, rec, gh_cmd):
            live.append(rec)
        else:
            dead.append(rec["key"])
    return live, dead


def emit(repo: str, state_path: Path, outbox: Path, ack: bool = True,
         now: dt.datetime | None = None, gh_cmd: str = "gh", out=None) -> dict:
    """measure -> outbox (durable) -> state -> print -> acknowledge.

    The order is the fix. The outbox append is the only thing that must not be lost, so it comes
    first; the state advance records "this fact was handled" and may follow. If the process dies
    after the state write and before the print, the record is still pending and the next pass
    re-emits it — at-least-once, with the original measurement time, which is what the receiver
    needs to see.
    """
    out = out if out is not None else sys.stdout
    now = now or dt.datetime.now(dt.timezone.utc)

    facts = measure(repo, now, gh_cmd)                       # 1. measure (live reads)
    state = read_state(state_path)
    known = set(state.get("facts") or [])
    known_outbox = {rec["key"] for rec in read_outbox(outbox)}
    delta = [facts[key] for key in sorted(facts) if key not in known and key not in known_outbox]
    append_outbox(outbox, delta)                             # 2. OUTBOX BEFORE STATE
    state["facts"] = sorted(facts)
    state["updated"] = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_state(state_path, state)                           # 3. advance the durable state

    live, dead = pending_records(repo, outbox, state, gh_cmd)  # 4. live state at EMIT time
    lines = [rec["line"] for rec in live]
    if lines:
        try:
            out.write("\n".join(lines) + "\n")
            out.flush()
        except OSError as exc:
            raise DeliveryError(
                f"could not deliver ({exc}); {len(lines)} line(s) stay pending in {outbox}") from None

    if ack:                                                  # 5. acknowledge only what landed
        landed = {rec["key"] for rec in live} if lines else set()
        state["acked"] = sorted(set(state.get("acked") or []) | landed | set(dead))
    else:
        state["acked"] = sorted(set(state.get("acked") or []) | set(dead))
    state["suppressed"] = sorted(set(state.get("suppressed") or []) | set(dead))
    write_state(state_path, state)

    return {"measured": len(facts), "appended": len(delta), "emitted": len(lines),
            "suppressed": len(dead)}


def _now(text: str | None) -> dt.datetime:
    if not text:
        return dt.datetime.now(dt.timezone.utc)
    try:
        return dt.datetime.strptime(text.replace("+00:00", "Z"), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        raise SystemExit(f"--now must be an ISO instant like 2026-10-30T21:14:07Z, not {text!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The orchestrator tick's dispatch producer (issue #1125).")
    parser.add_argument("command", choices=("emit", "pending", "report"))
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--state", type=Path, default=STATE_FILE)
    parser.add_argument("--outbox", type=Path, default=OUTBOX_FILE)
    parser.add_argument("--gh", default="gh", help="the gh executable (a stub in the tests)")
    parser.add_argument("--now", default=None, help="pin the clock (ISO instant); tests do")
    parser.add_argument("--no-ack", action="store_true",
                        help="print the lines and acknowledge nothing: a lost delivery, by hand")
    args = parser.parse_args(argv)

    try:
        if args.command == "emit":
            result = emit(args.repo, args.state, args.outbox, ack=not args.no_ack,
                          now=_now(args.now), gh_cmd=args.gh)
            print(f"[orchestrator-tick] measured={result['measured']} appended={result['appended']} "
                  f"emitted={result['emitted']} suppressed={result['suppressed']}", file=sys.stderr)
            return 0
        if args.command == "pending":
            state = read_state(args.state)
            live, dead = pending_records(args.repo, args.outbox, state, args.gh)
            if live:
                print("\n".join(rec["line"] for rec in live))
            print(f"[orchestrator-tick] pending={len(live)} suppressed-now={len(dead)}", file=sys.stderr)
            return 0
        state = read_state(args.state)
        acked = set(state.get("acked") or [])
        records = read_outbox(args.outbox)
        live, dead = pending_records(args.repo, args.outbox, state, args.gh)
        print(f"[orchestrator-tick] facts={len(state.get('facts') or [])} records={len(records)} "
              f"acknowledged={len([r for r in records if r['key'] in acked])} "
              f"suppressed={len(state.get('suppressed') or [])} pending={len(live)} "
              f"suppressible={len(dead)}")
        return 0
    except DeliveryError as exc:
        print(f"[orchestrator-tick] DELIVERY-FAILED: {exc}", file=sys.stderr)
        return EXIT_DELIVERY
    except TickError as exc:
        print(f"[orchestrator-tick] READ-FAILED: {exc}", file=sys.stderr)
        return EXIT_READ


if __name__ == "__main__":
    raise SystemExit(main())
