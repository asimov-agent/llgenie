# 2026-10-05 — engine skills (issue #98)

- There is one `skills/engines/<id>/SKILL.md` per registry engine (16). Each fact was read
  from the upstream repo at the pinned sha or tag. `scripts/engine_skills.py` is the generic,
  stdlib-only runner: it detects hardware, renders steps, checks floors, validates and installs.
- llama.cpp and Prism builds are now driven by their skills. A CUDA build gets
  `-DCMAKE_CUDA_ARCHITECTURES=<compute_cap>` only when a GPU is visible.
  `-DLLAMA_CUBLAS=OFF` was removed (it is a FATAL shim upstream). Upstream clones from ggml-org.
- Non-servers: WebLLM (`false`), DFlash2 (`via` sglang), MLX-fast Bonsai 2 (`via`
  tensorfold, mlx).
- No `--served-model-name` exists in mlx_lm.server or trtllm-serve 1.2.1. Both
  advertise the model dir name, so their skills symlink the model as `served/llm-local`.
- Pitfall found by a real run: `uv venv` fails if the venv exists. Every venv and clone
  step is now guarded, and a test enforces it.
- Host verification: Prism CUDA sm_89 "hi" OK. Ollama v0.35.1 checksum OK and served
  llm-local on CUDA. vLLM 0.31.0 installed and served llm-local on the GPU.
- Pitfall: FlashInfer JIT calls `ninja` from PATH, and the venv bin was not on PATH, so it failed. Skill env
  values are now emitted as a bash `export` prelude (which also expands `$(hipconfig -R)`), and
  venv skills prepend `{venv}/bin` to PATH.
