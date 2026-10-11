# Tasks

- [x] 1. Cuda start scripts and llama-server / prism-server shims from `make install` run `nvidia-modprobe -c 0 -m -u` before `docker run` when `/dev/nvidia-modeset` is missing, and exit 1 naming that command if it stays missing. Non-cuda scripts do not call it. `LLGENIE_NO_GPU=1` drops the CDI device first.
- [x] 2. `make run-engine` (`engine_image.run`) does the same check before `docker run`.
- [x] 3. README states the guard. Tests lock each scenario (`tests/test_engine_skills.py`).
- [x] 4. `make test-unit` and `make openspec-validate NAME=fix-cuda-nvidia-modeset` pass.
