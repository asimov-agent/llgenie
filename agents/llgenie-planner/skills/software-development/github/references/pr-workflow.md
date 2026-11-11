# GitHub Pull Request Workflow

Complete guide for managing the PR lifecycle. Each section shows the `gh` way first, then the `git` + `curl` fallback for machines without `gh`.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)
- Inside a git repository with a GitHub remote

### Quick Auth Detection

```bash
# Determine which method to use throughout this workflow
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  # Ensure we have a token for API calls
  if [ -z "$GITHUB_TOKEN" ]; then
    if _hermes_env="${HERMES_HOME:-$HOME/.hermes}/.env"; [ -f "$_hermes_env" ] && grep -q "^GITHUB_TOKEN=" "$_hermes_env"; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" "$_hermes_env" | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(uv run python "${HERMES_HOME:-$HOME/.hermes}/skills/github/github-auth/scripts/git-credential-token.py")
    fi
  fi
fi
echo "Using: $AUTH"
```

### Extracting Owner/Repo from the Git Remote

Many `curl` commands need `owner/repo`. Extract it from the git remote:

```bash
# Works for both HTTPS and SSH remote URLs
REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
echo "Owner: $OWNER, Repo: $REPO"
```

---

## 1. Branch Creation

This part is pure `git` — identical either way:

```bash
# Make sure you're up to date
git fetch origin
git checkout main && git pull origin main

# Create and switch to a new branch
git checkout -b feat/add-user-authentication
```

Branch naming conventions:
- `feat/description` — new features
- `fix/description` — bug fixes
- `refactor/description` — code restructuring
- `docs/description` — documentation
- `ci/description` — CI/CD changes

## 2. Making Commits

Use the agent's file tools (`write_file`, `patch`) to make changes, then commit:

```bash
# Stage specific files
git add src/auth.py src/models/user.py tests/test_auth.py

# Commit with a conventional commit message
git commit -m "feat: add JWT-based user authentication

- Add login/register endpoints
- Add User model with password hashing
- Add auth middleware for protected routes
- Add unit tests for auth flow"
```

**Never `git checkout -- <path>` to undo a sabotage/scratch edit on a file that is
untracked or not yet committed.** `git checkout --` restores the file from the index;
for a file that was never committed (a new test, a scratch probe) the index has no copy,
so the command silently DELETES the whole file — the work is gone and must be rewritten.
To revert a scratch edit on a new file, re-apply the intended content with `write_file`
or `patch`; only use `git checkout --` on a file whose committed version you want back.
Check `git status` first: if the file shows as `??` (untracked) or `A` (staged-new), it
has no committed copy to restore.

Commit message format (Conventional Commits):
```
type(scope): short description

Longer explanation if needed. Wrap at 72 characters.
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`, `perf`

## 2b. Running the repo's own gates locally before pushing

Prefer the repo's own `make <check>` targets over hand-run linters/tests — and when those targets
execute inside a container as root, expect their OUTPUT to be root-owned on your worktree:

- **A generator run as root (a containerized `foo new <name>`, a schema/diff tool) leaves
  directories your agent cannot write into.** A `write_file`/`patch` then fails with `Permission
  denied` on a path that looks ordinary. Fix ownership back instead of working around it:
  `docker run --rm -v "$PWD":/repo alpine:latest chown -R $(id -u):$(id -g) /repo/<path>`.
- **Root-written `__pycache__` makes `rm -rf` fail** with `Permission denied` under your user.
  Clear it through the same container (`docker run --rm -v "$PWD":/repo alpine:latest rm -rf
  /repo/tests/__pycache__`) — `sudo` in a non-interactive shell has no terminal to prompt on and
  just fails.
- **Run ONE test file without a host venv** by reusing the repo's test image: `make test-image`
  (pulls the pinned image), then `docker run --rm -u root -v "$PWD":/repo -w /repo -e HOME=/root
  <test-image> python -m pytest tests/test_x.py -q -p no:cacheprovider`. Iterate on the file there,
  then run the full target once.
- **Never read a gate's verdict through a pipe.** `make test-unit 2>&1 | tail -40; echo rc=$?`
  reports `tail`'s exit status, not make's. Use `set -o pipefail`, `${PIPESTATUS[0]}`, or write to a
  log and check that file — a piped gate can look green while failing.
