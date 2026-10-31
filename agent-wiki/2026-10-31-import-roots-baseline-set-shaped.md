# 2026-10-31 — issue #1101: the import-roots baseline is set-shaped, so a red names the ONE new root

## What was wrong

`scripts/check_import_roots.py ratchet` — the CI gate `make check-import-roots` — refused a tree whose
count of a rule rose above `tests/fixtures/import-roots-baseline.json`, and #1066 made it name every
site its over-counted rule counted. But the baseline recorded a **count**: `{"bare": 52, "sys-path": 32, "syntax": 0}`, so a red still listed all 33 sites of the offending rule and the reader had to diff
to pick out the new one. For the lane that just added the root the list was enough; for a reviewer, a
rebase, or someone inheriting a red branch it was not — the gate named every site the rule counted and
none of them as the new one.

## What the change is

- **The baseline is now set-shaped.** Each rule records its counted `file:line` sites alongside the
  aggregate:

  ```json
  {"sys-path": {"count": 32, "sites": ["tests/test_a.py:12", "tests/test_b.py:1", "…"]}}
  ```

  The aggregate `count` stays for the ratchet's "may only shrink" semantics and for a one-time
  migration note.
- **`ratchet()` diffs the sets.** A site present now and absent at the baseline is a refusal (`new`)
  naming exactly that `file:line`; a site recorded then and gone now is the reported, allowed shrink
  (`removed`). Both halves are per-site facts rather than arithmetic.
- **A legacy count-shaped entry still ratchets.** A plain-integer baseline entry (the pre-#1101 shape)
  refuses on the count overshoot, names the rule's sites, and carries a note to re-record once with
  `--update` — so an un-migrated fixture keeps the gate closed rather than silently passing.
- `update_baseline` (`--update`) writes the set-shaped fixture; `report`/`check` and their exit codes
  are unchanged; `make check-import-roots` stays the `ratchet` path.

## Decisions

- **Record the set, not a "first new one".** The gate must name exactly the new site: a genuine set
  difference is the only honest way to know which site is new.
- **Removed sites are reported, not refused.** #796's "the migration may only shrink" is the contract:
  a root that vanished is green, and reporting which one keeps the shrink assertable in a hard way
  (the line names the file, not "and one fewer").

## Proof

Measured in this worktree (a scratch tree whose set-shaped baseline records `tests/test_a.py:2` and
`tests/test_b.py:2`):

- clean tree, baseline a 2-set = baseline:
  `ratchet` → `RC=0`, `[import-roots] OK: counts at or below the recorded baseline …`;
- one injected root at `tests/test_zz_probe_1101.py:2`:
  `ratchet` → `RC=1`, `sys-path: a NEW import root is refused — this exactly …` then
  `  tests/test_zz_probe_1101.py:2` — the recorded sites are **not** named alongside it;
- a recorded root removed (none added): `ratchet` → `RC=0`,
  `sys-path: removed site(s), allowed — the migration may only shrink …` then `  tests/test_b.py:2`;
- a legacy count-shaped `"sys-path": 1` entry with 2 current sites: `RC=1`, names both sites and
  says `re-record once with --update so a red names the new file`.

Issue: #1101
