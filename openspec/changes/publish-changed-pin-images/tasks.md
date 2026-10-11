# Tasks

- [x] 1. Scope `matrix(changed=<ref>)` to images whose tag differs from the ref (`scripts/engine_image.py`)
- [x] 2. Pass `CHANGED` on the push path in `.github/workflows/ci.yml`
- [x] 3. Tests with Given / When / Then, green in the test image (4 passed)
- [x] 4. README describes the scoped publish
- [x] 5. `make openspec-validate NAME=publish-changed-pin-images` exits 0
- [x] 6. Keep the tag hash framing byte-identical to the published tags
      (`engine_skills._image_inputs` is the one place it is defined; `_tag_at`
      and `_current_tag` both call it) so no engine's tag moves and no install
      job asks GHCR for an image that was never pushed
- [x] 7. Wire `tests/test_engine_image_matrix.py` into `make test-unit` (the CI
      `unit` job) — no gate ran it before
- [x] 8. Tag-contract tests: published digest pinned, every hashed input moves
      the tag, matrix tag == the tag `make install` pulls, every matrix row is
      buildable by `make build-engine ENGINE=… ARCH=…` (13 passed in the test image)
- [x] 9. Scoping tests on this repo's real committed build inputs in a scratch
      git repo: unchanged tree → placeholder only, one moved pin → that engine
      only, one moved variant param → that row only, shared build file → all
- [x] 10. Verify against the registry without pushing: every tag the fixed
      branch computes for the CI matrix is already published on GHCR
- [x] 11. Every Hub call sends `HF_TOKEN` (env, else `~/.zshrc` / `~/.bashrc`),
      and every workflow sets `HF_TOKEN` from the Actions secret
      (`secrets: inherit` into `pipeline.yml` and `published.yml`)
- [x] 12. For every engine, a moved pin produces the CI make calls
      `build-engine`, `test-engine-stage` and `push-engine` with that engine's
      `ENGINE`, `ARCH` and `TEST`
