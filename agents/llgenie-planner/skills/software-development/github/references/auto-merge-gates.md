# Letting CI merge the PR (auto-merge gates)

When a repo has an automated `auto-merge` job, the agent's job ends at a green,
reviewable PR — it never runs `gh pr merge` itself. The job merges, and every other
state is DEFERRED to a human (exit 0 with the reason printed, never a red run).
Design the gates so "green" cannot be faked, then debug deferrals from the PR's
merge state rather than from the workflow YAML.

## The gates, and the mechanism behind each

- **Every needed job must be `success`, not merely `!failure()`.** A SKIPPED job
  satisfies `!failure()`, so a condition of the form
  `always() && !failure() && !cancelled()` alone lets a PR merge when one of its
  jobs never ran. Add `needs.<job>.result == 'success'` for each need.
- **`always()` is still needed** when a push-only job sits in `needs:` or is skipped
  on a PR: without it, the dependent job is skipped too. Keep that job out of
  `needs:` where you can.
- **`mergeStateStatus == CLEAN`** is the whole "green and no merge conflicts" rule:
  `DIRTY` is a conflict, `BEHIND` is a stale branch, `BLOCKED` is a required check or
  review still pending.
- **`--match-head-commit <sha>`** pins the merge to the commit the run validated; a
  push after the run started leaves the PR open for the newer run.
- **A PAT, never the job token.** A merge made with `GITHUB_TOKEN` starts no
  workflows, so the post-merge run on the default branch (publishes, deploys) never
  happens. Read the token from a secret; keep the workflow's `permissions:` for the
  reads it does itself.
- **Post-merge closure check.** `gh pr merge` succeeds whether or not the body's
  `closes #n` bound, and GitHub parses closing keywords from prose anywhere in the
  body. Read `closingIssuesReferences` after the merge and fail naming any issue that
  is still open.
- **A human hold label** (e.g. `do-not-merge`): the escape hatch for a reviewer who is
  mid-read. Create the label on the repo (`gh label create … --color …`) or the hold is
  not real. `gh pr edit <n> --add-label do-not-merge` / `--remove-label`.

## Fork heads: the job cannot live in `pull_request` at all

**A `pull_request` run whose head is a fork receives NO repository secrets.** GitHub
withholds them by design, so a job in that workflow sees `secrets.<PAT>` as the empty
string — it reports `success` and merges nothing. A head condition accepting the fork
(`head.repo.owner.login == '<owner>'`) is necessary but NOT sufficient: it selects the
PR into a job that has no credential to act on it.

Recognise it from the job log's env block — `***` means present-and-masked, empty means
absent for this run (invisible in `gh run view --json`):

```
env:
  GITHUB_TOKEN: ***      # present, read-only for a fork run
  GH_TOKEN:              # EMPTY — the PAT secret resolved to nothing
```

Move the merge to a `workflow_run` workflow: it executes in the **base** repository
with the **base** repository's secrets.

```yaml
on:
  workflow_run:
    workflows: ["CI"]        # must match the workflow's `name:` exactly
    types: [completed]
jobs:
  merge:
    if: >-
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success'
```

- `conclusion == 'success'` is the same "every job passed" guarantee `needs:` gave, one
  level up; a push run is excluded because it has no PR to merge.
- **Check out the base branch** (`ref: ${{ github.event.repository.default_branch }}`),
  never the PR head: the job holds a write token and must run trusted code only.
