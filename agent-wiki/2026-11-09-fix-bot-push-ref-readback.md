# 2026-11-09 — the fix-bot outcome comment claims a push only when the API head ref moved (#2370)

**Issue:** [#2370](https://github.com/asimov-agent/llgenie/issues/2370) ·
**OpenSpec:** `ci-bot-pr-body-stamp-at-open` · **Related:** #2050, #2051, #2045, #964

## What was measured

On PR #2161 (`fix/2156-verdict-paginate-no-verdict`) 2026-11-08 the fix-bot posted a
**false "Pushed as one commit" claim**: an actual push never landed. Dispatch chain —
failed run 42455803930 → sweep run **42455823222** (`workflow_run`, posted `bot-claim`)
→ fix run **42455842695** (`workflow_dispatch`). Run 42455842695's fix-job log
(job 128654550769) reads `06:43:43Z` **"The loop ended green with no changes — nothing
to push."** with `changed=0`; the tree-dirty guard made the push step `exit 0`, so no
push was issued. Yet the outcome comment, keyed only on `OUTCOME == success`, posted
**"Pushed `…` as one commit with the owner PAT"** at `06:43:44Z` (PR comment 6718362362).
The PR `headRefOid` at `06:42:28Z` and again at `06:45Z`/`06:47Z` was the identical
`1ac54b7e5d5d9635860effa7b2b73a4089008f28` — **the head never moved.**

This is the "a report is a claim, the ref is the evidence" class (#2050's follow-up): a
green loop verdict, and even the push step's own `pushed` output, are not the fact — the
fact is the PR head ref read **back from the API before and after** the repair.

## What changed

- `.github/workflows/fix-bot.yml`: a new `prehead` step reads the PR `headRefOid` from
  the API **before** the fix loop (`gh pr view --json headRefOid`, the #964 read-back
  discipline); a new `posthead` step (`if: always()`) reads it **after** the push step;
  the outcome-comment gate now claims "Pushed as one commit" only when
  `[ -n "${POST:-}" ] && [ "$POST" != "${PRE:-}" ]` — on top of the pre-existing
  `PUSHED`-empty check. The equal-ref path posts a **non-success** comment naming the
  unchanged head: "the PR head ref did not move (pre `…` == post `…`)".
- `tests/test_bot_stamp_body.py`: `test_fix_bot_claims_a_push_only_when_the_api_head_ref_moved`
  asserts the pre/post API read-back is wired to the comment and gated on `$POST != ${PRE:-}`.
  Guard teardown-verified: with `fix-bot.yml` reverted to the pre-fix take, the new test
  FAILS; restored, all 11 tests in the module pass.

No gate weakened, no `enforce_events` moved, the push guard is intact, and the fix-bot
never merges — a human still reviews the head the comment names.

## Status

PR #2433 (`fix/2370-fixbot-push-ref-readback`) implements this closed against OpenSpec
`ci-bot-pr-body-stamp-at-open`, the active change that owns the
#2050 body-stamp and phantom-push discipline. `pytest tests/test_bot_stamp_body.py -q`
→ **11 passed**; the acceptance write-back that ticks issue #2370's boxes is verdict-gated
(#1644) and lands at merge.
