# check-docs reds a literal conflict marker in the rendered index (#1762)

A post-merge finding: main `CHANGES.md` at `e7d51d48` (the #1758 dead-vehicle-guard merge) shipped
a literal unbeheaded conflict block — lines 24/26/28 `<<<<<<< HEAD` / `=======` /
`>>>>>>> d33fed73`. Two concurrent PRs each added a row to the one contended rendered line and a
manual resolve committed the merge markers instead of re-rendering from `docs/changes.d/` (#934).

## Why it shipped green

`make check-docs` passed (run 41981717162) because it validates fragment↔note↔row linkage but
**never scanned for the raw markers** — a `<<<<<<<` / `=======` / `>>>>>>>` line is not a change
record and matches no rule. `CHANGES.md` is re-rendered from the fragments, so a conflict block is
one line away from a permanent broken row in every render.

## The gate

`scripts/check_docs.py` now scans the committed `CHANGES.md` for lines starting `<<<<<<<`, `=======`
or `>>>>>>>` (`CONFLICT_MARKER_RE`) and reds the render, naming every marker line. Because
`CHANGES.md` is rendered from the fragments, the fix for an existing block is `make changes-index`
(which this PR's own render already applies — markers live in no fragment, so the render is
marker-free by construction). `make check-docs` stays strict and now catches the class.

## Prove-the-gate

At `e7d51d48` (base), `graph()` + `problems()` return exactly 3 marker findings:
`CHANGES.md:24/26/28`. This PR re-renders `CHANGES.md` from its 526 fragments (purges the markers,
adds this note's row) and the gate is green on the clean render (issue #1762; #1761 separately owns
the tracked content heal).

