# Tasks

- [x] 1. `scripts/install_engine_launchers.py` adds `cuda_install_exercisable()` (has an NVIDIA GPU via `detect_server._has_nvidia_gpu()`), `install_leg_skip_reason(arch)` ('' unless arch==cuda and GPU-less, then the documented actionable reason), and the `--install-leg-skip-reason --arch` CLI flag exiting 0 either way.
- [x] 2. `Makefile test-engine-install` runs `scripts/install_engine_launchers.py --install-leg-skip-reason --arch "$(ARCH)"` first, echoes a non-empty reason and exits 0 (SKIP, never a red); otherwise runs the install-leg exactly as before.
- [x] 3. `docs/ENGINES.md` and the `engine-build.yml` header state the cuda install-leg is not exercisable on GitHub-hosted GPU-less runners and SKIPS there with a documented reason, running on a GPU+CDI-capable host.
- [x] 4. Tests lock the skip/runs/untouched scenarios in `tests/test_engine_skills.py`; `make test-unit` (hermetic) and `make openspec-validate NAME=cuda-install-leg-gpu-less-skip` pass.
