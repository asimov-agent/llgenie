# cuda start scripts create /dev/nvidia-modeset before CDI injection

## Why

Picking a cuda engine (Strata on this host) dies before the container starts
(issue #157):

```
docker: Error response from daemon: CDI device injection failed: failed to inject devices: failed to stat CDI host device "/dev/nvidia-modeset": no such file or directory
```

The `nvidia_modeset` module can be loaded while `/dev/nvidia-modeset`
(character device 195, 254) was never created. `nvidia-ctk cdi generate`
lists that node, and `docker run --device nvidia.com/gpu=all` stats it and
aborts. `nvidia-modprobe` is setuid and `nvidia-modprobe -m` creates the node.
`make install` writes the start scripts and the llama-server shims, and they
go straight to `docker run`.

## What Changes

- A cuda start script and the llama-server / prism-server shims that
  `make install` writes run `nvidia-modprobe -c 0 -m -u` when they are about
  to pass `--device nvidia.com/gpu=all` and `/dev/nvidia-modeset` is missing.
  If the node is still missing, the script exits 1 and prints
  `nvidia-modprobe -m`.
- `make run-engine` (`engine_image.run`) does the same check before
  `docker run`.
- `LLGENIE_NO_GPU=1` rewrites the gpu flags first, so that path does not call
  `nvidia-modprobe`. Non-cuda scripts do not contain the call.

## Impact

- `scripts/install_engine_launchers.py` (generated `~/bin/llgenie-engine-*`,
  `~/bin/llama-server`, `~/bin/prism-server`)
- `scripts/engine_image.py` (`make run-engine`)
- `tests/test_engine_skills.py`
- `README.md`
