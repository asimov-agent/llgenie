# 2026-11-18 — engine tag publish scoping (issue #178, PR #<PR>)

OpenSpec change: `engine-tag-publish-178` (issue #178).

## What was verified

- **The bug class**: a PR-repin `engine-build` dispatch runs with `push=true` and published
  EVERY ref `publish_refs` returns — the immutable pin AND the moving `:<arch>`/`:latest`
  aliases. A PR whose pin is unmerged therefore repointed an alias out from under main's
  published pin, and the published-leg step then demanded `digest(pin) == digest(:arch)`
  against an alias main no longer owned — the mid-wave digest mismatches observed during
  engine-bump waves.
- **The scoping (one code path, no fork)**: `engine_image.push(spec, moving=True)` and
  `pull_published(spec, moving_check=True)` keep the main-scope default; `--no-moving`
  (CLI) / `MOVING=0` (make) publish and measure the unique pinned tag only, with a named
  issue #178 note for every skipped ref. `Makefile` gained `MOVING_FLAG`
  (`$(if $(filter 0 false,$(MOVING)),--no-moving,)`); `push-engine` and
  `published-engine-pull` pass it. `engine-build.yml` gained the `moving_tags` input
  (default `true`); its `push-engine` and published-binary-leg steps export
  `MOVING: ${{ inputs.moving_tags == 'false' && '0' || '1' }}`. The PR repin trigger
  (`engine_build_trigger.py`) dispatches `moving_tags=false` on every cell.
- **Tests**: `tests/test_engine_tag_publish.py` (6 hermetic tests: pin-only PR push,
  main-scope push regression, PR pull passes mid-wave despite a diverged `:cuda` digest,
  main-scope pull still fails on mismatch, CLI wiring, make/workflow/trigger wiring).
  `tests/test_engine_build_trigger.py` updated in place (5 assertion sites, 29 pass).
  `test_ci_publish_order.py::test_an_identical_params_file_defers_only_when_a_tag_retags`
  reads the WORKING tree's tag inputs — it reddens while `scripts/engine_image.py` is
  modified-but-uncommitted (tag digest moves vs HEAD) and greens once the change is
  committed; it is not a defect of this change.

## Key decisions

- Default `moving=True` keeps every existing producer (main run, engine-bump wave, human
  dispatch) byte-identical; only the PR repin trigger opts out.
- `MOVING=0` skips the alias DIGEST CHECK too (not just the push): a PR-scoped pull that
  still demanded `digest(pin) == digest(:arch)` would measure whichever pin last moved the
  alias — never its own.

## Current status

PR #2921 open against upstream `main` with `closes #178`; CI green at head
`42682a4e4` (run 44381889400, verdict green, 9/9 scoped jobs). Proof commands were
re-measured at that exact head for the #2288 live-run evidence rule: the tag-publish +
build-trigger pair (35 passed), the hermetic launcher suite `tests/test_check_engine_launchers.py`
(15 passed — the `make -s check-engine-launchers` gate itself reads HOST launcher state,
which lags the registry lane's pins on this host), and `make test-unit` (4068 passed).
Issue #178's AC proofs name these commands with `rc=0` + this head sha.
