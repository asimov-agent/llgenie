# Engine-bump regen guard: judge the delta, not the cumulative tree (#2506)

Verified against the OpenSpec change `engine-bump-regen-guard` (issue #2506):

- Reproduced the defect at `origin/main` `b2e3b1ec4`: `make engine-bump-daily` planned 4 moved
  engines; llama.cpp bumped fully; ollama/strata/tensorfold each died with
  `regen changed a file outside <engine>: containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu`
  — the cumulative `git status` carrying llama.cpp's own completed-bump dirt.
- Fix: `_regen_guard` now snapshots `_porcelain_paths()` before regen and verdicts only paths
  new after it. The five §"Regen guard + changed-engines scoping" tests gained call-sequence-aware
  fakes (first status read = baseline) and keep their original verdicts; new regression test
  `test_regen_guard_ignores_a_prior_engine_s_dirtiness` proves the multi-engine shape.
- `pytest tests/test_engine_bump.py -q` → 75 passed (host venv).

Pipeline duty evidence captured the same day (detached worktree of `b2e3b1ec4`):
`make build-engine ENGINE=ollama ARCH=cpu` → rc=0, `make build-engine ENGINE=llama.cpp ARCH=cpu`
→ rc=0 (`llgenie/ollama:d63b7026-97b16d24-cpu`, `llgenie/llama-cpp:cb44fdb1-db578616-cpu`), and
`make test-engine-image ENGINE=ollama ARCH=cpu` → rc=0 (binary flags answer, entrypoint
`detect` proves client version 0.40.16). Publishing stays on the merge path (GHCR only after
the bump PR lands); this fix unblocks the bump PR the weekly job can never open today.

Current status: branch `feat/engine-bump-regen-guard`, PR pending with `closes #2506`.
