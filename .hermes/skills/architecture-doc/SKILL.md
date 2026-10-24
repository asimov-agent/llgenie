---
name: architecture-doc
description: Use when the llgenie architecture bot must rewrite docs/ARCHITECTURE.md from the generated brief, without touching any other file.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, architecture-bot, docs]
---

# Architecture doc

`docs/ARCHITECTURE.md` is the map of the shipped path, and it ages the moment the tree moves. This
leg rewrites it from a brief the host derived from real `git` state. It writes one document and
nothing else; the deterministic publish step files the issue and the PR.

## Inputs

- `$(ARCH_BRIEF)` (default `architecture-brief.md`) at the repo root — **read it first**. It carries
  the current document, the drift since that doc was last committed, and the real code surface:
  tracked layout, `scripts/` modules, public make targets, workflows and crons,
  `data/`/`skills/`/`containers/`/`tests/`.
- The tree itself, when the brief is not enough: read the file you are about to describe.

## Output

- **`$(DOC)` (default `docs/ARCHITECTURE.md`) rewritten** so it describes that tree as it is now:
  the shipped path end to end (install → backend/hardware detection → trend list → engine skill →
  engine image → launcher), the data files, the CI jobs, the bots with their cron slots, and the
  test/gate layout.
- Nothing else in the tree changes.

## Rules

- **Name real files, targets, workflows, crons and images.** Never invent one the brief does not
  list; a doc that names a module which does not exist is worse than a stale doc.
- **Keep what is still true; fix or delete what moved.** A rewrite that drops shipped behaviour is
  a regression, not a refresh.
- **The brief is evidence, not prose to paste.** If the drift and the tree disagree, the tree wins —
  say so in the doc.
- **Modify no file except `$(DOC)`.** No branch, no commit, no push, no issue, no PR — the publish
  step does all of that, and never touches `main`.
