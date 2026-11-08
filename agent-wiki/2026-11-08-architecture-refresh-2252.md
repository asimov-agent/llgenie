# llgenie — #2252: docs(architecture) refresh for the tree at 20261108T1400

- **Date:** 2026-11-08 · **Issue:** #2252 (architecture-bot refresh drift)
- **Branch:** `agent/architecture-20261108T1400` (base `7e633a28`, the head's parent)
- **PR:** the ready-for-review PR closing #2252

## What changed

`docs/ARCHITECTURE.md` lagged the tree — last updated at `b58215b558c8`, with 1 commit(s)
and 10 changed path(s) since, so the document did not describe the code a reviewer was
reading. The architecture bot re-derived the surface and the drift from real `git` state
(`make architecture-bot-brief` -> `make architecture-bot-doc`) and rewrote only the doc; this
PR carries that one file on `agent/architecture-20261108T1400`.

The refresh re-measures the census at `7e633a28` (3886 tracked files; `data/` 13,
`skills/` 18, `containers/` 60, `tests/` 235, `scripts/` 166, `openspec/` 1544,
`agent-wiki/` 675, `docs/` 684; openspec 395 changes) and folds the committed-set
pin-validity prose from the merged guard (`scripts/check_engine_pins_published.py --all`,
`make check-engine-pins-valid`, the `registry-liveness` monitor) into the engines section so
the document states the publish-gap gate that the tree now runs.

## Verified

- `docs/ARCHITECTURE.md` is current at `7e633a28`; drift paths include `CHANGES.md`, `Makefile`,
  `agent-wiki/2026-11-08-committed-set-pin-validity.md`,
  `docs/changes.d/2026-11-08-committed-set-pin-validity.md`,
  `openspec/changes/committed-set-pin-validity/` (proposal + specs + tasks),
  `scripts/check_engine_pins_published.py` and `tests/test_check_engine_pins_published.py` —
  each re-measured against the real tree, not by eye.
- `make check-docs` rc=0 on the pushed head (guard + change-note trio present).
- Committed as `Asimov Agent <support@docondee.com>`; the bot never merges and never pushes to
  `main`.

## Decision

The refresh is a docs-only change: nothing under `scripts/`, `tests/`, `containers/` or
`.github/workflows/` moved on this branch — only `docs/ARCHITECTURE.md` plus this note and its
index row. The `change->note` rule (issue #1123) still requires the trio because
`docs/ARCHITECTURE.md` is a `NOTE_SURFACE_RES` path, so the note + `docs/changes.d/` fragment +
`CHANGES.md` index row are added here.
