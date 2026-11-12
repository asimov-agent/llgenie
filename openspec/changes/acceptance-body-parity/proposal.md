# Proposal: acceptance-body-parity

## Why

A closing PR body's own `## Acceptance criteria` is a copy of the issue's checklist that is never
re-read after creation. The proven ticks land on the issue during the work; the body keeps its
`- [ ]` boxes and merges anyway: auto-merge fires on job-green + `mergeStateStatus == CLEAN` and
never reads body checkboxes. Measured at main `614838fb8` (`gh pr list --state merged --limit 12`
+ regex `^\s*- \[ \]`): 4 of the 12 most recently merged PRs merged with unticked body acceptance
boxes — #2507 (2), #2498 (3), #2496 (3), #2490 (3) — while the issues they closed carried (or
later received) ticked criteria. The reviewer's permanent record therefore reads `not done` under
an issue that reads `done`. GitHub issue: #2511.

## What Changes

- `scripts/check_pr_acceptance.py::acceptance_verdict` gains a blocking finding
  `acceptance-body-lag`: a PR body that closes `#N` with a `- [ ]` under its OWN canonical
  `## Acceptance criteria` section is red. Scope is the canonical section only
  (`_acceptance_items` exact-match, same as the issue side), so a `## Verify` list elsewhere in
  the body is not a criterion copy. The exemption mirrors the issue side: the box named under
  `## Not covered` with a linked work item (`_declared_out_of_scope`).
- The finding is reported from the live close path already used by the `guard` job
  (`make check-pr-acceptance` in PR CI and the verdict lane), so no new workflow or Makefile
  target is needed — the finding set grows.
- `tests/test_check_pr_acceptance.py` proves the five states: closing body with an unticked box
  → blocking; fully ticked mirror → green; `## Not covered` exemption → green; unticked boxes
  outside the canonical section → not a lag; body without a criteria section → closes normally.
- The four measured merged bodies (#2507 #2498 #2496 #2490) are retro-fixed with `gh pr edit`,
  ticking with the proof the issues already carry (issue-side `(proven: …)` lines / merged head).
- AGENTS.md gains the durable lockstep rule; because AGENTS.md is an approval-protected file and
  the write prompt timed out without consent in the implementing session, that text lands through
  the linked companion issue (#2512) once approval is granted. `## Not covered` names it.

## Impact

- Affected specs: none previously required body-side parity; this change adds the requirement.
- Affected code: `scripts/check_pr_acceptance.py`, `tests/test_check_pr_acceptance.py`.
- Affected GitHub state: four merged PR bodies updated; issue #2511 body synced.
