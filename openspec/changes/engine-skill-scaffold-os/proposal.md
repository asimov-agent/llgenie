# engine-skill-scaffold-os — proposal

Issue: [#772](https://github.com/asimov-agent/llgenie/issues/772)

## Why

`scripts/engine_skill_scaffold.py::skill_text` wrote `os: [linux]` unconditionally. That file is what
`issue-bot` runs for every engine tracking issue (`issue_implementer.engine_scaffold_line` ->
`engine_skill_scaffold.scaffold`), so a new engine the registry lists as macOS/Metal-only started life
as a Linux server.

The consequence is measured, not hypothetical. `skills-validate` demands `container_spec()` for each
non-metal backend of a servable engine that has `linux` in `os`, and `make generate-engine-params`
renders a Dockerfile for every container backend it finds. A skill that wrongly claims `linux` is
therefore a skill whose params and Dockerfile are generated for an architecture upstream cannot build,
and an implementer either records a "deferred" decision it does not need or spends a PR fighting that
image. This is the invisible-engine class of defect #771 exists to catch — except here the skill itself
asserts the false cell.

The evidence needed was already in the input: the registry's `backend` string (`Metal`,
`CUDA / ROCm / CPU / Metal`, …) is what `backends()` reads. Today 42 registry engines are listed, and
the deferred decisions include Kapitsa, MTPLX, LM Studio, oMLX, Slotstream, mlx-serve and
turbo-fieldfare — every one `backend: Metal`, exactly the shape the scaffold would claim for Linux if
it were new rather than already decided.

## What Changes

- **`scripts/engine_skill_scaffold.py`**: `oses(backs)` derives `os:` from the backends the scaffold
  was given. `metal` alone (no `cuda`/`rocm`/`vulkan`/`cpu`) is `[darwin]`; `metal` plus a Linux backend
  is `[darwin, linux]`; no `metal` is `[linux]`. `os_note(backs)` renders the same evidence as one
  sentence, and `skill_text()` puts it as the first entry of the file's own to-do list — stating both
  the value written and where it came from, so the implementer corrects it with evidence from the
  pinned repo rather than by guessing. The `--backends` override is evidence too: the derived `os:`
  follows the effective backend list.
- **`tests/test_engine_skill_scaffold.py`**: the Metal-only shape (`os: [darwin]`, and
  `container_spec()` produces no image so the "a real OpenAI server always gets an image" rule does not
  apply), the Linux shape (`os: [linux]`, `container_spec()` does produce one), the dual shape
  (`[darwin, linux]`, only when the registry names both), the body's provenance line, and the explicit
  `--backends` path. The existing cases keep running unchanged.
- **Docs**: `README.md`'s `make engine-skill-scaffold` block, `docs/BOTS.md` and
  `docs/ARCHITECTURE.md` say the target derives `os:` from the same backend evidence.

## Not covered

- The 26 dated decisions in `data/unsupported-engines.json` stay as they are; this changes the
  scaffold, not the decisions.
- Whether a native Metal skill should carry a `container:` block: it must not (Metal cannot run in an
  image), and `skills-validate` already enforces the container rule only for engines with `linux` in
  `os`. Nothing here adds a second rule.

Refs: #757/#760 (the scaffold this corrects), #771 (the coverage gate that would otherwise see the
false cell), #229 (the decisions table).
