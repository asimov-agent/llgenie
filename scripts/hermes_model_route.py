#!/usr/bin/env python3
"""Report which model served a lane's newest Hermes session (issue #2931).

Since the chain landed (issue #2929), a leg may be served by the free primary or by the
paid last resort, and only Hermes' own session store records which. This is the after-the-leg
report wired into every Hermes bot recipe: it reads the `model` column of the newest session
that started inside the leg's window from the lane's store, and prints exactly one line:

    model-route: <model-id>

Store resolution mirrors `hermes_smoke.state_db` (measured against Hermes 0.23.2 in issue
#2929): a `hermes -p <lane>` run gets the profile's own home as its Hermes home, so a lane
WITH a profile home is read from `$HERMES_HOME/profiles/<lane>/state.db`, and only a lane
without one falls back to the global `$HERMES_HOME/state.db`.

A missing store, an unreadable store, a window with no session, and a session with no recorded
model are each a loud, named failure on stderr with its own exit code: the report never prints
a route the store cannot evidence. The line carries only the model value — the script reads no
credential, no config field, and no environment value beyond the store's own location.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

#: The acceptance line every bot leg log must carry (issue #2931 AC 1).
LINE = "model-route: %s"

#: Distinct exit codes so a log says WHICH evidence was missing, not just "report failed".
EXIT_STORE = 2       # the lane's store is absent or unreadable
EXIT_WINDOW = 3      # the store holds no session started inside the leg window
EXIT_MODEL = 4       # the session exists but carries no model value

#: Hermes stamps `started_at` when the run creates its session, a heartbeat after the recipe
#: captured `--since`; a small tolerance absorbs launch latency, never a previous leg's session.
WINDOW_TOLERANCE_SECONDS = 5.0


def state_db(home: str | None = None, lane: str | None = None) -> Path:
    """The transcript store the lane's run wrote (profile home first, same rule as the smoke)."""
    base = Path(home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    if lane:
        profile_home = base / "profiles" / lane
        if profile_home.is_dir():
            return profile_home / "state.db"
    return base / "state.db"


def connect(db: Path) -> sqlite3.Connection:
    """Read-only, so the report can never mutate the store it inspects."""
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def newest_in_window(conn: sqlite3.Connection, since: float | None) -> tuple[str, str | None, float] | None:
    """The newest session's (id, model, started_at), optionally inside the leg's window.

    Constant query, the window bound passed as a bound argument (never formatted): a leg
    window is a value, not SQL shape. `started_at` is stored REAL epoch seconds, like the
    bound `since` from `date +%s` — same numeric order, so the SQL ORDER BY is exact.
    """
    if since is None:
        row = conn.execute(
            "SELECT id, model, started_at FROM sessions ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, model, started_at FROM sessions WHERE started_at >= ? "
            "ORDER BY started_at DESC LIMIT 1",
            (since - WINDOW_TOLERANCE_SECONDS,),
        ).fetchone()
    if row is None:
        return None
    session_id, model, started_at = row
    return str(session_id), model, float(started_at or 0.0)


def report(lane: str, home: str | None, since: float | None) -> int:
    """Read the lane's store and print the one line, or name the missing evidence."""
    db = state_db(home, lane)
    tried = db
    try:
        with closing(connect(db)) as conn:
            found = newest_in_window(conn, since)
    except sqlite3.Error as exc:
        print(f"[model-route] FAIL: the lane store {tried} is absent or unreadable ({exc}); "
              f"the leg's serving model cannot be reported, and no line is invented",
              file=sys.stderr)
        return EXIT_STORE

    if found is None:
        window = "any window" if since is None else f"started at or after {since:.0f}"
        print(f"[model-route] FAIL: {db} holds no session {window}, so this leg cannot be "
              f"attributed to a model and no line is invented", file=sys.stderr)
        return EXIT_WINDOW

    session_id, model, started_at = found
    value = (model or "").strip()
    if not value:
        print(f"[model-route] FAIL: session {session_id} in {db} (started {started_at:.0f}) "
              f"carries no model value, so the route is unevidenced and no line is invented",
              file=sys.stderr)
        return EXIT_MODEL

    print(LINE % value)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report which model served a lane's newest session")
    parser.add_argument("--lane", required=True,
                        help="the profile lane the leg ran as (the -p <lane> name)")
    parser.add_argument("--home", default="",
                        help="override the Hermes home (default $HERMES_HOME or ~/.hermes)")
    parser.add_argument("--since", type=float, default=None,
                        help="epoch seconds of the leg start: only sessions started at or after "
                             "it can be reported; omit to take the store's newest session")
    args = parser.parse_args(argv)
    return report(args.lane, args.home or None, args.since)


if __name__ == "__main__":
    sys.exit(main())
