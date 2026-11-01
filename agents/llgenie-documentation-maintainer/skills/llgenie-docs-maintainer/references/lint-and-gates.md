# Lint + PR gates: sharp edges

## `scripts/lint_linefeeds.py` lints the SCRIPT's repo, not your worktree

`_repo_root()` is `parent.parent` **of the script file**. Running the script by absolute path from a
`/tmp` worktree lints the *main clone* and can return rc=0 while the branch tree actually fails — a
false pass that cost hours of chasing a phantom green. Always run it from inside the target worktree
(`cd <wt> && make lint`, or via that worktree's own `scripts/` path), never by absolute path from
elsewhere.

`make ci-lint` == `make lint` == this script. Two rules: **trailing newline** required on every
tracked text file, and **a markdown heading must be preceded by a blank line** — a `## Foo` glued to
the last line of a list is the recurring red (flag names the line number).

## Gate semantics that red a fold PR's `scope` / `guard` job

- **check-docs (#1123) change→note:** a changed surface under `agents/.../skills/` owes an
  `agent-wiki/` note **in the branch diff** — the note merely *existing in `main`* is not enough. A
  ref-only corrective fold must amend the existing note (or add a row) so the diff carries an
  `agent-wiki/` change.
- **check-pr-closing (#1329):** an `agent/*` PR needs an adjacent `closes #N` in the squash commit
  **and** the PR body. A stale base that predates a `main` move re-trips it — rebase onto current
  `main` fixes it.

## Scope job matrix

The `scope` check runs a matrix; a single sub-step doing `make ci-lint` or `make check-docs` can
fail while the others pass. Read the sub-job log that names the file/line, not the summary status.
