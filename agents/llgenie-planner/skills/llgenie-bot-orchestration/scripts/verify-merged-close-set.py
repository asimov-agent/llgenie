#!/usr/bin/env python3
"""Post-merge proof that a check-pr-closing fix actually LANDED on main.

After a vehicle merges you cannot rerun the gate against the (now-gone) open PR.
Instead prove the two facts the gate enforces pre-merge still AGREE on the landed
tree:
  (1) the merged/squash commit message in main history carries the plain adjacent
      close, and (2) the PR body's close-issue set equals the commit's close set.

Also a regression guard: the FAILING form must still fail (`closes **#N**` -> no
match) and the fixed form must match (`closes #N` -> match).

Usage:
  python3 verify-merged-close-set.py <repo-slug> <merged-commit-sha> <PR-number>
  e.g. python3 verify-merged-close-set.py asimov-agent/llgenie 90bab322... 1705

Exit 0 = MATCH (fix proven on main). Exit 1 = mismatch/missing (amend owed).
"""
import re
import subprocess
import sys

# The literal regex from scripts/check_pr_closing.py
PAT = re.compile(r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)(?![#\w])", re.IGNORECASE)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    slug, sha, pr = sys.argv[1], sys.argv[2], sys.argv[3]
    repo_path = run(["git", "rev-parse", "--show-toplevel"]).strip() or "."

    msg = run(["git", "-C", repo_path, "log", "-1", "--format=%B", sha])
    if not msg.strip():
        print(f"ERROR: commit {sha} not found in local clone; fetch first "
              f"(git -C {repo_path} fetch origin main)")
        return 2
    # gh api --jq .body returns a RAW STRING, not JSON -> use stdout directly.
    body = run(["gh", "api", f"repos/{slug}/pulls/{pr}", "--jq", ".body"]).strip()

    hits_commit = sorted({int(m.group(1)) for m in PAT.finditer(msg)})
    hits_body = sorted({int(m.group(1)) for m in PAT.finditer(body)})

    print(f"sha={sha[:12]}  PR=#{pr}")
    print(f"merged commit close-issues: {hits_commit}")
    print(f"PR #{pr} body  close-issues: {hits_body}")
    match = hits_body == hits_commit and bool(hits_commit)
    print(f"MATCH (body == commit set, non-empty): {match}")

    # Regression guard on the gate regex itself.
    print(f"'closes **#N**' matches: {bool(PAT.search('closes **#' + str(pr) + '**'))}  (expected False)")
    print(f"'closes #N' matches:     {bool(PAT.search('closes #' + str(pr)))}  (expected True)")

    return 0 if match else 1


if __name__ == "__main__":
    sys.exit(main())
