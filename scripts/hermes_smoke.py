#!/usr/bin/env python3
"""Prove the model every bot leg uses can CALL A TOOL, not just answer in text (issue #407).

`make hermes-smoke` used to ask the model for the single sentence `ok` and assert that sentence came
back. A model whose tool calling is broken, disabled, or unsupported on the current snapshot answers `ok`
too, so the smoke stayed green and the first real failure cost a 120-180 minute bot job. Every leg it
guards is a tool-using agent (`implement-issue` runs `make` gates through its terminal tool, the fix
loop hands the agent a failing check, the refiner writes `refine.md`).

This proves the capability instead, with a value the model cannot produce without a tool:

1. a random nonce is written to a file; the prompt names the FILE, never the value;
2. the agent is told to run one exact command with its terminal tool that prints that file;
3. the run passes only when the session it created carries a `role='tool'`, `tool_name='terminal'`
   result containing `smoke-ok:<nonce>` AND the final answer carries the same string.

A text-only model cannot produce the nonce. A model that calls another tool, or none, fails. A missing
transcript is a loud, named failure — never a pass.

Reads the same store `hermes sessions list` reads: `$HERMES_HOME/state.db` (`sessions`, `messages`).
"""
from __future__ import annotations

import argparse
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

#: The marker every passing run must carry, in the tool result and in the final answer.
MARKER = "smoke-ok"

#: The one command the agent is told to run. `printf` (the shape issue #407 names) prints the nonce
#: from the file, so the output can only exist if a shell actually ran.
COMMAND = "printf 'smoke-ok:%s\\n' \"$(cat {token_path})\""

PROMPT = (
    "You have a terminal tool. Use it to run this exact shell command:\n\n"
    "    {command}\n\n"
    "The command's output is the only correct answer, and you cannot guess it: it holds a nonce that "
    "exists only in that file. Reply with ONLY the command's output on a single line - no prose, no "
    "quotes, no explanation, and never an answer from memory."
)

def expected_value(nonce: str) -> str:
    """The string the tool result AND the final answer must carry, for a given nonce."""
    return f"{MARKER}:{nonce}"


def prompt_for(token_path: str) -> str:
    """The instruction, built once: it names the file's PATH and never its content."""
    return PROMPT.format(command=COMMAND.format(token_path=token_path), token_path=token_path)


def state_db(home: str | None = None) -> Path:
    """The transcript store Hermes writes: `$HERMES_HOME/state.db`."""
    base = home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(base) / "state.db"


