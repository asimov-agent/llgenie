---
name: import-roots-baseline-set-shaped
about: The import-roots baseline records the counted set, not a count, so a red names the one new file:line
status: active
---

# The import-roots baseline records the set, not just the count (issue #1101)

## Proposal

`scripts/check_import_roots.py ratchet` — the CI gate `make check-import-roots` — refuses a tree whose
count of a rule rose above `tests/fixtures/import-roots-baseline.json`. The baseline records a number per
rule:

```json
{"bare": 52, "sys-path": 32, "syntax": 0}
```

so a red can name every site the rule counted (`[import-roots] sys-path: over by 1 — the 33 site(s)
this rule counts, and the new one is among them`) but cannot identify **which** site is the new one — the
reader must diff. #1066 fixed the withholding; this fixes the identification.

## Change

Make the baseline **set-shaped**: record the counted sites themselves, not just the aggregate. Each rule
becomes

```json
{"sys-path": {"count": 32, "sites": ["tests/test_a.py:12", "tests/test_b.py:1", "..."]}}
```

The ratchet then computes a genuine set difference: a site present now and recorded then is a refusal
naming that exact `file:line` as `new`; a site recorded then and gone now is the sanctioned shrink
(`removed`, allowed — issue #796's "may only shrink"). The aggregate `count` stays for the ratchet's
"may only shrink" semantics and for a one-time migration note.

## Motivation

When an author adds a root they see their own file in the list (#1066's win). A reviewer, a rebase, or
someone inheriting a red branch does not — and must supply the diff the gate already holds. A gate that
names 33 sites for a change that added one does not answer the question it was asked.

## Acceptance

- a single injected `sys.path.insert` produces **one** red naming that exact file:line, not a list of everyone;
- removing a root produces no red, and reports the shrunken site (so #796's "may only shrink" stays assertable);
- the fixture grows to a site list per rule, and the aggregate keys stay readable for a transition (or a migration note states the one-time regeneration);
- `make check-import-roots` remains the gate path (`ratchet`, never `check` — see #1066).

## Relation

- **#1066** — fixed the withholding; this fixes the identification.
- **#796** — the ratchet's origin (the migration may only shrink); the shrink reporting now carries the site.
- **#1082** — the merged PR that landed #1066; its behaviour is the baseline for this issue.
