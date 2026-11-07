# Tasks

- [x] `scripts/engine_image.py::decide()` skips the help-family failure when `policy == "version"` — the version family must still answer (the binary self-proves); a version-only CLI is not red for the help it truthfully lacks (issue #1888).
- [x] `scripts/engine_skills.py`: `BINARY_PROBES = ("device", "help", "version")`; `probe_policy()` accepts `version`; validation message names all four policies.
- [x] `skills/engines/tensorfold/SKILL.md` declares `binary_probe: {cuda: version}` per-backend (metal unchanged — the macOS binary answers both).
- [x] `containers/engines/binaries.json` regenerated: tensorfold/cuda `probe: "version"`, flags `["--version"]` unchanged.
- [x] Tests: `tests/test_engine_binary_flags.py` adds a version-only pass case, a dead-version red case, `test_a_binary_file_works_passes_the_version_cell_with_dead_help_flags` (the real `binary_file_works` gate with the exact measured probe output), and a direct `probe_policy()` per-backend unit test in `tests/test_engine_skills.py` (`test_probe_policy_honours_the_version_only_per_backend_branch`) — 151 passed across test_engine_skills / test_engine_binary_flags / test_engine_gate_strict / test_engine_force_rebuild.
- [x] Docs trio: `docs/changes.d/2026-11-07-engine-binary-probe-version-policy.md` (one table row) + `agent-wiki/2026-11-07-engine-binary-probe-version-policy.md` narrative + regenerated `CHANGES.md`; `docs/ENGINES.md` documents the `version` policy.
- [x] PR body carries `AGENTS:`/`BASE:` (#792) and `closes #1888`; acceptance write-back via reviewer verdict (#1644); owner merges. No merge/arm (#1088).
