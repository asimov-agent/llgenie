# Turning a data-pinned suite into invariants

A wholesale store refresh (new rows, restyled published columns, renamed "models") reds a suite whose
tests assert the previous store's contents. This file is the rewrite procedure: how to triage the red,
which invariant replaces which pin, and the traps that make a rewrite look done while it proves nothing.

## 1. Triage by CAUSE before rewriting anything

Count the failures **per file** and group them by their assertion text. A hundred reds are usually three
or four causes, and one of them is a single product field:

```bash
pytest tests/<file>.py -q -p no:cacheprovider > /tmp/f.log 2>&1; grep -c '^FAILED' /tmp/f.log
pytest tests/<file>.py -q -p no:cacheprovider 2>&1 | grep -E '^E ' | sort | uniq -c | sort -rn | head
```

- **One repeated `StopIteration` from a test's own helper is a stale PARSER, not data.** Read the helper
  before the store. The same helper is usually copy-pasted into several test files with the same regex —
  grep the regex (`grep -rn '_readme_rows\|fullmatch(r"\\\\d+GB' tests/`) and fix every copy, or the next
  file reds for the identical reason.
- **A field-vs-column disagreement is one product decision** that can clear a third of the suite at once.
  After changing it, re-measure every file: the ledger (33 / 21 / 4 / 1 cleared by one field) is what you
  report, and it tells you how much pinning is left.
- **A failure that is a real rule, not a pin, ends the rewrite there.** "Every registry member must have a
  skill or a dated decision" is a decision to be made by a human; re-deriving that test would delete the
  gate. Say so and name the owning issue.

## 2. One invariant per test shape

| the pin | the invariant that replaces it |
|---|---|
| a frozen list of names (`== ["Row A", "Row B", …]`) | derive it from the frozen fixture through the PRODUCT's function, in the fixture's order (`[m["name"] for m in reg["models"] if fits(m, card) and engines(m)]`), and keep a `len(...) > N` floor so an empty derivation cannot pass |
| `assert <field> <= card` restating the fit rule | call the product's decision (`mp.fits(model, card, ram)`), never re-derive it from one field |
| "the published column equals field X" | "the published column equals a figure the store STATES (X or Y)", plus one row where X and Y differ |
| a table of exact filenames per (model, engine, card) | a rule the CLI output must satisfy (the plan the library computed appears in the wired CLI's output; a row the gate drops is absent from both lists; a row it cannot serve is printed with a reason) |
| a hand-written RAM/CPU ladder of filenames | monotonicity over the ladder (the chosen download never shrinks as the axis grows) |

- **Grep the suite for the rule restated before changing the rule.** A helper like
  `def _fits_card(m, gb): return _num(m["tier"]) <= card_class_gb(gb)` is the old formula copied into a
  test; after the product's gate changes it fails on a shard you did not run, and the failure reads as a
  data problem. Find them with `grep -rn 'vram_tier\|_num(.*tier' tests/` and point each at the product
  function.
- **A display column is a STATED figure, not a chosen one.** When upstream prints one of two possible
  figures in a published column, the parser test may only assert "the cell matches a figure the store
  states for that row" (within the column's rounding tolerance) and that at least one row has the two
  differing — which figure upstream prints moves with a sync, so freezing the choice reds the suite the
  moment the store updates. Prove which field the GATE uses separately and hermetically: a synthetic
  model with `published_tier` 32 GB / `measured_min` 12 GB must be offered on a 16 GB card, and one with
  16 GB / 24 GB must be refused — both directions, no store involved. A data-agreement test can only ever
  prove today's numbers.
- **A rule change contradicts an EXISTING test's fixture: rewrite that test, do not just add a sibling.**
  The old fixture encodes the behaviour being removed ("one extra plan makes the gate fail"), so it goes
  red on your change; deleting it loses the intent and adding a second test leaves a fixture documenting
  the removed rule. Rewrite it as the two halves the new rule has (lost/changed → fails; added → reported
  or noted) and keep its name or rename it to the rule it now states.

## 3. Regenerate the committed derived fixtures from the COMMITTED store

A rule change almost always invalidates a committed, generator-maintained fixture (`tests/fixtures/*.json`
rendered by the same make target). Regenerate it from the committed store — never from a locally synced
one — with the repo's own target (`make <render>`), commit the result, and confirm the target's `--check`
passes and its case count is the one you report. A fixture left at the pre-change render is what
`synchronised rows == committed rows` tests red on, at every configuration, and it reads as a code bug.
