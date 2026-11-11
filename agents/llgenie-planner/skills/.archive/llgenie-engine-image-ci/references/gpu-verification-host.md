# Host GPU-path verification (llgenie on a CUDA host)

## Installed shims are CPU variants

`make install` on this host writes the engine shims `~/bin/prism-server` and
`~/bin/llgenie-engine-*` pinned to the **`-cpu` image tags** (e.g.
`ghcr.io/asimov-agent/llgenie/llama-cpp-prism:<sha>-cpu`), and the shim never
adds `--device nvidia.com/gpu=all`. So launching a model through the installed
launcher runs the CPU image.

In the launcher log, `warning: no usable GPU found, --gpu-layers option will be
ignored` plus `compiled without GPU support` means the **CPU image** ran — it is
NOT a broken GPU. The CUDA image is ~7GB vs ~1.2GB CPU.

## `~/bin/llgenie` runs the MAIN checkout, not a feature branch

The installed launcher executes the user's main checkout, so it can never test a
worktree feature branch's pick/flag derivation. To exercise branch code, run the
branch's serve script directly via the gguf venv through a wrapper launcher:

```bash
~/llama-gguf-tools/.venv/bin/python \
  <worktree>/scripts/llgenie_serve.py <model-alias> --port <port> &
```

## Prove the real GPU engine image explicitly

The GPU path is only reachable by running the `-cuda` image by hand with the CDI
device mounted (`/etc/cdi/nvidia.yaml` present):

```bash
docker run --rm --device nvidia.com/gpu=all --shm-size 2g \
  -p 127.0.0.1:<port>:<port> -v <modeldir>:/models:ro \
  --entrypoint /app/llama-server \
  llgenie/llama-cpp:<sha>-cuda \
  -m /models/<model.gguf> --host 0.0.0.0 --port <port> --alias llm-local --jinja -ngl 99 -c <ctx>
```

**Read the entrypoint and device flags from the frozen params, never guess the
binary path.** `containers/engines/params/<engine>.json` -> `variants.<backend>`
has the authoritative `launch` (entrypoint = its first word), `run_args` (the
`--device nvidia.com/gpu=all` / `--shm-size 2g` lines), `base` and `detect`.
The prebuilt ggml-org cuda image (`base: ghcr.io/ggml-org/llama.cpp:server-cuda`,
`prebuilt: true`) puts the binary at **`/app/llama-server`**; a compiled-from-source
engine uses `build-<arch>/bin/...`. Hardcoding a `build-<arch>/bin` path into a
prebuilt image fails with `stat ... no such file or directory`.

**The CUDA banner may be absent even when the GPU is serving.** At verbosity 3
the ggml-org build prints no `ggml_cuda`/offload line, so `grep -i cuda` on the
log can be empty on a healthy run. The decisive offline proof is the ~10x
eval tok/s delta vs the CPU-path run (e.g. 394 t/s cuda vs 40 t/s cpu on the
0.5B q4_0 model) plus the `-cuda` image and the `--device nvidia.com/gpu=all`
flag; report those numbers rather than waiting for a banner.

then `curl /health` and POST a chat `"hi"` to `/v1/chat/completions`. The
device gadget name is `nvidia.com/gpu=all`; the host's CDI file is
`/etc/cdi/nvidia.yaml`. Run `nvidia-smi` to confirm the card (e.g. RTX 4090
Laptop 16GB) before concluding the CPU/GPU question.

Report honestly which path actually ran (CPU image vs `-cuda` image) rather than
claiming a GPU proof from a launcher that used a `-cpu` shim.
