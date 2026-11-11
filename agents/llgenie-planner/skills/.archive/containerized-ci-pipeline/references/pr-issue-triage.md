# PR and tech-debt triage on an auto-merge queue

## A red PR whose validate + live-smoke are green

If `validate` and `live-smoke` are green but `auto-merge` is red, the usual cause is the base moved: a sibling auto-merged and GitHub leaves the merge state as `CONFLICTING` while the code itself is fine. Triage BEFORE touching code:

1. `git fetch origin` and check `git log origin/master` — did it move since the branch was cut?
2. If yes: rebase the branch onto the fetched master, regenerate the generated index (`make openspec-index`) and run its gate (`make openspec-check`), re-run lint, push. The red was the moving baseline, not the change.

Reading the matrix: the three checks disagree → the fault is in the TARGET of the reading, not the code. `validate` is the deterministic machine, `live-smoke` the network, `auto-merge` the merge state. Green `validate` + red `auto-merge` = merge-state problem, never a code defect on the branch. Only change code when `validate` itself is red on the branch's own head.

## The owed-rulebook-row pattern

In a repo where a rules file (e.g. `AGENTS.md` §8 guard table) is protected, a headless/agent change that adds a guard often cannot write its rules-file row in the same change — the write is gated behind an approval prompt that silently never returns in a bot run ("Silence is not consent"). The guard ships registered in the test suite but undiscoverable from the rulebook, and a "rules-file row is owed" finding records exactly which row. It is a blocked artifact of the approval gate, not a defect.

Closing one:

1. Read the finding's **Done-when** for the exact row text — it names the section and the words.
2. Write the row(s) verbatim; never put another finding's row under this one's name — every finding's wording is its own, and a row is never smuggled.
3. Add a guard test that PINS the row: the row text is present, the module it names exists, the guard it names really lives in that module, and the section still parses as its table. Prove RED on the pre-change rules file, GREEN after.
4. PR body closes every implemented issue: one closing keyword each, each binding one reference.

## Re-evaluating open tech-debt against a new base

Before acting on an open finding, re-verify it against the CURRENT base (pull/fetch first — the baseline and its code move):

- **Code already fixed** (a helper now reads the right source, a guard asserts the right direction) → close with a comment carrying the EVIDENCE (file:line / command / measured output), not a bare close. The finding's full-bodied twin often already closed it.
- **Preconditions changed** (one half shipped, one remains) → refine: comment the change and keep it open for the remaining half, re-stating what is left. Do not close it; do not re-implement the shipped half.
- **Truncated/mangled body** (a filing defect) → the twin carries the full text; act on the twin, then close the mangled one with a pointer.
- Report the surviving count and the grouping (mechanical vs data-blocked vs pipeline) so the next pass starts scoped.

A finding that is blocked on DATA rather than code (no grounded way to backfill) is a dead end for implementation — record the reason with its evidence on the issue and stop, rather than forcing an invented value.
