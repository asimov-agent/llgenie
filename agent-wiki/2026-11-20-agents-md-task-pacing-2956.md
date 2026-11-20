# AGENTS.md carries the host-side task-pacing rule + the #2526 gate bullet

Date: 2026-11-20. Lane: `feat/agents-md-task-pacing-2956`. Issues: #2956 (pacing rule),
#2527 (folded by owner decision).

## What was verified against the spec

- `AGENTS.md` gains a new section **Host-side task pacing (MANDATORY, durable)**,
  placed immediately after the "Git workflow — feature branch + PR (MANDATORY)"
  section. It names all four mandated behaviors: one issue/PR at a time; never
  foreground-wait on a CI pipeline; the CI wait is a background watching task
  (poll loop with completion notification); start the next issue immediately and
  re-poll the board until every PR is green and armed. Matches the owner mandate
  restated in chat on 2026-11-20.
- `AGENTS.md` §"Every workflow file is validated before it can merge" gains the
  #2526 gate bullet: per-file start-surface classification, R1 explicit top-level
  `permissions:` (`write-all` refused), R2 `pull_request_target` ban, R3 the
  `github.triggering_actor` guard outside `run:` script text or a fixed-point
  `workflow_run` roster derivation (cycles are not trust), internal-only triggers
  platform-restricted, zero-exemption fleet state. Wording follows the
  `docs/BOTS.md` #2526 paragraph (same three rules, same fleet state).

## Key decisions

- Protected-file consent: the owner answered both approval questions directly in
  chat on 2026-11-20 (apply the pacing section; fold the #2527 bullet into this
  lane). The earlier #2527 approval prompts had timed out — silence was treated
  as no consent, so the edit waited for the explicit yes.
- Fold: #2527's deferred bullet ships in this lane instead of its own; the PR
  closes both issues (`closes` per issue, on separate lines).
- Hindsight lane: the owner voided it (2026-11-20) — no open Hindsight-memory
  issues remain (search `hindsight state:open` = 0); #2945 stays closed.

## Current status

Branch carries the OpenSpec change `agents-md-task-pacing` (proposal, spec, tasks),
the two `AGENTS.md` additions, this entry and its `docs/changes.d/` fragment.
`make check-docs`, `make lint`, `make openspec-validate`, `make lane-preflight`
run green at the lane head before push.
