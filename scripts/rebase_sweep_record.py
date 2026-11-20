#!/usr/bin/env python3
"""Post the rebase sweeper's own sweep summary onto its record target (issue #2950).

The sibling of `scripts/auto_merge.py recheck --record` (issue #2652). The `rebase-bot` lane's
drain loop measures dispatched/rebased/failed across its iterations and writes the deferral and
failure lines it collected to a file; this script assembles EXACTLY ONE comment:

    [rebase-sweep <UTC-stamp>] dispatched=<n> rebased=<n> deferred=<n>
    - PR #<n>: <reason>

and posts it to the record issue. The counts are the decisions THIS lane run took, so a passing
sweep and a stalled one are distinguishable by reading the tracker (#2652's whole point). A quiet
pass (all zeros) records itself too; `--dry` prints instead of posting; no `--record` posts nothing.
The per-PR claim/done markers on the PRs themselves are another script's business and untouched.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from proc import run_ok  # noqa: E402  the ONE subprocess policy seam (issue #797)

FIRST_LINE = "[rebase-sweep {stamp}] dispatched={dispatched} rebased={rebased} deferred={deferred}"


def _gh(gh: str, args: list[str]) -> str:
    proc = run_ok([gh, *args])
    if proc.returncode != 0:
        print(f"[rebase-record] gh {' '.join(args[:2])} failed rc={proc.returncode}: "
              f"{proc.stderr.strip()[:300]}", file=sys.stderr)
        return ""
    return proc.stdout


def summary(dispatched: int, rebased: int, lines: list[str]) -> list[str]:
    """Assemble the record body. Every line the lane hands over IS a deferral to the next run:
    the sweep's `deferred=#<n>` PRs and the picks that failed, so the deferred count is the
    number of (deduped) lines. `dispatched = rebased + failed` is checked in main()."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    first = FIRST_LINE.format(stamp=stamp, dispatched=dispatched, rebased=rebased,
                              deferred=len(lines))
    return [first, *lines]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rebase_sweep_record")
    p.add_argument("--gh", default="gh")
    p.add_argument("--repo", required=True)
    p.add_argument("--record", type=int, default=None,
                   help="post the sweep summary on this issue (issue #2652, the rolling tracker)")
    p.add_argument("--dispatched", type=int, required=True,
                   help="PRs the sweep picked this run (rebased + failed)")
    p.add_argument("--rebased", type=int, required=True)
    p.add_argument("--failed", type=int, required=True,
                   help="picked and not rebased; deferred to the next run")
    p.add_argument("--lines-file", default=None,
                   help="file of '- PR #<n>: <reason>' lines for deferred/failed PRs")
    p.add_argument("--dry", action="store_true", help="print the record instead of posting it")
    a = p.parse_args(argv)

    lines: list[str] = []
    if a.lines_file:
        try:
            with open(a.lines_file, encoding="utf-8") as fh:
                lines = [l.rstrip("\n") for l in fh if l.strip()]
        except OSError as exc:
            print(f"[rebase-record] cannot read {a.lines_file}: {exc}", file=sys.stderr)
            return 1
    # The lane may hand the same deferral once per sweep iteration (each iteration re-reads the
    # board); the record names each deferred PR once.
    lines = list(dict.fromkeys(lines))
    if a.dispatched != a.rebased + a.failed:
        print(f"[rebase-record] inconsistent counts: dispatched={a.dispatched} != "
              f"rebased({a.rebased}) + failed({a.failed}); refusing a record that miscounts",
              file=sys.stderr)
        return 1
    body = summary(a.dispatched, a.rebased, lines)
    if a.dry:
        print("[rebase-record] --dry: the record would read:")
        print("\n".join(body))
        return 0
    if not a.record:
        print("[rebase-record] no --record target: nothing is posted")
        return 0
    posted = _gh(a.gh, ["issue", "comment", str(a.record), "--repo", a.repo, "--body", "\n".join(body)])
    if posted == "" and not a.dry:
        return 1
    print(f"[rebase-record] sweep record posted on #{a.record}: {body[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
