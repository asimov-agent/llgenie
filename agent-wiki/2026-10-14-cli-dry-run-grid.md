# 2026-10-14 — the installed launcher's dry-run argument grid (issue #236)

## The gap

`ci-install-dry` ran `$HOME/bin/llgenie --dry` — **bare**, one invocation, no arguments —
and every (arch, vram, ram) dry run in the unit stage drives `scripts/llama_serve.py`, not
the installed wrapper. `tests/test_health.py` does run the installed launcher, but it
**serves** on the runner's own backend (no `--dry`, no mocked grid), and
`test_install_published.py`'s `--pick --auto` runs only in the published path. So the
wrapper a user runs had no test that passed it any argument at all.

## What was verified (real, in `llgenie/test:latest`)

After `make ci-install-run` installed the launcher into the CI home:

- `make ci-install-dry-args` → **48 passed in 7.20s**: the `--matrix` flag form for
  5 architectures × 3 vram × 2 ram, the positional form for each architecture, the
  flag-beats-positional precedence, `--pick --engine --dry`, bare `--dry`, `--engines`,
  `--trend`, `--help`, and the invalid-value contract (`--arch bogus`, `--vram abc` each
  exit non-zero naming the problem).
- **The demonstration the issue asked for**: a copy of the installed wrapper with `"$@"`
  dropped makes the named test FAIL. Measured behaviour of that broken wrapper: with no
  arguments the launcher falls through to the DEFAULT path and starts **downloading a
  model** (`0.0% (0.00/1.27 GB) attempt 1`) — it does not exit. So the test's 30s budget is
  the guard, and the "model root stays empty" assertion catches a wrong-path download even
  if it completes. Restoring the wrapper: the same case passes in 0.17s.

## Decisions worth recording

- **`DRY_RUN_TIMEOUT = 30`, not `hf_auth.TOP_TIER_DRY_RUN_TIMEOUT`.** The repo already has a
  named dry-run budget for CLI subprocess tests, but that one accommodates a Hub 429 wait.
  These cases are local (a one-model smoke registry, ~0.2s each with a warm cache) and the
  failure mode of a wrong invocation is a *download*, so waiting is the wrong behaviour:
  a run that does not answer promptly must fail.
- **No skip on a missing launcher.** The test fails loudly naming `make install`, because
  "the installed command" is exactly what it exists to test (AGENTS.md's no-skip rule).
- **One stage, chained.** `ci-install` chains `ci-install-run` → `ci-install-dry` →
  `ci-install-dry-args` → `ci-install-uninstall`, so the pipeline job still runs ONE
  `make ci-install` and no workflow step was added.
- **The wrapper-vs-entry-point agreement test** is the other half of the guard: it compares
  the installed launcher's `--matrix` answer (header + offered links) with
  `scripts/llama_serve.py`'s for the same mocked host, so a wrapper that mangles arguments
  answers differently instead of plausibly.

## Status

OpenSpec change `cli-dry-run-grid`, branch `feat/cli-dry-run-grid`, PR against
`asimov-agent/llgenie` (issue #236).
