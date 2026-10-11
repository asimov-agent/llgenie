# 2026-10-11 — cuda CDI needs /dev/nvidia-modeset (issue #157)

Picking Strata on this cuda host failed before the container started: NVIDIA CDI
stats `/dev/nvidia-modeset`, and that node was missing even though `nvidia_modeset`
was loaded. `nvidia-modprobe -m` creates it (setuid).

`make install` on a cuda host (`detected_arch` = cuda) writes the cuda start
scripts and the llama-server / prism-server shims. Those scripts, and
`make run-engine`, now run `nvidia-modprobe -c 0 -m -u` when the gpu flags
include `nvidia.com/gpu=all` and the node is missing. `LLGENIE_NO_GPU=1` drops
the CDI device first. Verified: `make test-unit` 3027 passed,
`make openspec-validate NAME=fix-cuda-nvidia-modeset` valid, and
`make engine-launchers ENGINES=strata` rewrote `~/bin/llgenie-engine-strata`
with the guard.
