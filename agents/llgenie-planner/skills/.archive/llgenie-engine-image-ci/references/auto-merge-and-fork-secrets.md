# Auto-merge, fork PRs and credentials in llgenie's CI

Why llgenie's merge job is a `workflow_run` workflow and not a job in `ci.yml`, and the
failure modes that made it one.

## The rule that explains everything

**A `pull_request` run whose head is a fork receives NO repository secrets.** GitHub withholds
them on purpose. llgenie's agent PRs are all pushed to the fork (`andyholst/llgenie`), so any job
that needs the owner PAT cannot live in a `pull_request`-triggered workflow — it runs with the
secret empty. `trending-local-llms` never hit this because its bots push branches inside the repo.

Recognise it by the job's `env` block in the log:

```
env:
  GITHUB_TOKEN: ***      # present, read-only for a fork run
  GH_TOKEN:              # EMPTY — secrets.BUMP_TOKEN resolved to nothing
```

`***` means the secret exists and was masked; an empty value means it does not exist for this
run. That distinction is the whole diagnosis, and it is invisible from `gh run view --json`.

## The shape that works

`.github/workflows/auto-merge.yml`, triggered by the finished CI run:

```yaml
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
jobs:
  merge:
    if: >-
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success'
```

- `workflow_run` executes in the **base** repository with the **base** repository's secrets, so
the PAT exists there.
- `conclusion == 'success'` is the same "every job passed" guarantee `needs:` gave, one level up.
- **Check out the base branch** (`ref: ${{ github.event.repository.default_branch }}`), never the
  PR head: the job holds a write token, so it must run trusted code only.
- Resolve the PR from the run two ways, because the payload's `pull_requests` array is often empty
  for fork runs:
  ```bash
  number=$(gh api "repos/$REPO/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number // empty')
  [ -n "$number" ] || number=$(gh pr list --repo "$REPO" --head "$OWNER:$BRANCH" --state open --json number --jq '.[0].number // empty')
  ```
  Fail loudly when both are empty — a green PR must never be silently dropped.
- The merge itself stays ONE make target (`make auto-merge PR=… REPO=… HEAD_SHA=…`) called with the
  PAT. A second hand-rolled `gh pr merge` in YAML is a defect, not a shortcut.

## A green job that merges nothing is the worst failure shape

Guard the credential as the workflow's FIRST step, before checkout:

```yaml
- name: Require the owner PAT
  env:
    BUMP_TOKEN: ${{ secrets.BUMP_TOKEN }}
  run: |
    if [ -z "$BUMP_TOKEN" ]; then
      echo "::error::secrets.BUMP_TOKEN is empty - this workflow cannot merge"
      exit 2
    fi
```

And in the decision script, exit 2 when neither `GH_TOKEN` nor `GITHUB_TOKEN` is set. A run that
cannot do its job must be red and name the missing credential; "deferred, exit 0" for a missing
token reads as a successful decision and hides the defect until somebody opens the PR.

## The trust boundary moves with the trigger

A `workflow_run` fires for **any** fork, so a job-level `if:` on
`head.repo.full_name == github.repository || head.repo.owner.login == 'andyholst'` no longer
guards anything. Put the rule where the decision is made: the merge script reads `headRepository`
from its one `gh pr view` and defers a head whose owner is neither the base repo's owner nor a
trusted fork owner. A workflow `if:` is not a security boundary once the trigger is `workflow_run`.

## Review-blocked PRs

- `mergeable: MERGEABLE` + `mergeStateStatus: BLOCKED` + `reviewDecision: REVIEW_REQUIRED` with 0
  reviews is a *procedural* block: the code is fine, GitHub wants an approving review. The
  ruleset API may show no approval rule at all (only `deletion`, `non_fast_forward`) while every
  merged PR carried an approval — do not trust the ruleset view to explain this.
- **GitHub refuses a self-approval.** A bot whose token belongs to the PR's own author cannot
  approve it; read the token's account with `gh api user --jq .login` and compare it with the PR
  author before attempting `gh pr review --approve`. Approve only with a *different* allowed
  identity, only for that exact state, only for an author on the repo's allowlist.

## Deferrals belong on the PR

A run log is not where a reviewer looks. Post ONE comment per head SHA, deduped by a marker
(`<!-- auto-merge: deferred <sha> -->`) carrying the reason and what would unblock it, and give a
read-only `make auto-merge-explain PR=… REPO=…` that prints the same verdict. "Checks green, not
merged, no explanation" is what sends someone hunting through 27 jobs.

## Verify the argv, not the intent

`make -n <target> VAR=1` prints the expanded command. Use it to prove a flag reaches the script
(`--approve-when-review-required`, `--dry`) instead of assuming the `$(if …)` expanded.

## `workflow_run` gotchas

- It only starts firing once the triggering workflow exists on the **default** branch; the first
  run after landing is the `main` push run.
- Name the workflow exactly (`workflows: ["CI"]`) and check it with `make check-workflows` — a
  `workflow_run` naming a workflow that does not exist never fires and reports no error.

## `AGENTS.md` is write-protected for the agent

A write to `AGENTS.md` triggers an interactive approval; a timeout is NOT consent and the write is
refused. Do not retry it and do not route around the refusal through `terminal`/`execute_code`.
Ship the change and put the exact proposed paragraph in the PR body for the owner to apply —
saying plainly that the rule list will not match the code until they do.
