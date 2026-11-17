# engine-base-cache-keyed-by-content

## ADDED Requirements

### Requirement: a base's buildx layer-cache ref is keyed by the base content hash

Each of the four engine base images (`cpu`, `cuda`, `rocm`, `vulkan`) MUST derive its buildx
registry layer-cache ref from the SAME content hash its base tag carries — the sha256 of the
rendered base Dockerfile — so a base dockerfile change starts a fresh cache namespace and an
unchanged base keeps its warm one. `scripts/engine_skills.py::base_cache_ref(backend)` MUST return
`llgenie/base-<backend>:buildcache-<hash[:10]>` where `<hash[:10]>` equals the hash `base_tag`
embeds, and `scripts/engine_image.py::build_base` MUST pass that ref (never a fixed `:buildcache`)
as the `cache_ref` to `_buildx`. Because the read and write share the ref, a content change
automatically re-keys BOTH sides.

WHEN `build_base(backend, …)` builds an engine base
THEN the buildx cache ref it hands `_buildx` is `buildcache-<hash[:10]>` matching the base tag's content hash, and a changed base Dockerfile produces a different cache ref.

#### Scenario: the cache ref tracks the base tag's content hash for all four backends

- **Given** the four base backends `cpu`, `cuda`, `rocm`, `vulkan`
- **When** `base_cache_ref(backend)` and `base_tag(backend)` are derived from the same rendered Dockerfile
- **Then** the cache ref is `llgenie/base-<backend>:buildcache-<hash[:10]>` with the identical hash the base tag carries, for every backend
- **Test:** `tests/test_engine_skills.py::test_build_base_uses_a_content_keyed_cache_ref` (the four-backend loop asserting `ref == f"llgenie/base-{backend}:buildcache-{hash}"`)

#### Scenario: a base Dockerfile content change starts a new cache namespace

- **Given** a base whose rendered Dockerfile gains a new `RUN` line
- **When** `base_cache_ref` is recomputed
- **Then** it differs from the pre-change ref (and the base tag differs too)
- **Test:** `tests/test_engine_skills.py::test_build_base_uses_a_content_keyed_cache_ref` (the perturbed-`render_base_dockerfile` assertion)

#### Scenario: the build seam passes the content-keyed ref to buildx

- **Given** `build_base("cpu")` with the base not locally available
- **When** `_buildx` is invoked
- **Then** it receives `cache_ref = ghcr.io/…/llgenie/base-cpu:buildcache-<hash>` matching the cpu base content hash
- **Test:** `tests/test_engine_skills.py::test_build_base_uses_a_content_keyed_cache_ref` (the `_buildx`-capture assertion)

### Requirement: a hermetic gate proves the base cache keying

A documented make target `check-engine-base-cache` MUST run the content-keying proof hermetically
(no container, no registry) and exit 0 only while every base cache ref tracks its base content
hash. The proof is also in the auto-discovered unit suite so `make test-unit` runs it in CI.

WHEN `make check-engine-base-cache` runs
THEN it executes the content-keying test and exits 0 (rc=0) on a conforming tree.

#### Scenario: the target exits 0

- **Given** the conforming tree in this change
- **When** `make check-engine-base-cache` runs
- **Then** it reports `1 passed` and exits 0
- **Test:** `make check-engine-base-cache` -> `tests/test_engine_skills.py::test_build_base_uses_a_content_keyed_cache_ref` (the target's sole step; the same body runs under `make test-unit`)
