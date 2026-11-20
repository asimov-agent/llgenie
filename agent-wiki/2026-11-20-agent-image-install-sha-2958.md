# The agent image verifies the Hermes installer before running it (issue #2958)

Date: 2026-11-20. Lane: `feat/agent-image-install-sha-2958`. Issue: #2958.

## What was verified against the spec

- `containers/agent/Dockerfile` pins the installer content:
  `ARG HERMES_INSTALL_SCRIPT_SHA="c73dad4dcf7c9ecadb98578e28cc763d23d7be3fa1b513545319038795493214"`
  (live `curl -fsSL … | sha256sum` measurement, 68,015 bytes, 2026-11-20),
  exported through the existing install-step ENV block.
- `scripts/install_hermes_ci.sh` now fetches to `$installer_tmp`, compares
  `sha256sum` against `HERMES_INSTALL_SCRIPT_SHA`, refuses on drift, and only
  then runs `bash "$installer_tmp" -s -- ${HERMES_INSTALL_ARGS:-}`. Live drift
  proof: a container run with an all-zeros pin printed
  `install script content drift … refusing to run the fetched installer` and
  exited 1 before executing the installer.
- `tests/test_agent_image_refresh.py` locks the ARG pin (64-hex), the ENV
  wiring, and the fetch → verify → run statement order; the ARGS-forwarding
  assertion was updated to the verified-temp-file invocation (7/7 green).

## Key decisions

- Fail-closed on drift, loud on an unset pin (the documented override path —
  e.g. local dev builds that swap the installer URL).
- A legitimate upstream installer change is handled by re-measuring
  `sha256sum` and bumping the ARG in the same commit; the Dockerfile is a
  hash input, so the image tag moves with the pin and every lane re-rolls.
- The `uv tool install` fallback stays unverified: it installs a PyPI package,
  not a URL-served script (issue #2958's out-of-scope note).

## Current status

OpenSpec change `agent-image-install-sha` validates. Real agent-image build
proofs (wrong-pin build must fail; default-pin build must complete) and the
unit battery run at the lane head before push.
