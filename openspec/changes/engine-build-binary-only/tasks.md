# Tasks — engine-build-binary-only

- [x] 1. `.github/workflows/engine-build.yml` runs **no serving step** for any cell — `serve-leg` and `host-verify MATRIX` are removed; dispatch inputs are `engine`/`arch`/`push`/`force`.
- [x] 2. The published-binary leg pulls the just-published image and verifies the engine BINARY answers exactly `-h`/`--version` (never starts a server).
- [x] 3. `scripts/engine_smoke.py` binary probe pin is exactly `["-h", "--version"]` on both paths; `TYPED_FLAGS` in `engine_image.py` is unchanged (the full user-typed set).
- [x] 4. `make test-engine-host ENGINE=<id> ARCH=<arch> [MODEL=...]` and `make test-engine-serve` are preserved and documented as HOST-only (the engine improver runs them manually, one engine at a time, never in CI).
- [x] 5. `make test-published-engine` verifies only the binary `-h`/`--version` on the built/published image (no `--serve` chat invocation).
- [x] 6. `make check-workflows`, `make check-wiring`, `make check-docs`, and the hermetic engine unit tests pass at the PR head (run ids quoted).
- [x] 7. Evidence note raised when done (run ids + `check-engine-params` / engine test results).
