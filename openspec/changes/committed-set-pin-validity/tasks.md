# Tasks

- [x] 1. `openspec/changes/committed-set-pin-validity` — proposal + `specs/committed-set-pin-validity/spec.md` (WHEN/THEN, a `- **Test:**` line per scenario) + this checklist
- [x] 2. `scripts/check_engine_pins_published.py` — `committed_cells()` (every committed enabled cell, all backends) + `check_committed()` (exit 1 on any unresolved tag); `check --all` runs it
- [x] 3. Makefile — `check-engine-pins-valid` target invoking `check --all`, `.PHONY`-declared
- [x] 4. `tests/test_check_engine_pins_published.py` — red/green sabotage loop (committed tag 404 → rc 1; same tag resolves → rc 0), committed-set enumeration covers all-backend cells and skips disabled ones, wiring test for the make target + `.PHONY`, and a `@pytest.mark.network` live sweep of every committed cell
- [x] 5. Publish the missing `tensorfold/cuda` image via the engine-build producer (the commit's fix): `push=true` dispatch `engine=tensorfold arch=cuda` — run **42479515494**, confirmed `PUBLISHED` in GHCR
- [x] 6. Sabotage proof: scoped real-GHCR sweep of `tensorfold/cuda` green at the real pin (`ef27f74f…` → PUBLISHED, rc 0); temporarily pointing the pin at a bogus sha reds (`…:00000000-… → 404`, rc 1); restore → green
- [x] 7. Verification: `tests/test_check_engine_pins_published.py` hermetic subset 10 passed; `make openspec-validate NAME=committed-set-pin-validity` exits 0