- Long gates belong in a background job with a completion notification; do not poll a still-running
  gate in a loop (see Section 4).

## 3. Pushing and Creating a PR

### Push the Branch (same either way)

```bash
git push -u origin HEAD
```

**Confirm which remote is the fork before pushing to a PR head.** `origin` is
NOT always the fork — in a fork-and-upstream setup the remotes may be named
`origin` (upstream) and `fork` (your fork), or the reverse. Pushing to the wrong
one either creates a stray branch on the upstream or leaves the PR head
unchanged. Run `git remote -v` and check the PR's actual head repo
(`gh pr view N --json headRepositoryOwner,headRefOid`) before pushing; push to
the remote that matches the PR's head owner, then re-verify the head oid
advanced. Do not trust a repo's AGENTS.md/README that says "push to origin" —
verify the live remote names.

### Create the PR

**With gh:**

```bash
gh pr create \
  --title "feat: add JWT-based user authentication" \
  --body "## Summary
- Adds login and register API endpoints
- JWT token generation and validation

## Test Plan
- [ ] Unit tests pass

Closes #42"
```

Options: `--draft`, `--reviewer user1,user2`, `--label "enhancement"`, `--base develop`

**With git + curl:**

```bash
BRANCH=$(git branch --show-current)

curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$OWNER/$REPO/pulls \
  -d "{
    \"title\": \"feat: add JWT-based user authentication\",
    \"body\": \"## Summary\nAdds login and register API endpoints.\n\nCloses #42\",
    \"head\": \"$BRANCH\",
    \"base\": \"main\"
  }"
```

The response JSON includes the PR `number` — save it for later commands.

To create as a draft, add `"draft": true` to the JSON body.

## 4. Monitoring CI Status

### Check CI Status

**With gh:**

```bash
# One-shot check
gh pr checks

# Watch until all checks finish (polls every 10s)
gh pr checks --watch
```

**With git + curl:**

```bash
# Get the latest commit SHA on the current branch
SHA=$(git rev-parse HEAD)

# Query the combined status
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
  | python -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Overall: {data['state']}\")
for s in data.get('statuses', []):
    print(f\"  {s['context']}: {s['state']} - {s.get('description', '')}\")"

# Also check GitHub Actions check runs (separate endpoint)
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/check-runs \
  | python -c "
import sys, json
data = json.load(sys.stdin)
for cr in data.get('check_runs', []):
    print(f\"  {cr['name']}: {cr['status']} / {cr['conclusion'] or 'pending'}\")"
```

**Waiting without burning turns on a long multi-job run.** A foreground
loop that polls a still-running Actions run (`gh pr checks --watch` included)
blocks in the `terminal` tool and times out at its limit (and `process_manage`
`wait` clamps to ~180s), so a multi-minute run turns into repeated wasted
calls. Instead run a **background** poller once and let a completion
notification deliver the result:

```bash
# background=true + notify=true; the poll loop exits when the run completes
while true; do
  s=$(gh run view <RUN_ID> --repo <owner>/<repo> --json status,conclusion \
      --jq '[.status,(.conclusion//"-")]|join("/")')
  echo "$(date -u +%H:%M:%S) $s"; echo "$s" | grep -q '^completed' && break
  sleep 60
done
echo DONE
echo "failing:"; gh run view <RUN_ID> --repo <owner>/<repo> \
  --json jobs --jq '.jobs[]|select(.conclusion=="failure")|.name'
```

Query just the job you care about with a `--jq` filter (e.g.
`.jobs[]|select(.name=="macos / unit")`) rather than the whole run, and
check `status,conclusion` per job — an in-progress job is not a failure. Do
Do NOT start a second poller while one is running, and do not re-poll the
process in a loop; end the turn with a one-line status and let the
notification start the next turn.

**`gh run watch --exit-status` is not proof a run is done.** `gh run watch`
stops waiting when its own poll/timeout budget lapses, and `--exit-status` maps
only whether it got a signal before stopping — so a watch that returns rc=0 does
NOT mean the run concluded successfully. Back every claim of a run's outcome
with a direct read: `gh run view <ID> --repo <owner>/<repo> --json status,conclusion`,
and per job `--json jobs --jq '.jobs[]|select(.conclusion=="failure")|.name'`.
An `in_progress` job is not a failure (a long `macos / unit` job keeps a run
non-concluded long after every other job passed).

