# 2026-11-16 — skill-size trio slimmed under the 100,000-char cap (issue #2114)

OpenSpec change: `skill-size-trio-over-cap`. Issue: #2114 (body corrected to the re-measured trio).

## What was verified

- Re-measure at fetched `origin/main` `58db552b7`: over-cap trio is engine-improver 106,390 chars,
  pr-rebase 104,616, planner-bot-orchestration 102,325; the filed body's ci-pipelines file is 96,513 —
  already under the cap with no exemption entry (it was 103,203 at `c3f3b2ac`).
- #2084 method applied per file: TREE copy as base, largest self-contained sections moved VERBATIM to
  `references/` (engine: test/CI-refactor section → `test-ci-refactor-method.md`, 46,573 chars;
  pr-rebase: fleet-orchestration lane side → `fleet-lane-side.md`, 19,138; planner: two filter/classifier
  sections → `filters-and-classifiers.md`, 8,038), each linked by a pointer paragraph left in place.
- Distinct-line subset proof printed `LOST: 0` for all three (pre-change body lines ⊆ slim body ∪ refs).
- Post-slim bodies: 60,165 / 85,726 / 94,626 chars — all under `SKILL_MAX_CHARS = 100_000`.
- `tests/fixtures/skill-size-exceptions.json` emptied (note rewritten to record #2114 closing the record).
- `make check-agent-profiles` reports zero `skill-size`/`skill-size-exemption-stale` findings; its remaining
  findings are the host's pre-existing tree↔live drift (also red identically at `origin/main`:
  1 `absent-from-tree`, 5 `live-lines-missing`), tracked by #928/#1079/#2090.
- `make check-agent-profiles-ratchet` rc=0.

## Key decisions

- AC4 was re-scoped after measuring the full check at `origin/main`: the size findings are the AC; the
  drift findings are host state this change neither creates nor is allowed to paper over (no live→tree copy).
- The live copies of all three files are byte-identical to the `origin/main` blobs, so the post-merge
  tree→live `make sync-agent-profile` (asserted by the PR body's three `SYNC:` lines, #1724) propagates the
  slimmed bodies without destroying any live-only content.

## Current status

Branch `feat/skill-size-trio-over-cap` carries the OpenSpec change + the three slimmed skills + the emptied
record; gates (openspec-validate, check-agent-profiles size findings, ratchet, test-unit, lane-preflight) are
proved at the branch head before the PR.
