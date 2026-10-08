## Why

On an Apple-Silicon Mac (M5 Pro, 48 GB unified memory) plain `llgenie` showed the
README trend list as a `cpu` host:

- the header said `(48 GB, cpu)`: `model_engine_pick.host_arch()` mapped
  detect_server's `metal` backend to `cpu`;
- no Metal engine was ever offered, because engines were taken only from the
  generated container params, and Metal cannot run in a container. TensorFold
  (the fastest measured engine for Qwen3.8-27B and Qwen3.8-Flash-Next on Apple
  Silicon) was never selectable, and t/s figures from Apple hardware were labelled
  `(Metal)` as "other hardware";
- the memory budget used the discrete-GPU rule (80% − 1 GiB = 37 GB on 48 GB). That
  is too large for Apple unified memory, where the GPU wires about 70% of RAM;
- Ornith 1.5 was "not here": the registry names only the base repo, and llgenie
  never looked for its `<name>-MLX-*` conversions on the Hub;
- TensorFold serves only its own checkpoints (`TensorFold/<base>-MLX-*`), and
  llgenie had no plan for them.

Qwen3.8-Flash-Next 125B (README #1, VRAM tier 12 GB) depends on Strata streaming
the MoE experts across GPU/RAM/SSD. Strata has no Metal backend. On a Mac every
TensorFold checkpoint of it (≥ 63 GB) and every GGUF (≥ 68 GB) is larger than what
a 48 GB Mac can hold for the GPU. So on 48 GB it MUST stay listed but not pickable,
and say exactly why. On a Mac with enough memory (e.g. 128 GB) it MUST be pick #1,
on TensorFold.

## What Changes

- `host_arch()` returns `metal` on Apple Silicon; Metal measurements count as this
  host's hardware (`HOST_TO_MEASURED["metal"] = "Metal"`).
- `metal_engines()`: every servable skill with `metal` in its backends and a metal
  install (TensorFold, MLX, llama.cpp, Prism, Ollama, LiteRT) gets a native `metal`
  variant in `engine_ids()`. Container-only engines fall back to their cpu image;
  cuda/rocm-only engines are absent.
- `weight_budget_gb(arch="metal")`: 70% of unified memory − 7 GiB (3 GiB process
  reserve + 4 GiB KV cache), floor 40%, MoE adds nothing.
- TensorFold gets its own plan and local copy (`tensorfold_plan` /
  `tensorfold_local`), like Strata: the largest `TensorFold/<base>-MLX-*` checkpoint
  that fits. The "not here" reason names the smallest TensorFold MLX size and the
  smallest GGUF size against the budget.
- `plan_download(fmt="mlx-safetensors")` also searches the Hub for `<base>-MLX*`
  conversions (`mlx_repos`).
- Native start script for Metal engines (`install_engine_launchers.native_launcher`
  / `ensure_native`). No container runtime is touched for a metal engine.
- **Seamless engine on pick (interactive llgenie by design):** hardware → the trend
  list that fits → model → supported engines → engine. Picking TensorFold makes it
  ready with its skill's install script whatever is on the host: missing → install,
  installed at another version than the skill's pinned `version:` → update to the
  pin, at the pin → reuse (`engine_skills.native_status` / `pinned_version`). The
  engine list and the `Engine :` line show which of the three will happen; `--dry`
  never installs; a failed install fails loudly and writes no start script. Then the
  model's TensorFold checkpoint is downloaded if missing and served on Metal.
- **65,536-token window for Hermes Agent:** TensorFold's default Mac budget (70% of RAM)
  gives a 48 GB Mac a 29,696-token window, below Hermes Agent's 64K tool-use floor. The
  Metal launch passes `--context {context}` (`LLGENIE_CONTEXT`, default 65536; `0` leaves the flag out and lets
  TensorFold size it) and `TENSORFOLD_MEMORY_LIMIT_GB=<RAM>` (capped by TensorFold at the
  GPU working set, 37.4 GiB on 48 GB). The CUDA launch is unchanged.
- **TensorFold stays pinned at v0.6.5:** 1.0.x is a native rewrite that does not serve
  Qwen3.8-27B (left out upstream; the 1.0.2 binary refuses the checkpoint with
  `UnsupportedQwenConfig` on the M5 Pro). Moving to 1.0.x is a separate change.
- `make test-native-engine` (REAL uv, isolated tool dir: install / update / reuse /
  version) on the Apple-Silicon host and in the CI job `native-engine-macos-arm64`
  (macos-15, reports only); `make test-native-engine-serve` adds the real download +
  Metal serve + "hi" (local Apple-Silicon host); `make test-interactive-tensorfold`
  drives plain interactive `llgenie` (Qwen3.8-27B → TensorFold) end to end;
  `make test-native-engine-light` serves the lightest model TensorFold 0.6.5 runs
  (`mlx-community/Qwen3.5-9B-MLX-4bit`) through the start script on Metal, or asserts
  TensorFold's budget refusal where it does not fit (the 7 GB `macos-15` runner). All native
  targets run real cases only on Apple Silicon and exit 0 with a Metal-only notice elsewhere.
- The TensorFold container image stays CUDA-only and is built by the Linux CI. A
  Linux container cannot use the Apple GPU, so no Metal image exists.
- Tests: `tests/test_mac_trend_pick.py` (Mac behaviour), `tests/test_trend_list_acceptance.py`
  (acceptance criteria AC1–AC8 for linux cuda/rocm/vulkan/cpu and mac metal, several card
  sizes) and `tests/test_tensorfold_seamless.py` (install/update/reuse on pick), all in
  `make test-unit`; `tests/test_native_engine_real.py` on the Apple-Silicon host.
  The list is tested without the prompt (`llgenie --trend` prints exactly the rows the
  prompt asks from; one pty test proves the two are identical).

## Impact

- `scripts/model_engine_pick.py`, `scripts/install_engine_launchers.py`,
  `scripts/llama_serve.py`, `Makefile` (test-unit), `README.md`, tests.
- Linux behaviour is unchanged (locked by the acceptance matrix and the existing
  `tests/test_trend_pick.py`).
- Issue: #114.
