---
name: engine-ollama
description: "Use when installing or launching Ollama (checksum-verified release tarball into llgenie's tree, no systemd) and serving a GGUF as llm-local."
engine: "Ollama"
id: ollama
repo: https://github.com/ollama/ollama
ref: v0.40.3
ref_kind: tag
version: v0.40.3
pinned: eab97e9f92b9a25c2d52d2cc6c1b1c99bd9fae21
verified: "2026-10-11"
license: MIT
servable: true
backends: [cuda, rocm, vulkan, metal, cpu]
os: [linux, darwin]
formats: [gguf]
requires:
  min_compute_cap:
    cuda: "5.0"
prereqs:
  common: [curl, tar]
  cuda: [zstd, sha256sum]
  rocm: [zstd, sha256sum]
  vulkan: [zstd, sha256sum]
  cpu: [zstd, sha256sum]
  metal: [shasum]
assets:
  cuda: ollama-linux-{arch}.tar.zst
  vulkan: ollama-linux-{arch}.tar.zst
  cpu: ollama-linux-{arch}.tar.zst
  rocm: ollama-linux-amd64-rocm.tar.zst
  metal: ollama-darwin.tgz
install:
  common:
    - "mkdir -p {prefix}/{version}"
    - "curl -fsSL -o {prefix}/sha256sum.txt https://github.com/ollama/ollama/releases/download/v{version}/sha256sum.txt"
  cuda:
    - "curl -fsSL -o {prefix}/ollama-linux-{arch}.tar.zst https://github.com/ollama/ollama/releases/download/v{version}/ollama-linux-{arch}.tar.zst"
    - "cd {prefix} && grep ' ./ollama-linux-{arch}.tar.zst$' sha256sum.txt | sed 's# ./# #' | sha256sum -c -"
    - "zstd -dc {prefix}/ollama-linux-{arch}.tar.zst | tar -xf - -C {prefix}/{version}"
  vulkan:
    - "curl -fsSL -o {prefix}/ollama-linux-{arch}.tar.zst https://github.com/ollama/ollama/releases/download/v{version}/ollama-linux-{arch}.tar.zst"
    - "cd {prefix} && grep ' ./ollama-linux-{arch}.tar.zst$' sha256sum.txt | sed 's# ./# #' | sha256sum -c -"
    - "zstd -dc {prefix}/ollama-linux-{arch}.tar.zst | tar -xf - -C {prefix}/{version}"
  cpu:
    - "curl -fsSL -o {prefix}/ollama-linux-{arch}.tar.zst https://github.com/ollama/ollama/releases/download/v{version}/ollama-linux-{arch}.tar.zst"
    - "cd {prefix} && grep ' ./ollama-linux-{arch}.tar.zst$' sha256sum.txt | sed 's# ./# #' | sha256sum -c -"
    - "zstd -dc {prefix}/ollama-linux-{arch}.tar.zst | tar -xf - -C {prefix}/{version}"
  rocm:
    - "curl -fsSL -o {prefix}/ollama-linux-amd64.tar.zst https://github.com/ollama/ollama/releases/download/v{version}/ollama-linux-amd64.tar.zst"
    - "curl -fsSL -o {prefix}/ollama-linux-amd64-rocm.tar.zst https://github.com/ollama/ollama/releases/download/v{version}/ollama-linux-amd64-rocm.tar.zst"
    - "cd {prefix} && grep -E ' ./ollama-linux-amd64(-rocm)?.tar.zst$' sha256sum.txt | sed 's# ./# #' | sha256sum -c -"
    - "zstd -dc {prefix}/ollama-linux-amd64.tar.zst | tar -xf - -C {prefix}/{version}"
    - "zstd -dc {prefix}/ollama-linux-amd64-rocm.tar.zst | tar -xf - -C {prefix}/{version}"
  metal:
    - "curl -fsSL -o {prefix}/ollama-darwin.tgz https://github.com/ollama/ollama/releases/download/v{version}/ollama-darwin.tgz"
    - "cd {prefix} && grep ' ./ollama-darwin.tgz$' sha256sum.txt | sed 's# ./# #' | shasum -a 256 -c -"
    - "mkdir -p {prefix}/{version}/bin && tar -xzf {prefix}/ollama-darwin.tgz -C {prefix}/{version}/bin"
