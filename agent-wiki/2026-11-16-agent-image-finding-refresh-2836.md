# 2026-11-16 — refresh the agent image chain against its 91 HIGH findings (issue #2836)

OpenSpec change: `agent-image-finding-refresh`. Umbrella issue #2836 (the published-image
finding refresh leg of the security lane).

## Verified against the spec

- Inventory (measured from the open `security`-labeled issues, three independent fetches):
  **106 open HIGH/CRITICAL findings — 91 agent-image, 15 llama-cpp CUDA**. The largest cluster
  (~45) is the frozen Go stack inside the docker CLI binary copied from `docker:27-cli`
  (docker/cli 27.5.0, Go 1.22.11, x/crypto 0.31, buildkit 0.19, containerd 2.0.2, grpc 1.68).
- Chain fixes (`proposal.md` / `specs/agent-image-finding-refresh/spec.md`):
  `containers/test/Dockerfile` copies docker + buildx from `docker:29-cli` and upgrades
  `pip setuptools wheel` before the locked install; `containers/agent/Dockerfile` runs
  `apt-get upgrade -y` between update and install (refreshing inherited base debs) and declares
  `ARG HERMES_INSTALL_ARGS="--skip-browser --skip-computer-use"`, exported via `ENV`;
  `scripts/install_hermes_ci.sh` forwards it through `bash -s -- ${HERMES_INSTALL_ARGS:-}`.
  The agent tag hash already folds in `tag("test")`, so the rebuilt chain cannot silently drift.
- Tests: `tests/test_agent_image_refresh.py` (5 hermetic pins) rc=0; `make openspec-validate`
  rc=0. Local rebuild + pinned-grype disposition evidence is posted on issue #2836.
- The local rebuild caught a latent main breakage from issue #2680: the build-time provisioning
  step imports `check_agent_profiles`, which imports `check_agent_skills` at import time
  (`scripts/check_agent_profiles.py:74`), but that module was never in the agent image's staged
  inputs — every agent-image build from main died at step 16/18. `scripts/check_agent_skills.py`
  is now an agent input with a matching COPY; publish-agent-image is dispatch-only, so no CI leg
  exercised the build until this rebuild did.
- The rebuild then exposed a second, older failure class: the resolution proof's denominator
  (`tree_skill_names`) demanded skills Hermes can never resolve — 24 archived planner skills
  under `.archive/` (the loader skips hidden directories), 4 macOS-gated skills on the Linux
  build (hidden by design), directory-named skills whose frontmatter renames them
  (`pi-delegate` → `pi`, `obsidian-vault-automation` → `vault-cron-workflow`), and one identity
  collision in the issse lane (a flattened `bulk-mechanical-migration` copy beside its category
  copy; Hermes category-qualifies one, which the table proof cannot match), and one
  `environments: [kanban]` skill in the planner lane (`devops/sdlc-review` — Hermes hides
  environment-gated skills whose environment is inactive, and no fleet profile can activate
  kanban: provisioning writes no toolset config and AGENTS.md bars kanban lanes).
  `tree_skill_names` now mirrors Hermes' loader exactly (measured empirically against the CLI on
  this host): hidden trees skipped, `platforms:` gates honoured, `environments:` gates resolved
  against the same context Hermes detects (`kanban` via dispatcher env, `docker` via
  `/.dockerenv`, `s6` via s6-overlay paths, unknown tags fail open), frontmatter name as
  identity; the stale flattened copy and the kanban-gated skill are removed from the trees, and
  `tests/test_provision_agent_profiles.py` guards every shape — duplicate-identity and
  kanban-carry data guards included.
- Out of scope, each its own linked issue on #2836: the 15 llama-cpp CUDA findings (weekly
  engine lane, human permission gate for engine rebuilds) and the Wolfi scanner-binary findings
  (`make scanner-freshness` confirms the pins are newest published).
- Publish stays a human act: the published `agent:latest` refreshes only through a
  `publish-agent-image.yml` dispatch; the 91 finding issues close via their own scan-reconcile
  loop after that publish, not through this PR.

## Current status

Branch `feat/agent-image-finding-refresh`; unit + validate green locally; PR against upstream
main closing #2836; CI landing left to the auto-merge lane.
