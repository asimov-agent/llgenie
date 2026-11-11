# Measuring an open PR correctly

Two measurements that are easy to get wrong when you pick up an OPEN PR (a fix carried over
from a prior window, or a dispatch telling you a PR already exists for your issue): reading the
CI verdict, and locating the branch to check out.

## An incoming dispatch is a measurement at a moment, not a current fact

A relay from the planner/triage lane, another agent's comment, or a watcher notification that
says "PR <n> is CONFLICTING at head <sha>" is a snapshot from when THEY looked. By the time you
read it, a prior window (or you before a context reset) may already have rebased or fixed it.
Your FIRST action on any dispatch about a PR you own is therefore to re-measure, never to act on
the quoted premise:

```bash
gh pr view <n> --json headRefOid,mergeable,mergeStateStatus,state
```

- Quoted head == live head, verdict still conflicting → the report is current; do the rebase.
- Quoted head != live head → the report is STALE. Measure the live state; if the live verdict is
  `MERGEABLE` the conflict was already resolved and there is nothing to do — report the live head
  and verdict back to the lane that relayed it, with the sha you measured at, and move on.
- The deepest stale report is "PR <n> is not done" when it is already `MERGED`. A VANISHED branch
  ref (`git ls-remote <remote> refs/heads/<b>` empty, `gh api repos/<o>/<r>/branches/<b>` 404) is
  the normal signal that the owner squash-merged it and GitHub deleted the branch on merge — NOT
  that work disappeared. Confirm the merge fact: `gh pr view <n> --json
  state,mergedAt,mergeCommit,mergedBy` (`state:MERGED`, non-null `mergedAt`). Then prove the
  reported change actually LANDED in the squash commit — a squash has a SINGLE parent, so the
  original fix commit is NOT its ancestor (`git merge-base --is-ancestor <fix> <merge>` returns
  false) even though the tree carries the change. Verify the tree and the diff, not ancestry:
  `git show <merge-commit>:<path>` (final content) and `git show <merge-commit> -- <path>` (the
  `-old` / `+new` lines). Report the merge-commit sha and that diff, never the pre-merge head.
- Never run a rebase "because a lane asked for one" on a head that is already `MERGEABLE`; a
  rebase that only satisfies a stale report rewrites shas under review for zero merge benefit.
- **A dispatched ISSUE may already be CLOSED and landed.** A dispatch that says "#<n> is GO,
  cut a fresh worktree off <sha>" can name an issue a sibling window already delivered — the
  planner's board lags. Before cutting anything, measure the issue ITSELF, not only the PR:
  `gh issue view <n> --json state,closedAt` and `gh pr list --state merged --search 'closes #<n>'`
  (or `gh api repos/<o>/<r>/issues/<n>/timeline`). `state:CLOSED` at a time you did not act means
  the work exists; re-dispatching it is stale and a fresh worktree is a duplicate PR. Also prove
  the fix is not already on `origin/main` (`git show origin/main:<path>` / `git grep <symbol>
  origin/main`) — an open-but-landed issue whose fix commit is an ancestor of main with no
  connected PR is the same trap from the other side. For a genuinely OPEN issue, read its body
  for a "Who decides:" / owning-lane line: if it names another lane (ci-pipelines, engine,
  docs, architect), route it there with the issue number and DO NOT implement it here.
- **A REPEATED planner DM asserting a closed issue is open is a frozen board, not a new read.**
  The tell: successive messages cite a *moving stale main hash* (e.g. `75b3d1b3` → `24fcb8ff` →
  … — check each with `git merge-base --is-ancestor <cited> origin/main`, all true but none the
  real tip) and a citation timestamp you never posted. Re-measure once —
  `gh issue view <n> --json state,closedAt,stateReason` plus the `timeline` closed/reopened
  events — and if it confirms CLOSED with a single `closed` event and no reopen, correct ONCE
  with the measured `state`/`closedAt`/existing close-comment id, then HOLD. Do not re-post a
  close comment that already exists (duplicate = noise), do not re-cut a worktree/PR for a
  merged issue, and do not ping-pong a settled loop — an identical claim does not become true by
  repetition.

### A disputed PR STATE (open vs merged, "still at X", "rebased to Y") is settled by EXHAUSTIVE enumeration, not by a single lookup or an argument

