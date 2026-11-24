# Engine-bump PR bodies now render through one seam the PR gates accept (issue #3050)

Date: 2026-11-24. Issue: #3050. OpenSpec change: `engine-bump-pr-body`.

## What was verified
- The 2026-11-23 engine-bump wave opened 7 PRs (#3029–#3035) and all 7 are structurally red: `guard` fails
  at `make check-pr-openspec-change` ("the PR diff adds no OpenSpec change file and the body names no
  existing change") and `scope` fails at `make check-pr-acceptance-form` ("no `## Acceptance criteria`
  checklist"), so all 7 sit at `mergeStateStatus=BLOCKED` and `ci-verdict` reddens 7/7.
- Root cause measured in the live body of PR #3030 (head `20b3f030`):
  `OPENSPEC: publish-changed-pin-images## Documentation review`. The bump step composed the body with
  `body="$(printf '%b' "${body}" '\n')$(cat params-review-section.md)"`, and command substitution strips
  trailing newlines — so the documentation-review heading glued itself onto the change name, and
  `OPENSPEC_REF` (`^OPENSPEC:\s+([A-Za-z0-9_-]+)\s*$`) read nothing. `openspec/changes/publish-changed-pin-images/`
  is ACTIVE on `main` (proposal + specs + 12 ticked tasks), so the gate's "names no existing change" wording
  sent the producer down the wrong path; the same bodies carried no acceptance checklist at all, and their
  commit messages carried no ticked mirror for `make check-pr-commit-checkboxes` (issue #2519).
- The fix is one composer: `scripts/engine_bump_pr_body.py` behind `make engine-bump-pr-body`
  (`mk/engines.mk`), which joins sections through a list (no section can steal another's trailing newline),
  emits the `OPENSPEC:` line last with nothing after the change name, writes the `## Acceptance criteria`
  checklist whose `- [x]` items carry clauses `check_pr_acceptance._is_provable_tick` accepts (the lane's own
  run id + replayable make commands), and writes the same block under `## Acceptance:` for the commit message.
  The workflow calls the make target and passes the mirror as a third `-m` paragraph.
- Gate wording improved (not relaxed): `check-pr-openspec-change` now names the shape it saw — a line that
  does not parse, a name that is not an ACTIVE change, or no line at all.
- Tests: `tests/test_engine_bump_pr_body.py` rewritten to the new seam (13 passed) — the #144/#583 bash-slice
  assertions (real newlines, hard-fail paragraph, dependency line, `bash -n` on the step) keep their meaning
  and the #3050 regressions are pinned (glued reference survives, checklist provable, commit mirror required,
  inline composer banned). `tests/test_pr_hygiene_openspec_change.py` gained the three finding shapes
  (15 passed). The 12 adjacent engine-bump/PR-gate/workflow suites ran green together (265 passed).

## Key decisions
- Name the ACTIVE change the lane implements against (`OPENSPEC: publish-changed-pin-images`) rather than mint
  a throwaway OpenSpec change per weekly pin bump: the gate accepts either an `openspec/changes/` file in the
  diff or a body line naming an ACTIVE change, and a per-bump dir would add noise without adding a spec.
- Proven clauses cite the lane's `gh run` id, which exists before the commit does, so the same ticked block can
  sit in the PR body and in the squash-bound commit text (issue #2519 three-mirror rule).
- "The next wave shows guard+scope green" is NOT verifiable from this branch — it is a post-merge live read, so
  it is filed as its own linked issue (#3053) instead of being claimed here.

## Current status
Branch `feat/engine-bump-pr-body` carries the OpenSpec change first, then the composer, the make target, the
workflow seam, the gate wording and the tests. `make openspec-validate`, the engine-bump/gate suites,
`make test-unit`, `make lane-preflight` and the read-only `make ci-monitor` snapshot are proven at the pushed
head before the PR to `asimov-agent/llgenie:main` closes #3050; the existing red bump PRs #3029–#3035 are left
to their lane (no queue-pumping), and `make post-merge-live-check` plus the next wave's `guard`/`scope` verdicts
(issue #3053) are the landing record after the merge.
