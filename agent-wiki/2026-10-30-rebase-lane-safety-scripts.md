# The rebase lane's safety scripts, executed at last

**Issue:** [#1116](https://github.com/asimov-agent/llgenie/issues/1116) · **Closes:** #1060 ·
**PR:** [#1117](https://github.com/asimov-agent/llgenie/pull/1117)

## What was verified against the spec

This lane's pre-push verification and its salvage audit existed only in the live profile, so no
reader of the tree could see what a rebase push was checked against. Two scripts are now versioned
under `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/`, executable and
shell-syntax clean:

- `post-rebase-verify.sh` — nine assertions before a push: clean worktree, no committed conflict
  markers, every changed `.py` parses, every changed `.json` parses, `CHANGES.md` equals a fresh
  render, census, linefeeds, base is an ancestor of HEAD, and a clean `merge-tree` against the base.
- `salvage-audit.sh` — the four-bucket branch/worktree census, read-only by construction.
- `salvage-four-bucket.py` — the same census at the granularity a prune decision needs:
  `merged-and-clean` / `merged-but-dirty` / `unmerged-with-a-PR` / `orphan`, with an
  *added-path* test for "content exists only here" (a sha-diff is meaningless for squash-merged
  work, which is how a first pass over-reported unique branches by 20 instead of 6). It also
  tests whether an orphan's added paths are all carried by an open PR, because a scratch branch
  whose content is reviewable elsewhere loses nothing when deleted.

## Decisions taken

**Executing the shipped artifact, not the profile copy, found a defect no gate could see.** The
scripts had only ever been run from the profile. Running the tree copy for the first time printed
`base=refs/rem` — `${BASE:0:8}` truncates a *ref* argument instead of resolving it, so the tool
misreported the base it had verified against. A verifier that misnames its own subject is worse than
no verifier, because it produces confidence rather than a gap. Fixed by resolving the argument, so
both a ref and a sha report `base=ddcd2323`.

**The audit's one `rm` is fenced, because a read-only tool must be provably read-only.** The script
printed "Nothing was deleted, pruned or removed" while carrying an unqualified
`trap 'rm -rf "$tmp"' EXIT`. That was a temp-dir cleanup and never dangerous, but a reviewer
grepping for a destructive verb in a script whose whole contract is read-only stops on that line and
cannot tell the two facts apart. It is now fenced twice — the path must exist *and* match mktemp's
own `/tmp/salvage-audit.*` pattern — with a negative control showing a repository path is refused.

**A sha-diff is the wrong instrument for "does this branch hold unique work".** A first pass over
160 branches using `git diff --stat main...<tip>` returned 133 UNIQUE. The control was a replay of
#999, a PR that had **merged**: it reported "86 files changed, +10568" by sha-diff, because a
replay's commits are not patch-identical to the squash that landed them. The correct rule, already
in the script, asks whether the branch **adds a path main has never held**. Under it the answer is
6 UNIQUE branches, of which two are byte-identical duplicates.

## Generator defect pinned

`scripts/host_bot_capabilities.py` emitted the `## Tools` block with no preceding blank line, so any
skill it stamped failed `ci-lint`. `tests/test_host_bot_capabilities.py` gained a case that fails
without the fix (1 failed → 6 passed); re-running the generator over an already-stamped file is now
a no-op rather than a corruption.

## What was left open

The live profile still carries a duplicate `skills/development/llgenie-pr-rebase/`, which
`check_agent_profiles` reports as `absent-from-tree`. That is host state, present on clean `main`
too, and removing it is the owner's call — not a repository change.
