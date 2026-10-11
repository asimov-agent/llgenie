## ADDED Requirements

### Requirement: cuda start scripts create the modeset device node
`make install` MUST write cuda start scripts and the llama-server / prism-server
shims so that, when the gpu flags include `nvidia.com/gpu=all` and
`/dev/nvidia-modeset` does not exist, the script runs
`nvidia-modprobe -c 0 -m -u` before `docker run`. If the node is still missing,
the script MUST exit 1 and print `nvidia-modprobe -m`. A non-cuda script MUST
NOT call `nvidia-modprobe`. `LLGENIE_NO_GPU=1` MUST drop the CDI device before
that check, so the probe does not run.

WHEN a cuda start script or shim is about to pass `--device nvidia.com/gpu=all`
and `/dev/nvidia-modeset` is missing
THEN it runs `nvidia-modprobe -c 0 -m -u` before `docker run`, and exits 1 with
`nvidia-modprobe -m` if the node is still absent.

#### Scenario: cuda launcher and shim guard the CDI device
Given  a cuda start script and a cuda llama-server shim written by make install,
When   their text is read,
Then   each runs `nvidia-modprobe -c 0 -m -u` only when the gpu flags include
       `nvidia.com/gpu=all` and `/dev/nvidia-modeset` is missing,
And    that command appears before `docker run`,
And    a still-missing node exits 1 and the message names `nvidia-modprobe -m`,
And    a cpu start script does not call `nvidia-modprobe`.
- **Test:** `tests/test_engine_skills.py::test_cuda_start_script_creates_nvidia_modeset_before_cdi`

### Requirement: make run-engine creates the modeset device node
`make run-engine` MUST create `/dev/nvidia-modeset` with
`nvidia-modprobe -c 0 -m -u` before `docker run` when the run args include
`nvidia.com/gpu=all` and the node is missing. If `nvidia-modprobe` cannot
create it, the run MUST fail and print `nvidia-modprobe -m`. Run args that do
not request that CDI device MUST NOT call `nvidia-modprobe`.

WHEN `engine_image.run` is given run args that include `nvidia.com/gpu=all`
and `/dev/nvidia-modeset` is missing
THEN it runs `nvidia-modprobe -c 0 -m -u` before `docker run`, and fails with
`nvidia-modprobe -m` if the node is still absent.

#### Scenario: the node is created before the container starts
Given  cuda run args and no `/dev/nvidia-modeset`, with `nvidia-modprobe` on PATH,
When   the modeset check runs,
Then   it executes `nvidia-modprobe -c 0 -m -u`.
- **Test:** `tests/test_engine_skills.py::test_run_engine_creates_nvidia_modeset_before_cdi`

#### Scenario: a missing probe fails closed
Given  cuda run args, no `/dev/nvidia-modeset`, and no `nvidia-modprobe`,
When   the modeset check runs,
Then   it fails and the message names `nvidia-modprobe -m`.
- **Test:** `tests/test_engine_skills.py::test_run_engine_fails_when_modeset_node_cannot_be_created`

#### Scenario: an existing node and a non-cuda run skip the probe
Given  a node that already exists, or run args that do not request the CDI device,
When   the modeset check runs,
Then   `nvidia-modprobe` is not called.
- **Test:** `tests/test_engine_skills.py::test_run_engine_skips_nvidia_modprobe_without_a_missing_cuda_node`
