# force-phrase-instruction-drift: the whole agent instruction surface now qualifies `--force-if-includes` (#2502)

Date: 2026-11-11. OpenSpec change: `force-phrase-instruction-drift`. Issue: #2502.

## What was verified

- The drift, re-measured at `origin/main@8a4bc26df` (the tip after #2498 merged), over
  `agents/**/SKILL.md`, `agents/**/references/**` and `agents/**/prompts/**`, excluding the
  `llgenie-pr-merge-conflict` lane (it carries the canonical #1960 wording): **55 hits across 47
  files, 27 of them unqualified** — a line carrying the flag with no ancestor/amend/integrate/
  rejection qualification within ±2 lines. #2451 scoped the 20 rebase-at-worktree-start files; the
  same phrase class lives on in lane SKILLs, references, and the orchestrator prompt.
- Adjudication (table in `openspec/changes/force-phrase-instruction-drift/proposal.md`): 36 FIX
  sites rewritten to the canonical vehicle (plain `--force-with-lease` after a fresh fetch; the
  flag only for amend/integrate pushes whose remote tip is an ancestor of the new head), 10
  KEEP-QUALIFIED sites keep the flag and gain an explicit ancestor qualification, 9 KEEP sites
  already teach it inside the sanctioned ancestor/amend case. Includes the inverted teaching in
  `check-pr-acceptance-writeback-dispatch.md` ("require `--force-if-includes` not
  `--force-with-lease`") and the "amended **or re-cut** head" teaching in
  `worktree-and-push-hygiene.md`, both corrected.
- After the corrections, the same scan reports **29 hits across 24 files, 0 unqualified** (the
  remaining occurrences sit inside sentences that name the ancestor rule, including corrective
  sentences that cite the flag as the rejected vehicle).
- The rule is now gated: `tests/test_force_phrase_instruction_surface.py` scans the live surface
  (red on any unqualified occurrence), proves the check is not vacuous against planted fixtures
  (`tests/fixtures/force_phrase_instruction_surface/`: the stale tuple reds, the qualified form
  stays green), and honours a documented file-level allow-list
  (`tests/fixtures/force_phrase_allowlist.json`, empty at landing).

## Current status

OpenSpec `force-phrase-instruction-drift` validated. The PR carries the 47→24-file instruction-surface
corrections plus the hygiene test; the measured before/after pair above is the AC record.
