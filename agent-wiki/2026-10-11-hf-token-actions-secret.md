# 2026-10-11 HF token on every Hub call

Issue #153, PR #154. The macOS unit job 114535593927 got HTTP 429 because
Hub calls had no token. The repo Actions secret `HF_TOKEN` is set (value
not in git). `ci.yml`, `pipeline.yml`, `published.yml`, `engine-bump.yml`,
and `registry-sync.yml` export it. `scripts/hf_auth.py` attaches it to Hub
requests and the `hf` CLI. A non-Hub URL does not get the header.
