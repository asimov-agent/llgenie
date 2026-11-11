# Verifying that a delegated PR does what its issue asked

A lane reporting "DELIVERED" proves a branch exists, not that the branch satisfies the ask.
Read the artifact at the PR head and check the criterion on the *merged* tip. The checks below
are the ones a green gate set cannot make for you.

## 1. "I added a CI gate" → prove it is a gate, not a standalone target

A `make check-X` target that no workflow job invokes blocks nothing: it runs only when a human
types it. Verify all three at the PR head, in this order:

1. The script exists and fails on the shape it targets: `git show <head>:scripts/check_X.py`.
2. The target is *called* by an existing CI recipe: `git show <head>:Makefile` and look at the
   job's recipe body for the literal `$(MAKE) check-X` / `python3 scripts/check_X.py` line, e.g.
   `ci-lint:` running `lint` **and** `check-X`.
3. That job runs on every PR and is in the required-check set, not only on a schedule or a
   manual dispatch.

The commit subject ("wired into ci-lint") is a claim; the recipe line is the evidence. A gate
that only appears in `README`/`CHANGES.md`, or a Makefile target with no caller, is not wired.

## 2. Read the implementation at the PR head, never the planner's primary clone

The primary clone is owner-mediated and routinely tens of commits behind `origin/main`, so a
missing `grep` there reads as "the lane never wrote it" when it is pure drift. Use
`git show <head-sha>:<path>` / `git show <merge-commit>:<path>` for every content claim, and
`gh api repos/.../pulls/<n>/files` for the file set, so a measurement carries the sha it was made at.

## 3. Prove the gate's behaviour, not its test's name

Run the new check against a synthetic fixture of the exact shape it exists to catch (a 0-byte
*added* file must red; a `.gitkeep`-style sentinel must pass) with
`python3 scripts/check_X.py check --base origin/main`. A unit test named
`test_rejects_empty_file` is a claim until you watch it fail the fixture.

## 4. `closes #N` auto-closes the issue — post the evidence with `gh issue comment`

When the PR body carries `closes #N`, the merge closes the issue for you. `gh issue close <n>`
then prints `! … is already closed` (exit 0) and your verification/evidence body may never post.
Post the post-merge verification with `gh issue comment <n> --body-file <tmp>` and **assert the
returned comment URL** — that URL, not the exit code, is the proof the evidence landed.

## 5. Confirm the acceptance criterion on the merged tip

After the merge, measure on `main` at the merge commit, not on the PR head: a removal asks
`git show <mergeCommit>:<path>` → *not present*; an addition asks the gate is live in the
required-check set on `main`. If it does not hold, file a new issue naming the merged PR, the
merge-commit sha and the failing criterion — never reopen a merged PR.

## 6. Post multi-line comment bodies from a file

Inline bodies with backticks, `$()` or quotes get mangled or break the shell. Write the body to
a temp file once and use `gh issue comment <n> --body-file <tmp>` (and `gh pr comment` likewise)
every time.
