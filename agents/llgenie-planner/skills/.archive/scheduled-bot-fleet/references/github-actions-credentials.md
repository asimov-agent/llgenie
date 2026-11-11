# GitHub Actions credentials and triggers: the two silent no-ops

A bot job that "succeeds" while doing nothing is almost always one of these two. Both render as a
green run and an untouched PR.

## A fork `pull_request` run receives NO repository secrets

Mechanism: GitHub withholds `secrets.*` from a `pull_request` run whose head is a fork. The name still
exists in the step env, so it renders **empty** — `GH_TOKEN:` with nothing after it — while
`GITHUB_TOKEN: ***` renders masked because it is always present (read-only on a fork run). The script
then calls the API unprivileged, gets a refusal or a readable-but-unwritable state, and exits 0 having
decided to "defer".

Diagnosis — read the step's own env block, never the conclusion:

```bash
gh run view <run-id> --repo <owner/repo> --log --job <job-id> \
  | sed -n '/<step name>/,/##\[endgroup\]/p'
```

An empty `NAME:` line is the finding. If several secrets are empty at once (`HF_TOKEN`, `GH_TOKEN`, a
provider key), that is the fork rule, not a missing repository secret: the same names work on a push
run.

Fix shapes, in preference order:

1. **Move the privileged step to a `workflow_run` workflow** — it executes in the BASE repository with
the BASE repository's secrets.
   ```yaml
   on:
     workflow_run:
       workflows: ["CI"]      # must name an existing workflow file's `name:` or it never fires
       types: [completed]
   jobs:
     merge:
       if: >-
         github.event.workflow_run.event == 'pull_request' &&
         github.event.workflow_run.conclusion == 'success'
   ```
   `conclusion == 'success'` replaces a `needs:` list: it means every job of that run passed.
   Check out `github.event.repository.default_branch`, never the PR head — the job holds a write token,
   so PR code must never execute here.
   Resolve the PR from the finished run, because the payload's `pull_requests` array is often empty for
   fork heads:
   ```bash
   gh api "repos/$REPO/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number // empty'
   # fallback
   gh pr list --repo "$REPO" --head "$HEAD_OWNER:$HEAD_BRANCH" --state open --json number --jq '.[0].number'
   ```
   Fail loudly when both come back empty: a green PR with no resolvable number must not be dropped.
   Caveat: a `workflow_run` trigger only starts firing once the workflow file exists on the DEFAULT
   branch, so the first run after the change is a base-branch run.
2. `pull_request_target` — base secrets, but it runs against the base ref and is a well-known
   privilege-escalation footgun; only when the job is merge/metadata-only and never checks out the head.

## A PR opened with `GITHUB_TOKEN` starts NO workflows

Mechanism: GitHub's anti-recursion rule — an object created with the job token triggers nothing. The PR
arrives with **zero checks**, so no required check can ever report, `mergeStateStatus` stays `BLOCKED`
forever, and every merge gate defers. It also blocks the bot that opened it, if that bot refuses to
publish while one of its PRs is open.

Diagnosis — an empty check list means NO RUN EXISTED, which is a token/trigger bug, not a merge bug:

```bash
gh pr checks <n> --repo <owner/repo>    # "no checks reported on the '<branch>' branch"
gh pr view <n> --json author,headRepositoryOwner,mergeStateStatus,reviewDecision
# author=app/github-actions is the tell
```

Fix: open every PR with a PAT (`secrets.BUMP_TOKEN`-style), and split the token per WRITE when one step
needs two capabilities — an issue write on the scoped job token, the PR create on the PAT:

- pass the second token under its OWN env name (e.g. `PR_TOKEN`), never by overwriting `GH_TOKEN`;
- give the script a per-call token (`_gh(..., token=...)` building `env={**os.environ, "GH_TOKEN": token}`),
  so the issue call and the PR call authenticate differently;
- an empty value falls back to the inherited token for a local run AND prints on stderr that the PR will
trigger no CI — silence here is the bug being reintroduced.

Audit, don't spot-fix: grep every workflow that opens a PR.

```bash
grep -ln "gh pr create" .github/workflows/*.yml
```

## A gate that cannot act must say so — and must not exit 0

- **A missing credential is a red run naming itself** (`exit 2`, plus a workflow step that exits
  non-zero when the secret is empty before any checkout). A run that cannot merge must never look like
  a run that chose not to.
- **A deferral belongs on the PR, not only in the log.** Post ONE comment per head SHA with a marker
  (`<!-- auto-merge: deferred <sha> -->`) carrying the state, the reason, and what would unblock it;
  re-post only when the head moves. Reading the existing comments and skipping on the marker is what
  keeps it from spamming.
- **Expose the same verdict read-only** as its own target (`make <thing>-explain PR=<n> REPO=<r>`)
  printing state, mergeability, merge state, review decision, author and a one-line verdict. It turns
  "why is this not merged?" into one command instead of a run-log hunt.

## Approving a PR a bot must not be able to approve

GitHub refuses a self-approval, so a bot approval only works when the token's account differs from the
PR author's. Compare `gh api user --jq .login` against the PR's author login; on a match, defer naming
the self-approval rule instead of trying. Approve only the one procedural state (mergeable + `BLOCKED` +
`REVIEW_REQUIRED`) and only for an author on the repo's allowlist — never for a stranger's fork, and
never for `DIRTY`/`BEHIND`.

## A `workflow_run` fires for ANY fork

The job `if:` that used to reject third-party heads is gone once the merge moves out of `ci.yml`, so the
trust check must live in the decision: head repository owner must be the base owner or an explicitly
trusted fork owner, else defer naming the head.
