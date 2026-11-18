# 2026-11-17 — engine-skill-tensorfold-2867 (issue #2867, PR #<TBD>)

TensorFold re-pinned v1.2.5 → v1.2.9 with the companion set regenerated from the skill.

## What was verified

- **Failure anatomy of the old bump PR #2856.** `engine-build-tensorfold-cuda`
  (check-run 133455397346 at head `bb5ddc8a1`) was **cancelled** when the PR closed
  superseded — the run never reached a failing step (logs show it cut off in `apt-get`,
  and the "manifest unknown" line is a benign buildcache miss, not a recipe failure).
  Its CI-unit reds came from the missing note-pair docs gate that #2870 (#2865) fixed in
  main. So issue #2867's "recipe no longer matches the upstream release" premise had no
  captured build error behind it; the actionable gap is that main still pins v1.2.5 while
  upstream is at v1.2.9, and the bump needs a companion-complete landing (#2865/#2866 family).
- **Recipe interfaces re-checked at v1.2.9** (upstream `ashhart/TensorFold`, tag object
  `539dc9d6044cad545cae3abeb019bb8fe202d35a`): `.zig-version` still `0.17.0` (so the
  `ziglang==0.17.0` PyPI pin carries), `zig/build/cuda.zig` still exports
  `release_sms = "80,86,120,121"` (so `-Dsm=80,86,120,121` carries), and the installed
  artifact is still named `tensorfold` (`installArtifact(b.addExecutable(.{ .name =
  "tensorfold", … })` at cuda.zig:89), so the `zig-out/bin/tensorfold` symlink carries.
  The v1.2.5→v1.2.9 compare is 1108 commits (file list API-truncated at 300), but every
  interface this recipe reads is pinned by the tag checkout — the build is source-pinned,
  not preset-sensitive like ollama.
- **Companions regenerated in one pass**: `make -s generate-engine-params
  ENGINE=tensorfold` rewrote `Dockerfile.cuda` (pinned label + comment) and
  `params/tensorfold.json` (fetch/checkout commands, `…/1.2.9/…` paths, `pinned`);
  `binaries.json` has no tensorfold entry (build cell — binary path lives in params).
  Diff is confined to tensorfold paths.
- **Real-tree asserts followed the pin**: `tests/test_engine_skills.py` probe-policy
  docstring and `docs/ENGINES.md` probe-policy paragraph now name the 1.2.9 pin.
  `tests/test_tensorfold_seamless.py::ARCHIVE_PINNED`, `test_engine_binary_flags.py`
  verdict fixtures, `test_engine_gate_strict.py` and `test_engine_source_guard.py`
  fixtures are synthetic (not tied to the live pin) and stayed.
- **Gates**: `check-engine-params`, `check-engine-source`, `check-engine-capabilities`,
  `skills-validate` all rc=0. Targeted pytest across the seven tensorfold-adjacent test
  modules passed on the committed tree (see PR body proven strings). AC1 of #2867 is
  proven by the PR's own `engine-build-tensorfold-cuda` cell run id.

## Key decisions

- Land as a skill-driven re-pin (edit skill → regenerate), never by editing generated
  files — the same repair shape as #2866 (ollama) and #2865 (companions gate).
- No host-side engine image build (owner directive: builds belong to CI cells).

## Current status

Implementation complete; PR green state and the tensorfold-cuda cell verdict tracked on
the PR (issue #2867 closes on merge).
