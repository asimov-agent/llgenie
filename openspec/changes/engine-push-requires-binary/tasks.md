# Tasks

- [x] 1. `push` runs the image version check and returns before any `docker tag` or `docker push` when the binary does not report a version.
- [x] 2. A missing local image still returns before that check. A passing check still publishes the pinned tag and the moving arch tag.
- [x] 3. Lock both cases in `tests/test_engine_skills.py` with Given / When / Then. The engine-image job still runs `test-engine-stage` before `push-engine`.
- [x] 4. Note the gate in `README.md` and the `push-engine` target.
- [x] 5. `make openspec-validate NAME=engine-push-requires-binary` exits 0, and the new cases pass in `llgenie/test`.
- [x] 6. The probe resolves the engine file inside the image. `--version` or `-h` (`--help` for the long flag) must exit 0. A missing file fails. The path is not added to the hashed params.
- [x] 7. Every servable skill documents `binary_flags`; `make generate-engine-params` writes `containers/engines/binaries.json` (binary + flags + probe policy) and `make check-engine-params` fails when it is stale.
- [x] 8. The push check probes the manifest's documented flags inside the image (documented first, standard trio as fallback). A `binary_probe: device` variant must still contain the file; its version comes from `entrypoint.sh detect`.
- [x] 9. Unit tests lock the manifest coverage over every engine x variant, the documented flags, the probe exit codes (0 answered / 1 missing / 2 no answer) and the device exemption.
- [x] 10. CI on the PR is green: `make ci-unit` (test-unit, skills-validate, check-engine-params) plus the engine-image / published stages that run the probe against the real images.
