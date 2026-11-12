# Proposal: run-shell-injection-env-passing (#2505)

## Why

The semgrep rule `github-actions.security.run-shell-injection` reports four `high`
findings on `main` (measured at `b2e3b1ec4`, re-confirmed at `8a4bc26df`): `run:` steps that
interpolate untrusted GitHub Actions expressions straight into shell text —

- `.github/actions/agent-leg/action.yml:50` (`inputs.shell_keys` into a `make` argument line)
- `.github/workflows/engine-build-pr-trigger.yml:169` (`inputs.branch`, `inputs.base_ref`,
  `github.event_name` into `git fetch`/`rev-parse`/`make` lines)
- `.github/workflows/run-failure-reactor.yml:131` (`inputs.run_id` into a summary `echo`)
- `.github/workflows/review-verdict.yml:289` (`inputs.pr_number`/event fields and
  `steps.*.outputs` into summary `echo`s)

Every site lets a PR-, dispatch-, or issue-controlled string reach a shell on a runner that
holds repo credentials. The lane filed one issue per site (#2468 #2469 #2471 #2491, all closed
`duplicate`) under umbrella #2505, whose fix pattern is one review pass.

## What Changes

One PR rewrites all four sites so every untrusted value crosses into the step through a step-level
`env:` and is referenced as `"$VAR"` inside the shell — the shape these same workflows already use
everywhere else (`RUN_ID`, `PR_BASE_SHA`, `HEAD_REPO`, …) and the precedent set by the #1972 fix in
`ci-verdict.yml`. No step semantics change: same commands, same arguments, same summaries.

- `agent-leg`: `AGENT_SHELL_CHECK_KEYS` crosses as env; the Makefile's `AGENT_SHELL_CHECK_KEYS ?=`
  already reads an exported name, so the target line is unchanged in behavior.
- `engine-build-pr-trigger`: `EVENT_NAME`, `DISPATCH_BRANCH`, `DISPATCH_BASE_REF` env-ize the
  dispatch branch of the step.
- `run-failure-reactor` / `review-verdict` Report steps: env-ize the ids/outputs they echo, and
  they gain `set -euo pipefail` like every other step.

## Acceptance mapping (#2505)

- AC1: all 4 sites rewritten, `make check-workflows` + `make test-unit` green on the PR.
- AC2: the referee stays semgrep: a scan at this head (local `make security-scan TOOL=semgrep`
  and the PR's CI security job) reports zero `run-shell-injection` findings on the four files;
  the post-merge `main` pipeline scan records the clearing run id here automatically via
  `make security-issues-reconcile` — recording is bookkeeping on the merged main, not a gate on
  the merge (the wording was tightened here so the umbrella can close).
- AC3: #2468 #2469 #2471 #2491 stay closed as `duplicate` of #2505.

## Not covered / Out of scope

- DS-0002 (no non-root USER in shipped Dockerfiles) — its own umbrella #2504.
- `run:` interpolation in other workflows that the rule does not flag (they pass today via the
  same env shape or documented `nosemgrep` annotations).
