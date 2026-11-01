#!/usr/bin/env python3
"""A proof run must bind to the PR head it is cited for (issue #1293).

The strongest evidence a lane hands a reviewer is a build-and-verify run that went green at a named head.
But nothing binds that run's ``head_sha`` to the PR's *current* head before the proof is accepted: an engine
cell that proved the tree at ``abc1d3ac`` reads as green for a later push the run never saw, so a cheap board
reader treats \"run id + verdict\" as binding when it is a claim about time. This gate refuses to let a
superseded proof count as current-head evidence.

Usage
  python3 scripts/bind_proof.py --pr <n> --run <id> [--run <id2> ...] [--repo owner/repo]
  python3 scripts/bind_proof.py --pr <n> --run <id> --fixture f.json   # offline (the tests seed this shape)

Exit codes
  0  every cited run's head_sha == the PR's current head sha (prints the sha it bound to)
  1  at least one cited run's head_sha != the PR head (prints \"superseded proof at <old sha> …\")
  2  bad invocation (no --pr, no --run, unreadable fixture, a run id missing from the fixture map)

The fixture shape is the one the live path reads, keyed by the quoted run id:
  {"pr_head": "<sha>", "run_heads": {"<run id>": "<sha>", "<run id2>": "<sha>"}}
A run head that cannot be measured — a gh api failure, an unreadable fixture, or a fixture that lacks a
requested key — is bad invocation: the gate cannot run, so it exits 2, never a forgivable void.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _fail(message: str) -> int:
    """Exit 2 (bad invocation): a gate that cannot measure its input proves nothing."""
    print(f"[bind-proof] FAIL: {message}", file=sys.stderr)
    return 2


def _gh(args: list[str], repo: str) -> str:
    """Shell `gh api` and return stdout; a failed read is exit 2 (bad invocation), never a forgivable void."""
    proc = subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["gh", "api", f"repos/{repo}/{args[0]}", *args[1:]], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[bind-proof] FAIL: cannot read {args[0]} "
              f"({proc.stderr.strip() or 'gh returned no error text'})", file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout.strip()


def pr_head(repo: str, number: int) -> str:
    return _gh([f"pulls/{number}", "--jq", ".head.sha"], repo)


def run_head(repo: str, run_id: str) -> str:
    return _gh([f"actions/runs/{run_id}", "--jq", ".head_sha"], repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "bind a proof run to a PR head").splitlines()[0])
    parser.add_argument("--pr", type=int, required=True, help="the PR whose head the proof must bind to")
    parser.add_argument("--run", action="append", required=True,
                        help="a proving run id (repeatable for several runs)")
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--fixture", default=None,
                        help="read {pr_head, run_heads} from this JSON file instead of the API (tests use this)")
    args = parser.parse_args(argv)

    if args.fixture:
        try:
            fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"[bind-proof] FAIL: cannot read fixture {args.fixture}: {exc}")
        current = fixture.get("pr_head") or ""
        run_heads = {rid: (fixture.get("run_heads") or {}).get(rid, "")
                     for rid in args.run}
        missing = [rid for rid, sha in run_heads.items() if not sha]
        if not current or missing:
            return _fail(f"fixture {args.fixture} lacks pr_head and every run head "
                         f"(missing: {', '.join(missing) or 'pr_head'})")
    else:
        current = pr_head(args.repo, args.pr)
        run_heads = {rid: run_head(args.repo, rid) for rid in args.run}

    mismatched = [(rid, sha) for rid, sha in run_heads.items() if sha != current]
    if mismatched:
        detail = "; ".join(f"run {rid} proved at {sha}" for rid, sha in mismatched)
        print(f"[bind-proof] FAIL #({args.pr}) superseded proof at old head: {detail}; "
              f"the PR's current head is {current} — re-push the head or re-run the proof", file=sys.stderr)
        return 1

    joint = ", ".join(f"run {rid}={sha}" for rid, sha in sorted(run_heads.items()))
    print(f"[bind-proof] OK #({args.pr}) bound to head {current} ({joint})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
