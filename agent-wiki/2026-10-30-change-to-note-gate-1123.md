# 2026-10-30 — issue #1123: enforce change→note, the direction check-docs never checked

## The defect (measured at `main adf2c4e1`)

`check-docs` enforced **note → fragment** (a note must have an index row) but never **change → note**.
So a behavioural change with no `agent-wiki/` note merged green. Measured with the API:

```
gh pr list --state merged --limit 40 --json number,files
  → 12 of the last 40 merged PRs touch scripts/ | agents/ | docs/ and carry NO agent-wiki/ note
gh pr list --state merged --limit 60 …  → 18 of the last 60
```
Examples: #1052 (`docs/ARCHITECTURE.md`), #1044 (`agents/llgenie-security/SOUL.md`), #1040
(`scripts/`+`Makefile`+workflow), #1029 (large engine change), #1004 (workflows+scripts+docs).

## The rule (argued before the check)

A change owes a note when it touches a **behavioural surface**; a test-only, fixture-only or
record-only change does not. Demanding a note for a whitespace fix teaches filler notes, which is
worse than none — the record stops meaning anything. So the gate bites only where behaviour moved:

- **Owes:** `scripts/**`, `agents/*/SOUL.md`, `agents/*/skills/**`, `agents/manifest.json`,
  `docs/**/*.md`, `.github/workflows/**`, `Makefile`, `data/**`, `containers/**`, `openspec/**`.
- **Exempt:** `tests/**`, `agent-wiki/**`, `docs/changes.d/**`, `CHANGES.md`.

## The change

- `scripts/check_docs.py`: adds `owes_note(paths)`, `change_note_problems(root, base)`, `_default_base`,
  `_changed_paths`, and wires it into `main()` via `--base` / `CHECK_DOCS_BASE`, defaulting to
  `origin/main`. When no base ref resolves the rule is **skipped with a printed note**, so a base-less
  CI checkout never false-reds; where a base exists it gates.
- `tests/test_change_to_note.py`: exercises **both** evidence lines — a `scripts/` change with no note
  produces a problem; test-only and note-present changes pass; `owes_note` is asserted per surface
  (behaviour/subset, not an exact list).

## Verification

```
python3 scripts/check_docs.py check   (this branch, before its note)  → exit 1, names scripts/check_docs.py
python3 scripts/check_docs.py check   (after note + fragment)          → exit 0
python -m pytest tests/test_change_to_note.py                          → 21 passed
```

Issue: #1123
