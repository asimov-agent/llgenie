# 2026-10-23 — a top-tier dry run survives one transient Hub failure

Issue: [#399](https://github.com/asimov-agent/llgenie/issues/399)
PR: (opened by this run; body in `pr-body.md`)
OpenSpec change: `top-tier-dry-run-transient-retry`

## What was red

`macos / top-tier` runs `make ci-top-tier`, which runs the `--download-top-tier --dry`
acceptance cases against the live Hub inside a job every PR waits on. Run 39381961586
(#396 rebased): `tests/test_top_tier_acceptance.py::test_family_dry_run_known_lowend_one_provider`
failed at the zero-exit assertion with `TimeoutError: The read operation timed out`
(8m47s); its unchanged re-run passed, and `linux / top-tier` passed the same tree. The
job's conclusion was decided by Hub latency, not by the diff.

## What was already fixed, and what was not

`_hf_get` now retries a read-phase `TimeoutError` inside the process (#549, `333344c`,
`HF_GET_MAX_ATTEMPTS`). That bounds ONE read. When the in-process budget is spent the
subprocess still exits 1, and the job still rests on the Hub's behaviour during a single
run. #399's own scope is exactly that: the acceptance case shells out to a live read, and
one slow moment reds the PR.

## Fix

- `tests/top_tier_dry_run.py` (new) — `run_dry_run()`: the seam the `--dry` acceptance
  cases shell out through. `TOP_TIER_DRY_RUN_ATTEMPTS = 2` (the run plus one retry), and
  only a Hub **transport** failure is retryable, classified from the child's own stderr
  (`[ERROR] HF API still failing after N attempts`, `TimeoutError`, `URLError`,
  connection resets/errors, `SSLError`, resolution failures, transient 429/502/503/504).
  Anything else is returned on the first attempt, so a regression is never retried into a
  green.
- `tests/test_top_tier_acceptance.py` — both dry-run cases use the seam; the zero-exit
  assertion names the attempt count and the CLI's cause. No assertion was weakened: every
  row/readout assertion is unchanged.
- `tests/test_top_tier_dry_run_retry.py` (new) — real child processes (no mocked
  `subprocess`, no mocked transport).

## Decisions

- Chose the issue's first permitted mechanism (bounded retry inside the PR job), not the
  scheduled-workflow alternative: the retry is testable hermetically, needs no new
  workflow, and keeps the live proof on every PR. The issue's "What done looks like"
  allows either; the other is recorded as not covered in the proposal.
- The bound is stated at 2 attempts so a failing first run cannot double the job's
  60-minute budget the way a larger bound would.

## Verification

- `python3 -m pytest tests/test_top_tier_dry_run_retry.py -q` — 8 passed.
- The exact command `make test-unit` runs (`python3 scripts/unit_tests.py run`, on this
  host because the leg has no Docker daemon): **5069 passed, 6 deselected** in
  16m46s — the whole hermetic suite, including the new file, which the aggregator
  selects (`python3 scripts/unit_tests.py list` names
  `tests/test_top_tier_dry_run_retry.py`).
- `make test-top-tier` (host-side, real, no mocks, the target that runs the changed
  acceptance file): **15 passed** in 216.12s.
- Falsified: with a transiently failing child, `run_dry_run(attempts=1)` returns
  `returncode=1` — the measured red — while the shipping `attempts=2` returns
  `returncode=0`.
- `python3 scripts/lint_linefeeds.py`, `make check-workflows`, `make check-wiring`,
  `make check-docs`, `make openspec-tasks-check` — all exit 0.
- `make openspec-validate NAME=top-tier-dry-run-transient-retry` — exit 0,
  `Change 'top-tier-dry-run-transient-retry' is valid`, through the change's pinned CLI
  (`@fission-ai/openspec@1.10.0`, the version `openspec/Dockerfile` pins). The leg has no
  container runtime — a daemon started here cannot register a layer
  (`failed to register layer: unshare: operation not permitted`), so the target's
  Darwin/npm branch was selected on this host; the validation is the same pinned binary
  and the same change.
- `make lint` is the one gate not run through the make wrapper: its recipe always runs
  via the test image, which cannot start here. The gate's own command
  (`python3 scripts/lint_linefeeds.py`) exits 0.


## Status

Implemented on the issue's branch, OpenSpec change written, PR body ready. The whole
hermetic suite and `make test-top-tier` are green on this host; `make openspec-validate`
(container-only) is CI's to run, because no Docker daemon is reachable from this leg.
