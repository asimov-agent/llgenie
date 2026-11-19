# fix-wiki-index-row-stem (2026-11-19)

## What was verified

- Finding #2947, filed by the documentation-lane audit pass recorded at #2371 (2026-11-19 row): the only
  broken internal link in `agent-wiki/**` + `docs/**` at origin/main `cbead8b698` was the self-referential
  index row inside `agent-wiki/2026-11-07-ci-check-pr-base-stale-clean-attribution.md`, linking the
  nonexistent stem `2026-11-07-check-pr-base-stale-clean-attribution.md` (missing the `ci-` prefix).
- Fix: the row now links the file's own basename. The matching `docs/changes.d` fragment and `CHANGES.md`
  row already linked the correct file and were untouched.
- Scan recipe (denominator named): walk `agent-wiki/` + `docs/` for `.md` files (1844), extract
  markdown link targets, skip external URLs and angle-bracket placeholders, resolve
  repo-root-relative then file-relative; broken count 1 before, 0 after.

## Key decisions

- The audit pass recorded the finding rather than fixing it in-lane (#2371 AC3: findings route through the
  normal implementation queue); this lane implements it as a normal queue change.
- No gate change: `check-docs` covers CHANGES.md rows; extending it to self-referential rows inside notes
  would need its own issue — out of scope here (the corpus is now clean, so the gate gap has no live bite).

## Current status

- OpenSpec change `fix-wiki-index-row-stem`; proofs: grep for the broken stem prints 0, link scan rc=0,
  `make check-docs` rc=0, `make lint` rc=0.
