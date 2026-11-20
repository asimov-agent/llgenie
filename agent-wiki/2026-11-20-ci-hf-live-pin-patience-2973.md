# ci-hf-live pin patience: a mid-push manifest is a wait, not a red (issue #2973)

Issue: #2973. PR: pending (feat/ci-hf-live-pin-patience-2973).

## What was wrong (measured on `c9b36b19f`-era main)

`ci-hf-live` reddened three runs in a row (44739963771, 44743185352 verdict cascade,
44749136442) on `test_every_committed_engine_cell_tag_is_published_live` while every pin was
in fact published. The battery runs while the main CI run of the same landing is still in its
image-push stage; the check's single GHCR sweep caught manifests that did not exist YET, reddened
a green main, and poisoned `make post-merge-live-check`. Minutes later the same check was green
with zero code change — a structural producer/reader race (the #178 class), not a publish gap.

## What was verified against the spec

- `scripts/check_engine_pins_published.py::_probe` re-probes only the UNRESOLVED refs, every
  120 s, until ONE bounded deadline for the whole check (never one window per cell — 29 missing
  cells × window would outlive the job). Green the moment a manifest resolves; a genuinely
  unpublished ref reds AT the deadline, and the `[select]` dispatch line (#2561 contract) still
  names it. `check_committed` reads the window only from `ENGINE_PINS_PATIENCE_SECONDS`; unset
  means 0 — every PR lane and local run keeps today's immediate-red (#1622 strictness); a
  non-numeric value prints a WARN and stays impatient.
- `.github/workflows/ci-hf-live.yml`: the `make test-unit-network` battery step carries
  `ENGINE_PINS_PATIENCE_SECONDS: "3600"` (the main pipeline's normal push span); the job
  `timeout-minutes` moved 60 → 105 so a deadline-red is the check's verdict, never a timeout.
- Four hermetic fixtures (`tests/test_check_engine_pins_published.py`, virtual clock — nothing
  real is slept): mid-window publish → green + loud `PATIENCE` line, resolved on the FIRST
  re-probe; never-published → red AT the bounded deadline, 5 re-probes of 6 total probes;
  no-knob → one probe per cell, sleep forbidden (the callable RAISES if called); knob read from
  env + malformed knob loud-and-impatient. `tests/test_ci_hf_live_workflow.py` pins the env
  value and `timeout-minutes ≥ window + 1800 s` headroom.

## Decisions

- Window on the CHECK, not the Makefile or the test: the test injects clock/sleep so the
  boundedness is provable hermetically; the real network test stays untouched and simply
  inherits the window when the workflow env is set — one code path, no fallback.
- 3600 s, not a bigger number: it covers the measured main push span; the deadline keeps the
  worst case finite (job 105 ≥ 60 window + battery).

## Current status

OpenSpec change `ci-hf-live-pin-patience` validates; targeted battery green (40 passed incl.
the wiring pin). Next: full `make test-unit`, push the branch, open the PR closing #2973.
