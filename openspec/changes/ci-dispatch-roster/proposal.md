# Change: CI dispatch roster in the discipline rule

## Why

The CI-discipline section that landed with `ci-discipline-gate` (#2701/#2704) bans starts with
"never manually starts a CI pipeline. No `gh run rerun`, no `gh workflow run` /
`workflow_dispatch`". As written it is a blanket ban: it does not distinguish the principals the
owner explicitly allowed (issue #2718) — **the owner, a collaborator, and GitHub itself (the
Actions bot) may start a `workflow_dispatch` CI job**. What stays forbidden is queue-pumping by
the automated agent: reruns and requeue loops.

## What Changes

- `AGENTS.md` CI-discipline bullet rewritten: a CI pipeline starts from a GitHub event, **or from
  a dispatch a permitted principal starts — the owner, a collaborator, and GitHub itself (the
  Actions bot)**; the automated agent never dispatches or pumps (no `gh run rerun`, no requeue or
  re-trigger loops; a wedge is fixed by pushing a commit).
- `scripts/check_ci_discipline.py::AGENTS_PIN_PHRASES` re-pinned: the roster phrase
  (`owner, a collaborator, and GitHub itself`) and the queue-pumping ban (`gh run rerun`) replace
  the blanket-ban phrase (`never manually starts a CI pipeline`).
- The `ci-discipline` capability spec gains a MODIFIED requirement naming the roster.

## Impact

- Affected specs: `ci-discipline` (MODIFIED: the discipline rule lives in the repo rules file and the gate pins it)
- Affected code: `AGENTS.md` (one bullet), `scripts/check_ci_discipline.py` (constants)
- No workflow file changes; no Makefile changes.
