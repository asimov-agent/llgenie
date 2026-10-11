---
name: engine-litert
description: "Use when installing Google LiteRT-LM (the LiteRT LLM runtime, via uv) and serving .litertlm models with `litert-lm serve` as llm-local."
engine: "LiteRT"
id: litert
repo: https://github.com/google-ai-edge/LiteRT-LM
ref: v0.18.0
ref_kind: tag
version: v0.18.0
pinned: b2f686e2ed4718fb84ec398a61dd59ca0f0aff27
verified: "2026-10-11"
license: Apache-2.0
servable: true
backends: [metal, cpu]
os: [darwin, linux]
formats: [litertlm]
prereqs:
  common: [uv]
install:
  cpu:
    - "uv pip install --system --break-system-packages litert-lm=={version}"
  metal:
    - "uv tool install --force litert-lm=={version}"
binary: "litert-lm"
detect:
  metal: "{binary} --help > /dev/null && uv tool list | grep '^litert-lm '"
  cpu: "{binary} --help > /dev/null && python3 -c 'import importlib.metadata as m; print(m.version(\"litert-lm\"))'"
pre_launch: "{binary} import {model} {alias}"
launch: "{binary} serve --host {host} --port {port}"
health: "GET /v1/models"
alias_mode: create
upstream_watch: [pyproject.toml, python/litert_lm/cli, docs/cli/openai_server.md]
---

# LiteRT (LiteRT-LM)

The registry calls this engine "LiteRT" (google-ai-edge/LiteRT). The core LiteRT repo is
the on-device **runtime library** (the TFLite successor) and has no HTTP server. The servable
LLM engine on top of it is **LiteRT-LM**, which this skill installs.

## Hardware parameters

- **metal:** GPU on macOS arm64. **cpu:** Linux/macOS (it runs on a Raspberry Pi 5).
- NPU/TPU backends exist for specific devices only and are out of scope.
- The registry also lists "CUDA" for LiteRT, but LiteRT-LM has no CUDA backend. On an
  NVIDIA box, use the cpu backend.

## Serving as llm-local

The model id is chosen at **import** time:
`litert-lm import <model.litertlm | --from-huggingface-repo=...> llm-local`, then
`litert-lm serve --host 127.0.0.1 --port 11434`. The default port is 9379 and the default
host is 0.0.0.0, so always pass `--host`. Routes: `/v1/models`, `/v1/chat/completions` (streaming).
There is no health endpoint, so probe `/v1/models`. Models: `.litertlm` only (litert-community on HF).
