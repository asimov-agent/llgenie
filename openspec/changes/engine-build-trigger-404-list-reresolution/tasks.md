## 1. The resolution route

- [x] Add `_run_verdict()` — read `{status, conclusion, completed_at}` for one run
- [x] On a single-run 404, re-resolve the same run from the run-LIST endpoint by id
- [x] Name the resolved run in the log, so the decision is recorded rather than silent
- [x] Return the 404 verdict (not `None`) when neither endpoint yields a verdict
- [x] Call `_run_verdict()` from the await loop

## 2. Bounds preserved

- [x] The wall-clock wait bound still bounds a run that stays unresolvable
- [x] The terminal branches, exit codes and `in_progress`-holder logic (#917/#621) are untouched
- [x] A 404 alone never concludes success — success requires a real `conclusion` from the list
- [x] No re-dispatch is added; the re-resolution is a read

## 3. Proof

- [x] The fake `gh` models both endpoints (`single_run_404`, `list_missing`)
- [x] A regression test asserts a 404-then-visible producer concludes the wait as SUCCESS
- [x] The instant-expiry test reproduces the issue's own message on the parent (fix stashed)
- [x] Docs trio (#1123): this openspec change + `agent-wiki/` note + `docs/changes.d/` row
