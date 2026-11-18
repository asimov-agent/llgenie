# Spec delta: ci-image-build (cache refs keyed to image content)

## ADDED Requirements

### Requirement: The helper-image buildx cache ref is keyed to the image content

The registry layer-cache ref for a helper image SHALL name the exact content the cache
caches: `llgenie/<name>:<12-hex content tag>-buildcache`, where the tag is the same
`tag(name, root)` hash the pushed image ref carries. A fixed cache name SHALL NOT be used.

#### Scenario: unchanged content replays the same namespace

- **WHEN** `cache_ref(name, root)` is computed twice for the same inputs
- **THEN** both refs are identical and match `llgenie/<name>:[0-9a-f]{12}-buildcache`

#### Scenario: changed content moves to a new namespace

- **WHEN** a hashed input (Dockerfile or lockfile line) changes and `cache_ref` is computed again
- **THEN** the ref differs from the previous one and still ends with `-buildcache`

#### Scenario: publish passes the keyed refs to buildx

- **WHEN** `publish` builds and pushes a helper image
- **THEN** the buildx command carries `--cache-to type=registry,ref=<keyed ref>,mode=max`
  and reads `--cache-from` only when that same keyed ref is published