binary: "{prefix}/{version}/bin/ollama"   # linux tarballs; darwin tgz has ollama at the root (metal override below)
env:
  common:
    OLLAMA_HOST: "{host}:{port}"
    OLLAMA_MODELS: "{prefix}/models"
    OLLAMA_FLASH_ATTENTION: "1"
    OLLAMA_KV_CACHE_TYPE: "q8_0"
  rocm:
    HSA_OVERRIDE_GFX_VERSION: ""
detect: "{binary} --version"
launch: "{binary} serve"
post_launch: "printf 'FROM %s\\n' {model} > {prefix}/Modelfile && {binary} create {alias} -f {prefix}/Modelfile"
health: "GET /api/version"
alias_mode: create
container:                       # official upstream images already contain Ollama
  cuda:
    base: "ollama/ollama:{version}"
    prebuilt: true
    binary: /bin/ollama
  vulkan:
    base: "ollama/ollama:{version}"
    prebuilt: true
    binary: /bin/ollama
  cpu:
    base: "ollama/ollama:{version}"
    prebuilt: true
    binary: /bin/ollama
  rocm:
    base: "ollama/ollama:{version}-rocm"
    prebuilt: true
    binary: /bin/ollama
upstream_watch: [scripts/install.sh, docs/gpu.mdx, docs/faq.mdx, docs/openai.mdx]
---

# Ollama

Installed from the **GitHub release tarball** for the pinned tag. The archive is
verified against the release's `sha256sum.txt` before it is extracted into
`~/.local/share/llgenie/engines/ollama/<version>/`. llgenie does **not** run
`curl https://ollama.com/install.sh | sh`, does not create a systemd unit or an
`ollama` user, and does not write to `/usr`.

## Hardware parameters

| Backend | Asset | Notes |
|---|---|---|
| cuda | `ollama-linux-amd64.tar.zst` (`arm64` on aarch64) | NVIDIA compute capability >= 5.0, driver >= 550 (5.0-6.2 need >= 570) |
| rocm | `ollama-linux-amd64.tar.zst` + `ollama-linux-amd64-rocm.tar.zst` | ROCm v7 driver. Supported gfx: 908, 90a, 942, 950, 1030, 1100, 1101, 1102, 1150, 1151, 1200, 1201. Other RDNA cards: set `HSA_OVERRIDE_GFX_VERSION` (e.g. gfx1034 -> `10.3.0`) |
| vulkan | same as cuda | Intel/AMD fallback. VRAM scheduling needs `cap_perfmon` |
| metal | `ollama-darwin.tgz` | Apple Silicon |
| cpu | same as cuda | |

The env is derived from the card at launch: `OLLAMA_FLASH_ATTENTION=1` and
`OLLAMA_KV_CACHE_TYPE=q8_0` shrink the KV cache. Use `q4_0` on <= 8 GB cards.

## Serving as llm-local

1. `OLLAMA_HOST=127.0.0.1:11434 ollama serve` (the native port is already 11434).
2. Write a Modelfile with the line `FROM /abs/model.gguf` (optionally `PARAMETER num_ctx N`).
3. `ollama create llm-local -f Modelfile`.

`/v1/models` lists it as `llm-local:latest`. Requests with `"model": "llm-local"`
resolve to it, because Ollama adds `:latest` itself. Verified on an RTX 4090 Laptop: the
log shows `library=CUDA compute=8.9`, and the 0.5B Qwen answers "hi".

OpenAI routes: `/v1/chat/completions`, `/v1/completions`, `/v1/models`,
`/v1/embeddings`, `/v1/responses`. Readiness: `GET /api/version`.
