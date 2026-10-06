---
name: engine-mlx-fast-bonsai2
description: "Use when a model's best t/s is from MLX-fast (Bonsai 2): it is a Swift/Metal benchmark harness, not a server; serve Ternary Bonsai 2 via mlx or tensorfold instead."
engine: "MLX-fast (Bonsai 2)"
id: mlx-fast-bonsai2
repo: https://github.com/Layr-Labs/mlxfast-bonsai2-27b-engine
ref: main
ref_kind: branch
pinned: 0c7c39233afa8aa3e22ac9f36f113b1d2389c3af
verified: "2026-10-05"
license: OpenMDW-1.1
servable: via
via: [tensorfold, mlx]
backends: [metal]
os: [darwin]
formats: [mlx-safetensors]
upstream_watch: [README.md, setup.sh, Package.swift, fixtures/bonsai2_27b_mlx_v1_track.json]
---

# MLX-fast (Bonsai 2) — not servable

A Swift + Metal **speedup-benchmark engine** for Ternary-Bonsai-2-27B (track
`bonsai2-27b-mlx-v1`). Its `bench-worker` speaks a private Engine Protocol v1 to a
separate benchmarker (`benchd`). There is **no OpenAI-compatible HTTP server** and no
releases.

llgenie never installs it. When the index's best t/s for a model comes from
this engine, the resolver (#94) offers the `via` engines instead: `tensorfold`
(supports Ternary Bonsai 2 27B on MLX), then `mlx`.

Building it for benchmarking only: macOS 14+, Apple Silicon, full Xcode (the
`metal` compiler), Swift 6, CMake, about 22 GiB disk, about 13 GB unified RAM; `./setup.sh`.
