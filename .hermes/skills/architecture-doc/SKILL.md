---
name: architecture-doc
description: Rewrite docs/ARCHITECTURE.md from the deterministic brief so it describes the tree as it is now — real files, targets, workflows and crons only, the doc is the one writable file.
---

# architecture-doc

`docs/ARCHITECTURE.md` is the map of llgenie's shipped path, and it ages the moment the tree
moves. The host derives a brief from real `git` state; you rewrite the doc from it.

## Inputs

- The brief (`architecture-brief.md` by default, `$(ARCH_BRIEF)` in the leg): read it FIRST. It
  carries the current doc, the git drift since that doc was last committed, and the real code
  surface — tracked layout, scripts modules, public make targets, workflows and crons,
  `data/`, `skills/`, `containers/`, `tests/`.
- The current doc itself (`$(DOC)`), which the brief quotes.
- `AGENTS.md` is already in your context as the repository's durable rules.

## Output

- `$(DOC)` (default `docs/ARCHITECTURE.md`), rewritten in place. That is the only writable file.

## Rules

- Describe the tree **as it is now**: the shipped path end to end (install -> backend/hardware
  detection -> trend list -> engine skill -> engine image -> launcher), the data files, the CI
  jobs, the bots with their cron slots, and the test/gate layout.
- **Name real files and targets; never invent** a module, target, workflow, cron or image the
  brief does not list. Keep what is still true; fix or delete what moved.
- **Modify NO file except `$(DOC)`.** Do not create a branch, commit, push, or open an issue or
  a PR — the deterministic publish step does that. Never touch `main`.
