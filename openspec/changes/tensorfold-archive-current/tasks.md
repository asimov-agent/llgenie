# Tasks

- [x] 1. `scripts/engine_bump.py::release_archive_install` emits `ln -sfn {prefix}/{version} {prefix}/current` as the LAST install step, and `_apply_release_archive` sets `binary: "{prefix}/current/bin/{id}"` (detect stays `{binary} --version`)
- [x] 2. `_apply_release_archive` ensures `--version` is among the documented `binary_flags` (`["--help", "--version"]` when `--help` is present, else `["--version"]`), keeping valid YAML flow style
- [x] 3. `tests/test_engine_bump.py` locks the new derived shape (the `current` link and the `{prefix}/current/bin/{id}` binary) in `test_apply_release_archive_replaces_pip_install`, `test_bump_reads_the_destination_release` and `test_each_failed_bump_engine_keeps_its_install_kind`
- [x] 4. `tests/test_tensorfold_seamless.py` is install-kind agnostic: the pip/`uv` skill and a synthesized release-archive skill both reach `missing` / `outdated` / `current` through the real `native_status` + `ensure_native`, with `uv`/`curl`/`shasum`/`tar`/`tensorfold` as real stand-in executables on PATH; no product mock, no skipped test
- [x] 5. The picker labels hold for both install kinds (`test_archive_kind_picker_labels`), and the subprocess pick tests still pass for the live/pip skill
- [x] 6. `tests/test_mac_trend_pick.py::test_tensorfold_image_is_cuda_only_and_built_by_linux_ci` asserts the invariants (non-empty metal install = the skill's declared steps, no `sudo`, no `curl | sh` pipe, cuda-only image built by Linux CI) instead of a hardcoded `uv` list
- [x] 7. README documents the derived shape (the `{prefix}/current` link and the `{prefix}/current/bin/{id}` binary) where the engine skills / native installs are described
- [x] 8. `agent-wiki/2026-10-19-tensorfold-archive-current.md` records the work, referencing issue #386
- [x] 9. Verified with the real suite: `make test-unit`, `make lint`, `make check-engine-params`, `make check-wiring`, `make check-docs` and `make openspec-validate NAME=tensorfold-archive-current` all exit 0
- [x] 10. `scripts/engine_bump.py::_drop_pip_prereqs` removes `uv`/`pip`/`pip3` from the skill's `prereqs` when no derived step names it (only inside the `prereqs` block, per backend, keeping every other tool), and `tests/test_engine_bump.py` + `tests/test_tensorfold_seamless.py` lock it both on the derivation and on a host with no `uv` on PATH
