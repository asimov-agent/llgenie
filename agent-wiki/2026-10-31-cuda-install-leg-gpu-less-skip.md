# The cuda install-leg skips (not reds) on a GPU-less runner (#1240)

**Issue:** #1240 · **PR:** this change's PR · **Branch:** `fix/1240-cuda-cdi-install-leg`

## Problem

Every `ARCH=cuda` cell of `engine-build.yml` powers its install-leg on a **GPU-less
GitHub-hosted `ubuntu-latest` runner** and fails at `engine-launchers` (`Makefile:281`):
`[install] FAIL cuda host without the NVIDIA CDI spec: the engine containers could not use
the host driver. Install nvidia-container-toolkit and run sudo nvidia-ctk cdi generate`
(Covers both repeats: run `41236321425` @ `d85edab` and `41245076650` @ `abc1d3ac`). The
leg installs launchers that `docker run` the cuda image with `--device nvidia.com/gpu=all`
(the CDI device mounts the host driver), so exercising it *requires* an NVIDIA GPU on the
run host — a GPU-less GitHub runner has none, and installing nvidia-container-toolkit there
still yields no CDI spec (nothing to enumerate). This is a runner-infra precondition, not a
defect in any engine. The repo's docs already require the CDI path for cuda
(`README.md:79`, `AGENTS.md:696-697`, `docs/ENGINES.md:311-313`, `Makefile:257`).

## What changed

1. `scripts/install_engine_launchers.py`: new `--install-leg-skip-reason` subcommand +
   `cuda_install_exercisable()` (probes `detect_server._has_nvidia_gpu()`, so a GPU-less
   runner has no GPU) + `install_leg_skip_reason(arch)` returning the documented reason for
   `arch == "cuda"` on a GPU-less host, else `""`. A GPU host proceeds; a GPU host that
   merely lacks the CDI spec still FAILS loudly in `install()` (the existing message tells
   the user exactly how to fix the misconfiguration — the skip is only for the genuinely
   in-exercisable GPU-less case).
2. `Makefile` `test-engine-install:` asks `--install-leg-skip-reason --arch $(ARCH)` first;
   when it returns a reason the leg prints it and `exit 0` (SKIP, skip-not-red), otherwise
   the existing `engine-launchers → test-built-engine → ci-install-uninstall` chain runs
   unchanged. The comment on the target now states the cuda rule.
3. `docs/ENGINES.md` + `.github/workflows/engine-build.yml` header comment: state that the
   cuda install-leg is NOT exercisable on GitHub-hosted GPU-less runners and skips there —
   so the red is a known, classified limitation rather than an unowned red.
4. Added `tests/test_engine_skills.py::test_cuda_install_leg_skips_on_a_gpu_less_runner_but_runs_on_a_gpu_host`:
   on a GPU-less runner cuda's skip reason is non-empty and `main --install-leg-skip-reason
   --arch cuda` exits 0; on a GPU host all skip-reason calls return `""`.

## Why skip-not-red

The alternative (add CDI provisioning to the runner rows) is that lane's workflow ask; this
PR takes the issue's documented option — a GPU-less runner SKIPS the cuda install-leg with a
reason, so the matrix stops redding on infra the runner cannot exercise, while every row that
CAN run (cpu/vulkan/rocm, and cuda on a GPU host) is still genuinely exercised. The
`ci-install-uninstall` mkdir fix (#1196/is #1220's vehicle) is uninvolved and unaffected.
