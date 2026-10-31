# census-git-failure-diagnostic — proposal

Issue: [#1141](https://github.com/asimov-agent/llgenie/issues/1141)

## Why

`scripts/check_architecture_census.py` cannot tell *"git is unreadable"* from *"the document names
a bad commit"* — and it always reports the second. When the gate's own `_git()` call cannot run (no
repository at all, a `.git` file pointing at an unmounted bare repo from a container's partial
mount, `dubious ownership`, or a missing `git`), the non-zero return code is indistinguishable from
`cat-file` saying the sha genuinely does not resolve, so the failure is rendered as an accusation
against the document: "the doc's pointer `…` is not a real commit (dangling from an amend?)".

The issue carries two reproductions. **A.** A bare copy of `scripts/` + `docs/ARCHITECTURE.md`
with no repository at all: a real commit that IS an ancestor of `HEAD` is reported as "not a real
commit (dangling from an amend?)" and the gate exits 1. **B.** A worktree mounted alone into a
container: a worktree's `.git` is a file pointing at `<repo>/.git/worktrees/<name>`, and without the
bare repo every git call fails `fatal: not a git repository: …` — rendered as the same "not a real
commit" message. In both cases the reader is sent to re-cut the census (a document they must not
edit, on a gate that is actually green) when the real fix is their checkout.

This is the same invariant class the repo has been fixing all week: a check whose failure message
describes a different cause than the one that occurred. `check-docs` runs this gate in `ci-unit`,
so a lane verifying from a partial mount gets a red that names a document they must not edit.

## What Changes

- **`check()` first probes whether git can read the checkout.** A `git rev-parse --git-dir` call in
  `REPO_ROOT` is the probe: if it fails (non-zero), or its invocation itself raises (git missing),
  or its stderr names a git-environment failure (`not a git repository`, `dubious ownership`), the
  gate emits a distinct finding — `UNREADABLE: … the census was NOT checked …` naming the checkout /
  git as the failing side — and exits **2** (distinct from `1` = a real census defect, and from
  `0` = OK). The distinction is made from the git call's own failure, NOT by guessing at the
  document.
- **The old message survives only for a genuinely bad pointer.** When git runs and the sha truly
  does not resolve, today's `measured-at: … is not a real commit` finding and exit 1 are kept. The
  "(dangling from an amend?)" speculation is dropped — it is a guess offered when git has run and
  the object is simply absent, which is the exact case where offering a *reason* is safe but the
  specific "amend" guess is not supported.
- **The exit code stays non-zero either way**, so a check that cannot run never reads as clean.
- **Exit codes are documented** in the module docstring and asserted by tests (each built in
  `tmp_path`), so a caller can tell "my checkout is unreadable" from "the census is wrong".

## Benefit

A lane that runs `check-docs` from a container with a partial mount gets a red that names its own
checkout ("run this from a full clone or mount the whole repository") — a fixable difference — not
a document it must not edit on a gate that is actually green. The exit code now tells the caller
*which* side failed. A real bad pointer still fails with the old message and exit 1.

## Not covered

None.

## Technical

- `scripts/check_architecture_census.py`: a `git_unreadable()` probe (a `git rev-parse --git-dir`
  run in `REPO_ROOT` whose failure marks an unreadable checkout), called first from `check()`; on
  git-environment failure emit the `UNREADABLE` finding and exit 2. The dangling-pointer message
  drops the "(dangling from an amend?)" clause. Exit codes documented in the module docstring.
- `tests/test_architecture_census.py` (the census-gate test file — updated in place, not new): one
  test per control in `tmp_path` — (1) an unreadable checkout → exit 2 and `UNREADABLE`, naming git
  not the document; (2) a full clone with matching census → exit 0 and `OK`; (3) a genuinely bad
  pointer in a readable repo → exit 1 and the old `not a real commit` message. The module's only
  stand-in remains `REPO_ROOT`, so real git runs throughout.
- `agent-wiki/2026-10-31-census-git-failure-diagnostic.md` + `docs/changes.d/<stem>.md`.
- Gates: `make test-unit`, `make check-architecture-census`, `make check-docs`,
  `make openspec-validate NAME=census-git-failure-diagnostic`.
