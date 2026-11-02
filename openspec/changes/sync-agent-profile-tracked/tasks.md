# Tasks — sync-agent-profile-tracked

- [x] 1. `openspec/changes/sync-agent-profile-tracked` — proposal + `specs/sync-agent-profile/spec.md` (G/W/T, one scenario per requirement) + this checklist, written before any code (done pre-implementation)
- [x] 2. `scripts/agent_profile_sync.py` — `profile_files()` mirrors Git's tracked-file view (`git ls-files` over the profile subtree when the tree is a git worktree; skip ignored/untracked), so `__pycache__/*.pyc` and other git-ignored artifacts are never candidates
- [x] 3. `scripts/agent_profile_sync.py` — every `read_text()` (in `shrinks`/`newer_than_source`/write/check) is guarded so a non-UTF-8 file is a named non-zero refusal (stderr names the path and that it is binary/not UTF-8), never a `UnicodeDecodeError` traceback
- [x] 4. `tests/test_agent_profiles.py` — `test_sync_skips_gitignored_pyc_build_artifacts` (a git-ignored `.pyc` under `agents/<profile>` is absent from the candidate set; sync exits 0) and `test_a_non_utf8_profile_file_is_a_named_refusal_not_a_traceback` (stderr names the file, non-zero exit)
- [x] 5. `docs/changes.d/2026-11-02-sync-agent-profile-tracked.md` + `agent-wiki/2026-11-02-sync-agent-profile-tracked.md` + regenerated `CHANGES.md` row (#1123 trio)
- [x] 6. Verified: `make test-unit` green with the new behaviour, `make openspec-validate NAME=sync-agent-profile-tracked` exits 0, `make lint`, `make check-docs`, `make check-wiring` all exit 0
