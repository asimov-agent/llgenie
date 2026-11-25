# pins-gate-ordering — proposal

Issue: [#3051](https://github.com/asimov-agent/llgenie/issues/3051)

## Why

`make check-engine-pins-published` (`mk/engines.mk:319`, `scripts/check_engine_pins_published.py`)
is step 15/54 of `make ci-unit` (`scripts/ci_unit.py:50`). On an engine-bump PR it demands GHCR
manifests for the tags the PR **repins**, while the job that publishes them —
`engine-build-pr-trigger` (`.github/workflows/engine-build-pr-trigger.yml`, `mk/engines.mk:332`, a
SEPARATE workflow that dispatches `engine-build` push=true per repinned cell and awaits each verdict)
— is still running. Measured 2026-11-24T06:20Z on PR #3030 head `20b3f0307`: the pins step failed at
`19:08:53Z` with `vllm:0c57b419-ff61d9c3-cpu` / `vllm:0c57b419-227a9667-cuda` `HTTP Error 404`, and the
producer job in the same lane ran `18:50:31Z → 20:50:34Z`, i.e. it ended **1 h 42 min later**. 6 of 7
open engine-bump PRs carry a failed `trigger` job; 7 of 7 carry the red `linux / unit`.

The two arms have no ordering: GitHub `needs:` cannot cross workflows, so the `linux / unit` lane
(`pipeline.yml`'s `unit` job, which `ci.yml` calls) cannot depend on `engine-build-pr-trigger`, and the
pins gate reads a registry snapshot taken before the producer published anything. The unit verdict
therefore measures the race, not the code.

## What Changes

- `scripts/check_engine_pins_published.py` gains a **PR pending state** that is distinct from both
  `PUBLISHED` and `NOT PUBLISHED`: when the gate runs in a PR lane and a cell THIS change repins is
  unresolved, it prints `PINS-PENDING <ref>` (and `ALIAS-PENDING <ref>` for a lagging alias of a
  repinned cell) and exits 0 with a `PINS DEFERRED n` summary. The pending state is scoped to the
  repinned cells only — a gap the change did NOT repin (and every `--all` committed-sweep finding)
  stays hard red. Mode comes from the explicit `ENGINE_PINS_PR_PENDING` knob (`1/true` on,
  `0/false`/empty off, anything else warns and stays off); when unset it falls back to
  `GITHUB_EVENT_NAME == pull_request`, so the PR lane defers and a `push`/`main` run never does.
  `main` semantics are unchanged: an absent pin is `NOT PUBLISHED` + `[select]`, exit 1 (issue #178).
- New `scripts/engine_pins_await.py` + `make engine-pins-await`: the PR lane's read-only **await** on
  its own producer. It resolves the `engine-build-pr-trigger` run(s) for the current head through
  `gh api` and polls their status until they conclude or the bounded window
  (`ENGINE_PINS_AWAIT_SECONDS`, default 0) expires, printing `AWAIT <run_id> <status>` lines. It never
  dispatches, never re-triggers, never re-runs anything (AGENTS: queue-pumping is forbidden), never
  reddens the lane (exit 0 always, including when nothing is repinned), and takes `run_lookup` for
  tests.
- `.github/workflows/pipeline.yml` `unit` job (the job `ci.yml`'s `linux` lane calls): a step
  **before** the `make ci-unit` step runs `make engine-pins-await`, so the pins check inside the
  battery is evaluated against the producer's published state (or its concluded failure) rather than
  the pre-run snapshot. `mk/engines.mk` gains the target; `make check-wiring` covers the new script.
- Tests (`tests/test_check_engine_pins_published.py`, new `tests/test_engine_pins_await.py`,
  `tests/test_ci_unit_stage.py` / `tests/test_engine_build_workflow.py` for the graph ordering):
  PR-pending green, main hard-red negative control, non-repinned gap stays red in PR mode, `--all`
  stays hard, await-polls-then-returns, await no-op when nothing is repinned, await never dispatches
  (the seam's calls are inspected from its AST), and a pipeline.yml step-order assertion that the await
  step precedes the `make ci-unit` step.

## Benefit

A bump PR's `linux / unit` verdict means what it says: green = the pins resolve to images that exist
(or the pending window closed with the producer green), red = an image genuinely failed to build.
Reviewers stop triaging a gate that raced its own producer, the monitor stops re-routing lanes that
cannot pass (issue #3047), and real build failures (#3029's `engine-build-ollama-{cpu,cuda,rocm}`)
stand out. `main` keeps its hard requirement unchanged.
