#!/usr/bin/env python3
"""One pre-push target for a host lane: run the FAST gates before the push (issue #1058).

A host lane can push a PR whose own gates its head fails, and the fleet has no single command that
re-checks the fast set before the push. `make bot-preflight` (issue #792) fetches `main` and records
the `AGENTS.md` sha — it does NOT run the gates. `scripts/issue_bot_gates.py` (`FAST_GATES`) already
defines the right set, but only the **issue-bot** workflow runs it, and 16 workflow files are
disabled (issue #902), so in practice nothing runs it for host lanes.

Four PRs failed tonight on a gate a lane could have run before the push, each costing a full
`linux/unit` matrix before the error was visible — three are in `FAST_GATES` and run by default,
the fourth is a DEFERRED gate reachable on demand with `--gates check-import-roots`:

  #919   tests/fixtures/host-only-wiring.json malformed        -> check-wiring        (FAST_GATES)
  #919   agent-wiki/...-doc-soul-take.md missing trailing NL   -> lint                (FAST_GATES)
  #1056  openspec/.../tasks.md line 8 unchecked                -> openspec-tasks-check (FAST_GATES)
  #953   import-roots ratchet: bare 52 vs 47, sys-path 32 vs 26 -> check-import-roots  (--gates)

`check-import-roots` is NOT in `FAST_GATES`: it is DEFERRED (issue #475 owns widening that fixed
list), so this command does not run it by default — pass `--gates check-import-roots` to include it.


`make lane-preflight` runs the same set the issue-bot runs — the `FAST_GATES` tuple from
`scripts/issue_bot_gates.py`, **imported, never restated** so the "one list" property of #475 holds
and adding a gate stays a single edit — and prints one line per gate plus a final verdict.

Two properties this adds over `make issue-bot-gates`:

- **It reads the would-be-pushed head, not just the working tree.** A lane that verified its change
  against a dirty worktree and then pushed a differently-committed head has failed before (#919's
  trailer attempt was verified against a worktree, not the PR tree). This command fails when the
  working tree differs from `HEAD` on a TRACKED file, so the verdict always describes the tree the
  PR would carry — commit or stash first.
- **Every gate is reported, not just the first failure.** `make issue-bot-gates` stops at the first
  red (it must, it gates a push). A lane wants the whole picture in one run, so `lane-preflight`
  runs them all and prints `<gate>: rc=<n>` for each, then `preflight: OK` or
  `preflight: FAILED (n)`.

  `python3 scripts/lane_preflight.py run`      run the gates (exit 1 if any fails)
  python3 scripts/lane_preflight.py run --gates lint check-import-roots   run a named subset

Stdlib only: the gates it runs are static reads and a container-free `make` call, so it needs no
network and no image — it is safe to run on a bare host, exactly like `make issue-bot-gates`.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# `python3 scripts/lane_preflight.py` puts scripts/ on sys.path, so `from scripts.x import` is
# missing unless the repo root is added first (the engine_bump_rebase.py pattern).
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Import the ONE list. `FAST_GATES` is the fleet's decision about which gates are cheap enough to
# run every time (issue #475); restating it here would let the two drift, so we import it and fail
# loudly if it ever moves out from under us. `from scripts.issue_bot_gates` (not bare) so a test
# importing `scripts.issue_bot_gates` gets the SAME module object — the one-list property is identity.
from scripts.issue_bot_gates import FAST_GATES  # noqa: E402  (the single gate list, issue #475)

REPO = _REPO



def dirty_tracked_files(root: Path) -> list[str]:
    """Tracked files whose working-tree content differs from `HEAD` (the would-be-pushed tree).

    Untracked files are ignored: a lane's scratch/notes must not red the preflight. A TRACKED file
    that differs from `HEAD` means the working tree is not what the PR would carry, so a gate over
    the filesystem would describe the wrong tree — the #919 failure mode.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=str(root), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return []
    changed = []
    for line in proc.stdout.splitlines():
        # porcelain v1: XY <path>; skip renames' "old -> new" arrow, keep the new path
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append(path)
    return changed


def run(root: Path = REPO, gates: tuple[str, ...] = FAST_GATES) -> int:
    """Run every gate, print `<gate>: rc=<n>` for each, and print the final verdict.

    Unlike `issue-bot-gates` (which stops at the first red because it gates a push), this runs the
    whole set so a lane sees every failure in one pass.
    """
    dirty = dirty_tracked_files(root)
    if dirty:
        print("[lane-preflight] the working tree differs from HEAD on tracked file(s):",
              file=sys.stderr)
        for p in dirty:
            print(f"  {p}", file=sys.stderr)
        print("[lane-preflight] FAILED: the verdict would describe an unpushed tree; commit or "
              "stash first so the gates read the would-be-pushed head (issue #1058)",
              file=sys.stderr)
        return 1

    failed = []
    for gate in gates:
        proc = subprocess.run(["make", gate], cwd=str(root))
        rc = proc.returncode
        print(f"{gate}: rc={rc}", flush=True)
        if rc != 0:
            failed.append(gate)

    if failed:
        print(f"preflight: FAILED ({len(failed)}) - {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"preflight: OK ({len(gates)} gate(s))")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run the FAST gates before a host lane pushes (issue #1058)")
    ap.add_argument("cmd", choices=("run",))
    ap.add_argument("--root", default=str(REPO),
                    help="the checkout to run in (default: this repo)")
    ap.add_argument("--gates", nargs="+", default=list(FAST_GATES),
                    help="the gates `run` executes, in order (default: FAST_GATES)")
    a = ap.parse_args(argv)
    return run(Path(a.root), tuple(a.gates))


if __name__ == "__main__":
    raise SystemExit(main())
