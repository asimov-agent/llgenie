# tensorfold-archive-current — proposal

Issue: [#386](https://github.com/asimov-agent/llgenie/issues/386)

## Why

`scripts/engine_bump.py::release_archive_install` derives a native-archive install for an
engine that previously pip-installed itself, and `_apply_release_archive` rewrites the skill
to unpack into `{prefix}/{version}` and set `binary: "{prefix}/{version}/bin/{id}"`. Because
the **pinned version is baked into the binary path**, the skill's `detect` (`{binary} --version`)
can only ever answer "the pinned release is present" — the installed binary's own `--version`
is never asked. `scripts/engine_skills.py::native_status` (issue #114) therefore collapses to
two answers:

- nothing at the pinned path → `missing`, even when an **older** TensorFold is installed at
  `{prefix}/0.6.4`, so the picker says `(installs 1.1.1 on pick)` instead of
  `(installed 0.6.4 -> updates to 1.1.1 on pick)`;
- the pinned path present → `current`, even when a **newer, untested** release is what the
  user actually has at another path.

Measured on the TensorFold `v1.1.1` bump PR (#373), every unit lane in
`tests/test_tensorfold_seamless.py` that locks the missing/outdated/current contract failed.
A previous pass patched the symptom in `_version_line` (a bash `No such file or directory:
.../1.1.1/bin/tensorfold` line used to be read as an installed version) — the cause is the
path, not the parser. Separately, `_apply_release_archive` writes the detect flag `--version`
but leaves the skill's `binary_flags:` as whatever it was (`["--help"]`), which fails
`tests/test_engine_skills.py::test_each_engine_documents_the_flags_its_binary_answers` on a
bump branch.

## What Changes

- **`scripts/engine_bump.py`**: the release-archive derivation ALSO emits, as the LAST install
  step, `ln -sfn {prefix}/{version} {prefix}/current`, and sets
  `binary: "{prefix}/current/bin/{id}"` (detect stays `{binary} --version`). `{prefix}/current`
  is a symlink to the unpacked release, so detect asks the INSTALLED binary its version and
  `native_status` can report `outdated` / `current` truthfully. The derivation also ensures
  `--version` is among the documented `binary_flags` (writes `["--help", "--version"]` when
  `--help` is already there, else `["--version"]`), so the flags the binary answers stay honest.
- **`tests/test_tensorfold_seamless.py`**: made INSTALL-KIND AGNOSTIC — it drives whatever
  install the skill declares. The pip/`uv tool install` skill (main today) and the
  release-archive skill (the `v1.1.1` bump) both reach `missing` / `outdated` / `current`
  through the REAL `engine_skills.native_status` and `install_engine_launchers.ensure_native`,
  and the picker labels hold for both. The product code is never mocked; only the external
  tools the skill shells out to (`uv`, `curl`, `shasum`, `tar`, `tensorfold`) are real
  stand-in executables on PATH that log their calls and materialise a plausible install. No
  test is skipped.
- **`tests/test_mac_trend_pick.py::test_tensorfold_image_is_cuda_only_and_built_by_linux_ci`**:
  made kind-agnostic — it asserts the real invariants (the metal install is non-empty and is
  the skill's declared steps, no `sudo`, no `curl | sh` pipe, the image is cuda-only and built
  by Linux CI) instead of a hardcoded `uv` install list.
- **`tests/test_engine_bump.py`**: locks the new derived shape (the `current` link and the
  `{prefix}/current/bin/{id}` binary) through `bump()` → apply → `make generate-engine-params`.

## Not covered

- The TensorFold `v1.1.1` pin itself (#373) — this change makes the derivation and the tests
  correct so that bump can land; it does not move the pin.
- The engine-image smoke's Hub throttle (#385).
