# Tasks — agent-image-ci-verify

- [x] Write `scripts/agent_image_profiles_check.py`: read the lane roster from `agents/manifest.json`,
      test each lane's `$HERMES_HOME/profiles/<lane>/config.yaml` (the path Hermes resolves
      `-p <lane>` from) in the filesystem it runs in — the agent image boots it as the in-image
      `_agent-image-profiles-check` step — print `OK`/`MISSING` per lane, exit 1 naming every
      missing lane. Stdlib only.
- [x] Wire `make agent-image-profiles-check` in `mk/agents.mk` as a standard agent leg (env guard,
      ensure agent, scrubbed_run, AGENT_SHELL_FORWARD, AGENT_BOT_MARKER; internal
      `_agent-image-profiles-check` runs the seam inside the image), add it to the
      Makefile target roster and `scripts/package-layers.json` ("Bots and automation").
- [x] Add the two post-publish steps to `.github/workflows/publish-agent-image.yml`:
      `make agent-image-profiles-check`, then `make hermes-smoke` with
      `NOUS_API_KEY: secrets.NOUS_PORTAL_API_TOKEN`; extend the workflow header Flow comment.
- [x] Tests: `tests/test_agent_image_profiles_check.py` (hermetic lane-roster + verdict parsing,
      missing-lane refusal) and its wiring test locking the two verify steps after the publish step
      in `publish-agent-image.yml` plus the smoke step's credential env.
- [x] Local dry-run against the #2929 chain build: agent image from the chain tree passes
      `make hermes-smoke` (profile `llgenie-status-keeper`, no `-m`) and
      `agent-image-profiles-check` prints 13×`OK` (record run evidence).
      Evidence 2026-11-19: chain-tree image `llgenie/agent:probe` (id `489e97df8513`) built from the
      fixed chain tree; in-image chain check rc=0 (`nous-longcat` primary,
      `deepseek/deepseek-v4-flash-0731` last, Hermes v0.23.2 `ae2a81ccc00e`);
      `make agent-image-profiles-check AGENT_IMAGE=llgenie/agent:probe` rc=0 — 13×OK incl.
      `llgenie-status-keeper`; `make hermes-smoke AGENT_IMAGE=llgenie/agent:probe` rc=0 — alias
      `nous-deepseek` resolved from the profile config (no `-m`), nonce `smoke-ok:bc7a0612d471c53e7a2709bc`,
      session `local-9b5f0bd3d5d14a9a05e009c95b7f49f663a917320dec58c6294f66c5ed07b77a`.
- [x] Docs: `docs/BOTS.md` lines for the new target, `agent-wiki/` entry, `docs/changes.d/` fragment,
      `make changes-index`.
- [x] Gates: `make check-workflows`, `make check-ci-discipline`, `make check-wiring`,
      `make check-package-layers`, `make openspec-validate NAME=agent-image-ci-verify`,
      targeted pytest, then `make test-unit` and `make lane-preflight` green at the final head.
- [x] Push `feat/agent-image-ci-verify` and open the PR closing #2934 with mirrored ACs (issue body
      ticked with replayable proven clauses at the final head first). — mechanical push/PR lands in the
      same commit batch as this tick (repo precedent: the checklist describes the batch being pushed).
