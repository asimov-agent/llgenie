# 2026-10-31 — the census gate names the checkout when git itself failed, not the document

Issue: [#1141](https://github.com/asimov-agent/llgenie/issues/1141)

## Problem

`scripts/check_architecture_census.py` could not tell *"git is unreadable"* from *"the document
names a bad commit"* — and it always reported the second. The issue carried two reproductions:

- **A. No git repository at all** (a bare copy of `scripts/` + `docs/ARCHITECTURE.md`): a real
  commit that IS an ancestor of `HEAD` was reported as "not a real commit (dangling from an
  amend?)" and the gate exited 1.
- **B. A worktree mounted alone into a container.** A worktree's `.git` is a file pointing at
  `<repo>/.git/worktrees/<name>`; without the bare repo every git call fails `fatal: not a git
  repository: …`, rendered as the same "not a real commit" message.

In both cases the reader was sent to re-cut the census (a document they must not edit, on a gate
that is actually green) when the real fix was their checkout.

## What changed

- `check()` now first probes whether git can read the checkout — `git rev-parse --git-dir` in
  `REPO_ROOT`. If that fails (no repository, a `.git` file pointing at an unmounted bare repo,
  `dubious ownership`), returns nothing, or cannot even be invoked (git not installed), the gate
  emits `[census-gate] UNREADABLE: git could not read this checkout — …` and exits **2** — distinct
  from `1` (a real census defect) and `0` (OK). The distinction is made from the git call's own
  failure, never by guessing at the document.
- The old `measured-at: … is not a real commit` finding and exit 1 survive only for a genuinely bad
  pointer in a readable repo; the "(dangling from an amend?)" speculation was dropped.
- Exit codes are documented in the module docstring and asserted in tests.

## Verified

- `tests/test_architecture_census.py` (updated in place, not new): a new test builds a directory
  with the ARCHITECTURE doc but no repository, asserts `git_unreadable()` is true, `check()` exits 2
  and prints `UNREADABLE` naming the checkout — not `not a real commit`. The existing bad-pointer
  (`not a real commit`, exit 1) and full-clone `OK` exit-0 tests are kept and passing. All 6 tests
  pass in `llgenie/test:latest`.
- **Live reproductions**: no-repo → `UNREADABLE` exit 2; a `.git` file pointing at a nonexistent
  bare repo (reproduction B) → `UNREADABLE` exit 2; a full clone → `OK` exit 0.
- **Sabotage**: with `git_unreadable()` forced to `False`, the new test goes RED
  (`AssertionError: assert False … .git_unreadable`); restored → 6 passed.

## Status

OpenSpec change `census-git-failure-diagnostic`; branch `fix/1141-census-git-failure-diagnostic`.
Gates: `make test-unit`, `make check-architecture-census`, `make check-docs`,
`make openspec-validate NAME=census-git-failure-diagnostic`.
