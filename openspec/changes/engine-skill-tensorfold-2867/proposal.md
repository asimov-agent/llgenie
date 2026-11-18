## Why

The 2026-11-16 tensorfold bump (PR #2856) proposed `v1.2.9` but its engine-build run was
cancelled when the PR closed superseded (`engine-build-tensorfold-cuda`, check-run
133455397346), and its CI-unit reds came from the missing note-pair docs gate that #2870 has
since fixed in main. Main still pins tensorfold at `v1.2.5` while upstream moved four tags. This
change re-derives the tensorfold engine skill at `v1.2.9` and lands the complete companion set —
the same split-pin family as #2865/#2866 — with the PR's cuda cell as the live proof.

## What Changes

- `skills/engines/tensorfold/SKILL.md`: `ref`/`version` → `v1.2.9` (upstream tag object
  `539dc9d6044cad545cae3abeb019bb8fe202d35a`), `pinned` → that sha, `verified` → 2026-11-17. The
  cuda source-build recipe was re-checked at the new pin and carries unchanged: `.zig-version` is
  still `0.17.0` (so `ziglang==0.17.0` from PyPI stays), `zig/build/cuda.zig` still exports
  `release_sms = "80,86,120,121"`, and the installed artifact is still named `tensorfold`
  (`installArtifact(b.addExecutable(.{ .name = "tensorfold", … }))`), so `-Dsm=80,86,120,121` and
  the `zig-out/bin/tensorfold` symlink both hold.
- `make generate-engine-params ENGINE=tensorfold` regenerates the companions: the tensorfold
  Dockerfiles and `containers/engines/binaries.json` binary paths to `…/tensorfold/1.2.9/…`.
- Real-tree test asserts that name the tensorfold pin follow the new version.

## Impact

- Affected specs: `tensorfold-engine-build` (new capability: the shipped tensorfold cells pin one
  version across skill, generated dockerfiles/params, and the binaries manifest; a pin move
  re-checks the zig recipe interfaces)
- Affected code: `skills/engines/tensorfold/SKILL.md`, `containers/engines/dockerfiles/tensorfold/*`,
  `containers/engines/binaries.json`, `containers/engines/params/tensorfold.json`, and the
  real-tree asserts in `tests/test_engine_skills.py`
- The PR's `engine-build-tensorfold-cuda` job is the live proof (issue #2867 AC 1); no engine
  image is built on the host.
