## ADDED Requirements

### Requirement: Registry layer-cache namespaces track Dockerfile content hashes

The engine build seam SHALL derive every buildx registry layer-cache ref from the content hash the image tag already carries, so a Dockerfile content change starts a new cache namespace instead of replaying a stale one.

For a base image the cache ref SHALL be `llgenie/base-<backend>:<basehash>-buildcache`, where `<basehash>` is the digest `engine_skills.base_tag` computes from the rendered base Dockerfile. For an engine cell the cache ref SHALL carry the cell tag's full content suffix — `llgenie/<engine>:<pin8>-<content-hash>-<variant>-buildcache` — where `<content-hash>` hashes the rendered cell Dockerfile (whose `FROM` embeds the base tag's content hash), so a base or cell change yields a new tag AND a new cache namespace.

Cache WRITE policy (`LLGENIE_CACHE_WRITE`, owner-guarded dispatch only) and the `NO_CACHE_EXPORT` docker-driver escape (#1915) SHALL be unchanged by this requirement.

#### Scenario: base cache namespace follows base content

- **WHEN** `build_base` builds a backend base image
- **THEN** the buildx command's `--cache-from`/`--cache-to` refs carry the base tag's content digest
- **AND** a changed rendered base Dockerfile produces a different cache ref than the unchanged one

#### Scenario: cell cache namespace follows the cell tag hash

- **WHEN** `build` builds an engine cell for one variant
- **THEN** the cache ref carries the cell tag's `<basehash>-<cellhash>` pair and the variant
- **AND** a base or cell content change (a new tag hash) yields a new cache namespace

#### Scenario: the namespace gate is a make target

- **WHEN** `make check-engine-cache-namespace` runs on a tree whose cache refs are content-keyed
- **THEN** it exits 0; it exits non-zero when a cache ref stops tracking the content hash
