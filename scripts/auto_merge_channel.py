#!/usr/bin/env python3
"""Which engine merges a head: the `CI` completion or this auto-merge sweep (issue #1227).

`.github/workflows/auto-merge.yml` triggers on BOTH the `CI` workflow and the `ci-scope` workflow. The
scope workflow is the DOCS-CLASS completion: `ci.yml` skips a docs-only diff at the trigger
(`pull_request.paths-ignore`, `scripts/ci_scope.py::DOCS_TRIGGER_IGNORE`), so a docs-only PR has NO `CI`
run at all and its green head would otherwise never fire the merge job — whether the PR is green, armed
and un-held, it sat BLOCKED forever because the only code path to its merge was a run that never existed.

But `ci-scope` runs on EVERY PR (it carries no path filter), and on a code PR it finishes minutes before
`CI` — a scope sweep that decided a mid-flight code PR would defer it with a "Not auto-merged" comment its
own green `CI` completion then contradicts. The ONE fact that separates a docs-only head (this sweep's
job) from a code head (the CI completion's job) is whether a `ci.yml` run exists at the head. This script
answers that, and the merge job lets a scope sweep act only on a head with no CI run.

    python3 scripts/auto_merge_channel.py channel --repo o/r --head-sha <sha> [--gh gh]

Writes the single line `channel=auto-merge` (no ci.yml run at head — this sweep decides) or
`channel=ci` (a ci.yml run exists at head — its completion decides) to `$GITHUB_OUTPUT` when that
variable is set, and prints it otherwise. Stdlib only; the GitHub API only through a `gh` on PATH.

The query is `head_sha` + `event=pull_request` + `path=.github/workflows/ci.yml`, so the scope run AT THE
SAME HEAD does not count as a CI run (it is a different workflow file). A 404 or an unreadable answer is
a LOUD failure, never a "no CI run": a head the API cannot confirm must not be silently decided by a
premature scope sweep (or, worse, never reach a merge at all).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def _gh(gh: str, args: list[str]) -> str:
    """Run `gh`, returning stdout; a non-zero exit is a loud failure, never a skip."""
    done = subprocess.run([gh, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout or "").strip())
    return done.stdout


def ci_run_count(gh: str, repo: str, head_sha: str) -> int:
    """The number of `ci.yml` `pull_request` runs at `head_sha` — the one fact that separates classes.

    `gh api` prints the error BODY on stdout when a call is refused, so the parse must treat anything
    that is not a bare integer as no answer and fail loudly rather than guess "no CI run".
    """
    out = _gh(gh, ["api", f"repos/{repo}/actions/runs",
                   "-f", f"head_sha={head_sha}",
                   "-f", "event=pull_request",
                   "-f", "path=.github/workflows/ci.yml",
                   "-f", "per_page=1",
                   "--jq", ".total_count"])
    try:
        return int(out.strip())
    except ValueError:
        raise RuntimeError(
            f"cannot read the run count for head {head_sha} from `{out.strip()[:120]!r}`") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Which engine merges a head: the CI completion or this auto-merge sweep (#1227).")
    parser.add_argument("command", choices=["channel"])
    parser.add_argument("--repo", required=True, help="owner/repo of the BASE repository")
    parser.add_argument("--head-sha", required=True, help="the finished run's head sha")
    parser.add_argument("--gh", default="gh", help="the gh binary to call (default: gh from PATH)")
    args = parser.parse_args(argv)

    try:
        count = ci_run_count(args.gh, args.repo, args.head_sha)
    except RuntimeError as exc:
        print(f"[auto-merge-channel] FAILED: {exc}", file=sys.stderr)
        return 2
    channel = "auto-merge" if count == 0 else "ci"
    line = f"channel={channel}"

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    # The log says the decision and the number it was made from, so a reader can verify the wiring.
    print(f"[auto-merge-channel] {line} for head {args.head_sha[:8]} ({count} ci.yml run(s)); "
          f"{'this sweep decides' if channel == 'auto-merge' else 'left to the CI completion'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
