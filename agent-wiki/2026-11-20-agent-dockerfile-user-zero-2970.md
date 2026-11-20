# 2026-11-20 — the agent Dockerfile drops the literal `USER root` (issue #2970, PR #<TBD>)

The pinned semgrep lane files `dockerfile.security.last-user-is-root` (ERROR severity,
`component:code`) against `containers/agent/Dockerfile:108` (issue #2970, scan run 44736884703).
An ERROR finding is blocking in full-mode, so the daily security lane stays red until the matched
region changes.

## What was verified

- Root cause measured on the pinned scanner image (`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`):
  the rule exempts `USER root` only via a `USER root ... USER <non-root>` span, and that span
  degrades in this 258-line file. Reproduction matrix: the real file flags at line 108; `USER root`
  moved directly after `FROM` flags identically (line 66); a three-line synthetic reduction flags
  with dockerfile-language rules alone; every short synthetic shape passes; `USER 0` is clean in
  every configuration tested. No reordering of the literal clears it.
- Fix: `USER 0` at `containers/agent/Dockerfile` (uid 0 — privileges byte-identical), image still
  ends `USER agent`. `make security-scan TOOL=semgrep` at head of this branch: zero
  `last-user-is-root` findings for the agent Dockerfile.
- Regression: `tests/test_agent_image_refresh.py::test_agent_dockerfile_never_spells_user_root`
  asserts no literal `USER root`, a numeric `USER 0`, and a non-root final `USER`.
  `pytest tests/test_agent_image_refresh.py -q` → rc=0 at head of this branch.
- Build proof: `ci_images._build_local('agent')` → rc=0 with the edited Dockerfile.

## Key decisions

- Engine Dockerfiles' literal `USER root` (issue #2504 convention) are untouched: measured, the
  pinned scan does not flag them (the span resolves in those short files).
- No suppression, no ruleset or scanner-pin moves — the source edit is the fix.
- The edit shifts the agent image content hash (`ci_images.tag`): GHCR `agent:latest` stays the
  pre-fix image until the pending human `publish-agent-image.yml` dispatch ([issue 2935](https://github.com/asimov-agent/llgenie/issues/2935))
  rebuilds it; no PR job pulls the agent image by content hash, so PR CI is unaffected.

## Current status

Landed on `main` via the PR from this branch; issue #2970 closed by the PR's closing keyword.