def connect(db: Path) -> sqlite3.Connection:
    """Read-only, so a smoke run can never mutate the store it inspects."""
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def session_ids(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT id FROM sessions")}


def new_session(conn: sqlite3.Connection, before: set[str]) -> str | None:
    """The session this run created: the newest id not present before the run."""
    ids = session_ids(conn) - before
    if not ids:
        return None
    row = conn.execute(
        "SELECT id FROM sessions WHERE id IN (%s) ORDER BY started_at DESC LIMIT 1"
        % ",".join("?" * len(ids)),
        tuple(ids),
    ).fetchone()
    return row[0] if row else None


def wait_for_session(conn: sqlite3.Connection, before: set[str], expected: str,
                     deadline: float, interval: float = 0.5) -> str | None:
    """Poll for the session (and its evidence): a run finalizes its rows just after it exits."""
    found: str | None = None
    while time.time() < deadline:
        sid = new_session(conn, before)
        if sid and not evaluate(conn, sid, expected):
            return sid
        if sid:
            found = found or sid
        time.sleep(interval)
    return found


def messages(conn: sqlite3.Connection, session_id: str) -> list[tuple[str, str | None, str | None]]:
    return list(conn.execute(
        "SELECT role, tool_name, content FROM messages WHERE session_id = ? ORDER BY id", (session_id,)
    ))


def evaluate(conn: sqlite3.Connection, session_id: str, expected: str) -> list[str]:
    """The problems with this session, in the order a reader wants them. Empty means proof."""
    try:
        rows = messages(conn, session_id)
    except sqlite3.Error as exc:  # a store without the messages table is not evidence
        return [f"could not read the transcript of session {session_id}: {exc}"]
    if not rows:
        return [f"session {session_id} has no transcript at all - nothing proves a tool ran"]

    problems: list[str] = []
    tool_names = [name for role, name, _ in rows if role == "tool" and name]
    terminal_hits = [body or "" for role, name, body in rows
                     if role == "tool" and name == "terminal" and expected in (body or "")]
    if not tool_names:
        problems.append(
            "the model answered without calling a tool at all - a text-only model passes a sentence "
            "assertion, which is exactly the failure this smoke exists to catch"
        )
    elif not terminal_hits:
        problems.append(
            "no terminal tool result carried `%s` (tool calls seen: %s) - the legs need the terminal "
            "tool, so another tool does not count" % (expected, ", ".join(sorted(set(tool_names))))
        )

    answers = [body or "" for role, _, body in rows if role == "assistant" and (body or "").strip()]
    if not answers:
        problems.append("the run produced no final answer")
    elif expected not in answers[-1]:
        problems.append(
            "the final answer does not carry `%s`, so the agent did not report the command's output "
            "(it read: %r)" % (expected, answers[-1][:120])
        )
    return problems


def run(hermes: str, alias: str, reasoning: str, db: Path, timeout: float,
        keep_token: bool = False) -> int:
    """The proof: write the nonce, run the agent, judge the session it created.

    The store is what a successful run CREATES (`$HERMES_HOME/state.db`), so its absence before the
    call is normal — the fresh agent image ships without one. Only the store the run leaves behind is
    judged: absent, unreadable, or without a new session are each a loud, named failure (issue #471).
    """
    workdir = Path(tempfile.mkdtemp(prefix="hermes-smoke-"))
    token_path = workdir / "token"
    nonce = secrets.token_hex(12)
    token_path.write_text(nonce + "\n")
    expected = expected_value(nonce)
    prompt = prompt_for(str(token_path))

    try:
        # The snapshot a new session is measured against: empty when this run is the first one.
        before: set[str] = set()
        if db.exists():
            with closing(connect(db)) as conn:
                try:
                    before = session_ids(conn)
                except sqlite3.Error as exc:
                    print(f"[hermes-smoke] FAIL: {db} has no readable sessions store ({exc}), so the "
                          f"run's tool use cannot be proven", file=sys.stderr)
                    return 1

        argv = [hermes, "-z", prompt, "-m", alias, "--reasoning", reasoning, "--yolo"]
        print(f"[hermes-smoke] running the alias the bots use: {alias} (reasoning {reasoning})")
        proc = subprocess.run(argv, capture_output=True, text=True)
        if proc.stdout.strip():
            print(proc.stdout.rstrip())
        if proc.returncode != 0:
            print(f"[hermes-smoke] FAIL: hermes exited {proc.returncode}", file=sys.stderr)
            if proc.stderr.strip():
                print(proc.stderr.rstrip(), file=sys.stderr)
            return 1

        if not db.exists():
            print(f"[hermes-smoke] FAIL: hermes exited 0 but wrote no transcript at {db}, so there is "
                  f"nothing to prove (check HERMES_HOME)", file=sys.stderr)
            return 1

        with closing(connect(db)) as conn:
            try:
                session = wait_for_session(conn, before, expected, time.time() + timeout)
            except sqlite3.Error as exc:
                print(f"[hermes-smoke] FAIL: {db} has no readable sessions store ({exc}), so the "
                      f"run's tool use cannot be proven", file=sys.stderr)
                return 1
            if not session:
                print(f"[hermes-smoke] FAIL: the run left no new session in {db}, so its tool use "
                      f"cannot be proven", file=sys.stderr)
                return 1

            problems = evaluate(conn, session, expected)
            if problems:
                print(f"[hermes-smoke] FAIL: session {session} does not prove a tool call:",
                      file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                return 1
            print(f"[hermes-smoke] OK: session {session} called the terminal tool and its output "
                  f"(`{expected}`) reached the answer")
            return 0
    finally:
        if keep_token:
            print(f"[hermes-smoke] token kept at {token_path}")
        else:
            token_path.unlink(missing_ok=True)
            try:
                workdir.rmdir()
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the smoke for real and judge the session it created")
    r.add_argument("--alias", default="nous-deepseek", help="the model alias the bots use")
    r.add_argument("--reasoning", default="low")
    r.add_argument("--hermes", default="hermes", help="the hermes executable")
    r.add_argument("--state-db", default="", help="override the transcript store (default $HERMES_HOME/state.db)")
    r.add_argument("--timeout", type=float, default=60.0, help="seconds to wait for the session row")
    r.add_argument("--keep-token", action="store_true")
    p = sub.add_parser("prompt", help="print the prompt built for a given token path (no model call)")
    p.add_argument("--token-path", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "prompt":
        print(prompt_for(args.token_path))
        return 0
    db = Path(args.state_db) if args.state_db else state_db()
    return run(args.hermes, args.alias, args.reasoning, db, args.timeout, args.keep_token)


if __name__ == "__main__":
    sys.exit(main())
