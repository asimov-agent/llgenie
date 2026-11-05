# Engine-skill-gap decisions are coupled to the committed store

`make check-engine-skill-gap` (`scripts/engine_skill_gap.py`) compares the **committed** registry's
top-level `engines` block (`data/models.json`) against the skills tree and
`data/unsupported-engines.json`. Two facts follow, and both bite an implementer who tries to
"decide the new engines" as a standalone PR:

1. `gap()` builds `stale = [n for n in decisions if n in shipped_names or n not in reg_engines]`.
   A decision entry whose engine is **absent from the committed registry** is reported `stale`
   ("the registry no longer names it") and `check()` appends it to `errors` → **rc=1**. So adding a
   dated decision for an engine the committed `data/models.json` does not yet name makes the
   committed-tree gate RED, not green.
2. The gate is hermetic on the committed store — it never reads the live upstream store. CI runs on
   the committed tree, so a green-against-live measurement is irrelevant to whether the PR passes.

## The rule

A decision for an engine that is not yet in the committed registry **cannot ship in a decision-only
PR** — it must land in the SAME PR as the store update that names the engine. That is the pattern the
repo already uses: predecessor engine decisions landed together with the store snapshot that
introduced those engines. The correct vehicle is the registry-sync's store PR (store + decisions +
re-rendered `data/engine-skill-gap.json` in one commit), or a scoped re-dispatch that also lands the
store — never a standalone "add engine decisions" branch.

## How CI surfaces it (so you do not re-measure the red)

The red lands at `linux/unit`, on exactly two hermetic tests — both fail with
`decision for 'X' is stale — the registry no longer names it`:
`tests/test_engine_skill_gap.py::test_the_real_files_are_current_and_the_gate_agrees_with_the_gap`
and `::test_a_new_unskilled_engine_fails_the_gate_and_a_dated_decision_silences_it`. Every other CI
job (holds, ci-scope, ci-lint, check-docs, check-pr-closing) can be green at that head — the unit red
is the coupling and no decisions-only edit clears it. Author the decisions on the branch, keep those
other gates green, and route the branch to the store-sync vehicle rather than probing
`ci-images`/buildx or re-running jobs.

## Procedure when dispatched to "decide the engines a new store names"

1. Read the committed registry's engine set: `python3 -c "import json;print(len(json.load(open('data/models.json'))['engines']))"`
   and list the ids. This — not the live store — is what the gate and CI judge.
2. For each engine the issue names, check membership in that committed set. If ALL named engines are
   already present and decided, the scope is a measured no-op (see `references/measure-scope.md`).
3. Fetch the LIVE upstream store the next sync will download (`git ls-remote` / raw file at the
   upstream branch) and diff its `engines` keys against the committed set. Engines that appear ONLY
   in the live store are the NEXT sync's business — they cannot be decided ahead of the store.
4. Confirm by swapping the live store into a throwaway worktree and running
   `make check-engine-skill-gap`: rc=1 with `unresolved <n>` proves the live store still has undecided
   engines, but that is not shippable standalone. Confirm the committed tree is rc=0.
5. Report the split: the issue's listed engines are done on the committed store; any engines unique
   to the live store belong to the sync PR. Do not open a decision-only PR for them.

## Trailing newline

When you do write `data/*.json` (store or decisions), end the file with `\n` — `json.dump` does not
append one, and `make lint` reds `files missing a trailing newline` (part of `ci-scope`) on a file
whose content is otherwise correct.
