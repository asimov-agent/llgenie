# agent-image-finding-refresh — proposal

Issue: [#2836](https://github.com/asimov-agent/llgenie/issues/2836)

## Why

The published-image scan (run 43787049546 on `main` tip `ff44b4c4b84b2217b2f01a47f2611e0e41c41080`) carries **106 open HIGH/CRITICAL findings — 91 in `ghcr.io/asimov-agent/llgenie/agent:latest`, 15 in the llama-cpp CUDA image**. The agent image's layers freeze 2025 snapshots of their upstreams: the test image copies the docker CLI from `docker:27-cli` (that binary carries `docker/cli v27.5.0`, Go stdlib v1.22.11, `x/crypto v0.31.0`, `x/net v0.33.0`, `buildkit v0.19.0`, `containerd/v2 v2.0.2`, `grpc v1.68.1` — ≈45 of the 91 findings from one frozen Go stack); the apt layers install new debs but never upgrade the debs inherited from the base image (`apt 3.0.3`, `libapt-pkg7.0`, `zlib1g`, `tar`, setuptools 70.3.0, wheel 0.45.1 stayed at the base's build date); and the Hermes install ships the agent-browser/Playwright + computer-use toolchains — a Chromium package with a 1878-advisory stream — that no llgenie lane uses.

## What Changes

- `containers/test/Dockerfile` copies docker + buildx from `docker:29-cli` (the newest published CLI stage; the `docker/cli` advisory floor names ≥29.2.0) and adds a `pip install --upgrade pip setuptools wheel` layer so the Python build toolchain lands mirror-current.
- `containers/agent/Dockerfile` runs `apt-get upgrade` in its apt layer (refreshing inherited base debs at build time) and adds `ARG HERMES_INSTALL_ARGS="--skip-browser --skip-computer-use"`, exported via `ENV` to the install step.
- `scripts/install_hermes_ci.sh` forwards `HERMES_INSTALL_ARGS` to upstream `install.sh` through `bash -s --`, so the published image ships neither the browser nor the computer-use toolchain; `--build-arg HERMES_INSTALL_ARGS=""` re-adds them.
- A new hermetic test module pins the chain: the CLI stage, the upgrade layer, the apt upgrade, the install-args default, and the forwarding.

## Impact

- Affected: `containers/test/Dockerfile`, `containers/agent/Dockerfile`, `scripts/install_hermes_ci.sh`, `tests/test_agent_image_refresh.py` (new).
- Test-image and agent-image content hashes change, so the next publish builds and scans a refreshed chain. The 91 agent finding issues close through their own scan-reconcile loop after the next human `publish-agent-image` dispatch — this change does not close them directly.
- Not covered (each already its own issue): the 15 llama-cpp engine findings (the weekly engine lane rebuilds with current apt; engine rebuilds stay behind the human permission gate) and the Wolfi scanner-binary Go findings (`make scanner-freshness` reports the pins are newest published — clearing them needs upstream rebuilds). See #2836's `Not covered`.
