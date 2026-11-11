# CI workflow triggers: which workflow acts on a red PR, and how to make it manual-only

Use when the owner says a bot/workflow "fires when a PR turns red" and wants it (or its issue-filing /
auto-repair) disabled or made manual-start. The job splits into two: **pin the exact workflow** (evidence,
not guesswork), then **file + dispatch** the manual-only change to the owning lane (workflows/gates →
`llgenie-ci-pipelines-maintainer`). You never edit the workflow yourself.

## 1 · Classify every workflow's trigger surface (measure, don't assume)

```bash
cd "$HOME/repository/git/llgenie"
# auto vs manual per file — read origin/main, never a stale working tree
git show origin/main:.github/workflows/<file>.yml | grep -nE '^\s{2}(schedule|push|pull_request|workflow_run|workflow_dispatch|issues|issue_comment):|cron:|types:'
```

An **auto** trigger is any of `schedule` / `push` / `pull_request` / `workflow_run` / `issues`. A file whose
`on:` block carries only `workflow_dispatch` is already manual. `grep -c 'workflow_dispatch'` tells you
whether a manual start is currently *possible* — a workflow that reacts to a red run usually has **none** (its
header may say "a reaction, not an action — carries no workflow_dispatch"), so "make it manual" first requires
**adding** the trigger.

## 2 · Pin the offender by behaviour, not by name

The red-PR automation class splits into two distinct arms — grep the header/decide block for which one a file is:

| behaviour | tell in the file | typical example |
|---|---|---|
| **files a NEW issue** on a failed run | `workflow_run: [completed]` + `issues: write` + `gh issue create` / "file ONE marker-deduped issue labelled with the owning lane" | `run-failure-reactor.yml` |
| **auto-repairs** a red branch | `schedule` + `workflow_run:[completed]` running a fix loop | `fix-bot.yml` |

A request to "disable the issue bot on red" often touches **both** — the reactor files the issue and the
fixer repairs the branch. Ask which arm(s) the owner means, and if the ask is broad ("disable that, manual
start") treat both as in scope; name the scope boundary explicitly in the issue.

## 3 · File the manual-only change (six/seven-section issue)

Body shape: Problem (quote the owner's directive verbatim — it is the only durable citation) · Why it
matters · How we fix it · Benefit · Acceptance criteria · Not covered · Technical.

- **Targets, per file:** remove the non-`workflow_dispatch` triggers (`schedule:`, `workflow_run:[completed]`),
  and **add** a `workflow_dispatch` input (e.g. `run_id`) to any workflow that had none, so the owner can start
  it by hand.
- **Enforcement AC = a negative control, not a declaration.** "Re-adding a `schedule`/`push`/`workflow_run`
  trigger to either file fails `make check-workflows`" — so manual-only is *measured*. Both
  `make check-workflows` and `make check-wiring` must stay green after the edit. (A `workflow_run` with no
  `workflows:` list is refused by GitHub and reds `check-workflows` — removing the trigger also clears that.)
- **Scope boundary:** name what is NOT covered (e.g. label→implement / refine / dedupe schedule bots are not
  red-triggered issue *creation*; the planner's kanban red-PR delegation is unaffected — this disables the CI
  workflow, not the delegation).
- **Stale header note:** a workflow header that claims "deliberately NO workflow_run" while its `on:` block has
  one is a real defect — note it as part of making the header true.

## 4 · Dispatch to the owning lane (kanban card + on-issue record)

Workflows / gates / make targets are the `llgenie-ci-pipelines-maintainer` lane (host-lane precedence). Dispatch
via a kanban card when the tick toolset has no `message_agent`:

```bash
hermes kanban create "#<id> ci: make <workflow> manual-only" \
  --assignee llgenie-ci-pipelines-maintainer \
  --body-file ~/.hermes/profiles/llgenie-planner/cache/scratch/brief_<id>.md --json
```

Brief must carry: exact files + the trigger edits, the `make check-workflows` negative control, fresh
`origin/main` sha + AGENTS.md `Nbytes Nl` stamp, `$HOME`-not-`/home/<user>` rule, ONE ready PR closing the
issue, never merge / never arm, bookend on-issue (start + finish with head sha and gate result).

Then post the dispatch as a comment **on the issue** (durable channel a stranger can find) — not a DM. The
comment names: the task id, the two measured targets, the scope boundary, the enforcement AC, and "not merged,
not armed." Verify the issue exists on the wire (`gh issue view <n> --json ...`) before reporting it filed.
