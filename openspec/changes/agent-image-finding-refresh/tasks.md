# Tasks — agent-image-finding-refresh

Umbrella issue: [#2836](https://github.com/asimov-agent/llgenie/issues/2836)

- [x] 1. OpenSpec change (`make openspec-new`) + umbrella issue #2836 filed with the six-section body and the out-of-scope items split into their own linked issues.
- [x] 2. `containers/test/Dockerfile`: docker + buildx copied from `docker:29-cli`; `pip install --upgrade pip setuptools wheel` layer added before the locked-requirements install.
- [x] 3. `containers/agent/Dockerfile`: `apt-get upgrade -y` between `apt-get update` and `apt-get install`; `ARG HERMES_INSTALL_ARGS="--skip-browser --skip-computer-use"` declared and exported through the `ENV` block.
- [x] 4. `scripts/install_hermes_ci.sh`: installer piped into `bash -s -- ${HERMES_INSTALL_ARGS:-}` so the skip flags reach upstream `install.sh`.
- [x] 5. Agent-image build-chain fixes (caught by the local rebuilds): `check_agent_skills.py` staged in the agent inputs + Dockerfile; `provision_agent_profiles.py::tree_skill_names` rewritten to mirror Hermes' loader (hidden trees skipped, other-platform skills skipped, inactive-`environments` skills skipped, frontmatter-name identity); the flattened duplicate `bulk-mechanical-migration` copy removed from the issse lane; the kanban-gated `devops/sdlc-review` removed from the planner lane (the fleet can never activate its environment); hermetic tests for all of it plus the duplicate-identity and kanban-carry data guards.
- [x] 6. New hermetic module `tests/test_agent_image_refresh.py` pins all four behaviours; full `make test-unit` green at the PR head (no skips). (3900 passed, UNIT_RC=0)
- [x] 7. Local rebuild evidence (host, permitted non-engine lane): test image built with the new chain, agent image built on top of it, grype re-scan posted to #2836 as a per-cluster disposition table (how many of the 91 the refresh clears; what remains with its owner). (68/91 cleared, 23 upstream-pinned — comment 6906898722)
- [x] 8. `agent-wiki/2026-11-16-agent-image-finding-refresh-2836.md` + `docs/changes.d/` fragment; `make changes-index` regenerated (CHANGES.md from 869 fragments).
- [x] 9. Verification you can tick at the done-claim: `make openspec-validate NAME=agent-image-finding-refresh` rc=0, `make check-docs` rc=0, `make openspec-tasks-check` green with every task above ticked, and the full unit suite green at this head (3900 passed, UNIT_RC=0); the PR (`closes #2836`) carries this checklist mirrored and is driven green, then stopped for the CI auto-merge lane.
