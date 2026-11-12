# Design — vllm/rocm base access for uid 1000

## Key decision: `base_access` enters the hashed params — but only the declaring variant

The per-cell image tag hashes `sha256(variant params JSON + committed Dockerfile +
entrypoint + runner)` (`engine_skills._image_inputs`). Attaching the key ONLY to the variant
that declares `base_access` means exactly one digest moves. Measured before/after on this
branch: vllm cuda `4c1f3eee` and cpu `524f7326` are byte-identical hash inputs before and
after (their variant dicts gain nothing), so their published tags stay reachable; rocm moves
`db98981b` → `ba13b1d7` — and that move is REQUIRED: the old rocm image is the broken one,
so a new content hash must carry the fixed image. Attaching the key to every variant (even
empty lists) would move all 28 published tags at once — which is why the attach is
conditional on a non-empty declaration.

## Why chmod on directories only

Overlayfs copy-up: any `chmod` on a lower-layer file re-materializes that file in a new
upper layer. The base venv is ~15 GB (pytorch + ROCm wheels). `chmod -R a+rX /opt/python`
would add a ~15 GB layer to every rocm image. `find <dir> -type d -exec chmod a+rx` touches
directory metadata only (a few thousand dirs); `find <dir>/bin -maxdepth 1` adds the small
launcher set. File modes inside site-packages are wheel-normal (644 data / 755 binaries) and
become reachable once every parent directory carries `o+rx`.

Evidence the barrier is exactly this (run 43221661126, log lines 1145-1156):
- `timeout: failed to run command '/opt/python/bin/vllm': Permission denied` (126) on all
  four probed flags → the launcher entry itself is not exec-readable by uid 1000.
- `ModuleNotFoundError: No module named 'vllm'` from `python3 -c 'from vllm import
  __version__'` → the venv's `python3` executes, so its parent dirs up to `bin` work, but
  the package tree below is not traversable/readable for uid 1000.

## Placement in the Dockerfile

The `RUN` sits after `USER_CREATE_RUN_ENGINE` and immediately before `USER 1000:1000`, so it
runs as root (the stage is still privileged) and the opened tree is then used unprivileged.

## Idempotence

`test -d "$d" || continue` keeps the line valid if a future base moves the venv; the opens
are monotone permission grants, safe to re-run on any base.
