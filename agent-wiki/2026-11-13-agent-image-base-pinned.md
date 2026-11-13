# 2026-11-13 — the agent image's TEST_IMAGE base build-arg loses its mutable default (issue #2617, PR #pending)

- Problem: `containers/agent/Dockerfile` declared `ARG TEST_IMAGE=llgenie/test:latest` and
  `FROM ${TEST_IMAGE}`. Trivy reported it as the last dockerfile misconfig on `main`
  (`':latest' tag used`, measured 2026-11-13 on `da2fc5adb` with `make security-scan TOOL=trivy`:
  0 vulns / 0 secrets / 1 misconfig). The default let a bare `docker build -f
  containers/agent/Dockerfile .` resolve the base to the mutable `:latest` alias — the exact
  silent-base-drift the content-hash policy exists to prevent.
- Fix: the ARG now has no default (`ARG TEST_IMAGE`). `FROM ${TEST_IMAGE}` fails loudly with an
  empty base name whenever `--build-arg TEST_IMAGE` is missing. Every wired builder
  (`scripts/ci_images.py::build_args`) already passes the hashed ref and is unchanged, so
  `make agent-image`, `agent-image-pull`, `publish-agent-image` and all CI legs build exactly as
  before.
- Test: `tests/test_ci_images.py::test_agent_dockerfile_test_image_arg_has_no_default` locks the
  ARG line to no default and no `:latest`, next to the existing publish-pin lock. The lock was
  proven to red when a `=llgenie/test:latest` default is re-added and to pass on the fixed file
  (whole battery: `41 passed`).
- OpenSpec: `openspec/changes/agent-image-base-pinned/` (proposal, spec-driven spec with
  Given/When/Then + `- **Test:**` refs, tasks) validates (`Change 'agent-image-base-pinned' is
  valid`).
- Gates: `make lint` (linefeeds host run OK), `make check-docs` OK, `make check-wiring` OK
  (`422 documents, 375 make targets`), `openspec validate` OK. `make test-unit` and the live
  `docker build` empty-base proof and trivy re-scan run in CI on the PR.

Current status: implementation, OpenSpec change, task checklist and the hermetic lock test written
in the agent worktree; CI unit + trivy re-scan proof pending.
