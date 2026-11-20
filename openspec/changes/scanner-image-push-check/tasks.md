# Tasks: scanner-image-push-check

- [x] 1. Measure the failure on main: capture the run ids, the denial line, the digest-verify
      refusal line, and the GHCR package creation identity (done via issue #2960's Technical
      section; re-verify the package owner read).
- [x] 2. Wire `scanner_image → ci_images` in `scripts/package-layers.json` with a reason, and make
      `tests/test_package_layers.py` pass with the new import.
- [x] 3. Add the push-check gate to `ensure` in `scripts/scanner_image.py`: run it per missing
      scanner before the buildx publish; a refusal skips the build and returns non-zero naming the
      scanner.
- [x] 4. Hand `GITHUB_TOKEN` to the `make ci-security-images` step in
      `.github/workflows/security-images.yml`.
- [x] 5. Hermetic tests in `tests/test_scanner_images.py`: push-check precedes the build (stub
      registry + RUNTIME stub), a denial skips the build and names the refusal, and the workflow
      step carries the credential. All green under `make test-unit`.
- [x] 6. Docs in the same commit as the change: `ARCHITECTURE.md` security-images paragraph,
      `agent-wiki/` entry, `docs/changes.d/` row; `make check-docs` and `make changes-index` green.
- [x] 7. `make openspec-validate NAME=scanner-image-push-check` exits 0 and `make lane-preflight`
      prints `preflight: OK`.
- [x] 8. Final verification provable at this head: `pytest tests/test_scanner_images.py` rc=0
      (29 passed) and the full unit battery ran rc=0 (LANE_H_UNIT_RC=0) at this head. Pushing the
      branch and opening the PR closing #2960 is the ship action outside the task list (CI lands
      it; the agent never merges).
