# Reuse the agent leg — one reusable preflight + leg workflow

## Why

The six agent bot legs (`fix-bot.yml`, `issue-bot.yml`, `issue-refiner.yml`,
`rebase-bot.yml`, `architecture-bot.yml`, `registry-sync-review.yml`) hand-roll
the same ordered preflight: `make agent-jev-preflight` (issue #238), `make
agent-shell-keys-check` (issue #358) and, in the legs that reach a routed model,
`make hermes-smoke` (issue #407). Measured on `main`, the JEV step appears inline
in 8 workflows and the shell-keys step in 8 (a different set); the REDACTED
transcript upload block appears in all six agent legs. Four of the six carry the
block byte-identical. A fix to any one preflight has to be applied to every leg,
and a leg that misses a preflight is a bot that runs unattended without its JEV
check or without its credentials proven visible.

## What Changes

- Add one composite action `.github/actions/agent-leg/action.yml` holding the
  ordered preflight — JEV (issue #238), shell-keys proof (issue #358), and the
  Hermes routing smoke (issue #407, run only when the leg reaches a routed
  provider) — plus the REDACTED-transcript upload (issue #359). Those steps then
  exist in exactly ONE place in the tree.
- Add one reusable workflow `.github/workflows/agent-leg.yml`
  (`on.workflow_call`) providing the agent-leg JOB for a plain "checkout →
  preflight → run one `make` target → upload the transcript" leg, taking the leg
  as inputs: `target`, `skill`, `push`, `timeout`, `transcript` (`needs` is the
  checkout shape the caller wants — write vs read-only). A `uses:` job may not
  carry `steps`/`env`/`timeout` (issue #882), so the ceiling and checkout live
  inside this workflow's own job.
- Migrate the six agent legs to call the preflight through the composite action,
  removing the inline JEV / shell-keys / routing-smoke steps. This is the
  migration the ticket's "the reusable leg" means: the ordered preflight lives in
  one artifact, and each leg's file becomes its own decisions (when it runs, what
  `make` target it runs, whether it pushes) around a call to it.
- Extend `scripts/check_workflows.py` so `make check-workflows` REDS on a bot
  workflow that inlines the agent-leg preflight (both `make agent-jev-preflight`
  and `make agent-shell-keys-check` in its steps) instead of calling the reusable
  composite action. Proven by a test in `tests/test_workflows_valid.py`.
- `scripts/scrub_log.py` is unchanged.

## Capabilities

- **agent-leg-reuse**: the agent-leg preflight and transcript upload exist exactly once.
- **agent-leg-gate**: `make check-workflows` reds a bot workflow that inlines the preflight.

## Impact

No runtime behaviour changes: the steps are identical, just relocated into the
composite action and invoked by each leg. Pipeline minutes are unchanged. A fix
to #238 / #358 / #407 / #359 now reaches every leg by construction.
