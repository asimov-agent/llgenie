# Change: Publish unique engine tags on PRs; the main run moves the architecture tags (issue #178)

## Why

Issue #178's design says a PR build publishes only its unique engine tag and the run on
`main` moves the moving tags (`:<arch>`, `:latest`). Today's producer does not honor that:
the PR repin trigger (`engine-build-pr-trigger` → `engine-build.yml` with `push=true`) runs
`make push-engine`, and `engine_image.push()` publishes ALL of `publish_refs(spec)` — the
unique pin AND the moving `:<arch>` alias — before the PR merges. Measured consequence:
while a pin-bump wave is in flight, arch aliases repoint at PR-head pins that were never
`main` pins, and the full `make test-published-engine` sweep fails with
`FAIL digest mismatch` (e.g. `freetoken` cuda `RC=2` during the #2840 wave), and a PR's own
published-binary leg (`pull_published`, which requires digest(pin) == digest(:arch)) measures
an alias another PR moved under it.

## What Changes

- `engine_image.push(spec)` gains a `moving` gate: when disabled the run publishes ONLY the
  immutable pinned ref and prints a named note that the moving refs belong to the main run
  (issue #178). The CLI `push` subcommand gains `--no-moving`.
- `engine_image.pull_published(spec)` gains a `moving_check` gate: when disabled the pull
  measures the pinned ref alone and never requires the `:<arch>`/`:latest` digest equality
  (PR-scoped published leg). The CLI `pull-published` subcommand gains `--no-moving`.
- `mk/engines.mk`: `push-engine` and `published-engine-pull` pass `--no-moving` when the
  `MOVING` make variable is `0`/`false` (`MOVING_FLAG`).
- `.github/workflows/engine-build.yml`: new `moving_tags` workflow_dispatch input
  (default `"true"`). When `false`, the `push-engine` and published-leg steps export
  `MOVING=0` so the producer publishes/moves pins only.
- `scripts/engine_build_trigger.py`: the per-cell dispatches it makes for a PR carry
  `moving_tags=false`; PR builds stop moving the architecture tags.
- `main`-scope producers (registry-liveness gap dispatches, human dispatches, full sweeps)
  keep `moving_tags` at its default `true`: they publish their pins and move the aliases,
  so the aliases always point only at main-published pins. `build()`'s existing
  `_available()` path (pull the published pin, retag locally, no rebuild) already covers
  "don't rebuild a unique tag that already exists" when the main producer moves its alias.

## Out of scope

- Server-side (pull-free) alias retag: unnecessary — `_available()` already pulls the
  published pin and retags it locally, and `push()` then moves the aliases from it.
- The install-leg's refs: it already installs the pinned tag the cell just published.
- CI-side model serving: unchanged (issue #197/#320 discipline).
