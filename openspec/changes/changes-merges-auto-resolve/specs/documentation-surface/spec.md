## ADDED Requirements

### Requirement: a merge-time resolution helper for the rendered index

`scripts/changes_index.py` MUST provide a `resolve` subcommand (wired as `make changes-resolve`)
that repairs a conflicted `CHANGES.md` by taking a base's version and re-rendering from the merged
fragments: `git checkout <base> -- CHANGES.md` then `write()` then `git add CHANGES.md`, with the
given `<base>` (default `origin/main`). The resolution MUST keep determinism true — after it runs
the committed table equals `render(fragments)` exactly, and the existing determinism test is
unchanged.

WHEN a human (or a lane) runs `make changes-resolve` on a merge whose only conflict is
`CHANGES.md`,
THEN the conflict is resolved in one command: the file is the base's version re-rendered from the
merged fragments, carries no conflict markers, equals the renderer's output, and is staged for the
merge to complete.

#### Scenario: a real two-commit conflict resolves to the render in one command

Given a `tmp_path` git repo with two commits that each add a fragment row for a distinct note and
each rewrite `CHANGES.md`,
When   they are merged (`git merge`) and `resolve` runs against the conflicted worktree,
Then   `CHANGES.md` carries no `<<<<<<<` conflict markers,
And    it equals the renderer's output from the merged fragments,
And    the determinism test (`test_the_real_index_renders_the_committed_changes_md`) still passes.

- **Test:** `tests/test_changes_index.py::test_resolve_repairs_a_real_two_commit_changes_md_conflict`

#### Scenario: the helper is wired and the recipe is the issue's own

Given `make changes-resolve`,
When   the Makefile and `docs/BOTS.md` are read,
Then   the target exists, is `.PHONY`, runs `changes_index.py resolve`, and `docs/BOTS.md`
documents it as the automation surface for resolving a conflicted rendered index,
And    the issue's recipe (`git checkout <base> -- CHANGES.md && make changes-index`) is exactly
what the helper runs via `git checkout` + `write`.

- **Test:** `tests/test_changes_index.py` wiring assertions in the resolve test.

## MODIFIED Requirements

### Requirement: CHANGES.md is rendered from the fragments, never hand-merged (unchanged determinism)

The determinism requirement of issue #1063/#934 (`committed == render(fragments)`) MUST be UNCHANGED
by this change. `make changes-resolve` is an additional repair path, not a relaxation: it re-renders
`CHANGES.md` from the same fragments, so after it runs determinism still holds. The existing test
`test_the_real_index_renders_the_committed_changes_md` MUST NOT be modified.

WHEN a `CHANGES.md` conflict is resolved with `make changes-resolve`,
THEN the committed table still equals the renderer's output; no row is invented, dropped, or
duplicated.

#### Scenario: resolving a conflict keeps determinism strict
Given a `tmp_path` repo whose `CHANGES.md` merge was repaired by `resolve`,
When   the determinism test `test_the_real_index_renders_the_committed_changes_md` runs on it,
Then   it passes with no change to the assertion, and the committed table equals the render.

- **Test:** the determinism assertions in `tests/test_changes_index.py`, re-run unchanged.
