# Top-tier dry-run budget

Issue #180. The Hub client already sleeps a 429 for `rate_limit_wait` (up to 600s).
The CI dry runs killed that process at 180s and 300s. Both subprocesses now use
`hf_auth.TOP_TIER_DRY_RUN_TIMEOUT` (600 + 180). A local HTTP server locks the real
`_hf_get` wait. The live dry runs stay in `make test-top-tier-cli-ci`.
