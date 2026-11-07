# engine-build: GHCR login for every owner-guarded cell (issue #1843)

This change aligns the engine-build workflow's GHCR-login gate with the cache-write intent it
already documented. Issue #1843: the job set `LLGENIE_CACHE_WRITE: "1"` on every engine cell while
the "Log in to GHCR" step ran only when `inputs.push == 'true'` — so a build-and-verify
(`push=false`) cell armed an unauthenticated `--cache-to type=registry` and GitHub returned a
`403 Forbidden` anonymous `pull,push` token at the cache step. Measured in run `42192579462`, job
`127808054688` (tensorfold-cuda).

The fix gates the login on the same single condition that arms the cache write:
`if: ${{ matrix.engine != 'none' }}`. This workflow is `workflow_dispatch`-only (owner/collaborator),
so every real cell already flows through the owner-guarded dispatch that grants `packages: write` and
may legitimately log in and write the shared registry layer cache (#1694) — including a build-and-
verify cell warming the cache for the next run of the same cell.

## Why

- A cold-cache build-and-verify sweep no longer reds on an anonymous-token 403 for a cache the file
  promised it could write (#1694's cache-warming intent is satisfied).
- The docstring and the gate now tell the same story: the env comment at `LLGENIE_CACHE_WRITE` says
  the run logs in, and the login step does, for every cell.
- No push path or guard is weakened: `make push-engine` still runs only when `inputs.push == 'true'`
  and only after the binary test; the timeout/disk-headroom policies are untouched.

Pinned by a unit test (`test_cache_write_env_and_ghcr_login_share_one_gate`) that fails on the
pre-fix gate and passes on the fix.
