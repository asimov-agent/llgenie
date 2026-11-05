# derived engine images build their base as an internal stage so FROM resolves on the container driver

## Background (measured 2026-11-05)

`engine-build` workflow_dispatch (run **41971301136**, job 127060077658, mlx-cpu)
fails its derived FROM-base cells — base and cell both build on the docker-container
driver, and the derived `FROM llgenie/base-cpu:<sha>` cannot see the base left by the
earlier build. The base build (`docker buildx build --no-cache -t
llgenie/base-cpu:d0eb107fa0 --load`) lands the image in the docker **daemon**, not the
buildkit store the NEXT invocation's `FROM` searches; buildkit falls through to the
private docker.io tag and is denied:

```
FROM llgenie/base-cpu:d0eb107fa0 -> docker.io ... pull access denied ...
insufficient_scope: authorization failed
make: *** [Makefile:1306: build-engine] Error 1
```

Pre-#1747 the local path forced `--builder default` (docker driver = the daemon), so
FROM saw the daemon-local base; #1747 gates that away under `CACHE_WRITE` to get a
registry-cache export — and FROM-base cells broke in the other direction. The two
driver properties are mutually exclusive per driver, and the read-only verification
cell has no push rights, so a pullable-registry FROM is not an option there.

## The answer

`scripts/engine_image.py::build()` now, for a derived cell that `FROM`s the shared
toolchain base on the verification/local path, folds `containers/engines/base/
Dockerfile.<backend>` in as the FIRST stage (`AS llgenie-base`) and rewrites the
derived `FROM llgenie/base-cpu:<sha>` to `FROM llgenie-base`, lifting base + derived
in ONE buildx invocation. The committed base Dockerfile is byte-identical to
`render_base_dockerfile()` — verified: cpu hashes to `d0eb107fa0`, the exact failing
sha — so the inlined stage reproduces what the bare-tag `FROM` resolved. The
publishing path (`REGISTRY and push`) is unchanged: `build_base` pushes the base and
the derived `FROM` uses the registry-qualified base.

Local buildx probes (Docker 29.9.2) confirm this is the ONLY correct shape on a
docker-container builder: a base from a prior invocation via `-t`, `--load`, or
`--output type=image,name=` is NEVER `FROM`-resolvable (all fall to docker.io); an
internal-stage base in ONE invocation resolves.

**measured:** 34 tests pass (force_rebuild + image_matrix); 85 across the
cache-adjacent engine suite; linefeed + AST clean. #1753.
