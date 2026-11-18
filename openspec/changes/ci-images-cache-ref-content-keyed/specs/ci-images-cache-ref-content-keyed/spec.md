# ci-images-cache-ref-content-keyed

## MODIFIED Requirements

### Requirement: helper-image buildx cache refs are keyed to the image's content

The helper-image layer-cache ref MUST carry the same content identity as the image tag it warms:
`<registry>/llgenie/<name>:<content-hash>-buildcache` — one namespace per Dockerfile + context,
derived from the same hash `tag(name, root)` computes. Unchanged content MUST replay the same
namespace; a content change MUST produce a new namespace. Build and push policy is unchanged.

#### Scenario: the cache ref carries the image's content hash

- **Given** a helper-image name and a repo root whose content hashes to a 12-hex value
- **When** `ci_images.cache_ref(name, root)` runs
- **Then** it returns `<registry>/llgenie/<name>:<12-hex>-buildcache`, the hex equal to
  `tag(name, root)` and carrying the `-buildcache` suffix — never the fixed `<name>:buildcache`
- **Test:** `tests/test_ci_images.py::test_cache_ref_is_keyed_to_the_image_content`

#### Scenario: changed content moves the namespace, unchanged content replays it

- **Given** a helper image's content (Dockerfile + lockfiles) in a copy of the repo
- **When** `cache_ref` is computed twice on unchanged content, then once after a lockfile edit
- **Then** unchanged content yields the same ref and the edited content yields a different ref,
  both with the `-buildcache` suffix — one namespace per content, never a shared fixed name
- **Test:** `tests/test_ci_images.py::test_cache_ref_is_keyed_to_the_image_content`

#### Scenario: publish wires the content-keyed cache ref into the build

- **Given** `publish(name)` building a new helper-image content hash with a published cache
- **When** the buildx build runs
- **Then** both `--cache-from` and `--cache-to` name `<registry>/llgenie/<name>:<hash>-buildcache`
  (not a fixed `<name>:buildcache`), and a never-seeded cache still omits `--cache-from` while
  seeding `--cache-to` for the next run
- **Test:** `tests/test_ci_images.py::test_publish_builds_both_arches_and_pushes_a_new_hash`,
  `tests/test_ci_images.py::test_a_first_publish_omits_cache_from_but_keeps_cache_to`
