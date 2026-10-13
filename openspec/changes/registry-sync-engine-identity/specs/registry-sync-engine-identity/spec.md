# registry-sync-engine-identity

## ADDED Requirements

### Requirement: Engine tests address engines by id, never by index

Tests that drive `model_engine_pick.offer()` or the interactive picker MUST
select an engine by its `id`, or derive its position from the same offer, and
MUST NOT assume a fixed index for an engine. The engine order is vendored
upstream data: `rank_engines` sorts same-backend engines by measured t/s, so a
new upstream measurement on hardware of the host's backend can reorder a model's
engines without any llgenie code change.

#### Scenario: a new CUDA measurement reorders a model's engines

- **Given** `qwen3.8-flash-next-125b` is offered on a CUDA host
- **And** upstream adds a TensorFold measurement on a DGX Spark (classified CUDA, 67 t/s) above llama.cpp (33.7 t/s)
- **When** the offer row's engines are read
- **Then** the order is `strata, tensorfold, llama.cpp, mlx`
- **And** the Strata plan and the llama.cpp plan are still found by their ids
- **Test:** `tests/test_strata_download.py::test_offer_gives_strata_its_own_plan_and_llama_cpp_its_own`

#### Scenario: the interactive pick selects llama.cpp wherever it sits

- **Given** the same model on a CUDA host
- **When** the interactive picker is asked for llama.cpp's own files
- **Then** llama.cpp's 1-based position is derived from the offer (engine `3` on the new registry, `2` on the old)
- **And** the pick prints `Engine : llama.cpp [cuda]` and downloads the Unsloth GGUF, never Strata's files
- **Test:** `tests/test_strata_download.py::test_interactive_pick_llama_cpp_for_the_same_model_gets_its_own_files`
