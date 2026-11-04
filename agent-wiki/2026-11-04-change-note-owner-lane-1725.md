# Profile change-note discipline is a first-class deliverable — owned by the documentation-maintainer lane (#1725)

The change-note rule was rediscovering itself by CI failure on the `agents/<profile>/` path three
times — #1719 (engine lane), #1707 (docs-maintainer SOUL sync), #1697 (engine SOUL vehicle) — each
lane added its `agent-wiki/<stem>.md` note + `docs/changes.d/<stem>.md` row only after
`make check-docs` reddened (issue #1123, `Makefile:1004`). The gate worked; the process was not
first-class, and no lane owned keeping it current.

## The process (`docs/BOTS.md`, "Documentation is part of the change")

Rule 3 now states it as a required, owner-owned process, not a CI rediscovery:

- any commit that edits `agents/<profile>/SOUL.md`, a lane skill under `agents/<profile>/skills/`,
  or `agents/manifest.json` **owes its own `agent-wiki/<stem>.md` note and a
  `docs/changes.d/<stem>.md` row in the same branch** before it is ready-for-review;
- `check-docs` stays the strict backstop (nothing weakened, #1713-class gate untouched) but it is not
  the process;
- the **documentation-maintainer lane owns the practice** — a SOUL/skills PR that lands its note
  alongside the edit is the norm, and a missed one is filed as a tracked recurrence, never left to
  the next `check-docs` red.

## Prove-the-rule

This very PR is an instance of the rule it documents: changing `docs/BOTS.md` (a `NOTE_SURFACE_RES`
surface per `check_docs.py`) ships this `agent-wiki/` note + its `docs/changes.d/` row + the
regenerated `CHANGES.md` row in the same branch. Implements #1725.
