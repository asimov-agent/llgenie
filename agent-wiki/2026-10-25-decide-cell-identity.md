# 2026-10-25 — a device verdict needs the cell it is about

Issue: [#632](https://github.com/asimov-agent/llgenie/issues/632)
Follow-up to: [#625](https://github.com/asimov-agent/llgenie/issues/625)

## What was red

The first full sweep under the strict gate on `main` (`4763ce6`, run 40215905868) failed exactly one row,
`engine-build-mlx-cuda`: `test_image` ACCEPTED `llgenie/mlx:93e6d4a6-e2b0dee2-cuda` (`exempt from the flag rule
(#625 …)`, `installed mlx-lm 0.32.2 mlx 0.32.4`, `OK image test`), and the very next stage,
`tests/test_engine_version.py::test_engine_binary_answers_the_flags_a_user_types`, refused the same image with

```
every probed flag failed and / is NOT on the device-only exemption list
```

— note the `/`: the engine name was empty. That test called `ei.decide(documented, verdicts, policy)` with
three arguments, so the `("mlx", "cuda")` `DEVICE_ONLY` lookup never matched.

## Fix

- `tests/test_engine_version.py` passes `engine=spec["id"], variant=spec["variant"]`.
- `decide()` now REFUSES a `policy="device"` verdict taken without the identity, naming what is missing —
  a two-argument call can no longer silently mean "not exempt".
- `tests/test_engine_binary_flags.py`'s parser test carries the identity (it used the two-argument form).
- `tests/test_engine_gate_strict.py::test_a_device_verdict_needs_the_cell_identity` locks both: no identity →
  red with the reason; `mlx/cuda` → green.

## Verification

- Reproduced on the exact row before the fix (`LLGENIE_TEST_ENGINE=mlx LLGENIE_TEST_ARCH=cuda`, the real image
  mounted): **1 failed, 2 passed** — then **3 passed** after it, and **3 passed** for `llama.cpp/cpu` (a
  non-exempt cell) to prove the exemption is not applied blindly.
- 20 passed across `tests/test_engine_gate_strict.py` + `tests/test_engine_binary_flags.py`; `make lint` green.

## Note

`mlx/cuda` remains one of the four `DEVICE_ONLY` cells: on a GPU-less runner it proves the file plus a
version-shaped detect, not that the CLI runs — that was proved on a 4090 host earlier in this session.
