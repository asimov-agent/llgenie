# Tasks — registry-gc-digest-parse (issue #2924)

- [x] Add `_DIGEST_RE` + `_extract_digest` to `scripts/registry_cache_orphans.py`; `digest_of`
  consults it; refusal wording unchanged
- [x] Update `tests/test_registry_cache_orphans.py`: real-`digest_of` cases via monkeypatched
  `run_ok` — captured padded GHCR output, legacy single-space line, no-digest refusal
- [x] Re-run `make check-registry` neighbors + `pytest tests/test_registry_cache_orphans.py` +
  `make lint` + `make openspec-validate NAME=registry-gc-digest-parse`
- [x] `agent-wiki/` note + `docs/changes.d/` row + re-rendered `CHANGES.md` in the same commit
- [x] PR body mirrors #2924's acceptance items with proven tokens and carries `closes #2924`
  outside any code fence