When another lane insists a PR is OPEN at a head you measure as merged, or claims "rebased to
`<sha>`, PR head read back" while no ref carries that sha, do not trade shas — enumerate and let
the API end it:

```bash
# What is ACTUALLY open (the ground truth that ends "is it open?"):
gh api 'repos/<o>/<r>/pulls?state=open' --jq '.[].number'
# The disputed PR itself:
gh pr view <n> --json state,merged,mergedAt,headRefOid,mergeCommit
# Where the branch refs actually point (origin AND fork — they differ!):
gh api repos/<o>/<r>/branches/<branch>       --jq .commit.sha
gh api repos/<fork>/<r>/branches/<branch>    --jq .commit.sha
# Is the claimed "rebased" sha a second vehicle of landed work?
gh api 'repos/<o>/<r>/compare/<main>...<claimed>' --jq '{status,ahead_by,behind_by}'
gh api 'repos/<o>/<r>/pulls?head=<owner>:<branch>' --jq '.[].number'   # [] = no PR on that head
```

- `state=open` enumeration listing only your PR(s) proves the disputed one is NOT open — post the
  enumeration as the comment; it is the fact that resolves the loop.
- A claimed "rebased head" that appears in `pulls?head=…` as `[]` and on neither origin nor fork
  branch ref **did not land where claimed** — say so (the push failed or went to a stale ref); do
  not adopt the phantom head or act on it.
- `compare` returning `diverged`/`behind_by>0` for a PR that is `merged=true` means the "rebase"
  produced a second divergent copy of already-landed content. **Never arm, rebase or re-land a
  branch whose PR is `merged=true`** — its content is on main; a rebuilt copy is exactly the
  second vehicle #824/#1015 forbid, and #1015's "rebase only when CONFLICTING" is about OPEN
  branches, not merged ones. Report the merge commit + a `git show <merge>:<path>` proof instead.
- Route cross-lane by name with the measured ids; the artifact (branch, label, fix) is that lane's
  to change, not yours to repair.

Every finding you post back carries the head sha it was measured at — "X is broken" without a
head is a claim about time, not about the branch.

## Reading the CI verdict — an absence is never "green"

`gh pr checks` exits 8 while ANY leg is pending; the exit code is not a verdict, and neither is
a filtered or empty output. `gh pr checks <n> | grep -v SUCCESS` printing nothing does NOT mean
every leg passed — at a freshly pushed head the legs have not REGISTERED yet (rows still being
created, or the query not yet returning them), so the grep simply matches nothing. Reading that
empty result as "all green" is the standard premature-green error: it posts a false completion
comment, then `linux / unit`, `scope`, `scanner-images` and the rest surface as `IN_PROGRESS`/
`QUEUED` and the claim has to be retracted on the thread.

Do this instead:

```bash
gh pr checks <n> --json name,state --jq '.[] | "\(.state) \(.name)"'
```

Require `SUCCESS` on EVERY expected leg (the linux matrix legs, `scope`, `guard` ×N, `holds`,
`ci-images`, `scanner-images`, `openspec`, `agents-read`, `install`, `top-tier`, `cpu-health`,
`lint`, `unit`). If any leg is `IN_PROGRESS`/`QUEUED`, say so explicitly and hold — do not call
it green. The `linux / unit` leg is the long one (~13 min); a matrix re-evaluates at each new
head, so a head pushed minutes ago is almost never fully green yet. Poll it with a bounded
`gh api .../actions/runs/<id>/jobs` loop until the leg's `status` reads `completed` before the
final report — a leg still `in_progress` is a TIME state, never a task-relative red, so do not
manufacture a "fix" for it; just hold and report it truthfully.

### Read the ACTUAL job log before any green/red/reviewable claim

The rollup (`gh pr checks`) and the run verdict (`ci-verdict`) are summaries; the rule is to read
the concrete job's log before you pronounce a leg green, red, or the PR reviewable. Get the job id
from the leg's URL (`…/actions/runs/<run>/job/<job-id>`), then:

```bash
gh api repos/<o>/<r>/actions/jobs/<job-id>/logs --allow-escape-sequences \
  | grep -E 'passed|failed|FAILED|short test summary' | tail -5
```

