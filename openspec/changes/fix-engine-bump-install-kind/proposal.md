# fix(engine): bump switches a pip install when upstream ships a release archive

Issue: [#151](https://github.com/asimov-agent/llgenie/issues/151)

## Why

The weekly pin bump rewrites `pinned`/`ref`/`version` and mirrors cmake/toolchain
lines. It does not notice when upstream stops being installable that way.
TensorFold 1.0.0+ refuses `uv pip install 'tensorfold @ git+…@v1.0.5'` on
purpose ("install as a native binary… the Python engine stays at 0.6.6"), so
PR #146 went red on `engine-image-tensorfold-cuda`. The same apply pass also
wrote `toolchain.cuda`/`toolchain.rocm` into the first `cuda:`/`rocm:` line it
found (`prereqs:`, PR #149) and replaced every `AMDGPU_TARGETS`, including the
`derive.gpu_targets_var.candidates` list.

## What Changes

- E10: when the new tag's GitHub release assets are native archives
  (`<name>-<ver>-<os>-<arch>.tar.gz` plus a sibling `.sha256`), rewrite that
  engine's `install:` to a checksum-verified download and unpack, for every
  backend. Leave a pip/git install alone when the release has no such assets.
- Scope the toolchain rewrite to the `toolchain:` block, and the GPU-targets
  rename to `hw_flags:` (and the prose that names the old variable). Never
  touch `prereqs:` or `derive.gpu_targets_var.candidates`.
- Correct the TensorFold skill on the bump branch so the cuda image installs
  the release archive instead of the refused pip line.
- Wiring `tests/test_engine_bump.py` into `make test-unit` must not turn the
  unit job red. Those tests were never executed on main. The tag-plan fixture
  must move forward, a sha-only move must still rewrite the tag literal, the
  guard assert must read the guard job (not the file header that names
  `BUMP_TOKEN`), the real image build must run where docker answers and be
  absent from the hermetic unit list, and the unit job must fetch `origin/main`
  so `matrix(changed=origin/main)` can see an unchanged tag.

## Impact

- `scripts/engine_bump.py`, `tests/test_engine_bump.py`, `Makefile`
- `.github/workflows/pipeline.yml` (unit checkout fetches history)
- `skills/engines/tensorfold/SKILL.md` and its generated params/Dockerfile
  (on the bump PR, not on this branch's main)
