# 2026-10-11 engine bump install kind

Issue #151, PR #152, branch `feat/engine-bump-install-kind`.

E10 rewrites a `git+` pip install to a checksum-verified release archive when
the new tag's GitHub release ships `<name>-<ver>-<os>-<arch>.tar.gz` plus a
sibling `.sha256`. Toolchain and GPU-target rewrites stay in their own
front-matter block.

Wiring `tests/test_engine_bump.py` into `make test-unit` ran tests main never
executed. Fixed: a pin newer than every tag is not a bump; a sha-only move
still rewrites the tag literal; the guard assert reads the guard job; the unit
job fetches full history; the real llama.cpp cpu image build is not in the
hermetic list.

The three live TensorFold release tests run only on the Linux unit job
(`make test-engine-bump-live`). The macOS runner returned no assets from
`api.github.com`, and TensorFold publishes no `macos-x86_64` archive.

Verified: `make test-engine-bump-live` 3 passed; `linux / unit` and
`macos / unit` green on `abfd85d` before the squash. Squash invalidates that
run; a new CI run starts on the force-push.