**Verifying "PR #N is red/merged" is a live read, not a premise.** Never chase a
stale assumption that a PR failed. Confirm the PR's own truth
(`gh pr view N --json state,mergedAt`), then, for "landed on main", check that
`origin/main`'s head sha equals that PR's merge-commit sha — often the merge
commit IS main's tip, so a merged PR cannot still be red. List open PRs
(`gh pr list --state open`) and their checks to find which PR is actually red
before touching anything.

**A still-running run has no whole-run failure log yet.** `gh run view <ID>
--log-failed` on an in-progress run prints "run ... is still in progress; logs
will be available when it is complete" and returns nothing — that message means
WAIT for the run to finish, not that the log endpoint is broken. But you can
read a JOB's log while the run is still going, once that job itself has
finished: `gh api repos/<owner>/<repo>/actions/jobs/<JOB_ID>/logs
--allow-escape-sequences`. The flag is required (the log is ANSI-dense); strip
the codes and isolate the error with
`sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' | grep -iE 'error|assert|Traceback|failed'`.
Read the full error lines before attributing a failure to the PR's change — a
`TimeoutError: The read operation timed out` in a network-backed test is often a
transient flake, not a regression from the diff (check the failing test's
stderr/line before re-opening work).

### Poll Until Complete (git + curl)

```bash
# Simple polling loop — check every 30 seconds, up to 10 minutes
SHA=$(git rev-parse HEAD)
for i in $(seq 1 20); do
  STATUS=$(curl -s \
    -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
    | python -c "import sys,json; print(json.load(sys.stdin)['state'])")
  echo "Check $i: $STATUS"
  if [ "$STATUS" = "success" ] || [ "$STATUS" = "failure" ] || [ "$STATUS" = "error" ]; then
    break
  fi
  sleep 30
done
```

## 5. Auto-Fixing CI Failures

When CI fails, diagnose and fix. This loop works with either auth method.

### Step 1: Get Failure Details

**With gh:**

```bash
# List recent workflow runs on this branch
gh run list --branch $(git branch --show-current) --limit 5

# View failed logs
gh run view <RUN_ID> --log-failed
```

**With git + curl:**

```bash
BRANCH=$(git branch --show-current)

# List workflow runs on this branch
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?branch=$BRANCH&per_page=5" \
  | python -c "
import sys, json
runs = json.load(sys.stdin)['workflow_runs']
for r in runs:
    print(f\"Run {r['id']}: {r['name']} - {r['conclusion'] or r['status']}\")"

# Get failed job logs (download as zip, extract, read)
RUN_ID=<run_id>
curl -s -L \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/logs \
  -o ~/.hermes/cache/scratch/ci-logs.zip
cd ~/.hermes/cache/scratch && unzip -o ci-logs.zip -d ci-logs && cat ci-logs/*.txt
```

### Step 2: Fix and Push

After identifying the issue, use file tools (`patch`, `write_file`) to fix it:

```bash
git add <fixed_files>
git commit -m "fix: resolve CI failure in <check_name>"
git push
```

### Step 3: Verify

Re-check CI status using the commands from Section 4 above.

### Auto-Fix Loop Pattern

When asked to auto-fix CI, follow this loop:

1. Check CI status → identify failures
2. Read failure logs → understand the error
3. Use `read_file` + `patch`/`write_file` → fix the code
4. `git add . && git commit -m "fix: ..." && git push`
5. Wait for CI → re-check status
6. Repeat if still failing (up to 3 attempts, then ask the user)

## 5b. Review comments on YOUR PR

When someone comments on the PR for the branch you are working, the comment is work, not chatter:

1. Read BOTH surfaces — PR-level and inline diff threads live in different endpoints:

```bash
gh pr view <N> --json comments,reviews
curl -s -H "Authorization: Bearer $(gh auth token)" \
  "https://api.github.com/repos/<o>/<r>/pulls/<N>/comments" \
  | jq -r '.[] | "\(.user.login) \(.path // "-"): \(.body)"'
```

