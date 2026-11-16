# 2026-11-16 — workflow shellcheck cleanup + full-ruleset actionlint gate (issue #329)

## What was verified

- Baseline measured on `main` (`f45268c84`) with digest-pinned `rhysd/actionlint@sha256:b1934ee5…`
  (v1.7.12): 16 shellcheck findings across 12 workflow files + 1 syntax finding. The issue's original
  7-finding list was stale; the live set drove the fix.
- All 16 shellcheck findings fixed: SC2129 grouped `{ …; } >> file` in the eight bot-summary steps,
  SC2086/SC2046 quoting (engine-bump `${ID}` git-add + `${ENGINE}`, stale-branch-cleanup `$(if …)`
  restructured to an explicit if/else on the `make` call), SC2016 printf format moved to double
  quotes with escaped backticks (engine-bump PR-body step), SC2028 `echo`→`printf '%s\n'`
  (semgrep-rules-refresh), SC2209 `ENFORCE="pr"` quoted (security-scan — shellcheck flags bare
  `ENFORCE=pr` because `pr` is a command name).
- Verified locally: `make check-workflows` rc=0 with the chained full-ruleset step; actionlint without
  the ignore reports exactly ONE remaining finding — the `queue` key — proving the ignore is narrow.
- `-ignore` semantics measured: actionlint's `-ignore` is a regex matched against the MESSAGE only
  (labels/paths do not match; slash-wrapped patterns don't match message text either) — the gate's
  pattern is the bare message regex.

## Key decisions

- `concurrency.queue: max` in `engine-build.yml` STAYS (issue #2294: it is what stopped queued
  producers being cancelled; GitHub accepts the key; actionlint 1.7.12 hasn't catalogued it). The gate
  documents the exception as one narrow `-ignore` regex, and a test pins that the ignore is exactly
  one pattern — widening it later must be a filed decision.
- The step is digest-pinned (`ACTIONLINT_IMAGE := rhysd/actionlint@sha256:…`) per the #2235 no-mutable-
  gate-tags discipline, and chained from `check-workflows` via `+$(MAKE)` so every CI lane that runs
  the workflow gate also runs the full ruleset.
- Four wiring tests added to `tests/test_workflows_valid.py` (chain exists, digest pin, single ignore,
  queue key survives); the unit suite cannot run docker, so the tree-wide sweep stays the gate step's
  own job.

## Current status

Branch `feat/workflow-shellcheck-clean`, PR for #329 open (see the PR linked from the issue). Gate
`make check-workflows` green locally; `make test-unit` green on the branch head.
