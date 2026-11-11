# Retiring the four run-shell-injection sites by env-passing (issue #2505)

## What changed

Semgrep's `github-actions.security.run-shell-injection` reported four `high` findings on `main`:
`run:` steps interpolating `inputs.*` / `github.event*` / `steps.*.outputs` expressions straight
into shell text — `.github/actions/agent-leg/action.yml:50`,
`.github/workflows/engine-build-pr-trigger.yml:169`,
`.github/workflows/run-failure-reactor.yml:131`,
`.github/workflows/review-verdict.yml:289` (the four per-site issues #2468 #2469 #2471 #2491,
closed `duplicate` under this umbrella).

Each step now declares its untrusted values in a step-level `env:` and references them as
`"$VAR"` inside the shell — the shape the same workflows already use everywhere else
(`RUN_ID`, `PR_BASE_SHA`, `HEAD_REPO`), the #1972 `ci-verdict.yml` precedent. Same commands,
same arguments, same summaries; the two Report steps gained `set -euo pipefail` like every other
step. For `agent-leg`, the Makefile's `AGENT_SHELL_CHECK_KEYS ?=` reads the exported name
directly, so behavior is unchanged.

## Verification

- Negative control + referee, same pinned image (`semgrep:5954e2aad609`) and ruleset
  (`containers/scanners/semgrep/rules/default.yml`): on the PRE-fix `origin/main` copies of the
  four files the scan reports exactly **4** `run-shell-injection` findings at lines 50, 169, 289,
  131; at the fixed head `make security-scan TOOL=semgrep` reports **0** repo-wide
  (44 findings from other rules, pre-existing and unrelated — the DS-0002 umbrella #2504 owns
  the Dockerfile side).
- `make check-workflows` rc=0. OpenSpec change `run-shell-injection-env-passing` validates.
- The post-merge `main` security pipeline scan records the clearing run id on #2505 via
  `make security-issues-reconcile` (bookkeeping on merged main, not a merge gate — the issue's
  AC2 wording was tightened accordingly).

## Current status

Branch `feat/2505-run-shell-injection` -> PR against upstream main carrying `closes #2505`;
#2468 #2469 #2471 #2491 stay closed as duplicates. The bot-driven lane keeps its dedupe memory:
the umbrella marker stays the body's first line.
