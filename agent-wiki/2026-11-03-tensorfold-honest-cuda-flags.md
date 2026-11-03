# tensorfold/cuda honest per-backend flag set (#1685)

The tensorfold CUDA server answers only `--version`; `--help` is a separate
subcommand and the engine advertsises only `--version`. `skills/engines/tensorfold/SKILL.md`
`binary_flags` is now a per-backend map (`metal: ["--help","--version"]`, `cuda: ["--version"]`)
instead of a single global set, and `scripts/engine_skills.py` `documented_flags()` resolves the
correct set per backend (e.g. `engine_image.py` probes only `--version` for the cuda image). The
`engine_image.py` help-family gate is unchanged (WAI); the tensorfold/cuda publish stays blocked at
its pin until upstream `ashhart/TensorFold` adds a help spelling — no upstream patch (issue #687).

**measured:** cuda `documented_flags == ["--version"]`; manifest `binaries.json` tensorfold/cuda
`["--version"]`; metal unchanged `["--help","--version"]`.
