# a ticked acceptance criterion must cite a live-green run and a current head (issue #2288) — 2026-11-09

**Implements:** issue #2288 — a write-back tick on an acceptance box passes the run-id branch of
`check-pr-acceptance` even when the cited run is a RED by-design gate run and the head is no longer
the PR's live head.

Measured live at `main@e34cfd2e` (2026-11-09 evidence audit, posting on #2223): of 8 ticked
write-back issue-PR pairs, 4 cite a `run=` whose `gh run view` conclusion is `failure` — the
by-design `check-pr-acceptance` guard red that fires while the box is still unchecked — and all 8
tick heads differ from the PR's current live head. The four cited runs (`42530742557`, `42508044658`,
`42513135877`, `42155990415`) each conclude `failure` at their head, and every ticked issue
(#2296×3, #2181×6, #2061×1, #1558×1) cites a head the PR has rebased away from.

## What changed

- **`scripts/check_pr_acceptance.py`** — two NEW blocking live-evidence findings, checked per TICKED
  criterion against the PRESENT tree at merge:
  - `tick-red-run`: a cited `run=<id>` whose live `gh run view` conclusion is not `success`
    (a failed/by-design-guard-red run, or an unreadable run) holds the merge — never trusted as proof.
  - `tick-stale-head`: a cited `head=<sha>`/`live=<sha>` that is not the merge-time head holds the
    merge. `--rev` is the staleness referee only when it is a sha (`GIT_SHA.fullmatch`); a bare
    `HEAD`/branch word cannot be a sha to compare against, but the run re-check still runs.
- **`scripts/review_finalize.py`** — `with_live_head` appends the PR's live head as a `live=<sha>`
  twin beside every `head=<sha>` a write-back writes (idempotent), so a rebased tick is visible as
  stale from the issue thread alone (AC2).
- **`tests/test_check_pr_acceptance.py`**, **`tests/test_review_finalize.py`** — green success-run +
  current-head tick; red-run hold; stale-head hold; current-`live=` green; non-sha `--rev` skips only
  the staleness referee; `with_live_head` twin attachment. The fake `gh` fixtures now answer
  `gh run view` so the live re-check runs hermeticly.
- **`docs/BOTS.md`** — documents the new findings and records the 11 measured red-run/stale ticks as
  stale (their four runs all conclude `failure` at `e34cfd2e`).
- **`openspec/changes/acceptance-tick-green-run-and-live-head/`** — the required OpenSpec change.

## Decisions

- **The gate re-verifies live.** `check-pr-acceptance` already reads the linked ISSUE live at merge;
  resolving each cited run's conclusion and the staleness referee is the same live seam, not a new
  code path. An unreadable run is held (never trusted), because a named-but-unreadable run is not
  `success` — evidence is never fabricated from a data gap.
- **Verdict-driven write-back stays.** This change does not weaken the #1644/#1808 verdict gate; it
  makes the evidence a tick writes (run id, head) re-checkable at merge.
- **AC3 is satisfied as "recorded explicitly as stale".** The 11 measured ticks are red under the new
  gate; re-ticking them with a green run or current-head evidence is the write-back seam's job once
  that evidence exists. This change records them as stale and holds them until such a re-tick lands.

Refs: #2288 (this issue), #2223 (the audit it posts on), #1644/#1808 (the write-back seam),
#1858/#1857 (the provability gate it sharpens).
