# cuda install-leg skips with a documented reason on a GPU-less runner

## Why

The `engine-build` producer's install-leg (`make test-engine-install`, issue #1027)
runs, per row, after that row's image is built and published. For cuda rows it
installs launchers that docker-run the engine with `--device nvidia.com/gpu=all`
— the nvidia-container-toolkit CDI device, which mounts the **host's** NVIDIA
driver at runtime. Exercising the leg therefore needs an NVIDIA GPU on the run
host so a CDI spec exists (a GPU-less host has none to enumerate no matter what
tooling is installed).

GitHub-hosted `ubuntu-latest` runners are GPU-less, so every cuda install-leg in
a full `engine-build` sweep fails at `Makefile:281` (`install()` from
`scripts/install_engine_launchers.py`) with the cuda CDI error (runs 41245076650,
d85edab; measured at abc1d3ac). The leg is not exercisable on the host CI could
actually provide, and nothing about this host can exercise a cuda install, so a
GPU-less runner must not red a gate it cannot exercise.

## What Changes

- The producer's install-leg (`make test-engine-install`) first asks the
  launcher installer whether the leg for this row's arch is exercisable on THIS
  host (`scripts/install_engine_launchers.py --install-leg-skip-reason --arch`).
- A cuda leg on a host with no NVIDIA GPU prints the documented, actionable
  reason and exits 0 (a SKIP, not a red). A GPU host proceeds; a GPU host that
  merely lacks the CDI spec still FAILS loudly in `install()` with the existing
  message telling the user how to generate it (`cuda_cdi_ready`).
- The reason names the exact fix
  (`sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`).
- Docs (`docs/ENGINES.md`) and the `engine-build.yml` header state that the cuda
  install-leg is not exercisable on GitHub-hosted GPU-less runners and runs on a
  GPU+CDI-capable host instead.
- cpu (and every non-cuda) install-leg runs exactly as before — the skip is a
  cuda-only gate.

## Impact

- `Makefile` (`test-engine-install`)
- `scripts/install_engine_launchers.py` (`--install-leg-skip-reason`,
  `cuda_install_exercisable`, `install_leg_skip_reason`)
- `.github/workflows/engine-build.yml` (header docs)
- `docs/ENGINES.md`
- `tests/test_engine_skills.py`

No change to `check-security-scan`, `enforce_events`, #1227 automerge, census, or
#1196 — only the cuda install-leg gating on GPU-less run hosts.
