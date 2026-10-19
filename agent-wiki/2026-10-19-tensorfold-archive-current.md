# A release-archive install tracks {prefix}/current so the native state can be outdated (#386)

## Why

`scripts/engine_bump.py::release_archive_install` derives a native-archive install for an
engine that previously pip-installed itself, and `_apply_release_archive` rewrote the skill to
unpack into `{prefix}/{version}` and set `binary: "{prefix}/{version}/bin/{id}"`. Because the
pinned version was baked into the binary path, the skill's `detect` (`{binary} --version`)
could only ever answer "the pinned release is present" — the installed binary's own `--version`
was never asked. `scripts/engine_skills.py::native_status` (issue #114) therefore collapsed to
`missing` (nothing at the pinned path, even when an older release was installed) and `current`
(the pinned path present, even when a newer untested release was what the user had). Measured
on the TensorFold `v1.1.1` bump PR (#373), every unit lane in `tests/test_tensorfold_seamless.py`
that locks the missing/outdated/current contract failed. A previous pass had patched the symptom
in `_version_line`; the cause is the path, not the parser.

## What landed

- **`scripts/engine_bump.py`**: the release-archive derivation now ALSO emits, as the LAST
  install step, `ln -sfn {prefix}/{version} {prefix}/current`, and sets
  `binary: "{prefix}/current/bin/{id}"` (detect stays `{binary} --version`). `{prefix}/current`
  is a symlink to the unpacked release, so detect asks the INSTALLED binary its version and
  `native_status` can report `outdated` / `current` truthfully. The derivation also ensures
  `--version` is among the documented `binary_flags` (`["--help", "--version"]` when `--help`
  is already there, else `["--version"]`), so the flags the binary answers stay honest and
  `test_each_engine_documents_the_flags_its_binary_answers` holds on a bump branch.
- **`tests/test_tensorfold_seamless.py`**: made INSTALL-KIND AGNOSTIC. It drives whatever
  install the skill declares — the pip/`uv tool install` skill (main today) and a synthesized
  release-archive skill (the `v1.1.1` bump shape) — and both reach `missing` / `outdated` /
  `current` through the REAL `engine_skills.native_status` and
  `install_engine_launchers.ensure_native`, with the picker labels holding for both. The
  product code is never mocked; only the external tools the skill shells out to (`uv`, `curl`,
  `shasum`, `tar`, `tensorfold`) are real stand-in executables on PATH that log their calls and
  materialise a plausible install (fake `curl` writes the archive, fake `shasum` exits 0, fake
  `tar` reads `-C <dir>` and creates `<dir>/bin/tensorfold-native` + `<dir>/VERSION`, and the
  fake binary prints the release from a shared state file so `--version` reports the installed
  release). No test is skipped.
- **`tests/test_mac_trend_pick.py::test_tensorfold_image_is_cuda_only_and_built_by_linux_ci`**:
  made kind-agnostic — it asserts the real invariants (the metal install is non-empty and is
  the skill's declared steps, no `sudo`, no `curl | sh` pipe, the image is cuda-only and built
  by Linux CI) instead of a hardcoded `uv` install list.
- **`tests/test_engine_bump.py`**: locks the new derived shape (the `current` link and the
  `{prefix}/current/bin/{id}` binary) in `test_apply_release_archive_replaces_pip_install`,
  `test_bump_reads_the_destination_release` and `test_each_failed_bump_engine_keeps_its_install_kind`.
- **README.md**: the native-Metal paragraph now documents the derived shape (unpack into
  `{prefix}/{version}`, point `{prefix}/current` at it, binary `{prefix}/current/bin/{id}`).

## Verification

- `tests/test_tensorfold_seamless.py`: **34 passed** (both install kinds).
- `tests/test_engine_bump.py`: **71 passed** (with the parent repo mounted, as `make test-unit`
  does via `WORKTREE_MOUNT`); the two live-GitHub-release tests are excluded from `make test-unit`
  and run only in `make test-engine-bump-live`.
- `tests/test_engine_skills.py` and `tests/test_mac_trend_pick.py`: pass.
- `make lint`, `make check-engine-params`, `make check-wiring`, `make check-docs` and
  `make openspec-validate NAME=tensorfold-archive-current` exit 0.

Implements #386. The TensorFold `v1.1.1` pin itself is #373 (out of scope here).

## Follow-up in the same change: the pip prerequisite the archive install abandoned

Reproduced while verifying: with the archive-shaped skill and `uv` **absent** from PATH,

```
prereqs: {'common': ['uv'], 'cuda': ['nvidia-smi', 'nvcc']}
install uses uv: False   install uses pip: False   install uses curl/tar: True
blockers (native): ['missing prerequisite: uv']
```

— the derivation left the pip-era prerequisite behind, so `engine_skills.check(mode="native")`
refused an install whose steps never call `uv` (a Mac without uv could not run TensorFold 1.1.1 at
all). `_drop_pip_prereqs` now filters each `prereqs` flow list inside that block, per backend, and
drops `uv`/`pip`/`pip3` only when no derived step names them; `prereqs.common` is dropped only when
no backend's steps call it. Verified on the real skill text (`common: [uv]` → `common: []`,
`cuda: [nvidia-smi, nvcc]` kept) and by
`tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install`, which also
proves the pip kind IS still refused without uv — the check was narrowed, not removed.
