# 2026-10-30 — issue #1053: the census gate's referent is the tree at the sha the doc names, not HEAD

## What was wrong

`scripts/check_architecture_census.py` counted `git ls-tree -r --name-only HEAD` and compared the
doc's `measured at <sha>` pointer's tracked count against `HEAD`'s. So the doc was only satisfiable
when it had been re-derived from the tree the gate happened to be standing in: every PR that adds a
file had to rewrite the same census block in `docs/ARCHITECTURE.md`. That hunk was the only
conflicting path between `main@369e191` and several open branches (`#932`, `#953` — `CONFLICTING`
on `docs/ARCHITECTURE.md` and nothing else), and the pointer a PR was forced to write named its own
head, which dangled as soon as the PR was squash-merged (`#1048` → `#1051` → `#1052`).

The same function checked the pointer for existence (`commit_is_real`) but never for reachability,
so a branch head that is not an ancestor of `HEAD` could satisfy it — the remaining half of #1043.

## What the change is

A census is a fact about **one commit**, so that commit is the referent:

- `measure(ref)` counts the tree at `ref`; `check()` reads the doc's `measured at <sha>` pointer and,
  when it is a real commit **and an ancestor of `HEAD`**, compares every claim with the tree at that
  sha. A file-adding branch therefore passes with the doc untouched.
- A missing pointer, a dangling sha and a non-ancestor sha each red, naming the sha and the reason.
- A stale number still reds, and now names **both** values: what the doc states and what the tree at
  the pointer states.

## Decisions

- **The ancestry check, not "must equal `main`"** — the contract is reproducibility from a tree this
  branch contains, which is `merge-base --is-ancestor`. Pinning to a remote branch would make the
  gate un-runnable in a detached checkout or before a fetch.
- **The referent is not required to be recent.** A pointer to an old ancestor whose tree matches the
  numbers is a true census; keeping it fresh is the docs lane's refresh (#1046/#1047), not this gate.
- **Every claim is compared at the pointer's tree**, including `tracked`. Comparing any one count at
  `HEAD` would reintroduce the per-PR churn for that one number.

Measured (2026-10-30, `main@369e191`, doc pointer `450981f`): 2002 tracked; `data/` 9, `skills/` 17,
`containers/` 57, `tests/` 202, `scripts/` 121, `openspec/` 1034, `agent-wiki/` 245, `docs/` 252;
`tests/test_*.py` 172; openspec changes 265. The doc's numbers were correct for `450981f`; only the
referent they were checked against was wrong.

`make test-unit`: 15026 passed; the only two reds on the first run were the two fixtures that assert
`CHANGES.md` links every `agent-wiki/` note, cured by `make changes-index` (the rendered index is a
committed file the suite compares, so this change renders it too).

Issue: #1053, #1043
