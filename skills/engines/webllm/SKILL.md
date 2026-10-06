---
name: engine-webllm
description: "Use when the index lists WebLLM: it runs only inside a browser (WebGPU, npm library), has no HTTP server, so llgenie never installs it."
engine: "WebLLM"
id: webllm
repo: https://github.com/mlc-ai/web-llm
ref: v0.2.85
ref_kind: tag
pinned: 5f742443179a5463e83a19f704d7c19f1f019f98
verified: "2026-10-05"
license: Apache-2.0
servable: false
backends: []
os: [browser]
formats: [mlc]
upstream_watch: [package.json, src/config.ts, README.md]
---

# WebLLM — not servable

`@mlc-ai/web-llm` is an npm library that runs models **inside the browser** with WebGPU
(WASM + WebGPU, MLC model libs). It exposes an in-process OpenAI-shaped JS API
(`engine.chat.completions.create`). There is **no network server and no `/v1` endpoint**,
so it cannot back `http://127.0.0.1:11434/v1`.

llgenie shows it as `not servable` and never installs it. Use it directly in a
web app: `npm install @mlc-ai/web-llm`.
