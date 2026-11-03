# Dependency-pin validity audit at 75f85118 (security lane, own-domain)

Audit date: 2026-11-03. Measured head: `75f851180e` (main at dispatch; current tip `0a0dbddd` differs by docs-only merges #1643 and #1653, so the dependency-pin tree is identical). Bounded own-domain audit per #1245 (security: dependency-pin validity) — the `#1252/#1262` class: a pin valid in **form** that cannot resolve in **fact**.

## Classes swept

1. **Third-party Actions `uses:` SHA-pins** (`.github/workflows/*.yml`) — all 7 unique `uses: <owner>/<repo>@<40-hex>` resolve upstream via the GitHub commits API (`actions/checkout`, `upload-artifact`, `setup-python`, `setup-node`, `setup-uv`, `setup-buildx-action`, `setup-qemu-action`). Only non-SHA `uses:` are repo-local paths (`./.github/actions/docker`, `./.github/workflows/pipeline.yml`) — not floating pins. **Clean.**
2. **Install-time package pins** (`tools/requirements.txt`, `tools/requirements-dev.txt`, consumed by `python:3.11-slim` via `containers/test/Dockerfile`) — actual resolution on Python 3.11 (uv dry-run): `requirements.txt` 20/20 install (incl. `numpy==2.4.6`, `requests==2.34.2`, `packaging==26.3`, `hf-xet==1.6.0`, `certifi==2026.10.23`); `requirements-dev.txt` 24/24 install. (The `huggingface-hub[cli]==1.30.0` star-spec resolves; the `cli` extra name is a non-fatal warning.) **Clean.**
3. **Scanner/image tags** — `ghcr.io/asimov-agent/llgenie/{semgrep,trivy,grype}` digest pins and `ghcr.io/astral-sh/uv:0.9.5` resolve via `docker buildx imagetools inspect`; the vllm `5df63a72-*-cuda` glob that #1365 flagged is now published (GHCR lists `5df63a72-*-cuda` variants). **Clean.**

## Finding — four cuda-variant engine-image pins silently unsatisfiable (#1652)

`scripts/check_engine_launchers.py check --check-registry --arch cuda` at `75f851180e` → exit 1:
`NOT PUBLISHED sglang/strata/tensorfold/vllm: llgenie/<e>:<tag> resolves no manifest (ghcr.io/asimov-agent)` ×4; summary `4 ok, 7 stale, 1 missing, 4 not published (arch cuda)`.

Direct resolution (`GET ghcr.io/v2/asimov-agent/llgenie/<engine>/manifests/<tag>`) → `HTTP 404` ×4:
- `llgenie/sglang:7df5dd09-d6464b56-cuda`
- `llgenie/strata:d94bac6a-8f35f372-cuda`
- `llgenie/tensorfold:ef27f74f-ab048303-cuda`
- `llgenie/vllm:3a4d82f5-9be509b4-cuda`

Expected tags are params-derived (`install_engine_launchers.install_plan('cuda', ['all'])`), so not a stale-launcher artefact. The dedicated owner pipeline (`registry-liveness`, #1365 precedent) sweeps **cpu only** (`0 not published (arch cpu)` at the same head), so these cuda pins never gate until an install-time pull fails.

Filed: **#1652** — six-section, tagged `[agent:implement, security, vulnerability, severity:high]`, sha-bound at `75f851180e`.

## Finding — registry-liveness monitor sweeps cpu only, never non-cpu pins (#1661)

The dedicated owner pipeline (`registry-liveness`, #1365 precedent) calls `make check-engine-launchers CHECK_REGISTRY=1` with **no `--arch`** (fit at `0a0dbddd`): the `check-engine-launchers` Makefile target forwards `--arch` only `$(if $(ARCH),--arch "$(ARCH)",)`, and `scripts/check_engine_launchers.py` falls back to `iel.detected_arch()` — `ubuntu-latest` resolves to **cpu**. The monitor therefore sweeps cpu pins only and can never observe a broken cuda/rocm/vulkan pin — the direct reason #1652's four cuda pins glided green (its cpu sweep reported `0 not published (arch cpu)` at the same head) even while all four cuda manifests returned `HTTP 404`.

Severity: medium. Not a code-path exploit, but a silent coverage gap in the security-lane's own control: every engine-image variant except cpu is unmonitored, and the failure is invisible until an install trips over it.

Filed: **#1661** — six-section, tagged `[agent:implement, security, vulnerability, severity:medium]`, sha-bound at `75f851180e` (monitor unchanged through `0a0dbddd`).

## Result

Two filed findings (#1652, #1661); every other class re-verified clean. Fixes route to the implement queue: #1652 = publish each cuda pin (`make push-engine ENGINE=<id> ARCH=cuda`) or drop the variant from params; #1661 = sweep each arch the tree pins in `registry-liveness` (`make check-engine-launchers CHECK_REGISTRY=1 ARCH=<arch>` per arm, arch named in the tracking issue). Neither is implemented by this audit lane.
