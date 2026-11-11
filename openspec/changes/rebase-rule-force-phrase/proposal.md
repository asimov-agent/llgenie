# rebase-rule-force-phrase

## Why

The rebase-at-worktree-start fleet rule (`agents/standing-rules.md` line 43, issue #1891) still
offers "`--force-with-lease`/`--force-if-includes` after a fresh fetch", contradicting the
#1960-corrected force-push line in the same file (line 31): after a genuine rebase the tracking ref
holds the just-fetched expected value and the rebased head does NOT contain the old remote tip, so
`--force-if-includes` rightly REFUSES the push. A lane following the rebase rule gets its push
refused and may strip the guard to "make it work" — the exact failure class #1960 retires. Measured
at `origin/main@23faf955`: the stale tuple sits in the canonical rule, all 13 `agents/*/SOUL.md`
rebase blocks (byte-exact mirrors), the pr-rebase splice source
`references/standing-rules.md`, and 5 per-lane `references/rebase-at-worktree-start.md` — 20 files,
one occurrence each, no other variants (issue #2451).

## What Changes

- The rebase-at-worktree-start phrase in all 20 scoped files reads
  `plain \`--force-with-lease\` after a fresh fetch (#1960: a rebased head does NOT contain the old remote tip, so \`--force-if-includes\` would rightly refuse it)` —
  plain lease only for a rebase push. `--force-if-includes` stays sanctioned exactly where the
  #1960 line sanctions it (amend/integrate pushes where the remote tip is an ancestor), which this
  change does not touch.
- No other rule text moves: every diff hunk is that one phrase, byte-identical across all 20 files,
  so the SOUL↔standing-rules byte-exact mirror property is preserved.

## Impact

- Modified: `agents/standing-rules.md`, 13 `agents/*/SOUL.md`,
  `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/references/standing-rules.md`,
  5 per-lane `references/rebase-at-worktree-start.md` (ci-pipelines, issse-implementer, planner,
  pr-merge-conflict, pr-reviever).
- Closes GitHub issue #2451.
