# The goal judge now targets the model the local server serves (#3089, PR #3090)

**Issue:** #3089 · **PR:** #3090 · **Branch:** `feat/goal-judge-served-id` · **base:** `0ad1e31685ec45525702a9919fd90b29fb5330c1`

## What changed

An explicit Hermes auxiliary provider does not walk the top-level `fallback_providers`: it tries
only `auxiliary.<task>.fallback_chain`, then the profile's main model. With `goal_judge` pinned to
a Strata id the local server was not serving, the judge failed five transport calls in a row and
the goal paused (`judge API unreachable`). Issue #3089 records that failure; the openspec change
`openspec/changes/goal-judge-served-id` records the rule and the decision
(`proposal.md:7`, `proposal.md:11`, `specs/goal-judge-served-id/spec.md:7`, `tasks.md:3-5`).

The committed base config now owns the judge pin. `agents/hermes-base-config.yaml:126-151` adds
`auxiliary.goal_judge` with `provider: custom` (line 128), `model: qwen3.8-flash-next-iq3_xxs`
(line 129) and `base_url: http://127.0.0.1:8080/v1` (line 130), with no `key_env` — this file
declares no named strata provider, so Hermes resolves the explicit `custom` provider plus the
base URL as the anonymous local route (`proposal.md:11`). Its `fallback_chain` (lines 131-151)
repeats, in order, the five Nous routes already in `fallback_providers` (lines 99-119):
`tencent/hy4-flash:free`, `stepfun/step-3.7-flash:free`, `qwen/qwen4-max:free`,
`upstage/solar-mini4:free`, `deepseek/deepseek-v4-flash-0731`, each with the Nous base URL and
`key_env: NOUS_API_KEY`. `model.default` stays `meituan/longcat-2.5:free` (line 44); the local
quant is not promoted to the primary lane model.

`scripts/apply_hermes_base_config.py` gained exactly one owned auxiliary key: `AUX_KEY` and
`JUDGE_KEY` (lines 49-50), required `model` + `base_url` + non-empty `fallback_chain` in
`load_base` (lines 83-90), the judge in the owned view (lines 115-116) and in `drift`
(lines 144-147), and a deep copy written by `apply()` (lines 171-176). Only `goal_judge` is
replaced: other tasks under `auxiliary` survive the merge (`tests/test_apply_hermes_base_config.py:101,111`).

## What was verified

- Real test run at the PR head `d4eb2bc6fbff50bc7cf7e24d056be675a6ad4326` in a worktree whose
  parent is the freshly fetched main `0ad1e31685ec45525702a9919fd90b29fb5330c1`:
  `$HOME/llama-gguf-tools/.venv/bin/python -m pytest tests/test_apply_hermes_base_config.py tests/test_agent_model_pin.py tests/test_agent_lanes_check.py -q`
  returned `47 passed in 1.23s` (rc 0, measured 2026-11-27T11:04Z).
- The committed tests lock the claim: `tests/test_apply_hermes_base_config.py:222-225` asserts the
  served id, the local base URL, `fallback_chain == fallback_providers` and no judge `key_env`;
  lines 101/111 assert a foreign auxiliary task survives while the stale `goal_judge` id is replaced.
- `make -s openspec-validate NAME=goal-judge-served-id` printed
  `Change 'goal-judge-served-id' is valid` (rc 0, measured 2026-11-27T11:03Z).
- `make -s check-docs` is the gate this note and its one-row `docs/changes.d/` record satisfy;
  its change→note leg reads the committed `origin/main...HEAD` diff (issue #1123).

## Anything left open

- The live `$HOME/.hermes` profiles were corrected on the host on 2026-11-27 and are not part of
  this repository (`openspec/changes/goal-judge-served-id/proposal.md:19-23`).
- Nous catalog or budget drift (#3026) and the sibling rendering in the trending-local-llms repo
  (#1798) are explicitly out of scope (`proposal.md:21-23`).
