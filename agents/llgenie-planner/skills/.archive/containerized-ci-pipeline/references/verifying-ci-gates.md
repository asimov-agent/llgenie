# Verifying a CI gate is genuinely green (or red)

Three ways a gate can look green while proving nothing, and how to check each.

## 1. A generated artifact that every change regenerates races under merges

When a tracked file is GENERATED and every change regenerates it against its OWN base
(an index like `OPENSPEC.md`, a README, a registry), a PR's `validate` can pass while the
MERGE result is stale: another change that also touches the file merged after the branch
was cut, so the branch's regenerated copy is missing that change's row — or, more often,
carries EVERY row and only a stale AGGREGATE line. Two branches regenerating the same file
from one base write the SAME count line (`Active changes: **N**`), and git merges the
differing ROW lines while the identical aggregate line collapses to one value, so the merged
tree holds N+1 rows under a count of N. Do not go hunting for a missing row: read the
check's own message, which names the drift (`count line says N, disk needs N+1`), and repair
by regenerating on the merged tree — a one-line diff, not a re-derivation. The gate then
re-reds `validate` for every subsequent PR until someone regenerates again — a loop that
repeats on every merge.

- **The `pull_request` merge-ref checkout is the TRAP, not the fix.** A clean
  `actions/checkout` on a `pull_request` event checks out the MERGE COMMIT by default, so
  a gate that compares a generated file against the tree (e.g. `make openspec-check` on
  `OPENSPEC.md`) compares the branch's regenerated copy against a tree carrying EVERY
  OTHER open change. The result: every open PR goes red with the SAME wording
  (`[openspec-index] FAIL … (N active, 0 archived on disk)`) whenever a sibling merges
  first, and the "repair" — merge the base and regenerate by hand — is invalidated by the
  next merge. With several PRs open, none of them can ever go green. Fix the WORKFLOW, not
  each branch: in the `validate` job check out the PR's own tree
  (`ref: ${{ github.event.pull_request.head.sha || github.sha }}`), so a generated file is
  compared with the tree that produced it. `master`'s own index is still verified by the
  same pipeline's `push` run (where `github.sha` IS the merge result), and `auto-merge`'s
  `--match-head-commit` means what merges is exactly what was checked. Keep `fetch-depth: 0`
  so the authorship guard still has the base ref.
- **When several PRs go red with the SAME error, suspect a systemic workflow defect, not N
  independent branch problems.** Same wording across runs = the gate is comparing against
  the wrong tree (or a shared image is stale), so fix the class once and add a guard that
  asserts the checkout `ref` expression — then re-base + regenerate the affected branches
  as a stopgap, knowing the next merge would have re-red them.
- To check the CURRENT state of `master` locally, run the check against `origin/master`
(`git reset --hard origin/master` then the check), never against your local `master`
which may be stale — a local fetch of `master` can silently lag the remote tip.
- When the drift is a single generated line, the check should NAME the drift ("count line
says 35, disk needs 36") rather than blame the rows — a generic "rows changed" message
sends a maintainer hunting for a row diff that does not exist.
- A recurring race like this is a SYSTEMIC gap, not a one-off: file it as its own tracked
issue (via `make file-findings`) so the durable fix (the head-SHA checkout) has a home,
instead of regenerating by hand each time.

## 2. Reading validator/test logs: count real failures, not `FAIL` lines

Validators emit EXPECTED negative-case output — lines containing `FAIL:` are the
validator's own demonstration that a bad fixture is caught, not test failures. So
`grep -c FAIL` over a full log massively over-counts and misleads.

- Count real failures with the process exit code, the pytest summary line, or
`grep -c "FAILED [1-9]"` (pytest's per-test failure marker) — never a raw `FAIL` grep.
- A background job's notification `exit code 1` may be the exit of the LAST command in
  the pipeline (e.g. `grep` returning 1 because it found nothing) — read the command that
  produced it, not the number alone.
- **A long suite you re-ran after a fix makes the PREVIOUS run's notification STALE.** A
  `make test`-style job started before the fix can complete minutes later and report the
  old failure with exit 1, long after the corrected run went green. Check the run's start
  time / the commit it tested against before diagnosing: a notification is about the run
  you launched THEN, not about the tree you have NOW.
- **A `_validate-*` make target runs the validator AND a chain of test files after it.**
When `_validate-mapped`/`_validate-search` exits non-zero but the validator prints
`QA PASSED`, the failure is downstream in the `python3 tests/test_*.py && …` chain the
recipe appends — read the tail of that chain (which test, which assertion) before
touching the validator. The usual trigger is a make-target recipe change: a test that
asserts the old recipe text fails here (update it in the same change, rule 6b).

## 3. Proving a guard is real: dispatch the bot and read its own log

A green pipeline run is not verification that a check ran. A check that is SKIPPED at
runtime (e.g. one that needs a credential the run's token cannot have) leaves the run
green while a third of the checks never execute.

- To prove a guard/check is real, dispatch the bot on `master` and read ITS OWN log for
`SKIPPED` / `WARNING` / `refused` lines — a green run that prints "check skipped" is a
false green.
- When a check can only run with a credential the default token cannot have, either grant
the token the scope or make the skipped check FAIL LOUDLY (leave the bot red) — a check
that silently skips on every production run is dead code.

## 4. Protected instruction files need live approval

Edits to a protected instruction file (e.g. `AGENTS.md`) require the user's live approval.
If the approval prompt TIMES OUT, that is NO consent — do not retry the edit and do not
route the same change through `terminal`/`sed` to bypass the guard. Abort the operation
(rebase/merge) to leave the tree clean and report that the approval is needed.

## 5. A step that captures `make` stdout, and a stub that ignores argv, both hide a broken step behind a green test

- **A workflow step that captures `make <target>` stdout breaks when the recipe echoes its own command line.** `make` prints the recipe to stdout before running it, so `make issue-verdict | tee /dev/stderr >> "$GITHUB_OUTPUT"` writes `python3 scripts/issue_verdict.py --issue 266` into `$GITHUB_OUTPUT` (dies with `Invalid format`, not `key=value`) and `{ make refresh-run-block; ... } > "$PR_BODY"` puts the command on the PR body's first line (violates "body LEADS with the block"). Prefix the recipe with `@` so make does not echo, and add a test asserting the target's stdout is ONLY the composer's output — run it with a stub `gh` on PATH and assert the first stdout line is the marker, not a command.
- **A stub CLI on PATH must enforce the argv contract, not just return canned output.** A `gh` stub that ignores its argv lets a wrong subcommand pass — `gh repos/...` (missing the `api` subcommand) returned the fixture and the test stayed green while the real `gh` died with `unknown command`. Assert the subcommand/args the step is expected to send, so a malformed invocation goes red.
