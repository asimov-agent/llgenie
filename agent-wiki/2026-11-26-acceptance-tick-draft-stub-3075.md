# 2026-11-26 — acceptance-tick readers refuse draft-stub proof clauses (issue #3075)

## What was verified against the issue

- The issue's measured symptom was re-measured live before any code: `git log origin/main -1 --format=%B 53a56da90`
  (the merged PR #3035 squash) carries 3 ticked acceptance lines whose `(proven: …)` clauses end in the draft
  stub — `(proven: gh api …/blobs/<40-hex> rc=0 PLACEHOLDER)` ×2 and `(proven: rc=0, engine-build run at head
  PLACEHOLDER)` ×1 (measured 2026-11-26, same numbers as the issue body).
- `scripts/check_pr_acceptance.py` gained a shared `DRAFT_STUB` whole-word regex (`PLACEHOLDER`, `HEADSHA`,
  `MAINSHA`) and `_is_provable_tick` consults it BEFORE the `RUN_ID` shortcut: a ticked box whose clause carries
  a stub reports `tick-unprovable` (red) whatever run token or sha sits beside it. The reader previously passed
  the blob-shape residue because `RC_SHA` + a 40-hex blob token satisfied the proof heuristic.
- `scripts/check_pr_hygiene.py` gained `_COMMIT_PROVEN_STUB`, a `(proven: …)`-scoped scan, and a new
  `commit-tick-draft-stub` finding in `commit_text_findings`, so the commit-text mirror gate (and the
  `auto_merge.commit_checkbox_hold` merge lane that reads the same findings) refuses a squash whose acceptance
  mirror cites a stub — the exact route `53a56da90` took onto `main`. The scan is scoped to proven clauses:
  prose that merely NAMES the stub word is not this gate's business (pinned by test).
- Both halves pinned with tests built from the measured clause shapes: 3 new acceptance cases (blob-shape ×2 +
  the engine-build clause, a stub-carrying `run=` tick, `HEADSHA`/`MAINSHA` variants, and a green control — the
  identical blob clause with a real tree sha stays provable) and 4 new hygiene cases (the exact #3035 squash
  text refused; the same text with real proof passes; prose-only mention not flagged; the merge lane defers on
  it). Targeted run: `python3 -m pytest tests/test_check_pr_acceptance.py tests/test_pr_hygiene_commit_checkboxes.py`
  rc=0, 92 passed.
- `make openspec-validate NAME=acceptance-tick-draft-stub-3075` rc=0 for the change (`acceptance-tick-proof`
  spec delta with the blob-shape, commit-text, and real-proof scenarios).

## Key decisions

- Refusal, not restamp: the lane must supply the measured proof; rewriting commit text automatically would
  re-introduce the #3035 author-drift the mirror rule exists to prevent. The producer-side automation (a
  commit-text mode for the PR-body-only restamp seam `scripts/engine_bump_restamp.py`, issue #3054) is filed
  as side issue #3076.
- The already-landed `53a56da90` text is NOT rewritten — history rewrite is out of bounds per AGENTS.md; the
  fix closes the reader so no future wave can re-land it.
- Case-sensitive whole-word stub set (`PLACEHOLDER|HEADSHA|MAINSHA`) — the draft placeholders the stamp
  tooling itself emits; lower-case prose like "placeholder text" stays out of the gate's scope.

## Current status

- Change `acceptance-tick-draft-stub-3075` fully implemented on `feat/acceptance-tick-draft-stub-3075`; all
  tasks ticked; issue #3075 acceptance criteria ticked with replayable proven clauses at the pushed head;
  PR open against upstream `main` with `closes #3075` and the `#3076` Not-covered pointer.
