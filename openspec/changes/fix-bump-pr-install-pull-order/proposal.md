# ci: a bump PR must publish its engine image before its own install job pulls it

Issue: [#169](https://github.com/asimov-agent/llgenie/issues/169) (related:
[#155](https://github.com/asimov-agent/llgenie/issues/155),
[#153](https://github.com/asimov-agent/llgenie/issues/153) / PR #154)

## Why

A bump PR pins one engine to a new upstream commit. Its CI run builds and
publishes exactly that engine's images — one image per backend variant, by
design (`CHANGED` scoping, #153) — and `make push-engine` is an unconditional
step of every `engine-image-*` job, so a same-repo `pull_request` run does push
them (verified: run 38121659510 pushed
`ghcr.io/asimov-agent/llgenie/llama-cpp:23b0202a-021e11d2-cuda`; the current
bump tags `llama-cpp:f2cc7282-*` and `llama-cpp-prism:e8fd209c-cb5b6dc0-cpu`
answer `200` on GHCR).

The publish lands too late for the same run's `install` job. `pipeline.yml`
`install` needs only `ci-images`, so it runs in parallel with `engine-image-*`
and asks GHCR for the brand-new tag before anyone has pushed it:

```
04:48:08  [install] backend cpu: llama.cpp, llama.cpp-prism (pull published images only)
04:48:08  [engine-image] $ docker pull ghcr.io/asimov-agent/llgenie/llama-cpp:23b0202a-2da4cf2a-cpu
04:48:08  [install] FAIL llama.cpp/cpu: not published in ghcr.io/asimov-agent
04:51:26  engine-image-llama.cpp-cpu  completed success   # the push that would have satisfied it
```

(run 38112341463 / PR #130; the same shape on run 38186233274 / PR #168, where
`linux / install` failed 23:59:17 → 00:00:41 and `engine-image-llama.cpp-cpu`
pushed at 00:05:28.)

`make install` pulls through `install_engine_launchers.ensure_image` →
`engine_image._available`, which tries the registry pull **once**. Only
`engine_image.pull_published` (the `test-published-engine` path) waits out that
race. So the same race is handled in one code path and not the other, and every
first run of a new pin is red. A branch pushed several times looks green by
accident because an earlier run already published the tag.

## What Changes

- `install_engine_launchers.py` gains `wait_published(arch, only)`: it resolves
  exactly the tags `install()` would pull for that backend (same
  `CORE_ENGINES` / `variant_for` / `engine_image.resolve`), polls the registry
  manifest for each (no pull, no build), and returns non-zero — naming every
  tag still missing — when one never appears. One code path, no
  build-instead-of-pull fallback, no silent skip.
- New gate `make ci-wait-engine-images ARCH=<backend>` drives it. `make ci-install`
  runs it **before** `make ci-install-run`. The OS branch lives in the gate: Darwin
  prints that macOS pulls no engine image and does no lookup, Linux polls the
  registry. `ci-install` stays OS-neutral. The gate is a make prerequisite, not a
  workflow step, and it is defined after `HOST_OS := $(shell uname -s)`. The
  `install` job keeps running exactly one `make ci-<job>` target.
- `engine_image._available` keeps its single-attempt behaviour for local build
  decisions; the publish race is waited out by the CI gate, not by every
  `make build-engine` on a laptop.
- `tests/test_ci_publish_order.py` locks the gate (step order in
  `pipeline.yml`), the tag identity (the gate resolves exactly what `install`
  pulls), the loud failure on a tag that is never published, and a real GHCR
  manifest check that every image `make install` pulls is published. Wired into
  `make test-unit` and the CI `unit` job.
- README and AGENTS.md describe the gate and correct the stale claim that a
  `pull_request` run never publishes.

## Impact

- `scripts/install_engine_launchers.py`, `Makefile`,
  `.github/workflows/pipeline.yml`, `README.md`, `AGENTS.md`
- `tests/test_ci_publish_order.py` (new, wired into `make test-unit`)
