# registry-liveness-dispatch — proposal

Issue: [#2259](https://github.com/asimov-agent/llgenie/issues/2259)

## Why

A committed engine tag whose manifest is missing is a partial publish the pipeline produced and
nothing repairs. `check_engine_pins_published.py --all` (issue #2190, the #2245 hard-fail) turns the
scheduled `registry-liveness` run RED on the 404, but nothing performs the remedy — the check only
prints "dispatch engine-build with push=true, then re-run" and `registry-liveness` files a tracking
issue. Measured: vllm cuda `3a4d82f5-9be509b4` / rocm `3a4d82f5-5772a26a` returned HTTP 404 for five
days (#1682/#1684, open since 11-03) while cpu carried the new tag — a params edit that changed an
install line (`torch 2.13→2.14`) at an UNCHANGED `pinned` retaged every backend cell, the initial
push run aborted on the first (cpu) cell failure so cuda/rocm were never rebuilt at the new hash, and
the follow-up republished cpu only. The gate named the gap; nothing closed it.

## What Changes

- **`.github/workflows/registry-liveness.yml`** — after the `ALL=1` hard-fail (kept verbatim — no gate
  weakening; the job's exit is still the gate's), a new `always()` step parses each
  `NOT PUBLISHED <engine>:<pin8>-<hash8>-<variant>` tag, derives engine+arch, and dispatches
  `engine-build` with `push=true` for every missing cell, so the publish is performed by the producer,
  not filed as a dead issue. Grants `actions: write` on this (caller) workflow — `gh workflow run`
  needs it to start the producer. engine-build's own `packages: write` and the fork guard are
  untouched.
- **`scripts/engine_image.py`** — new `collect` command: build (and with `--push`, publish) EVERY
  enabled CI cell of an engine as one sweep, so a success is built, a failure is NAMED and does not
  stop the next cell, and the exit is 0 only when every cell succeeded. A repin is all-green or
  explicitly partial — never silent.
- **`scripts/run_failure_reactor.py`** — the pins-publish failure class (`registry-liveness`, or a
  `NOT PUBLISHED` / `manifest unknown` log) files an issue naming the publish remedy, not the useless
  "no PR this bot can repair was found".
- **tests** — the sweep-collect regression (`tests/test_engine_build_collect.py`), the workflow-shape
  dispatch assertions (`tests/test_check_engine_pins_published.py`), and the reactor's publish-class
  body.

This closes the #1365/#1622 recurring publish-gap class: the gate that finds the gap also starts the
build that closes it, and a cell failure no longer strands the sweep's later cells.
