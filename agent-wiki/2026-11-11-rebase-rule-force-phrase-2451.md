# rebase-rule-force-phrase: the rebase push teaches plain --force-with-lease (#2451, #2498)

Date: 2026-11-11. OpenSpec change: `rebase-rule-force-phrase`. PR: #2498. Issue: #2451.

## What was verified

- The contradiction, measured at `origin/main@23faf955`: the rebase-at-worktree-start line offered
  "`--force-with-lease`/`--force-if-includes` after a fresh fetch" while the same file's
  #1960-corrected force-push line (line 31) states a rebased push must use plain
  `--force-with-lease` because a rebased head does not contain the old remote tip and
  `--force-if-includes` would rightly refuse it. The stale tuple sat in 20 files: canonical
  `agents/standing-rules.md:43`, all 13 `agents/*/SOUL.md` rebase blocks, the pr-rebase splice
  source `references/standing-rules.md`, and 5 per-lane `references/rebase-at-worktree-start.md`.
- The fix: one byte-identical phrase replacement in exactly those 20 files (one occurrence each,
  no variant spellings in scope — scanned programmatically): "plain `--force-with-lease` after a
  fresh fetch (#1960: a rebased head does NOT contain the old remote tip, so
  `--force-if-includes` would rightly refuse it)". Amend/integrate pushes keep the #1960 line's
  own sanction of `--force-if-includes`; no other rule text moved.
- AC2 grep at the new head over the scoped files is CLEAN.
- Rulebook tests: `tests/test_agent_profiles.py` and `tests/test_pr_hygiene_sync_line.py` green at
  this head (188/189 in scope). The single failure —
  `test_rebase_lane_scripts.py::test_the_revert_detector_catches_a_revert_and_clears_a_restored_tree`
  — was reproduced byte-same at `origin/main@ac0cd6736` in a detached probe worktree (the harness
  diffs `master` while this host's git inits `main`); it is pre-existing, host-only, and filed
  separately as #2497 — not folded into this docs change.

## Current status

OpenSpec `rebase-rule-force-phrase` validated. PR #2498 carries the 20-file rulebook fix; tasks 1–3
ticked at this head, 4 after preflight.
