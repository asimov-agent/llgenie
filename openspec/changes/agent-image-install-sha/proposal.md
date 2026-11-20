# Proposal: agent-image-install-sha

## Why

Issue #2958 (filed from the residual scope of #406): the agent image build pipes
the Hermes installer straight off an unversioned URL into `bash`
(`curl -fsSL "$HERMES_INSTALL_URL" | bash -s -- ...` in
`scripts/install_hermes_ci.sh`). The `HERMES_INSTALL_COMMIT` pin selects which
Hermes the script installs, but nothing pins the **installer's own bytes**:
whoever answers that URL chooses what every `agent:<hash>` build executes, and
a change to the endpoint would land inside every published image while the tag
— the contract every bot job trusts — stays unchanged.

## What Changes

- `containers/agent/Dockerfile`: new `ARG HERMES_INSTALL_SCRIPT_SHA` pinning
  the installer's sha256 (measured 2026-11-20), exported via the existing ENV
  block to the install step.
- `scripts/install_hermes_ci.sh`: fetch the installer to a temp file; if
  `HERMES_INSTALL_SCRIPT_SHA` is set, verify `sha256sum` against it **before**
  executing, and fail the build on mismatch; only then run
  `bash "$installer_tmp" -s -- ${HERMES_INSTALL_ARGS:-}`. Unset pin = loud
  unverified warning (the documented override path).
- `tests/test_agent_image_refresh.py`: update the ARGS-forwarding pin to the
  verified-temp-file invocation and add a test locking the ARG pin, the ENV
  wiring, and the fetch-verify-run order.

## Out of Scope

- The `uv tool install` fallback path (a PyPI package install, not a URL-script
  execution) stays as the documented no-network fallback.