2. Reproduce what it flags and fix the ROOT cause, with a test.
3. Commit as a NORMAL commit on top — never squash/rebase/force-push a branch a reviewer has already
   engaged with; the sha they read must stay reachable.
4. Reply on the SAME thread with the fixing sha, the root cause, and the verification:

```bash
curl -s -X POST -H "Authorization: Bearer $(gh auth token)" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<o>/<r>/pulls/<N>/comments/<COMMENT_ID>/replies" \
  -d '{"body":"Fixed in <sha>: <root cause>. Verified: <gate + result>."}'
```

A reply that only says "done" without the sha and the gate result is not a resolution.

## 5c. Rebasing onto a moved default branch

`gh pr view <N> --json mergeStateStatus` returning `DIRTY` (conflicts) or `BEHIND` (stale) is the work
item, not a reason to merge by hand. Rebase, then:

- **A newest-first index/changelog conflicts on almost every concurrent change.** Resolve by keeping
  BOTH rows, newest first — dropping the other branch's row silently deletes a landed change, and the
  repo's docs gate may fail on the missing entry. Re-read the file after resolving; conflict markers
  inside a markdown table are easy to leave behind.
- Re-run the repo's index/wiring gates after the rebase (`check-docs`, `check-wiring`, or whatever the
  repo documents) — they validate that every record is indexed, so they catch a lost row.
- Push with `git push --force-with-lease` on your own PR branch only, after the rebase you just did.

## 5d. A red PR that its change did not cause

Before writing any fix, answer "did this PR cause it?". A surprising share of red PRs fail on a gate
that is red on the base branch too, and repairing the diff for it wastes the whole session.

1. **Identify the failing TARGET, not the failing job name.**
   `gh run view <run> --log-failed` (or `gh run view --job <id> --log-failed`) ends with the make
   line that actually failed (`make[1]: *** [Makefile:N: check-foo] Error 1`) — that target, run
   locally, is the reproduction.
2. **Reproduce it on a clean base.** In the worktree, `git reset --hard origin/<base>` (or a
   `git worktree add --detach origin/<base>` checkout) and run the same `make <target>` 2–3 times.
   Reproducible with the PR's diff absent → it is a shared gate, not the change. Run it more than
   once: a gate that reads a live service (a Hub search, a registry API, a download counter) passes
   on one call and fails on the next, so a single red or a single green is not a verdict.
3. **The base branch's last CI run is weaker evidence than your own reproduction** — the same
   time-dependent gate can be green on the base an hour earlier and red now. Say which one you
   measured.
4. **Fix a stale GENERATED artifact by running its generator target, never by hand-editing it** —
   `make sync-<thing>` / `make generate-<thing>` — then commit the regenerated files as their own
   `data(...)`/`chore(...)` commit, quoting the numbers the target printed (rows, links probed,
   dead/gated). Hand-pruning the artifact to just-pass leaves the tree disagreeing with the
   generator, and the next sync re-churns it.
5. **File the gate's own defect as its own issue** when the cause is the check's design (it fails on
   live-data churn, it cannot tell a genuinely gone entry from one a search page dropped). The
   blocking data refresh is one objective, the gate fix is another; both get an issue link in the PR
   body's `Not covered`, and the change note records why a data commit sits inside a feature PR.
6. **Re-read the PR's real head before editing.** Bots rebase and force-push PR branches, so your
   worktree branch and `gh pr view N --json commits` can both be behind: the authoritative head is
   `gh api repos/<o>/<r>/pulls/N --jq .head.sha`. Fetch the fork remote and `git reset --hard
   <fork>/<branch>` onto it, then rebase onto `origin/<base>` — editing the stale tip produces
   commits the PR never sees.
7. **Bot claim comments (`<!-- bot-claim: fix-bot … -->`) do not block a human/agent repair.** They
   are advisory leases; take the work over, and push a normal commit on top rather than fighting the
   claim.

