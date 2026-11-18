# Engine buildx cache namespaces keyed to content hashes (issue #2891)

## What was verified

Issue #2891 measured a cold ROCm engine-base build at 45-90+ minutes (engine-build run
44143247189: the ROCm job still building at 61+ minutes) and four engine PRs re-shipping
near-identical ROCm layers 28 times in one day. The registry layer cache was already
wired into the seam (#1694/#1842/#1880/#1915: `_cache_read_args`/`_cache_write_args`),
but the cache REFS were fixed names — `llgenie/base-<backend>:buildcache` and
`llgenie/<engine>:buildcache-<variant>` — so a base bump replayed a stale,
content-unrelated namespace.

This lane keys both derivations to the hashes the tags already carry (OpenSpec change
`engine-cache-namespace-2891`, PR #2912):

- `build_base` exports/reads `llgenie/base-<backend>:<basehash>-buildcache` — the digest
  `engine_skills.base_tag` computes from the rendered base Dockerfile;
- `build` exports/reads the full cell tag suffix, `llgenie/<engine>:<pin8>-<content-hash>-<variant>-buildcache`,
  where the content hash covers the rendered cell Dockerfile (whose `FROM` embeds the
  base tag hash), so a base bump = new tag = new cache namespace, exactly the
  `539dc9d6-e82c9353` pin shape the issue names.

`make check-engine-cache-namespace` (new gate) runs `tests/test_engine_cache_namespace.py`:
5 hermetic tests — stubbed buildx, no docker — asserting (a) the base ref IS the content
tag plus `-buildcache`, (b) a rendered-content change yields a different namespace,
(c) unchanged content replays the same one (AC 2's warm-replay precondition), (d)-(e)
the cell ref carries the full tag suffix and follows a hash change. Green locally:
`make check-engine-cache-namespace` rc=0 (5 passed).

## Key decisions

- Cache WRITE policy untouched: `LLGENIE_CACHE_WRITE` stays owner-guarded-dispatch-only
  (#1694/#155/#638), `NO_CACHE_EXPORT` docker-driver escape untouched (#1915).
- Existing seam tests call `_buildx` with explicit refs (signature unchanged) — none
  pinned the derived names, so no test updates were needed for them.
- AC 1 (cache export visible in an engine-build run log) and AC 2 (replayed unchanged
  ROCm cell < 1200s) are proven by engine-build chain runs on the PR head, not locally.

## Current status

Implementation + gate green locally; unit suite green (4040 passed); PR #2912 open against upstream main; AC 1/AC 2 chain evidence tracked as the landing stamp on issue #2891.
First chain on the head pays the one-time cold rebuild under the new namespaces; the
issue's < 20 min warm replay is proven by the head replay after that chain.
