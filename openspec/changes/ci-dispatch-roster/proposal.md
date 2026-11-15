# Change: CI dispatch roster — owner, collaborator, and GitHub may start a `workflow_dispatch`; queue-pumping by the agent stays forbidden

## Why

Issue #2702 (owner correction 2026-11-15, spun out of #2701): the CI-discipline section landed with an
absolute ban — "The agent never manually starts a CI pipeline. No `gh run rerun`, no `gh workflow run` /
`workflow_dispatch`" — which as written also outlaws dispatch by the principals the owner does allow.
The owner's real policy is: **the owner, a collaborator, and GitHub itself (the Actions bot) are all
allowed to start a `workflow_dispatch` CI job**; what stays forbidden is queue-pumping by the automated
agent (no `gh run rerun`, no requeue or re-trigger loops). Measured on main `1dcbf4c3ae` at
`AGENTS.md:1442-1443`: the durable section pins `workflow_dispatch` among the forbidden starts, and
`scripts/check_ci_discipline.py::AGENTS_PIN_PHRASES` (lines 97-102) pins the phrase "never manually
starts a CI pipeline".

## What Changes

- **AGENTS.md, one bullet** (lines 1442-1443): rewrite from "The agent never manually starts a CI
  pipeline. No `gh run rerun`, no `gh workflow run` / `workflow_dispatch`, no requeue or re-trigger
  loops" to state the dispatch roster — a CI pipeline starts from a GitHub event, **or from a dispatch
  a permitted principal starts: the owner, a collaborator, and GitHub itself (the Actions bot)** — and
  keep the queue-pumping ban (the automated agent never dispatches or pumps: no `gh run rerun`, no
  requeue or re-trigger loops; a wedge is fixed by pushing a commit). Retired machinery (#2702) stays
  dead.
- **`scripts/check_ci_discipline.py::AGENTS_PIN_PHRASES`**: replace the blanket-ban phrase with the
  roster wording (so the gate pins the roster) plus the queue-pumping ban phrase.
- **`openspec/changes/ci-dispatch-roster/specs/ci-discipline/spec.md`**: MODIFIED requirement on the
  `ci-discipline` capability — dispatch by owner/collaborator/GitHub is a sanctioned start; the agent
  never dispatches or pumps.
- **`tests/test_ci_discipline.py`**: a new hermetic test proves the gate stays green on the tree and
  that the roster wording is what the section carries (the gate's own pin check covers the rest).
- **`agent-wiki/` + `CHANGES.md`**: dated note + index row.

No workflow files change.

## Impact

- Affected specs: `ci-discipline` (MODIFIED)
- Affected code: `AGENTS.md` (one bullet), `scripts/check_ci_discipline.py`,
  `tests/test_ci_discipline.py`, `openspec/changes/ci-dispatch-roster/`, `agent-wiki/`, `CHANGES.md`