Long tail: after the push, `gh pr checks <n>` for the OS-slowest job (`macos / unit` routinely runs
40–50 min while Linux finishes in ~20). Foreground `--watch` dies at the tool timeout, so either
background the poller (Section 4) or issue bounded `timeout … gh pr checks --watch` calls and re-read
between them. The repo's own auto-merge job lands the PR when the run is green — never `gh pr merge`.
Finish on live reads: `gh pr view N --json state,mergedAt,mergeCommit`, the merge commit on
`origin/<base>`, the linked issue actually CLOSED, and then prune the branch + worktree with the
repo's prune target rather than `git branch -D`.

## 6. Merging

**With gh:**

```bash
# Squash merge + delete branch (cleanest for feature branches)
gh pr merge --squash --delete-branch

# Enable auto-merge (merges when all checks pass)
gh pr merge --auto --squash --delete-branch
```

**With git + curl:**

```bash
PR_NUMBER=<number>

# Merge the PR via API (squash)
curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER/merge \
  -d "{
    \"merge_method\": \"squash\",
    \"commit_title\": \"feat: add user authentication (#$PR_NUMBER)\"
  }"

# Delete the remote branch after merge
BRANCH=$(git branch --show-current)
git push origin --delete $BRANCH

# Switch back to main locally
git checkout main && git pull origin main
git branch -d $BRANCH
```

Merge methods: `"merge"` (merge commit), `"squash"`, `"rebase"`

### Enable Auto-Merge (curl)

```bash
# Auto-merge requires the repo to have it enabled in settings.
# This uses the GraphQL API since REST doesn't support auto-merge.
PR_NODE_ID=$(curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER \
  | python -c "import sys,json; print(json.load(sys.stdin)['node_id'])")

curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/graphql \
  -d "{\"query\": \"mutation { enablePullRequestAutoMerge(input: {pullRequestId: \\\"$PR_NODE_ID\\\", mergeMethod: SQUASH}) { clientMutationId } }\"}"
```

## 7. Complete Workflow Example

```bash
# 1. Start from clean main
git checkout main && git pull origin main

# 2. Branch
git checkout -b fix/login-redirect-bug

# 3. (Agent makes code changes with file tools)

# 4. Commit
git add src/auth/login.py tests/test_login.py
git commit -m "fix: correct redirect URL after login

Preserves the ?next= parameter instead of always redirecting to /dashboard."

# 5. Push
git push -u origin HEAD

# 6. Create PR (picks gh or curl based on what's available)
# ... (see Section 3)

# 7. Monitor CI (see Section 4)

# 8. Merge when green (see Section 6)
```

## Useful PR Commands Reference

| Action | gh | git + curl |
|--------|-----|-----------|
| List my PRs | `gh pr list --author @me` | `curl -s -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/repos/$OWNER/$REPO/pulls?state=open"` |
| View PR diff | `gh pr diff` | `git diff main...HEAD` (local) or `curl -H "Accept: application/vnd.github.diff" ...` |
| Add comment | `gh pr comment N --body "..."` | `curl -X POST .../issues/N/comments -d '{"body":"..."}'` |
| Request review | `gh pr edit N --add-reviewer user` | `curl -X POST .../pulls/N/requested_reviewers -d '{"reviewers":["user"]}'` |
| Close PR | `gh pr close N` (verify state after) | `curl -X PATCH .../pulls/N -d '{"state":"closed"}'` |

### Closing a PR: verify it actually closed

`gh pr close N --comment "..."` can exit 0 having closed NOTHING — it prints only the
accessibility footer and leaves the PR `OPEN`. Never treat the exit code or the absence of an
error as proof. Close via the API and read `state` back:

```bash
gh api -X PATCH repos/<o>/<r>/pulls/<N> -f state=closed \
  --jq '"state="+.state+" merged="+(.merged_at//"never")'   # want: state=closed merged=never
```

`gh api ... -f body=...` on the issue-comment endpoint can also fail to parse; if a
follow-up comment errors, re-add the body with `gh issue comment <N> --body "$(cat file)"`,
then re-read `gh pr view <N> --json state` to confirm `CLOSED`.

Put the closure rationale (e.g. a superseded-duplicate comparison table) as a comment ON the
closed PR — do NOT open a new issue just to hold a "closure record" that then needs its own close.
| Check out someone's PR | `gh pr checkout N` | `git fetch origin pull/N/head:pr-N && git checkout pr-N` |
