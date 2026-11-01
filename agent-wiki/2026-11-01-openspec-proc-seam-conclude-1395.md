# docs(openspec): conclude the proc-seam OpenSpec change — archive + supersession note, ci-openspec rc=0 (#1395)

## Why

After #797 (proc-seam, CLOSED COMPLETED) and #1385 (its successor fix, MERGED), the
`openspec/changes/proc-seam/` OpenSpec change object was still ACTIVE with four unchecked task
checkboxes (lines 6, 9, 10, 11 — the internal 16-checking-wrapper collapse, plus validate / docs /
gates record tasks). `make ci-openspec` (`openspec-tasks-check`) therefore exited rc=2 on every
balanced PR built from main, and a reader could not tell whether the change's intent was completed or
merely closed. #1385 touched only ARCHITECTURE.md / `issue_bot_gates.py` / docs-exceptions, not the
change's own task list, so it fixed the check-classification gates but left the change object red.

## Resolution (route b — conclude, do not re-open)

#797 was closed COMPLETED and its What-Changes steps 1–3 and 5 landed (the three named policies in
`scripts/proc.py`, the swallowing wrappers migrated loud, the 11 no-exit-code wrappers gone, the
`# proc-allow:` gate + census shipped). Step 4 — collapsing the internal *checking* wrappers onto
`run_checked()` — was the deferred refactor tail the #797 closure did not require; executing it now
would re-open #797's closed scope at large risk for zero board value. Per the #1395 dispatch this is the
sanctioned "conclude the change" path.

## What changed

- Moved `openspec/changes/proc-seam/` → `openspec/changes/archive/proc-seam/` (git rename), so the
  active-set gate (`make ci-openspec`) no longer sees it.
- Ticked every task box `[x]` in `tasks.md`, with a **supersession note** on task 6 (the collapse is
  recorded as concluded-not-performed, referencing #797/#1385) and task 10, and verification notes on
  tasks 9 and 11.
- Appended a `## Conclusion (archived — superseded by #797 closure)` section to `proposal.md`.

## Measured (clean worktree at the PR head)

- `make ci-openspec` **rc=0** — `Totals: 297 passed, 0 failed`; `proc-seam` no longer in the active output.
- `python3 scripts/check_openspec_tasks.py` → 0 failures; `proc-seam` absent (archived).
- This note pair ships per #1123.

`AGENTS:` preflight — base = `origin/main` `b6b5ad32` (fetched 17:38Z on 2026-11-01).

