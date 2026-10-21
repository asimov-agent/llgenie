# "Implemented" is measured from the tree, not from Hermes's exit code

## Why

`.github/workflows/issue-bot.yml` decides whether the run implemented anything from the agent's exit
status alone:

```yaml
set +e
make implement-issue
rc=$?
if [ "$rc" != "0" ]; then echo "implemented=false" >> "$GITHUB_OUTPUT"; else echo "implemented=true" >> "$GITHUB_OUTPUT"; fi
```

Hermes exits 0 whenever the conversation ends — including a run that reports what it did *elsewhere*
(run [39513850754](https://github.com/asimov-agent/llgenie/actions/runs/39513850754) ended 0 with
`ad266c6` "committed" inside a container worktree that was deleted with `--rm`). `implemented` therefore
means "the model stopped talking", and the one step written to catch a no-op is gated on the flag the
no-op sets:

```yaml
- name: Fail loudly when the implementation did not happen
  if: … && steps.impl.outputs.implemented != 'true'
```

It reported `skipped` on that run, the commit step staged the leftover `triage.md`, and the bot opened
PR #424 as an implementation of #407 (issue #428).

## What Changes

- **`scripts/issue_implementer.py`** — a `changed` subcommand: prints `changed=true` when the working
  tree carries a change that is not one of the bot's own run inputs (`issue.md`, `triage.md`,
  `refine-in.md`, `refine.md`, `comment.md`), `changed=false` otherwise. It reads
  `git status --porcelain --untracked-files=all` — the tree, not the process. File discovery is a
  `git`, not a heuristic, and a `git` that fails is exit 2 (a tree that cannot be read must never look
  like a green run).
- **`make issue-bot-changed`** — the target the workflow runs (no `pytest`/`git` in a workflow step).
- **`.github/workflows/issue-bot.yml`** — a `Detect what the implementation changed` step runs it; the
  push step requires `changed == 'true'`, and the loud failure fires when `rc != 0` **or**
  `changed != 'true'`. `implemented` no longer exists: the run's real outcome is `changed`.
- **`tests/test_issue_implementer.py`** — real git cases on throwaway repositories: a tree with only a
  run input is `changed=false`, a real file is `changed=true`, a `git` that cannot read the tree is exit
  2, and the workflow never derives the flag from `rc` alone (it must call the target and gate the push
  and the failure on the tree).
- **`README.md` + `agent-wiki/`** — the new target and what it measures.

## Impact

- A run that changed nothing now pushes nothing and fails loudly with the issue number, instead of
  opening a one-line PR.
- A run that changes something behaves exactly as before.
- Independent of #427: the run-input filter lives in the script, so this change is correct whether or
  not the ignore file carries `triage.md` yet (with #427 landed the filter is redundant, not wrong).
