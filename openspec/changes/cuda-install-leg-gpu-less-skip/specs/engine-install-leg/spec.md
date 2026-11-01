# engine-install-leg

## ADDED Requirements

### Requirement: the cuda install-leg skips with a documented reason on a GPU-less run host

The producer's install-leg (`make test-engine-install`, issue #1027/#1240) MUST
first ask the launcher installer whether the leg for this row's arch is
exercisable on THIS host (`scripts/install_engine_launchers.py
--install-leg-skip-reason --arch <arch>`). When the arch is `cuda` and the host
has no NVIDIA GPU, the leg MUST print the documented reason and exit 0 (a SKIP,
never a red): the cuda engines mount the host driver via
nvidia-container-toolkit CDI (`--device nvidia.com/gpu=all`), which needs an
NVIDIA GPU on the run host, and the reason MUST name the fix
(`sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`). On a host WITH an
NVIDIA GPU the cuda leg MUST proceed; a GPU host that merely lacks the CDI spec
MUST still FAIL loudly in `install()` with the existing `cuda_cdi_ready` message.
Every non-cuda arch (cpu, rocm, vulkan) MUST return no skip reason and run its
install-leg exactly as before.

WHEN `make test-engine-install` runs with `ARCH=cuda` on a host whose
nvidia-smi lists no GPU
THEN it prints the documented GPU-less skip reason and exits 0 (never a red),
       naming `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`.

#### Scenario: a cuda install-leg on a GPU-less runner prints the reason and skips
- **Given** a GitHub-hosted `ubuntu-latest` runner (nvidia-smi lists no GPU)
- **When** the engine-build producer runs `make test-engine-install ENGINE=<cuda engine> ARCH=cuda`
- **Then** `install_leg_skip_reason("cuda")` returns a non-empty message mentioning
  `nvidia.com/gpu=all` and the `nvidia-ctk cdi generate` fix
- **And** `make test-engine-install` echoes that reason and exits 0, marking the leg GREEN by SKIP
- **And** the workflow header and `docs/ENGINES.md` state the cuda install-leg is
  not exercisable on GitHub-hosted GPU-less runners and runs on a GPU+CDI-capable host
- **Test:** `tests/test_engine_skills.py::test_cuda_install_leg_skips_on_a_gpu_less_runner_but_runs_on_a_gpu_host`

#### Scenario: the cuda install-leg runs on a GPU host
- **Given** a run host with an NVIDIA GPU (nvidia-smi lists at least one)
- **When** the producer runs `make test-engine-install ENGINE=<cuda engine> ARCH=cuda`
- **Then** `install_leg_skip_reason("cuda")` returns `""` so the leg proceeds
- **And** a GPU host whose CDI spec is absent still FAILS loudly in `install()`
  (covered by `test_cuda_containers_get_the_host_driver_via_cdi`)
- **Test:** `tests/test_engine_skills.py::test_cuda_install_leg_skips_on_a_gpu_less_runner_but_runs_on_a_gpu_host`

#### Scenario: non-cuda install-legs are unaffected
- **Given** `ARCH=cpu` (or rocm/vulkan) on any host
- **When** the producer runs `make test-engine-install`
- **Then** `install_leg_skip_reason("<arch>")` returns `""` and the install-leg runs exactly as before
- **Test:** `tests/test_engine_skills.py::test_cuda_install_leg_skips_on_a_gpu_less_runner_but_runs_on_a_gpu_host`
