# 2026-09-27 — server-variant jobs run as a matrix

Run 36288948408 (`feat/server-clone-build`, PR 90) built prism CPU, prism CUDA,
stock CPU, and stock CUDA as four steps of one `server-variants` job. The job
hit its 100-minute cap during stock CUDA and was cancelled. The mac job built
its four variants the same way and passed, but serially.

`.github/workflows/ci.yml` now expands `server-variants` and
`server-variants-mac` into one job per variant (`fail-fast: false`). On Linux
that is prism CPU beside prism CUDA, and stock CPU beside stock CUDA. On macOS
that is prism CPU beside prism Metal, and stock CPU beside stock Metal.
`tests/test_ci_variant_matrix.py` locks those pairs and is on `make test-unit`.

Every variant, including CUDA and Metal, downloads the Qwen 0.5B GGUF and
must answer "hi". `--n-gpu-layers` is not passed, so `llama-server` keeps
its default and takes GPU or CPU, whichever it can.