- Resolve the PR from the run two ways — the payload's `pull_requests` array is EMPTY
  and the endpoint 404s for a fork run, and `--head owner:branch` matches a same-repo
  branch only, so a fork head needs the search qualifier:
  ```bash
  # gh api prints a 404's error BODY on stdout: a value is a PR number only when it is digits
  number=$(gh api "repos/$REPO/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number // empty' 2>/dev/null || true)
  case "$number" in ''|*[!0-9]*) number="" ;; esac
  [ -n "$number" ] || number=$(gh pr list --repo "$REPO" --search "head:$BRANCH" --state open \
      --json number,headRepositoryOwner \
      --jq ".[] | select(.headRepositoryOwner.login==\"$OWNER\") | .number" | head -1)
  case "$number" in ''|*[!0-9]*) number="" ;; esac
  [ -n "$number" ] || { echo "::error::no open PR for run $RUN_ID (head $OWNER:$BRANCH)"; exit 1; }
  echo "number=$number" >> "$GITHUB_OUTPUT"
  ```
  `|| true` discards the exit status, NOT the output: without the digits guard the JSON
  error body becomes `$number`, the fallback never fires, and the multi-line blob kills
  the step at `$GITHUB_OUTPUT` (`Invalid format '  "message": "Not Found",'`). Keep the
  resolution in its own script or `make` target with a test (real fake `gh` on PATH)
  rather than inline shell, and assert it writes exactly one `number=<n>` line. Fail
  loudly when nothing resolves; a green PR must never be dropped silently.
- **The trust boundary moves with the trigger.** `workflow_run` fires for ANY fork, so
  a YAML `if:` on the head repo no longer guards anything. Read `headRepository` in the
  decision (the one `gh pr view`) and defer a head whose owner is neither the base
  repo's owner nor a trusted fork owner.
- **Guard the credential as the FIRST step**, before checkout: `exit 2` (or
  `::error::`) when the secret is empty. In the decision script, exit 2 too when neither
  `GH_TOKEN` nor `GITHUB_TOKEN` is set. A run that cannot act must be red and name the
  missing credential — "deferred, exit 0" for a missing token is indistinguishable from
  a decision and hides the defect until someone opens the PR.
- A `workflow_run` only starts firing once the triggering workflow exists on the
  **default** branch, so the first run after landing is the `main` push run.

Merge a fork head **without `--delete-branch`**: the base token cannot delete a branch
in the fork, so the flag turns a successful merge into a failed run. Read
`headRepository` from the same `gh pr view` and pass the flag only when it equals the
base repo.

## Why a green PR is still not merged

Read one call before touching anything:

```bash
gh pr view <n> --repo <o>/<r> --json state,isDraft,mergeable,mergeStateStatus,reviewDecision,reviews,headRepository,headRefOid,author
```

| State | Meaning | Action |
|---|---|---|
| `CLEAN` + all needs green | the job's happy path | nothing |
| `DIRTY` / `BEHIND` | conflicts / stale | rebase the branch |
| `BLOCKED` | a required check or review is pending | see below |
| draft, moved head, untrusted fork, hold label | not this run's decision | nothing |

**The `--json` field list of THAT call is a closed set.** One field `gh pr view` does
not have (`authorAssociation` is a GraphQL field, not a `gh pr view` field) fails the
call itself — `Unknown JSON field: "authorAssociation"` — so the job dies before any
deferral is printed, and a fake `gh` in the tests accepts it silently. Validate any new
field against the real binary before shipping it; the author gate reads
`gh api repos/R/collaborators/<login>/permission` instead.

- **A merge-time job only reaches an EXISTING PR via a push.** A `pull_request` run is
  created by a push to the branch, and `gh run rerun` re-executes the *same* workflow
  definition — so a job added to the default branch after the PR's last run will not
  appear until the branch is rebased or gets a new commit. Rebase, don't re-run. The
  job list also grows as `needs:` finish, so an absent `auto-merge` entry early in a
  run proves nothing.
- **A green run with a `success` merge job and an unmerged PR is a TOKEN problem more
  often than a merge-state problem.** Before theorising about reviews, read the job
  log's env block (see Fork heads) and its printed deferral reason.
- **`BLOCKED` + `reviewDecision: REVIEW_REQUIRED` + zero reviews** is a review
  requirement no bot can satisfy *as itself*. The visible rules often do not explain
  it; check the observable settings before blaming the merge job:

  ```bash
  gh api repos/<o>/<r>/branches/<branch> -q .protected
  gh api repos/<o>/<r>/rulesets -q '.[] | "\(.id) \(.name) \(.enforcement)"'
  gh api repos/<o>/<r>/rulesets/<id> -q '[.rules[].type] | join(", ")'
  gh api repos/<o>/<r>/rules/branches/<branch>
  ```

  Report what the API shows, name the two ways out (a human approval for that PR, or
  scoping the rule so the bot account may land its own PRs), and stop — never merge by
  hand to "unblock" it.
