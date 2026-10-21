# feat-architecture-bot

## Why

The repository has no architecture document, and nothing re-derives its structure when the
code moves. A reviewer reconstructs the `install -> hardware -> trend list -> engine skill ->
engine image -> launcher` path, and the bot/CI topology, from source every time; AGENTS.md
carries rules, not a current map. Every other recurring reading of the tree already has a
bot (issues, review findings, registry sync, engine bumps); architecture is the gap.

Issue: [#449](https://github.com/asimov-agent/llgenie/issues/449).

## What Changes

- **New workflow `.github/workflows/architecture-bot.yml`**: cron `47 */6 * * *` and
  `workflow_dispatch` (owner/collaborator/bot guard before any secret is read; `dry` and
  `doc` inputs). It never merges, never pushes to `main`, and never edits anything except
  `docs/ARCHITECTURE.md` on its own branch.
- **New `scripts/architecture_bot.py`** (stdlib, no model): the deterministic half.
  - `surface` reads the real tree (git-tracked files, `scripts/` modules and their first
    docstring line, public make targets, workflow names + crons, `data/`, `skills/`, tests).
  - `drift` compares `HEAD` against the commit that last touched the doc, so the brief says
    what changed since the document was written.
  - `publish` files ONE issue (Issue/Fix/Benefit/Technical), commits the doc as
    `Asimov Agent` on `agent/architecture-<UTC stamp>`, and opens ONE PR that ends with
    `closes #<issue>`. It refuses an empty doc, refuses when nothing changed, and skips
    when an `agent/architecture-*` PR is already open (no issue spam every 6 hours), and
  refuses to publish from any branch other than `main` (a refresh must never ride on another
  branch's PR), and refuses when the run changed a tracked file other than the doc (the agent's
  write boundary is enforced, not just prompted).
- **New make targets**: `architecture-bot-brief`, `architecture-bot-doc` (the one Hermes
  leg, inside the agent image, transcript redacted by the existing `scrubbed_run` seam),
  `architecture-bot-publish`, and the `architecture-bot` chain for a manual local run.
- **New `docs/ARCHITECTURE.md`**: the current map, seeded by this change and thereafter
  maintained by the bot.
- README section + dispatch table, `agent-wiki/` entry, and hermetic tests in
  `tests/test_architecture_bot.py`.

## Impact

- Affected specs: new capability `architecture-bot`.
- Affected code: `.github/workflows/architecture-bot.yml`, `scripts/architecture_bot.py`,
  `Makefile`, `docs/ARCHITECTURE.md`, `README.md`, `tests/test_architecture_bot.py`.
- No change to the serving path, engine images, or the registry.

## Not covered

- Semantic explanation of *why* a design decision was made: the bot can only read the tree
  and git history. A decision record stays a human/OpenSpec artifact.
- Diagram rendering (Mermaid/SVG): the doc is markdown. A rendering bot would be its own
  change.
