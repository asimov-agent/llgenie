# Reduce the CHANGES.md merge-collision cost (issue #1103)

## Why

Every change PR that regenerates `CHANGES.md` (via `make changes-index`) modifies the same shared
append file, so several open PRs race on it and each merge re-conflicts the rest. Measured at
`main@d86c43bd` (2026-10-31), four PRs (#1065, #1074, #1075, #1077) independently carried a
`CHANGES.md` hunk.

The obvious fix — "fragment-only, do not regenerate" — was proposed, measured, and **rejected**
(recorded in `design.md`) because it trades a cheap mechanical cost for a real correctness defect:
relaxing the determinism gate (`committed == rendered`, issue #1063) to `committed ⊆ rendered`
would permit a fragment with no row, i.e. the published `CHANGES.md` silently omitting a change.
A missing published change is a defect in the artefact this repo publishes; a merge conflict is
minutes of work.

The two are **duals, not duplicates**: the determinism guarantee is not to be relaxed. #1063 ships
the row-side gate and leaves that test strict. This change attacks the remaining cost — the
manual rebase work when a `CHANGES.md` conflict does happen — while keeping `committed == rendered`
true at every commit.

## What Changes

- **`scripts/changes_index.py resolve` — the merge-time resolution helper (candidate 1).**
  On a conflicted `CHANGES.md`, `make changes-resolve` takes `<base>`'s file (`git checkout
  <base> -- CHANGES.md`) and re-renders from the merged fragments (`make changes-index`),
  then stages it. Deterministic, no invariant change, and it is the exact recipe the issue names:
  `git checkout <base> -- CHANGES.md && make changes-index`.
- **`make changes-resolve`** — a user-facing target (documented in `docs/BOTS.md`; `.PHONY`),
  defaulting `BASE` to `origin/main`. A lane resolves in one command instead of a rebase.
- **A real two-commit conflict test** in `tests/test_changes_index.py`: build two commits in
  `tmp_path`, each adding a fragment/row to `CHANGES.md`, merge them to a real conflict, run
  `resolve`, assert the result equals `git checkout <base> -- CHANGES.md && make changes-index`,
  `CHANGES.md` parses, and the determinism test still passes.
- **Docs**: `docs/BOTS.md` documents the new target (the audit surface requires it);
  `docs/ARCHITECTURE.md`'s relevant prose already states the index convention, so the change
  completes it with the resolution recipe. Work record
  `agent-wiki/2026-10-31-changes-resolve-helper.md` + its fragment.

`test_the_real_index_renders_the_committed_changes_md` (determinism) is **unchanged** — this
change never touches the `committed == render` assertion.

## Impact

- Affected specs: `documentation-surface` (the resolution helper on the rendered index).
- Affected code: `scripts/changes_index.py` (add `resolve` subcommand), `Makefile`
  (`changes-resolve`, `.PHONY`), `tests/test_changes_index.py` (the two-commit conflict test),
  `docs/BOTS.md`, `agent-wiki/2026-10-31-changes-resolve-helper.md`,
  `docs/changes.d/2026-10-31-changes-resolve-helper.md`.
- Not affected: #1063's determinism test (unchanged by design); no `.gitattributes` union, no
  fragment-only relaxation (both rejected in `design.md`).
