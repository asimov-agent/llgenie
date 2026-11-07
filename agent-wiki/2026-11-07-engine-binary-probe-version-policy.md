# engine-build: tensorfold-cuda's flag probe honours the version-only binary (#1888)

The default `make engine-build` sweep red on `engine-build-tensorfold-cuda` because its binary
flag probe failed even though the image built. Measured (run `42280478755`, job `128107985154`,
`make test-engine-stage ENGINE=tensorfold ARCH=cuda TEST=detect`):

```
[engine-image] tensorfold/cuda binary /opt/llgenie/engines/tensorfold/current/bin/tensorfold (documented: --version, policy: flags, probed: --version -h --help -V)
[engine-image]   --version: answers -> tensorfold 1.2.1
[engine-image]   -h: NO ANSWER (exit 2) -> ...
[engine-image]   --help: NO ANSWER (exit 2) -> ...
[engine-image]   -V: NO ANSWER (exit 2) -> ...
[engine-image] FAIL tensorfold/cuda binary ...: 1 flag problem(s)
[engine-image]   - the help family answers to neither -h nor --help: a user typing either gets nothing
```

The engine **truthfully implements no help flag**: at the 1.2.1 pin (`ef27f74f`) TensorFold's
`-h`/`--help` are a separate **subcommand**, not flags — measured in #1685 and re-confirmed here.
The manifest already documents `--version` only (the honest set, corrected by #1690). The
remaining wrong half was the probe policy: `binary_probe: flags` makes `decide()` demand the help
family unconditionally (`scripts/engine_image.py::decide`), so a version-only CLI reds for a flag
it truthfully never had.

Fix: a new `binary_probe: version` policy, the mirror of the existing `help` policy.

- `scripts/engine_image.py::decide()` skips the help-family failure when `policy == "version"` —
  the version family must still answer (the binary self-proves, and the image's own `detect`
  re-answers `--version`, double-proving it).
- `scripts/engine_skills.py`: `BINARY_PROBES = ("device", "help", "version")`; `probe_policy()`
  accepts `version`; the validation message names all four policies.
- `skills/engines/tensorfold/SKILL.md` declares `binary_probe: {cuda: version}` per-backend
  (metal unchanged — the macOS binary answers both `--help`/`--version`).
- `containers/engines/binaries.json` regenerated: tensorfold/cuda `probe: "version"`,
  `flags: ["--version"]` unchanged.

This is **not** a gate weakening: every other policy (`flags` default, `device`, `help`) is
unchanged, and a `version` cell whose version family answers nothing still reds — the #625
guarantee ("at least one probed flag must exit 0, always") stays true. The `-V` NO ANSWER is
likewise expected and not red under `version`: tensorfold answers `--version` (one spelling of the
version family suffices, as it does for every other version-only engine).

The vllm-cuda / vllm-rocm cells in the same run are separate defects (buildcache refs + a `poetry`
import) and are out of scope, as is #1880's cache-write tolerance.

## Delivery

- PR #1892 (one vehicle, `fix/1888-tensorfold-help-probe`), head `38a1ece9`, `closes #1888`.
- `scripts/engine_skills.py`: `BINARY_PROBES = ("device", "help", "version")`; `probe_policy()`
  accepts `version`; validation names all four.
- `scripts/engine_image.py::decide()`: help family exempt only when `policy == "version"`; the
  version family must still answer (a `version` cell whose version answers nothing still reds —
  #625 holds).
- `skills/engines/tensorfold/SKILL.md`: `binary_probe: {cuda: version}` (metal unchanged).
- `containers/engines/binaries.json`: tensorfold/cuda `probe: "version"`, flags `["--version"]`.
- Tests: `test_a_version_only_cli_is_not_failed_for_having_no_help_flag`,
  `test_a_version_only_cli_with_a_dead_version_flag_still_reds`, and
  `test_binary_file_works_passes_the_version_cell_with_dead_help_flags` (the real `binary_file_works`
  gate with the exact measured probe output); plus `probe_policy()` per-backend unit in
  `test_engine_skills.py`. 151 passed across binary_flags/skills/gate_strict/force_rebuild.

Measured evidence (run `42280478755`, job `128107985154`): `--version -> tensorfold 1.2.1`,
`-h`/`--help`/`-V` → exit 2 with no output; under `probe: version` the cell is green, under
`flags` it reds the help family. The default-sweep AC1 is a reviewer-gated post-merge verdict.

