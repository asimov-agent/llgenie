# run-failure-reactor manual-dispatch verification recorded (issue #1498)

**Implements:** issue #1498 — prove the run-failure reactor works as intended via manual dispatch,
then make the proof durable. PR #2394 adds the verification record at
`docs/CI/run-failure-reactor-verify-1498.md`, so the discipline is reviewable without re-deriving it.

## What changed

The reactor is `workflow_dispatch`-only (issue #2293), so no automatic run can exercise it — the only
way to prove it is a manual dispatch. A durable `docs/CI/` record now captures the 2026-11-09
five-dispatch proof (evidence comment 6735895019): the exact dispatch command, the S1–S5 table (run
ids, run URLs, head shas, verdicts), the checklist results, and the one finding at proof time.

S1–S5 all completed success: S1 not-fire on a success run, S2 not-fire on a cancellation, S3 Route A
→ wake fix-bot (dispatch refused `HTTP 403` on the `BUMP_TOKEN` credential — the reactor handled the
refusal as designed, issue #2086), S4 Route B → one deduped issue (#2378), S5 idempotent re-dispatch
(no duplicate). The single end-to-end gap — S3's fix-bot *wake* could not run at proof time — was a
credential scope, not a reactor defect, and is resolved: issue #2091 CLOSED, `main` `6f3d65b0`
carries the `github.token` dispatch fix per #412 (fix-bot's guard admits the repo bot on a
`workflow_dispatch`, #1571). The record states both the proven and the not-proven honestly.

Record-only PR: no script, test, or reactor logic change; no gate weakened.

## Evidence

- PR #2394, head `4a5ca0c0`, based on `origin/main` at `ffac2227`.
- Verification record: `docs/CI/run-failure-reactor-verify-1498.md` (~70 lines).
- Gates green on the branch: `make lint`, `make check-docs`, `make check-wiring`,
  `make check-pr-hygiene`, `make check-workflows`.
- Original proof: #1498 comment `6735895019`.
