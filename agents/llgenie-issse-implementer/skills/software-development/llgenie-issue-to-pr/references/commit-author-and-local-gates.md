# Commit author gate + where local gates actually run

Two reds that each cost a full CI cycle, both reproducible. (Note: this skill's
SKILL.md is at its 100,000-char limit, so new lessons go here as reference files —
patching SKILL.md is rejected until it is split.)

## `check-pr-authors` reds on the wrong commit identity

The `guard` / `check-pr-authors` job only accepts commits authored by an
allowlisted identity. `asimov-agent@users.noreply.github.com` (the default of many
bot tools) is **rejected**, and the job log is the only place that says so — the PR
page just shows `guard` red. Read the log before hunting a code defect:

```
gh run view <run-id> --log-failed
```

Fix with one metadata-only rewrite (content untouched, so the diff is
byte-identical):

```
git commit --amend --reset-author        # with GIT_AUTHOR_*/GIT_COMMITTER_* set to the allowlisted pair
git push --force-with-lease --force-if-includes origin <branch>
```

`--reset-author` changes the sha, so the PR head moves and CI restarts. Say so in a
comment (`<old> -> <new>`, metadata-only) so a reader does not mistake it for a
content force-push.

## Never run `docker ... pytest` by hand from a worktree

`make test-unit` (it drives `scripts/unit_tests.py`) is the honest local equivalent
of the `linux / unit` job and reproduces its verdict:

- A **bare `docker run ... pytest`** from a linked worktree fails with
  `fatal: not a git repository: <repo>/.git/worktrees/<name>` — the container sees
the worktree pointer, not a real `.git`. The fallout looks like dozens of unrelated
  `test_engine_bump.py` / `upstream lookup failed` failures. Harness artifact, not
  your change.
- A **standalone clone** (`git clone --shared`) fixes the git pointer but lacks the
  gitignored generated artifacts the worktree carries, producing tens of collection
  errors at low percentages.

Use `make test-unit` in the worktree.

## Reading a run that is still in progress

`gh api ...runs/<id> --jq '.conclusion'` returns an **empty string** (not `null`,
not an error) while the run is unfinished — empty means "still running". Job
`select(.name==...)` filters can also return empty on name mismatch. Poll a plain
`{status,conclusion}` object from a bounded background watcher instead of blocking.
