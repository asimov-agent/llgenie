# Tasks

- [x] 1. E10: detect a native-archive GitHub release and rewrite `install:` to a checksum-verified unpack (`scripts/engine_bump.py`)
- [x] 2. Scope toolchain rewrite to the `toolchain:` block and the GPU-targets rename to `hw_flags:`
- [x] 3. Unit tests for both, including a live read of the TensorFold v1.0.5 release and `derive()` against it (Given / When / Then). `make test-unit` not re-run on request; the new cases passed in the test image
- [x] 4. `make openspec-validate NAME=fix-engine-bump-install-kind` exits 0
- [x] 5. Correct the TensorFold skill on `chore/engine-bump-tensorfold` (PR #146) and push so CI rebuilds the cuda image from the archive. Not done on that branch: the fix lands through this PR; #146 closed when strata merged.
- [x] 6. The bump unit suite is green inside `make test-unit`. The three live TensorFold release tests run only on the Linux unit job (`make test-engine-bump-live`): the macOS runner returned no assets from `api.github.com` and TensorFold publishes no `macos-x86_64` archive.
