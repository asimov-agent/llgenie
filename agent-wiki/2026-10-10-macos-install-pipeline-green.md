# 2026-10-10 llgenie macos / install pipeline — fixed green

## Goal
PR #121 / issue #120 (`make ci-install` on macOS) failed on the three macOS pipeline jobs
(`install`, `cpu-health`, `top-tier`) and the hermetic unit suite. Task: monitor CI and drive it green.

## Root causes fixed
1. **Intel macOS `make install` installs arm64 Metal wheels it can't run** — LiteRT/MLX/TensorFold
   publish Apple Silicon wheels only; the `macos-15-intel` runner could never install them.
   → `7e679d4`: on Darwin `x86_64`, `make install` (no `--ensure`) prints
   `no native Metal engines and no engine image is pulled` and exits 0.
2. **`test-built-engine` / `uninstall` had nothing to act on** — they follow `make install` and
   failed loudly when no start scripts were written (`test()` returns 1).
   → `113f840`: on Intel macOS those two are no-ops that exit 0; Linux still fails on a missing install.
3. **`--arch cpu` must still be refused on Intel** — `macos / cpu-health` and `macos / top-tier`
   run `install_engine_launchers --arch cpu` and assert it is refused (`rc != 0`).
   → `3526d3d`: an explicit non-metal `--arch` is refused on Intel; only default install /
   `--test` / `--uninstall` no-op.
4. **`--ensure <engine> --arch metal` must still install natively** — the llgenie pick path,
   exercised hermetically by `tests/test_tensorfold_seamless.py` on the Intel runner via
   `LLAMA_BACKEND=metal`. The Intel guard returned 0 for `--ensure` too, failing both seam tests
   (`macos / unit` red, `assert [] == ['uv tool install ... tensorfold ... @v0.6.5']`).
   → `cb182a4`: `--ensure` bypasses the Intel no-op and reaches `ensure_native`.
5. **Spec lock** → `0bf090b`: Intel scenario names the no-op / refusal / ensure locks.

## Verification
- Local (host): `make test-unit` 805 passed (incl. TensorFold seam + all three Intel locks),
  `make openspec-validate NAME=macos-parity-install` valid, `make lint` OK.
- CI run `38011213913` (head `cb182a4`) and run `38011904799` (head `0bf090b`):
  **all 10 `macos / *` jobs SUCCESS** — install, cpu-health, top-tier, unit, lint, openspec,
  cron, watch-report, dispatch-e2e, agents-read. No completed failures anywhere on the run.
  (Earlier superseded runs: `38007002663`/`3526d3d` proved install+cpu-health; `38001242985` was the pre-fix red install.)

## Locks
`tests/test_macos_install.py`:
- `test_intel_mac_install_does_not_install_metal_engines`
- `test_intel_mac_built_engine_test_and_uninstall_are_noops` (incl. `--arch cpu` refused)
- `test_intel_mac_ensure_still_installs_a_metal_engine_natively`

## Run 38012660601: the macOS end-of-pipeline jobs do not belong on macOS
- `macos-published / install-published-*` failed: `docker: command not found` at the GHCR login.
  macOS never runs an inference server in a container, so it has no published images to test.
- `native-engine-macos-arm64` never finished (cancelled): GitHub's macOS runners have no usable Metal GPU.
- Both jobs are removed from `ci.yml` (OpenSpec §17); `published.yml` is Linux only. Native Metal
  engines are proven with `make ci-engines BACKEND=metal` on an Apple-Silicon host.
- `macos / top-tier` on that run was a live Hugging Face API flake (429/5xx), green on the two runs before.

## Commits
The branch is squashed into one commit for PR #121 at the user's request (no review yet).
Merge waits on a reviewer's approval per AGENTS.md.
