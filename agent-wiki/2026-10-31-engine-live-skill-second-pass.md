# engine-improver live skill second-pass sync (#1204)

**Issue:** #1204 · **Branch:** `fix/1204-live-skill-second-pass` · beyond #1115 (`0da8eeb5`) and #1097.

## Why a second pass

#1115 first versioned the engine-improver skill tree; #1097/#1190 synced the immediate follow-up. The live
profile kept growing after those lands, so a later "version the skill" dispatch is a **sync of the drifted
files**, not a fresh first-time copy. Measured this turn against `origin/main` `769964a1`: two of five files
drifted, three identical.

## What changed (verbatim from live)

1. **`SKILL.md`** 905 → **913** lines (+8): the #1123 note→wiki-duty lesson — editing an EXISTING tracked
   behaviour file (agent skill/SOUL, script that moves product output) owes an agent-wiki note even with no
   new wiki file; write `agent-wiki/<stem>.md` + `docs/changes.d/<stem>.md` + commit the regenerated
   `CHANGES.md`, else `check-docs` reds.
2. **`references/agent-profile-soul.md`** 98 → **120** lines (+22): the "the tree copy DRIFTS after the
   first merge" second-pass runbook — measure per-file bytes tree-vs-live before assuming the whole job
   remains; `diff -rq` empty is the proof; check whether the earlier PR already MERGED; the two repo copies
   obey opposite rules (mirror `agents/`, content-add `.hermes/`).

## Gate record

- `diff -rq agents/llgenie-engine-improver/skills/... LIVE` → **empty** (tree matches live verbatim).
- `make lint` → LINT OK · `make check-docs` → OK (after this note + fragment + regenerated CHANGES.md).
- `make changes-index` → regenerated `CHANGES.md` from fragments; committed in the same PR.
