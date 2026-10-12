# Top-tier dry-run budget

Issue #180. The Hub client already sleeps a 429 for `rate_limit_wait` (up to 600s).
The CI dry runs killed that process at 180s and 300s. Both subprocesses now use
`hf_auth.TOP_TIER_DRY_RUN_TIMEOUT` (600 + 180). A local HTTP server locks the real
`_hf_get` wait. The same budget covers every other `llama_serve.py` or
`hf_download.py` subprocess that can call the Hub, including the 120-second
`vllm` pick dry run. Local-file pickers stay short. The live dry runs stay in
`make test-top-tier-cli-ci`.
