# Tasks

- [x] `scripts/engine_skills.py::base_cache_ref(backend)` derives the buildx cache ref from the base Dockerfile content hash (`buildcache-<hash[:10]>`, the same hash `base_tag` carries).
- [x] `scripts/engine_image.py::build_base` passes `f"{REGISTRY}/{es.base_cache_ref(backend)}"` to `_buildx` (never the fixed `:buildcache`); read and write share the content key.
- [x] `tests/test_engine_skills.py::test_build_base_uses_a_content_keyed_cache_ref` proves (a) all four base cache refs track their base content hash, (b) a perturbed Dockerfile re-keys the ref, (c) the seam passes the content-keyed ref to buildx — green under `make test-unit` and `make check-engine-base-cache`.
- [x] `make check-engine-base-cache` target declared `.PHONY` and documented in `docs/ENGINES.md`; `make check-engine-base-cache` exits 0.
- [x] OpenSpec change `engine-base-cache-keyed-by-content` present with proposal/spec/tasks; spec scenarios carry `- **Test:**` lines; `docs/ENGINES.md`, `agent-wiki/` dated note and `CHANGES.md` row accompany the change and the PR body.