- **Clear the review in this order: approve as the OTHER identity, then merge plainly.**
  `--admin` is not the answer (next bullets). Read the author and the token's own account
  (`gh api user --jq .login`), approve when they differ, re-read the PR, then merge the
  pinned head with a normal `gh pr merge --squash --match-head-commit`:

  ```bash
  gh pr review <n> --repo <o>/<r> --approve --body '<which job is acting, and why>'
  gh pr view <n> --repo <o>/<r> --json reviewDecision,mergeStateStatus   # APPROVED + CLEAN
  gh pr merge <n> --repo <o>/<r> --squash --match-head-commit <sha>
  ```

  Re-read after approving: the decision was written against `BLOCKED`, and the state to
  merge on is the post-approval one. A stranger's PR is never approved; a close, conflicts,
  a stale branch, a draft and a hold label are still deferred.
- **`--admin` does NOT bypass a review rule enforced for admins.** With N required
  approvals and administrators not exempt, GitHub answers `GraphQL: At least 1 approving
  review is required by reviewers with write access` however privileged the token is. Keep
  `--admin` for the one case an approval cannot cover, and when both are refused post the
  deferral comment and exit 0 — a repository setting is blocking the gate, not the script.
- **GitHub refuses a self-approval.** When the PR's author IS the merge token's account,
  no approval from that token can land: those PRs need a second identity's PAT (an optional
  secret used for the approve call only, passed through the child's environment — never
  argv — and named in whatever secret-scanner list the repo keeps). Unset must degrade to
  the deferral, not to a crash. Never fabricate an approval record.
- **The approval gate and the author gate must accept the same logins.** A job that admits
  the opener as "the repo's own bot" for the merge decision but only allows two human
  logins for the approval leaves every workflow-created PR (`app/github-actions`, `…[bot]`)
  permanently blocked — two halves of one job disagreeing. One predicate, both places.
- **A PR created with `GITHUB_TOKEN` has NO checks at all.** `gh pr checks <n>` answering
  `no checks reported on the '<branch>' branch` for a PR that exists means no
  `pull_request` run ever started (GitHub's anti-recursion rule), so a `workflow_run` merge
  gate never fires either and the PR sits `BLOCKED` forever with nothing red to read. Fix
  the CREATOR: open the PR with the owner PAT (a separate env var read by the publish path)
  while keeping the job token for `gh issue create` where the PAT may lack Issues write.
  The PR's author then becomes that PAT's account — which re-enters the self-approval case.

## Make a deferral visible on the PR

A run log is not where a reviewer looks. A deferral that exists only in CI output
produces the same question — "green, why is it not merged?" — on every run:

- post ONE comment per head SHA, deduped by a marker
  (`<!-- auto-merge: deferred <sha> -->`) carrying the reason and what would unblock
  it; re-post only when the head moves;
- ship a read-only `make auto-merge-explain PR=<n> REPO=<o>/<r>` that prints the same
  fields and verdict without merging, so the answer is one command locally.

## Test the decision without merging

Give the decision its own `make` target and a `--dry` mode that prints the fields it
read and the reason it would defer, then exercise it against the real PR:

```bash
make auto-merge PR=<n> REPO=<o>/<r> HEAD_SHA=<sha> DRY=1
```

Prove a flag actually reaches the script with `make -n <target> VAR=1` (the expanded
argv, not the intent) rather than assuming a `$(if …)` expanded.

Unit-test it with a fake `gh` on PATH that records argv: embed fixtures as JSON text
(`PR = json.loads({json.dumps(fixture)!r})`, one level of `!r` — double-encoding makes
the child parse a JSON *string*), let the fake flip to `MERGED` after a `pr merge`
call (and to `APPROVED` after `pr review --approve`, to assert the order), and assert
the argv (`--squash`, presence/absence of `--delete-branch`,
`--match-head-commit <sha>`).
