# Give the committed-pin live check a bounded patience window (issue #2973)

## Why

`ci-hf-live` is red on `main` three runs in a row (44739963771, 44743185352 cascade,
44749136442-class) while every pin is in fact published. The battery runs
`test_every_committed_engine_cell_tag_is_published_live` at the SAME time as the main
CI run of the very landing that moved the pins — and that run pushes the images only in
its late image-push stage. The check's single sweep hits GHCR mid-push, sees manifests
that do not exist YET, and reddens a green main. `make post-merge-live-check` inherits
the red. The transient is structural (issue #178's "the producer wave and the reader
check race"), not a publish gap: the same check goes green minutes later with zero code
change.

## What Changes

- `scripts/check_engine_pins_published.py::_probe` gains a bounded patience window:
  every cell is probed once; only UNRESOLVED refs are re-probed every 120 s until ONE
  deadline for the whole check (never one window per cell). A manifest landing inside
  the window resolves green; a genuinely unpublished ref still reds AT the deadline,
  never later. The wait is loud (`[pins] PATIENCE <ref> ...` lines).
- The window arrives only through `ENGINE_PINS_PATIENCE_SECONDS`, read by
  `check_committed` when no explicit value is passed. Unset (every other caller, incl.
  every PR lane and `make check-engine-pins-published` locally) keeps today's
  immediate-red: a pin bump may still not merge while its image is unpublished
  (#1622 strictness preserved). A non-numeric value warns on stderr and stays 0.
- `ci-hf-live.yml` sets `ENGINE_PINS_PATIENCE_SECONDS: "3600"` on the
  `make test-unit-network` battery step — the main pipeline's normal push span — and
  raises the hf-live job `timeout-minutes` 60 → 105 so an unpublished pin reds at its
  own deadline, never disguised as a job timeout.
- Fixture tests (hermetic, virtual clock): mid-window resolution → green;
  never-published → red AT the bounded deadline (negative control, AC of this change);
  no-knob → exactly one probe per cell, no sleep; env knob drives the window and a
  malformed knob stays impatient + loud. A workflow test pins the env wiring and the
  timeout headroom.

## Impact

- `scripts/check_engine_pins_published.py` — `_probe`/`check_committed` signature
  (new bounded-patience params), PR-lane `check()` unchanged in behavior.
- `.github/workflows/ci-hf-live.yml` — battery-step env + job timeout.
- `tests/test_check_engine_pins_published.py`, `tests/test_ci_hf_live_workflow.py` —
  four hermetic tests + one wiring pin.
- No new make targets; the existing `check-engine-pins-published` target and
  `test-unit-network` seam carry it.
