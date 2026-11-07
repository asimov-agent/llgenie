# engine-binary-probe-version-policy

## Why

The default `make engine-build` sweep (issue #1842) is red on `engine-build-tensorfold-cuda`
(run `42280478755`, job `128107985154`, `make test-engine-stage ENGINE=tensorfold ARCH=cuda
TEST=detect`). The image builds successfully but its binary flag probe fails:

```
[engine-image] tensorfold/cuda binary /opt/llgenie/engines/tensorfold/current/bin/tensorfold (documented: --version, policy: flags, probed: --version -h --help -V)
[engine-image]   --version: answers -> tensorfold 1.2.1
[engine-image]   -h: NO ANSWER (exit 2) -> ...
[engine-image]   --help: NO ANSWER (exit 2) -> ...
[engine-image]   -V: NO ANSWER (exit 2) -> ...
[engine-image] FAIL tensorfold/cuda binary ...: 1 flag problem(s)
[engine-image]   - the help family answers to neither -h nor --help: a user typing either gets nothing
```

The engine **truthfully implements no help flag**: at the 1.2.1 pin (ef27f74f) TensorFold's
`-h`/`--help` are a separate **subcommand**, not flags — measured in #1685 and re-confirmed here.
The manifest already documents `--version` only (honest set, corrected by #1690/#1685). The
remaining wrong half is the **probe policy**: `binary_probe: flags` makes `decide()` demand the
help family unconditionally (`scripts/engine_image.py::decide`), so a version-only CLI is red for
a flag it truthfully never had. This is distinct from #1880 (the GHCR cache-write tolerance).

## What Changes

- **New `binary_probe: version` policy** (the mirror of the existing `help` policy, which exempts
  the version family for a parser that has no version flag). A `version` cell:
  - MUST answer its version family (the binary self-proves — and the image's own `detect`
    re-answers `--version`, double-proving it);
  - is EXEMPT from the help family because it truthfully has none.
  This is not a gate weakening: every other policy (`flags` default, `device`, `help`) is
  unchanged, and a `version` cell whose version family answers nothing still reds (#625 stays true).
- **`scripts/engine_skills.py`**: add `"version"` to `BINARY_PROBES`, accept it in
  `probe_policy()`, and document it in the validation message.
- **`scripts/engine_image.py::decide()`**: skip the help-family failure when `policy == "version"`.
- **`skills/engines/tensorfold/SKILL.md`**: declare `binary_probe: {cuda: version}` per-backend.
- **`containers/engines/binaries.json`**: regenerated — tensorfold/cuda `probe: "version"`.
- Docs: `docs/ENGINES.md` documents the policy; the #1123 trio (change-note + agent-wiki +
  regenerated `CHANGES.md`).

## Out of scope

- #1880's buildcache cache-write tolerance (separate fix, PR #1881).
- The vllm-cuda / vllm-rocm cells in the same run (separate defects: buildcache refs + `poetry`
  import).
- Patching upstream `ashhart/TensorFold` to add a help spelling — never patch upstream (#687).
