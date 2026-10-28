# A scaffolded engine skill derives `os:` from its own backend evidence

Issue #772, implemented by the issue-bot on its feature branch; the PR number is added to the
`CHANGES.md` row when the PR opens. Corrects the scaffold added by #757 (#760): `skill_text()` wrote
`os: [linux]` unconditionally.

## What was verified

- **The shape the bug was measured on.** `Kapitsa`, `MTPLX`, `LM Studio`, `oMLX`, `Slotstream`,
  `mlx-serve` and `turbo-fieldfare` all carry `backend: Metal` in `data/models.json`; before this change
  the scaffold would have written `os: [linux]` for every one of them, and `skills-validate` would then
  demand `container_spec()` for a backend the engine cannot build on Linux.
- **The derivation now reads the evidence it already had.** `oses(backs)`: `metal` alone -> `darwin`;
  `metal` plus any of `cuda`/`rocm`/`vulkan`/`cpu` -> `darwin, linux`; no `metal` -> `linux`. Run
  against the vendored store: `Kapitsa`/`MLX` -> `os: [darwin]`, `llama.cpp`/`Ollama`/`LiteRT` ->
  `os: [darwin, linux]`.
- **The gate agrees with the value.** `engine_skills.container_spec()` returns `None` for a
  `backends: [metal]`, `os: [darwin]` skill, so `validate()` raises no "servable engine has no
  container image for …" — the Linux-image rule applies exactly where an image is possible. That is
  asserted in the Metal-only test rather than assumed.
- **`tests/test_engine_skill_scaffold.py` — 11 passed.** New cases: Metal-only (`os: [darwin]`),
  Linux (`os: [linux]`, `container_spec()` non-empty), dual (`CUDA / Metal` -> `[darwin, linux]`),
  the body's provenance line, and the `--backends` override driving `os:` as well. The five existing
  cases were not weakened; one gained an `os:` assertion.

## Decisions

- **`--backends` is evidence too.** The `os:` derivation reads the effective backend list, so a caller
  who supplies the list from the engine's own docs gets the `os:` that list implies, not the registry's
  wording's.
- **The body states the derivation, as a to-do item.** Requirement 2 of the issue asks the implementer
  to see *why* the value is what it is; `os_note()` writes the value plus the backend evidence plus
  "check it against the pinned repo", which keeps a wrong value a correctable claim with a named source
  rather than a guess.
- **No second rule for Metal.** A native Metal skill carries no `container:` block because
  `container_spec()` already refuses a non-Linux `os:`; nothing here duplicates that check.

## Not covered

The 26 dated decisions in `data/unsupported-engines.json` are untouched — this change fixes the
scaffold, not the decisions table (#229), and whether a native Metal skill may carry a `container:`
block stays as `skills-validate` already has it.

## Status

Complete: `os:` derived, body states the provenance, both shapes locked by tests, README
`make engine-skill-scaffold` block plus `docs/BOTS.md` and `docs/ARCHITECTURE.md` updated.

Gates: `scripts/unit_tests.py run` (the suite `make test-unit` runs) `14549 passed, 6 deselected`;
`lint_linefeeds.py` LINT OK; `check_wiring.py check` OK; `check_docs.py check` ok;
`check_openspec_tasks.py engine-skill-scaffold-os` OK. The two make targets that wrap `docker run`
(`test-unit`, `openspec-validate`) cannot start here — the agent container has no Docker socket — so
`ci-unit` and `ci-openspec` are what run them on the PR.
