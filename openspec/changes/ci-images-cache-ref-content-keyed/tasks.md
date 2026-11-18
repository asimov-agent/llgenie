# Tasks

- [x] `scripts/ci_images.py::cache_ref(name)` now takes the repo root and returns
      `<registry>/llgenie/<name>:<tag>-buildcache` — the same content hash the image tag computes —
      with `publish` and `_buildx_push` passing the build root through so the namespace matches the
      content being built.
- [x] Hermetic regression tests: `tests/test_ci_images.py::test_cache_ref_is_keyed_to_the_image_content`
      proves unchanged content replays the same namespace and a changed lockfile moves it; the two
      publish tests now assert a content-keyed ref (`<hash>-buildcache`) for `--cache-from`/`--cache-to`.
- [x] `tests/test_ci_images.py` passes under `make test-unit`.
- [x] Docs: `agent-wiki/2026-11-18-ci-images-cache-ref-content-keyed.md` (#2911) + `CHANGES.md`
      index row; `make check-docs` green.
- [x] `make openspec-validate NAME=ci-images-cache-ref-content-keyed` passes (CLI 1.10.0 — the
      docker daemon is unavailable in the implementation container, so the make target's nerdctl
      seam cannot run; the same `openspec validate <name>` ran directly) and `pr-body.md` carries
      the four labelled parts.
