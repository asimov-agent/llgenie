# 2026-11-09 — the six agent legs share one reusable preflight (issue #798)

## The defect

The six agent bot legs (`fix-bot.yml`, `issue-bot.yml`, `issue-refiner.yml`,
`rebase-bot.yml`, `architecture-bot.yml`, `registry-sync-review.yml`) hand-rolled
the same ordered preflight: `make agent-jev-preflight` (#238), `make
agent-shell-keys-check` (#358) and `make hermes-smoke` (#407), plus the
REDACTED-transcript upload (#359). Measured at origin/main `6f3d65b0`: the JEV
step inline in 8 workflows, the shell-keys step in 8 (a different set), and the
upload block present in all six agent legs. A fix to any preflight had to be
applied to every leg, and a leg that missed one ran unattended without its JEV
check or its credentials proven visible.

## What shipped

- **`.github/actions/agent-leg/action.yml`** — one composite action holding the
  ordered preflight (JEV #238, shell-keys #358, routing-smoke #407 when the leg
  opts in) and the REDACTED-transcript upload (#359). `phase: preflight` runs the
  checks, `phase: upload` publishes the redacted transcript; input IDs use
  underscores (`shell_keys`, `routing_smoke`) because GitHub parses a hyphen as
  subtraction in `inputs.…`. The three preflight steps now exist in exactly ONE
  place in the tree.
- **`.github/workflows/agent-leg.yml`** — the reusable agent-leg `workflow_call`
  (a plain "checkout → preflight → one `make target` → upload" leg), taking the
  leg as inputs: `target`, `skill`, `push`, `timeout`, `transcript`, `shell_keys`,
  `routing_smoke`, with the ceiling and checkout inside its own job because a
  `uses:` caller job may not carry `steps`/`env`/`timeout-minutes` (#882). Added
  to the `workflow-run-exemptions.json` roster with a dated reason: `workflow_call`
  never runs on an event, so a `workflow_run` consumer has nothing to watch (the
  `pipeline` precedent).
- **The six legs now call the composite action** for their preflight and upload;
  their inline JEV / shell-keys / routing-smoke steps are gone.
- **`make check-workflows` now reds an inline preflight**: `check_workflows.py`
  gained `check_inline_agent_preflight`, which refuses a workflow whose steps
  inline BOTH `make agent-jev-preflight` and `make agent-shell-keys-check`
  (instead of calling the composite action), proven by four tests in
  `tests/test_workflows_valid.py`. A lone single call is a different control
  (engine-bump's non-blocking JEV report, search-smoke/issue-dedupe's lone
  shell-keys proof) and is not reddened.
- **`scripts/scrub_log.py` is unchanged.**

## Why the six legs use the composite action, not the reusable workflow

GitHub's `workflow_call` is one whole JOB: a caller job is either `uses:` a
workflow OR carries `steps:` — never both — and jobs cannot share a workspace or
`steps.<id>.outputs`. Every one of the six legs needs seed steps (pick / dispatch /
brief), the leg, and post steps (apply / publish / report) in ONE job, sharing
files (`refine-in.md`, the issue number, the scrubbed log). So the six migrate
through the step-level composite action (the "reusable leg"): the shared preflight
lives once, and each leg's file keeps its own decisions around a call to it. The
reusable workflow is the entry point for a leg that IS a plain preflight→target→
upload — no seed/post steps.

## Verification

- `python3 scripts/check_workflows.py check` → exit 0; `make check-workflows` gate
  names the new rule.
- `tests/test_workflows_valid.py` → 35 passed (4 new, incl. the inline-sabotage
  negative control and the tree-wide "no workflow inlines the pair" assertion).
- `actionlint` over the six migrated legs + `agent-leg.yml` → 0 (only pre-existing
  SC2129 style in untouched blocks).
- `make openspec-validate NAME=reuse-agent-leg` → valid.
- `make lane-preflight` → OK (6 gates); `make test-unit` → green at the branch head
  (run ids recorded on the PR).