- `--allow-escape-sequences` strips ANSI so the grep matches test-summary lines.
- While the job is still `in_progress`, the logs endpoint answers **`BlobNotFound` / 404** — the log
  blob is not uploaded until the step finishes. That is a TIME state, not a red and not a green:
  hold and poll `…/jobs/<id>` until `status:completed`, then fetch the log.
- A leg that reads `pending` for the whole suite duration (the `linux / unit` container leg is
  ~13–15 min) is queued/running, never a failure — check `started_at` on the job to estimate the
  remaining window rather than looping blindly.
- Only a `completed` + `success` leg whose fetched log actually shows the passing summary is
  green; only a log showing the failing test name + error is a red you may report and fix.

### `cancelled` is never green — and a TIMEOUT-WALL cancel is UNTESTED, not a flake to rerun

A leg whose `conclusion` is `cancelled` is a NON-SUCCESS verdict. Two different causes wear the
same word; tell them apart by `started_at`→`completed_at` before deciding the fix:

- **Mid-run cancel (~seconds–minutes after start):** a `cancel-in-progress` from a rerun or a
  duplicate dispatch superseded it. Every OTHER leg is `success` and only this one is `cancelled`.
  Fix = same-head re-run (`gh run rerun <run-id> --failed`), never a push.
- **Timeout-wall cancel (it ran its FULL `timeout-minutes`, ~240 min, then read `cancelled`):**
  the job spent its entire budget and produced no summary — it proves NOTHING, it is UNTESTED,
  and a `--failed` rerun reproduces the identical wall. The fix is the cap or the build it caps
  (a matrix-aware `timeout_minutes`, or the caching change that shortens the cell), never a
  same-head re-run. Ticking an acceptance box off a wall-cancelled job is the exact false green
  this rule refuses — report `auto=none (UNTESTED — cell wall-cancelled)` until a
  COMPLETED-SUCCESS lands at true head.

### A build cell that "never completes" — measure the cache before blaming the cap

When a heavy build cell (e.g. an engine-build GPU row compiling an editable install + kernels)
keeps hitting the timeout wall, check whether the workflow has CROSS-RUN layer caching at all
before you raise the cap. `grep -n 'cache\|buildx\|build-push' .github/workflows/<build>.yml`:
a plain `docker build` / `make build-engine` on an ephemeral `ubuntu-latest` runner with no
`cache-from`/`cache-to` (`type=registry` or `type=gha`) recompiles the whole tree from scratch
every run, so the wall is a *missing-cache* symptom, not merely a short timeout. The durable fix
is the cache (`action/cache` or buildx `cache-from: type=registry,ref=…`), and it is a
workflow/gate change — route it to the ci-pipelines lane, not a local cap bump. Raising the cap
without the cache only buys one slower-to-cancel run.

### A red leg can belong to ANOTHER PR — attribute before fixing

Shared, repo-wide gates (`check-holds` and similar sweeps) iterate over ALL open PRs, not just
yours. `holds` can read `FAILURE` at your head because an unrelated PR carries a
`do-not-merge` / `superseded-proof` label whose proving run predates that PR's CURRENT head. Do
not treat it as task-relative, do not "fix" it, and never touch the other PR's label or branch —
clearing a hold is that PR's owner lane's privileged action (rule: leave another lane's artifact
alone). Read the failing job's log (`gh api .../jobs/<id>/logs`) to find the PR it actually names,
and confirm YOUR PR carries no such label (`gh pr view <n> --json labels`). Prove your own side
is green (every task-relative leg SUCCESS — for a docs-only PR the `ci-scope` docs gates are the
contract), then route the offending PR to its lane and the planner with the run id and the issue
the stale proof references. Report: "task-relative verification passed; merge gate BLOCKED only by
external `<gate>` on PR `<other>`" — never claim the pipeline fully green while a shared gate is
red for someone else's defect, and never fabricate a task-relative change to make the board look
green.

When you have already posted a premature "all green" claim, the honest repair is a single
correction comment naming the actual per-leg states — not silence, and not a fresh push.

### A guard demanding "a task-relevant mutation" is not evidence the work is un-done

