# trigger-subprocess-deadline-bound

## Why

The `engine-build-pr-trigger` "will"-arm gate dispatches `engine-build push=true` for every engine a
bump repins and awaits each run's verdict against `DEFAULT_MAX_WAIT`
(`scripts/engine_build_trigger.py`). Measured live: trigger run `42180155072`'s
`make engine-build-pr-trigger` step sat `in_progress` ~69 min **past** its own 60-min
`DEFAULT_MAX_WAIT` at head `7967bb3f` — because `_sh`/`_gh` call `subprocess.run` with **no
`timeout=`**, so a stalled `gh api` (slow registry/API) blocks the poll loop and the
`time.time() > deadline` bound is never reached. The job-level `timeout-minutes: 250` then becomes
the effective (very long) bound, so a never-publishing image can hold the gate for hours invisibly.
Root never-publishes cause is tracked separately (#1836 default vllm = CPU; #1832 CUDA build); this
change is the gate-robustness arm only.

## What changes

Every subprocess the trigger performs — `_sh`, `_gh`, and the `gh workflow run` dispatch — is capped
at `SUBPROCESS_TIMEOUT = 30s`. On `TimeoutExpired`, `_sh`/`_gh` yield `""` and the dispatch call
falls through to run discovery, so the poll loop's own `DEFAULT_MAX_WAIT` deadline remains the
authoritative bound and fails with the existing clear message instead of hanging. A regression test
drives a real slow child with the cap shrunk and asserts a prompt `""` return.

## Out of scope

- Prebuilt never-publishes root cause (#1836 / #1832) — separate lanes.
- The `engine-pins` job does not exist on `main` (part of PR #1696's own diff, already bounded at
  `WAIT=290` + `timeout-minutes: 300`) — no side-claim here.
