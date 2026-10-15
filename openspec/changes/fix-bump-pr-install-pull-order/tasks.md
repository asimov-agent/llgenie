# Tasks

- [x] 1. `wait_published(arch, only)` in `scripts/install_engine_launchers.py`:
      resolve exactly the tags `install()` pulls for that backend, poll the
      registry manifest until each exists, name every tag still missing and
      return non-zero when one never appears
- [x] 2. `make ci-wait-engine-images ARCH=<backend>` target driving it
      (`scripts/install_engine_launchers.py --wait-published`)
- [x] 3. `Makefile`: `ci-install` runs `make ci-wait-engine-images ARCH=cpu` before
      `make ci-install-run`, and the OS branch lives in the gate target (its Darwin branch
      does no lookup), so `ci-install` stays OS-neutral and `pipeline.yml`'s `install` job
      still runs exactly one `make ci-install` target
- [x] 4. `tests/test_ci_publish_order.py` with `# Given / # When / # Then`
      markers: gate before install in the recipe, the job runs one ci target, gate
      tags == install tags, loud failure on a never-published tag, macOS not gated,
      and a real GHCR manifest check that every image `make install` pulls is published
- [x] 5. Wire the test into `make test-unit` (no gate ran it before)
- [x] 6. README: the gate + the new make target, and the corrected statement
      that a same-repo `pull_request` run does publish its engine images
- [x] 7. AGENTS.md: replace the stale "pull_request runs never push" line with
      the measured behaviour, add the gate rule and the target
- [x] 8. `make lint` green on the branch, and the new test wired into the unit
      gate the CI `unit` job runs (the suite runs in CI, not on the host)
- [x] 9. `make openspec-validate NAME=fix-bump-pr-install-pull-order` exits 0
- [x] 10. Gate verified against the real failing case: the tags the gate resolves
      for the `chore/engine-bump-llama.cpp` tree (pin `f2cc7282`) are
      `llama-cpp:f2cc7282-3673c4ad-cpu` and `llama-cpp-prism:2459f68b-f4a50e08-cpu`;
      the first is exactly the tag run 38186233274's `install` job could not pull at
      23:59 and its own `engine-image-llama.cpp-cpu` job pushed at 00:05, and both
      answer with a manifest digest on GHCR today