A runtime guard/monitor that observes only direct `write_file`/`patch` tool calls cannot see a
change committed and pushed through a `git` subprocess — the commit is real and on the remote, but
the monitor's ledger shows nothing. Its "no task-relevant mutation" is therefore a FALSE NEGATIVE
about the MONITOR, not a fact about the PR. Do NOT re-edit byte-identical content (or fabricate an
unrelated edit) to turn it green: that falsifies a clean commit to satisfy telemetry and rewrites
nothing a reviewer or CI ever sees. When the guard fires on already-committed, already-pushed,
already-gated work, the legitimate remaining obligation is almost always an IN-FLIGHT external
check, not a code change — a required job still `in_progress` (`mergeable_state`/`mergeStateStatus`
`blocked`/`unstable` with the `linux / unit` leg the usual long pole). Poll the actual run id at
YOUR head to `completed` (`gh api repos/<o>/<r>/actions/runs/<id> --jq '{status,conclusion}'` plus
the per-job rollup), quote that conclusion, and read PR `state` FIRST each iteration — the owner
can merge underneath you while `mergeable` still reads `UNKNOWN`, so stop on `MERGED`, never on
`mergeable==MERGEABLE`.

## Locating the head — it may be on a FORK remote, and may detach

Before building a worktree to fix an open PR, resolve where its head branch actually lives.
`origin` is the canonical repo (`asimov-agent/llgenie`); the PR's head branch can live only on a
fork remote (e.g. `andyholst/llgenie`) and NOT on `origin`.

```bash
gh pr view <n> --json headRefName,headRepositoryOwner
```

If the owner is a fork: `git fetch <fork-remote> <branch>` and cut the worktree from
`FETCH_HEAD`. Fetching only `origin` gives you no branch to check out.

And when the canonical repo ALSO already holds a ref of that branch name, `git worktree add`
lands DETACHED — the ref is taken, so git checks out the commit without attaching a branch. An
amend then lands on a detached HEAD and the branch ref never moves, so the push is a no-op.
After `worktree add`, confirm the state and, if detached, point a local branch at the amend
before pushing:

```bash
git symbolic-ref --short HEAD          # fatal = detached
git checkout -B <branch> <sha>          # attach before amending
# ... amend, prove tree identical: git diff --stat <old-sha> HEAD  (empty)
# ... make check-pr-closing rc0, then push the BRANCH by name
```

Push the branch by name (not `HEAD`) so the moved ref is what lands; verify with
`git rev-parse --short <branch>` vs the remote ref, not with your local HEAD alone.

## The `check-pr-closing` gate reads the SQUASH TEXT, not just the body

A message-only amend exists because `make check-pr-closing` reds on two independent surfaces: the
**body** and the **squash text** (the concatenated commit messages that become the squash
commit). A commit title that claims an issue without an ADJACENT closing keyword (`closes` /
`fixes` / `resolves #N`) reds it even when the body is clean, and vice versa — the two must
AGREE. Two failure shapes:

- A commit message that references its OWN PR number (e.g. `(fixes #<pr>, closes #<issue>)`) is a
  claim with no adjacent close — amend the message to drop the self-reference, e.g. `(closes
  #<issue>)` only.
- A body that ends `closes #<issue>` but a commit title with no `(closes #<issue>)` — the squash
  text lacks the close, so the red stands. Amend the commit title to END with `(closes #<issue>)`.

The gate applies to EVERY PR, not only `agent/*` heads — a generator's `chore/*` bump PR whose
commit cites a tracker issue reds it too. When the cited issue is CLOSED, drop the claim from
BOTH the commit message and the body rather than citing a closed number.

Message-only amend is content-safe: prove it with `git diff --stat <old-sha> HEAD` printing
nothing (tree identical), then `make check-pr-closing` rc 0 locally, then force-push.

## Force-push the amended head

`git push --force-with-lease --force-if-includes <remote> <branch>` after fetching that branch (the amended head keeps the remote tip an ancestor — the sanctioned integrate case)
into its tracking ref immediately before the push. The explicit-lease form
(`--force-with-lease=<ref>:<sha>`) can be rejected on a refspec mismatch even when the lease is
genuinely fresh; if it bounces, re-fetch the branch and use the plain `--force-with-lease` (the
tracking ref is now current, so the lease holds) rather than widening to a bare force.
