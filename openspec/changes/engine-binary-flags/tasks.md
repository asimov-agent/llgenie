# Tasks — engine-binary-flags

- [x] 1. `scripts/engine_image.py`: `BINARY_PROBE` runs every flag and prints `LG-FLAG <flag> <rc> <bytes>` per flag (exit 1 only when the binary file is missing).
- [x] 2. `scripts/engine_image.py`: `parse_probe()` and `decide()` — pure, hermetic; every documented flag must answer, help/version families must answer, empty manifest falls back to the trio, `probe: device` contained.
- [x] 3. `scripts/engine_image.py`: `binary_file_works()` runs the probe, parses, decides; failures name the flag with its own output tail.
- [x] 4. `tests/test_engine_version.py`: assert the built image's per-flag verdicts (documented flags, help family, version family) through the same parse/decide pair.
- [x] 5. `tests/test_engine_binary_flags.py` + fixtures: the real probe text against real fake binaries — all-answer passes; dead `--help` reds naming it; no help spelling reds the family; device contained; empty manifest still requires an answer; the probe reports every flag.
- [x] 6. README's engine-bump section states what the bump's CI actually executes (every documented flag, both families) and `agent-wiki/2026-10-24-engine-binary-flags.md` records the change with #580 / the PR.
- [x] 7. `make test-unit` green and `make openspec-validate NAME=engine-binary-flags` exits 0.
