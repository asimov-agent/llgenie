# The engine arch → build → offer → sync loop (issue #1092)

The engine lane's contract: for this host's hardware, offer only model + inference-server pairs that are **(a)** genuinely supported by the engine's arch, **(b)** proven to build as a Docker image, and **(c)** measured to run. This records the loop and the defects found while verifying it at `ac12cae9`.

## The loop

1. **Sync** the trending local-LLM list and the trending local inference-server list **from `andyholst/trending-local-llms`** (the `registry-sync` pipeline) — not hand-edited. Each engine's supported arch types (cuda/cpu/vulkan/rocm) come from that sync.
2. **Verify the Dockerfile chain** — for every engine × supported arch: a generated `containers/engines/dockerfiles/<engine>/Dockerfile.<variant>`, a params entry under `variants` in `containers/engines/params/<engine>.json`, and a **built `linux/amd64` image** whose tag hashes ref+params+Dockerfile+entrypoint+runner. Pinned now as `test_every_supported_arch_has_a_generated_dockerfile` (PR #1107). Audit at `ac12cae9`: 13/13 engines complete, 0 missing; disabled cells documented (#103 prism cuda/rocm, #625 vllm/mlx/tensorrt-llm cuda).
3. **Verify the build + install pipeline** — `engine-build` builds/serves/smokes every non-disabled cell; the install-leg must test the **container path** (`engine-launchers` → pull + launcher), not a host `engine_skills.py install` (which correctly exits 3 for a container-only engine). Fixed in PR #1093.
4. **Offer** — `trend_list`/`rank_engines` order by a run whose `measured_on` matches the host arch and a card the host can reproduce. Never a run measured on other/unknown hardware.

## Defects found (all measured)

| defect | evidence | status |
|---|---|---|
| `measurement_backend()` defaulted unknown hardware to **CUDA** | `CMF Phone 2 Pro (on-device)` → CUDA, `iPhone 18 Pro Max` → CUDA | fixed: default CPU + mobile tokens + explicit CUDA/generic-GPU (PR #1099) |
| A **ternary** model routed to plain `llama.cpp` | `Bonsai 2 4B` → `llama.cpp cuda@6.0` (a phone's 6 tok/s, on the engine that cannot load the ternary file) | **blocked**: the correct signal is the per-file GGUF tensor type (`GGML_TYPE_PQ2_0`=142, `PTQ1_0`=143); the registry records none. A per-model "ternary" heuristic is too broad — `Qwen3.8-27B` has mixed variants and loses its `llama.cpp` row. Needs `registry-sync` to record the tensor type |
| install-leg red every cuda cell | `engine_skills.py install` exits 3 for container engines, while the image serves green in the same job | fixed (PR #1093) |
| `registry-sync` `disabled_manually` | no new server/arch type reaches `params/` | **owner-only** re-enable |

## The standing rule

A merged change that moves a product's **output order** silently invalidates every stale order expectation in the repo — and each one will look like a merge conflict while actually being an outdated expectation. **Re-derive from the product, never hand-adjust the expectation.** Same shape as the stale trend-list golden.

## PRs that close the legs

- **#1093** — install-leg tests the container path (was reding every cuda cell).
- **#1107** — `test_every_supported_arch_has_a_generated_dockerfile` (the arch → Dockerfile gate).
- **#1099** — `measurement_backend` default CPU (a phone is never a cuda measurement).
- **#1115** — this lane's skill versioned under `agents/llgenie-engine-improver/skills/`.

## Measured verification (#1099) — HELD RED, fixture not regenerated

**Shape chosen: (a)** — classifier only, the existing matrix assertion untouched, the golden 0 diff
vs main, held red with the reason. Not (b) regenerated golden, not (c) an edited expectation.


```
classifier (-k measurement_backend/hardware/card_aware/engine_tps) → 15 passed
canary (test_the_1073_ternary_routing_defect_is_still_present)     → 1 passed
ratchet → OK {sys-path: 32, bare: 52, syntax: 0} · check-docs → census-gate OK
tests/fixtures/trend-list-matrix.json → 0 diff vs main (NOT regenerated)
```

**Why the golden is not regenerated:** with the classifier fix the render changes `server` and `tps`,
not merely `measured_on` — measured vs main: `Bonsai 2 4B` `llama.cpp (PrismML fork)@128 → llama.cpp@6.0`
(16 cases), `Bonsai 2 27B` tps 300→2.5, `GLM-5.3-Flash` `vLLM→llama.cpp` 62.2→27.5, `MiniCPM-V 4.7`
`llama.cpp→MLX` CUDA→Metal, `LFM2.5-24B` tps 184→25.4, `Qwen3.8-27B` tps 159→80. Main's fixture
currently has the **correct** `Bonsai = PrismML fork @ 128`; regenerating would regress it to plain
`llama.cpp @ 6.0`.

**Root cause, and it is not the classifier (#1124):** `rank_engines(bonsai, "cuda")` returns
`llama.cpp-prism @128 same_hw=True` first, while **`trend_rows` (which generates this fixture)
returns `llama.cpp @6.0`** — the two product paths select different engines for the same model and
host. The golden inherits `trend_rows`' choice, so regenerating bakes a row the ranking would never
pick. Fixing #1124 (make one path match the other) is a precondition for regenerating this golden.

**Narrowed further:** the wrong path is `rank_engines` on a **cpu** host — it ranks the phone's
plain `llama.cpp@6.0` first because `same_hw=True`, blind to the model's ternary weights.
`matrix()`/`trend_rows` currently choose the PrismML fork, which is the better row. Making
`trend_rows` follow `rank_engines` was tried and **reverted** (it regressed). So the regen needs
both **#1124/#1073** (the routing — `registry-sync` per-file tensor type, owner-gated) and **#1109**
(the hermetic snapshot, so the render does not depend on Hub 429s). #1109 makes it *reproducible*;
#1124 makes it *correct*; neither substitutes for the other.



**Confirmed red, not merely untested:** `pytest tests/test_trend_list_matrix.py -k "cuda and 8 and 8"`
→ `11 failed` (the code now classifies the phone run CPU while main's fixture records CUDA) —
i.e. the PR is visibly RED for the exact reason stated above, not silently green. That is the
deliberate state until #1073's routing lands.

**A guard enforces the hold:** `test_the_golden_was_not_regenerated_while_ternary_routing_is_broken`
asserts the fixture still names `PrismML` for `Bonsai 2 4B`, so a future "fix the red" that
regenerates the golden fails at that assertion instead of silently baking #1073's defect. It is
deleted together with the canary when the routing lands.

**Why a canary and not an `xfail`:** `tests/conftest.py` carries two skip guards that disagree —
`pytest_report_teststatus` marks every skipped report failed (no xfail exemption) while
`pytest_runtest_logreport` explicitly exempts `wasxfail`, so an xfail whose test fails is RED while
an xpass is green (#1121). A canary assertion is the only mechanism that both documents the defect
and reds when it is fixed.






