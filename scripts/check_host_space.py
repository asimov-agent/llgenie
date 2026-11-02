#!/usr/bin/env python3
"""Host /tmp tmpfs headroom gate (issue #1583): refuse a build/dispatch on a shared tmpfs at the limits.

The host /tmp tmpfs (32G, 1,048,576 inodes) is a finite resource every lane shares for worktrees,
probes, and container builds, and it has NO headroom gate — a single multi-GB probe tree
(`/tmp/trtllm-probe`, 15G / ~197k inodes) drove it to 71% space AND 100% inodes on 2026-11-02 and
wedged two lanes (implementer tool channel, reviewer ENOSPC). The only disk tooling is `ci-free-disk`
(CI runner disk for engine images) — host tmpfs is out of its scope.

This module is the measurable preflight: read BOTH axes (`df -h` space and `df -i` inodes) for a
mount and refuse when the tmpfs is below a documented threshold. It becomes `make check-host-space`,
a target the planner (or any lane) runs BEFORE spawning a /tmp worktree or container build — never
after a lane has already failed.

    check_host_space.py [report|check] [--mount /tmp] [--space-min 20] [--inodes-min 50000]
      report   print the space + inode measurement and the verdict; always exit 0
      check    same, but exit 1 when either axis is below its threshold (the gate)

The default thresholds (documented in the planner's standing behaviour under agents/llgenie-planner/):
space free < 20% OR inodes free < 50_000 → refuse. A `df` that cannot be read is an error, not a
benign "nothing to do": a preflight must not silently proceed when the measurement failed.

The `df` calls go through `scripts/proc.py` (the repo's one subprocess policy seam, issue #797) and
the tests drive it with a fake `df` on PATH, so the gate runs hermetically on CI.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proc import run_ok  # noqa: E402  the subprocess policy seam (issue #797)

#: Where the shared work-area tmpfs lives; the planner's placement rule moves heavy worktrees to real
#: disk under /home/asimov/repository/git/llgenie-wt/, so /tmp holds at most small/scratch files.
DEFAULT_MOUNT = "/tmp"

#: Documented thresholds (issue #1583, under agents/llgenie-planner/SOUL.md standing behaviour).
#: Refuse when less than this much space (%) is free…
DEFAULT_SPACE_MIN_PCT = 20
#: …OR fewer than this many inodes are free.
DEFAULT_INODES_MIN = 50_000

#: df -h header and a data row: `Filesystem  Size  Used Avail Use% Mounted on`
_SPACE_RE = re.compile(
    r"^\S+\s+\S+\s+\S+\s+\S+\s+(\d+)%\s+\S+\s*$"
)
#: df -i header and a data row: `Filesystem  Inodes  IUsed  IFree IUse% Mounted on`
_INODES_RE = re.compile(
    r"^\S+\s+\S+\s+\S+\s+(\d+)\s+\d+%\s+\S+\s*$"
)


class HostSpaceError(RuntimeError):
    """A tmpfs axis is at or below its threshold, or the measurement failed — a lane must stop."""


def _df_line(mount: str, *, inodes: bool) -> str:
    """Return the first data row of `df` for `mount` (space or inodes)."""
    flag = "-i" if inodes else "-h"
    r = run_ok(["df", flag, mount])
    if r.returncode != 0 or not r.stdout:
        raise HostSpaceError(
            f"[host-space] `df {flag} {mount}` failed (rc={r.returncode}): "
            f"{r.stderr.strip() or r.stdout.strip() or 'no output'}"
        )
    # The first line after the header is the target's own row (a tmpfs mount line).
    for line in r.stdout.splitlines()[1:]:
        line = line.strip()
        if line and not line.startswith("Filesystem"):
            return line
    raise HostSpaceError(f"[host-space] `df {flag} {mount}` printed no data row")


def space_free_pct(mount: str = DEFAULT_MOUNT) -> int:
    """Percent of `mount` still FREE (100 - Use%), from `df -h`."""
    m = _SPACE_RE.match(_df_line(mount, inodes=False))
    if not m:
        raise HostSpaceError(f"[host-space] could not parse `df -h {mount}` space usage")
    used = int(m.group(1))
    return 100 - used


def inodes_free(mount: str = DEFAULT_MOUNT) -> int:
    """Count of free inodes on `mount`, from `df -i`."""
    m = _INODES_RE.match(_df_line(mount, inodes=True))
    if not m:
        raise HostSpaceError(f"[host-space] could not parse `df -i {mount}` inode usage")
    return int(m.group(1))


def measure(mount: str = DEFAULT_MOUNT) -> dict[str, int]:
    """Measure both axes; raise HostSpaceError if either measurement fails."""
    return {
        "space_free_pct": space_free_pct(mount),
        "inodes_free": inodes_free(mount),
    }


def report(mount: str = DEFAULT_MOUNT,
           space_min: int = DEFAULT_SPACE_MIN_PCT,
           inodes_min: int = DEFAULT_INODES_MIN) -> int:
    """Measure, print the verdict, and return the exit code (0 ok, 1 below threshold)."""
    m = measure(mount)
    print(f"[host-space] {mount}: {m['space_free_pct']}% space free, "
          f"{m['inodes_free']:,} inodes free (thresholds: <{space_min}% OR <{inodes_min:,} inodes -> refuse)")
    if m["space_free_pct"] < space_min:
        print(f"[host-space] FAIL: {mount} below {space_min}% space free "
              f"(got {m['space_free_pct']}%) — a build/dispatch will wedge the shared tmpfs")
        return 1
    if m["inodes_free"] < inodes_min:
        print(f"[host-space] FAIL: {mount} below {inodes_min:,} free inodes "
              f"(got {m['inodes_free']:,}) — container builds and small files will exhaust it")
        return 1
    print(f"[host-space] OK: {mount} above the headroom threshold")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_host_space.py", description="host tmpfs headroom gate")
    p.add_argument("mode", nargs="?", choices=("check", "report"), default="check",
                   help="check exits 1 below threshold (default); report always exits 0")
    p.add_argument("--mount", default=DEFAULT_MOUNT, help="mount to measure (default /tmp)")
    p.add_argument("--space-min", type=int, default=DEFAULT_SPACE_MIN_PCT,
                   help=f"minimum % space free (default {DEFAULT_SPACE_MIN_PCT})")
    p.add_argument("--inodes-min", type=int, default=DEFAULT_INODES_MIN,
                   help=f"minimum free inodes (default {DEFAULT_INODES_MIN:,})")
    a = p.parse_args(argv)
    code = report(a.mount, a.space_min, a.inodes_min)
    if a.mode == "report":
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
