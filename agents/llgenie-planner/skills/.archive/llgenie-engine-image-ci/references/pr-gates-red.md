# Why a llgenie PR is red, and what each red means

Work through this list before calling anything a flake. Most reds on a llgenie PR are structural
contracts the change itself broke, and each one names its own fix.

## First: read the actual job, not the check name

```bash
gh pr checks <n> --repo asimov-agent/llgenie --json name,state,link
# per-job log, ANSI stripped (gh run view --log-failed is EMPTY for some failures)
gh api repos/asimov-agent/llgenie/actions/jobs/<job-id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -nE 'FAILED|AssertionError|LINT|error:' | tail -20
```

Reproduce locally in the same image CI uses, never a host venv:

```bash
docker run --rm -v "$PWD":/repo:rw -w /repo llgenie/test:latest python -m pytest tests/test_x.py -q
```

## Adding `workflow_dispatch` costs a guard job

A workflow with `workflow_dispatch` MUST carry the byte-identical owner/collaborator guard job
(`github.actor` AND `github.triggering_actor`, `admin|maintain|write`, before any secret is read).
Adding it to a previously scheduled-only workflow turns the unit suite red in `test_workflow_guards`
(4 cases), `test_dispatch_forms` (2) and `test_issue_bot_manual_pick`. For a leg a human rarely needs
to trigger, keep the schedule alone and let the make target be the manual path — a bot whose only job
is to merge should not grow a twelfth guard site.

A dispatchable workflow header also needs the `# Trigger surface:`, `# Flow:` and `# Never:` lines, and
a header that names a clock time must match a literal cron field: for `37 */6 * * *` write
"every six hours at :37", never "00:37, 06:37, 12:37, 18:37" (the checker resolves `*/6` as no literal
hour and fails).

## The README dispatch table is generated

```bash
docker run --rm -v "$PWD":/repo:rw -w /repo llgenie/test:latest \
  python scripts/check_dispatch_forms.py report      # pipe the block over the table in README.md
```

The `report` argument on the make target is not wired (it runs `check`, which fails). Paste the whole
generated block, header row included, over the existing table.

## New make targets

A target with a `##` help line must be named in `README.md` (`make check-docs`), every helper must be in
`.PHONY:` (`make check-wiring`), and a script only earns its keep when a CI-called target runs it.

## Bot time budgets are arithmetic, not vibes

`timeout-minutes` must be >= rounds x (check minutes + agent minutes). Raising the attempt count
without raising the job timeout fails `test_bot_time_budget` — and in production cancels the run
mid-repair, which looks exactly like "the bot stopped working".

## Agent legs: credentials vs paths, and the unattended rule

- Only CREDENTIALS may be forwarded with `-e NAME` to the agent container; `AGENT_SHELL_KEYS` is the
  single list and `test_agent_shell_keys` fails on anything else. A path-like setting
  (`*_FILE`, `*_DIR`) must be set INSIDE the container from a make variable, e.g.
  `bash -lc 'FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh'`.
- Every `hermes -z` prompt needs the UNATTENDED rule: never ask, never wait; an open decision becomes a
  refine with its `REASON` or the safest reversible choice. Exit **3** is Hermes detaching on a
  question, not "changed nothing" — name rc=3 as its own message in the failure step, or the next reader
  chases data/keys instead of the prompt.

## Auto-merge: two identities, and a deferral nothing retries

The merge token cannot approve its own PR (GitHub refuses self-approval), so a bot-authored PR needs a
repository secret holding the OTHER identity's token for the approval. Without it the job defers with the
reason on the PR and exits 0 — by design, so it never reds a run. A deferral is therefore invisible to
retry logic: re-running the workflow is the manual fix, and the durable fix is a scheduled sweep that
re-runs the same decision for PRs whose deferral marker names their CURRENT head (a marker for an older
head is skipped). Never hand-run `gh pr merge`; drive the PR green and let CI land it.

## Changing a test that pins the bug

When the fix contradicts an existing test, the fixture is pinning the defect: change it in the same
commit and say so in the PR body ("three fixtures that pinned the old behaviour now encode the fix").
That is not loosening a test, and leaving it unstated invites a review that thinks it is.

## OpenSpec shape

Every `## ADDED Requirements` block needs at least one `#### Scenario:` with a `- **Test:**` line naming
a test that actually exists, or `make openspec-validate` fails. New task checklists start unticked and
`make openspec-tasks-check` reds the openspec job on any remaining `- [ ]`.
