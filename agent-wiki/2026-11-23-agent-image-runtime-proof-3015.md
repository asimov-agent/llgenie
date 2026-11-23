# Publish lane proves the agent image is this tree and every lane resolves (#3015)

Date: 2026-11-23. Issue: #3015. OpenSpec change: `agent-image-runtime-proof-3015`.

## What was verified

- Owner dispatch [run 45134224656](https://github.com/asimov-agent/llgenie/actions/runs/45134224656) finished **success**: `guard` and `publish` green; `ci-images` published `ghcr.io/asimov-agent/llgenie/agent:fef0147326e3` and `:latest` for linux/amd64 + linux/arm64. The image was created `2026-11-23T07:57:00Z` and carries `llgenie.agent.source=fef0147326e3`; the stale `ea98772a4319` tag from 2026-10-29 is gone.
- The lane ran the published image: all **13** `agents/manifest.json` profiles were present under the image's `/home/agent/.hermes`, and `make hermes-smoke` passed a real terminal-tool nonce (`smoke-ok:e74279f2cfacc09ff3c5e1d6`) through profile `llgenie-status-keeper`, with `model-route: meituan/longcat-2.5:free`.
- GHCR v2 read-back: `:latest` and `:fef0147326e3` resolve to the same index digest `sha256:cfcafa0a494d3faa36212105348571ac6fb7484a41dc832c1ccf4a06a1a3a5bb`.
- Fix in this change: `publish-agent-image.yml` pulls the just-published `:latest` (because `buildx --push` leaves no local image) and adds the credential-free `make agent-image-source-check` before the other post-publish proofs; `agent_image_profiles_check.py --resolve` asks Hermes to resolve every declared lane locally (`hermes -p <lane> skills list --source local`) before the paid prompt smoke. The stale `agent-image-pull` host-only exception in `tests/fixtures/host-only-wiring.json` is deleted (CI now reaches that target). 12 hermetic seam tests, including a sabotage proof against the pre-fix sources.
- Host verification: the three wiring failures this change first introduced are fixed (3/3 targeted tests pass). The other 24 `make test-unit` failures are host false-reds reproduced on a detached `origin/main` baseline `fde44d14` (24 failed / 151 passed on the same modules) — no new failure attributable to this change.

## Key decision

Keep the real model prompt as the last proof, but put two deterministic, key-free proofs in front of it: source-stamp equality (is this image even from this tree?) and per-lane local resolution (can Hermes actually boot each bot?). A credential failure can no longer be misread as a stale image or a broken profile.

## Current status

Implementation + tests on branch `feat/agent-image-runtime-proof-3015` for issue #3015, PR #3018. The owner dispatch itself is complete and green (issue #2935), so no new dispatch is required to verify this change's pipeline wiring until the next publish.
