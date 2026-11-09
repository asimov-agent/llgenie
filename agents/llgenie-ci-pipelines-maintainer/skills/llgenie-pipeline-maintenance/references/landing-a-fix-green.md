# Landing a fix PR green in llgenie

Ordered procedure for taking an owned gate/workflow fix from branch to green rollup, plus the attribution traps that make a green look red.

## 1. Cut from live upstream, not a stale local ref

`git fetch upstream main` and branch from the sha you fetched *in that moment*. A worktree whose `origin` is the user's fork has a **fork** `origin/main` that lags upstream — `bot_preflight.py` and `check-pr-base` both read that local ref and will emit the wrong base sha. Cite the base sha you fetched, never one quoted in chat.

## 2. Rebase your own branch when main advances mid-flight

`check-pr-base` reds when `main` moves after your branch cut (a squash-merge landed in between). The remedy is a rebase of **your own** branch onto live `upstream/main` and a re-verify — not a new BASE line. After rebasing, confirm `git merge-base HEAD origin/main == origin/main` and that the branch is exactly one commit. (Rebasing *someone else's* PR is `llgenie-pr-merge-conflict`'s job, never this lane's.)

## 3. Trailing newline on every docs fragment

`make ci-lint` reds `Missing trailing newline` on `docs/changes.d/*.md` written by `write_file` — the tool normalises away the final blank. After writing or patching any docs fragment, guarantee exactly one `\n` at EOF (`printf '\n' >>` only when absent; verify with `tail -c1 file | xxd`) and re-run lint. This is a recurring class, so check it before pushing every docs-bearing commit rather than after the red.

## 4. AGENTS line = the AGENTS.md *blob* citation

The established citation is `<AGENTS.md blob sha> <lines>b <lines>l` — the blob of `AGENTS.md` at base, matching what previously merged PRs carry. Do **not** trust `bot_preflight.py`'s emitted line inside a fork worktree: it derives from the local `origin/main` commit (see step 1), so it names a stale commit and a stale line count. Verify the blob sha with `git rev-parse origin/main:AGENTS.md` after fetching upstream, and amend the commit's `AGENTS:` line before pushing.

## 5. `holds` is fleet-wide — attribute before you believe it

`check-holds` scans **every open PR** for a `do-not-merge` whose remedy proof does not bind to its current head. So a `holds` FAILURE can land on *your* PR's rollup while naming *someone else's* PR. Read the log (`gh run view --log --job <id> | grep check-holds`) and parse the `FAIL <pr>` line:

- `FAIL` names **your** PR → your hold/label is the defect; fix or remove it here.
- `FAIL` names **another** PR → report it (`message_agent` to `llgenie-planner` with that PR, its owner from `gh pr view <n> --json author,headRefName`, the proving run id and current head) and route it to that lane. Never re-run or re-push another lane's branch, and never treat it as your red. Your own gates (guard/scope) can be fully green while `holds` stays red for this reason.

## 6. Prove the mechanism in the real job log, not the badge

A green check-run proves the gate passed, not that your new code path executed. Grep the failing/succeeding job's log for the evidence the change exists: the new env/step names, the command actually invoked, and the gate's own OK line. A cancelled run reads `fail`; a job that never loads has zero jobs and a clean-looking rollup. Report from the log.

## 7. Shape changes have a spelling — sweep the suite first

Before pushing a workflow edit, grep `tests/` for assertions on the shape you removed (an event-snapshot expression, an inline command, a `run.status` field, a `##` help line). Workflow-reading tests (`test_check_pr_closing.py`, `test_workflows_valid.py`, `test_ci_scope.py`, `test_pin_actions.py`) red on shapes they encode. Run them all at the final head before reporting green.

## 8. When the live PR head advanced past your worktree, reset to the live head

Your worktree's `HEAD` is not the PR's head. Before re-applying a fix, read
`gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` and compare with `git rev-parse HEAD`. If the
remote is ahead (a second commit landed on the branch — a change-dir scaffold, or another lane's
rebase), `git reset --soft` onto that head **conflates** your staged tree with the remote tree and
stages deletions of files that exist on the live head. Deterministic path instead:

```bash
git fetch origin <branch>
git reset --hard origin/<branch>     # or the exact sha from pulls/<n>.head.sha
# re-apply the single hunk with patch/write_file, re-run the local gate (rc=0), then:
git commit -am "..." && git push origin <branch>   # additive, no force needed
```

Pushing additively on top of the live head avoids `--force-with-lease` and the destructive
`cancel-in-progress` race entirely — and the push re-fires CI at a new head, so poll the run at
that head, not the one you were watching.
