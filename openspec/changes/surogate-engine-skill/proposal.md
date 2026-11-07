# Ship Surogate as a cuda engine skill

## Why

The weekly registry sync (issue #179) surfaced the engine **Surogate** (`invergent-ai/surogate`)
as unskilled: it has no `skills/engines/<id>/SKILL.md`, no params, no image, so `rank_engines`
drops it and no model can be offered through it. Surogate is a genuine, active, Apache-2.0 CUDA
serving engine (published manylinux cu130 wheel, OpenAI-compatible API, GGUF/safetensors), so it
should be shipped, not excluded.

## What changes

1. **Carry the Surogate registry entry additively** into `data/models.json` + `data/measurements.json`
   (engine row + the `qwen3.8-flash-next-125b` measurement row). The vendored 2026-10-31 store
   predates Surogate (upstream added it 2026-11-04); the full store sync is blocked on 7 unrelated
   upstream post removals the additive-only gate refuses, so only the additive Surogate entry lands.
2. **Ship the skill** `skills/engines/surogate/SKILL.md` pinned `v1.5.15` (`ad6c0bbf…`): installs the
   published cu130 wheel (the wheel IS the engine), launch `surogate serve --host --port
   --served-model-name`, health `GET /health`.
3. **Generate + commit** `containers/engines/params/surogate.json` + `Dockerfile.cuda` via
   `make generate-engine-params ENGINE=surogate` so the `engine-image-*` CI matrix builds the
   cuda cell with no workflow edit.
4. **Record the wheel-install exception** in `scripts/engine_source_guard.py::KNOWN_NOT_SOURCE`
   for `(surogate, cuda)` (the wheel is the precompiled product — litert precedent).

## Not covered

- A t/s runtime witness on a real GPU: the acceptance for #1962 is the registry/skill gate green,
  not a measured serving number. Surogate is a new add; its image builds and a live t/s witness
  ride the normal engine-image build + run path after this change lands.
