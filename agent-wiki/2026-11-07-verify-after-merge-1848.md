# Verify-after-merge: #1848 AC-2 re-measure + routing (issue #1875)

## Finding, re-measured at the current head

PR #1848 ("read --cache-from only when the registry cache exists, so a cold cache is a rebuild,
never a red cell") merged to `main` carrying **AC-2 ticked**: "A default `make engine-build` sweep
completes with all cells success." Re-measuring on merged main — run `42249201251`
(`workflow_dispatch`, head per issue) — that criterion does **not** hold: **26 success / 3 FAILURE**,
all three engine-build red:

- `engine-build-vllm-rocm` (job `127999598828`) → `exclude-dependencies` unknown field under
  `--no-build-isolation` (poetry build backend) → **#1558**
- `engine-build-vllm-cuda` (job `127999598717`) → `buildcache-cuda: not found` + cold build killed
  `exit 143` (timeout) → **#1843**
- `engine-build-tensorfold-cuda` (job `127999598844`) → GHCR `403 Forbidden` anonymous token on
  `tensorfold:pull,push` → **#1843**

All three job conclusions re-read `failure` at the issue-cited job ids (re-measured this session).

## Routing

This issue is the verify-after-merge finding only — it does not re-implement the fixed code:

- **#1843** (the GHCR cache/auth pair: cold-cache `--cache-to` 403 + login gated off `inputs.push`)
  is the engine-build workflow half, and this lane's fix landed it as **PR #1899**
  (`ci/1843-ghcr-login-gate`, head `8de2906b`): the GHCR-login step now runs for every owner-guarded
  cell so a build-and-verify cache-warm cell is authenticated and may seed the shared cache (#1694)
  instead of 403-ing. With that plus #1848's tolerant cache-read, a cold-cache cell reads
  `--cache-from` only when the registry cache exists.
- **#1558** (rocm pyproject `exclude-dependencies` under `--no-build-isolation`) routes to its own
  tracker — separate lane, not this PR.

## Acceptance criteria disposition

- **AC-1** (fresh default sweep all green): **not proven** at merged main — recorded as the finding;
  the three reds are routed exactly to #1558 / #1843 above with this issue + run `42249201251`
  named, which satisfies the OR-clause (route, not re-run).
- **AC-2** (cold-cache cell no longer reds on a cache that does not exist): **met once #1899
  lands** — it makes the `LLGENIE_CACHE_WRITE`/ghcr-login gating consistent so a non-push cell no
  longer arms an unauthenticated `--cache-to`; #1848 AC-1 covers the read side.
- **AC-3** (no regression, push path still logs in): **met** — #1899 keeps `make push-engine`
  gated on `inputs.push == 'true'` after the binary test (no regression).

## Not covered

The post-merge producer re-run of a full default sweep at the fix head is a dispatcher-owned run,
out of scope for this record (the sweep reads `engine-build.yml` from `main` after #1899 merges).
