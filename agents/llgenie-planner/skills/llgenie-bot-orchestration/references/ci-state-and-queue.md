# CI state, the runner queue, and controlling runs

Depth for the always-on rules in SKILL.md §3c. Everything here is `gh` on a GitHub Actions repo with
`cancel-in-progress: true` for pull requests.

## Read state as conclusions, not as a column

```bash
gh pr view <n> --json statusCheckRollup \
  --jq '[.statusCheckRollup[]|.conclusion // .status]|group_by(.)|map("\(.[0]):\(length)")|join(" ")'
gh run view <id> --json status,conclusion,headSha,run_attempt
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '[.jobs[]|"\(.conclusion // .status)"]|group_by(.)|map("\(.[0]):\(length)")|join(" ")'
```

- **Cite a run id at the head sha.** "All checks green" is unfalsifiable and usually stale: a superseded head keeps
  its old successes in the rollup for a while.
- **`cancelled` is not a verdict.** It means a newer run superseded it, or a sweep killed it. The PR then has *no*
  verdict and needs one fresh completed run at the current head.
- **A run queued behind nothing still queues.** `queued` with an empty repo queue means the platform has not started
  it yet, not that the job is broken.
- **An unexpanded matrix name** (`test-${{ matrix.engine }}`) in a run only means the matrix never instantiated. That
  is expected when a placeholder row yields no rows. Treat it as a workflow fault only when the run is **completed**
  *and* rows were expected.
- **A cancellation that survives a re-run** (`attempt >= 2`, still `cancelled`, no newer run on the branch) is not
  `cancel-in-progress`. Look at who triggered it before hunting YAML.

### What `mergeStateStatus` can and cannot tell you

One value, four different situations — the badge alone never answers "is a bad check blocking this":

| actual state | `mergeStateStatus` |
|---|---|
| a check **fails** | `UNSTABLE` |
| checks **still running** (8 pending, 0 failing) | `UNSTABLE` |
| review required (when every PR needs review) | `BLOCKED` |
| all green + approved | `CLEAN` |

Three of the four read as "not mergeable" and only one is about checks. A probe of enforcement must snapshot
`statusCheckRollup` conclusion counts **including the no-conclusion count**, `reviewDecision`, `isDraft` and the merge
decision (`auto_merge.decide()`) **in the same reading** — and the merge-decision half needs a token-bearing run
(`GH_TOKEN`/`GITHUB_TOKEN` empty locally), so it cannot be settled from a laptop.

## Query per commit, never a window

`gh run list --limit N` returns the newest N runs **repo-wide**. A monitor that derives per-PR state from it reports
"nothing stuck" exactly when the run it cares about has scrolled off page one:

```bash
gh run list --repo <o>/<r> --commit <sha> --json status,conclusion,runAttempt   # precise
gh run list --repo <o>/<r> --branch <branch> --limit 5                           # precise enough for a PR
```

Same class of error as counting a population with a page-size default: the window is not the population.

## A job whose label matches no runner never fails — it queues forever

This is the failure that looks like "blocked on review" for hours. GitHub does **not** fail a job when no machine
matches its `runs-on` label (an offline self-hosted runner, or hosted minutes/spending exhausted for that OS): the job
stays `queued`, the run never concludes, and every PR's checks stay pending. The repo's own instrument names it —

```bash
python3 scripts/queued_run_alarm.py --repo <o>/<r> --minutes 30
# → 80.1 min  CI / macos / top-tier  labels=[macos-15-intel]  run=<id>
#   "no machine matches those labels … GitHub does not fail such a job, so the run never concludes"
```

Read the shape before blaming the queue: **many queued runs whose stalled jobs all share one label** is capacity.
Cancelling runs or pausing scheduled workflows does not conjure a runner — it only removes evidence. Confirm by listing
jobs, not runs:

```bash
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '[.jobs[]|select(.status=="queued")|{name,labels:.labels}]'   # one label throughout ⇒ capacity
```

**The alarm cannot see a job that started and was then cancelled — so "never starts" is a claim you must test.**
`queued_run_alarm` lists the rows still `queued`; rows that got a machine, ran twenty minutes and were killed by a
cancellation are absent from its view. Read per-job timestamps on the *completed* run before blaming a label:

```bash
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '.jobs[]|select(.name|test("<platform>";"i"))|"\(.name) \(.started_at) -> \(.completed_at) \(.conclusion)"'
```

A row with `started_at` set is proof the label provisions — a label matching no runner cannot produce a green job. That
pushes the diagnosis down a layer: rows queue ~8 min, start, run 21 min, and die to a **cancellation**, which is what
every sweep and every push-while-a-run-is-live does. Report that as "killed mid-run", never as "never starts".

**Probe the label instead of theorising about it.** Cut a scratch branch off the default branch, change *one* row's
`runs-on` to a neighbouring image, open a draft PR, and read whether the job starts: starts ⇒ the label is not
provisionable on this account's plan, and the fix is the label list (one commit, probe run id cited); still queues ⇒
capacity/billing or an offline runner, which is the owner's to fix and **not** a code change. Close the probe after
capturing the status — it is evidence, not a deliverable. **A probe that has been queued for less than the platform's
normal provisioning lag proves neither answer** (a macOS row can wait 10+ minutes before a machine appears), so wait
until the queued rows outlive the lag by a clear margin, or every other row in the same run has finished.

Per-job status is the only honest progress report while this is unresolved: `14 success · 7 queued · 0 failed` where all
seven queued rows are one platform. Say "supply-limited, not quality-limited", and never present a run whose remaining
rows cannot start as "almost green".

## Read the failing test from the log — an empty result is a CLI guard, not a missing log

Do not conclude "CI logs are unavailable" from an empty body. `gh api .../jobs/<id>/logs` **refuses to print** when the
log carries ANSI escapes, and returns a short message that reads like a failure:

```bash
gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E 'FAILED|^\S*E +' | tail -20
```

- `gh run view <id> --log-failed` refuses while the **run** is in flight even when the **job** completed, so a finished
  failing job is readable through `jobs/<id>/logs` while the CLI still says "still in progress".
- Job ids come from the run's job list, not the URL:
  `gh api .../runs/<id>/jobs --jq '.jobs[]|select(.conclusion=="failure")|.id'`.
- **One log read replaces a lane-day of guessing:** six failing test ids and their assertion text from one command,
  after every lane had reported "logs return 0 bytes" and reproduced locally instead.
- **A log is evidence about the REF it ran on.** A failure read from a branch run says nothing about the default branch;
  quoting it as repo-wide turns one PR's defect into a phantom main-branch outage. Carry `head_branch` and `head_sha`
  beside every log-derived finding.

## `run.status` lies about progress; per-job state is the truth

A run can read `status: queued` for an hour while twenty jobs hold runners and one has been inside a single step for
fifty minutes. Anything keyed on `run.status` — an alarm, a retry policy, a "waiting for capacity" message — sleeps
through a hang:

```bash
gh api repos/<o>/<r>/actions/runs/<id> --jq '.status, .updated_at'
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '.jobs[]|"\(.name) \(.status)/\(.conclusion // "-") start=\(.started_at) runner=\(.runner_name // "none") step=\(.steps[-1].name)"'
```

- **An `updated_at` frozen while jobs run is the stall signature** — 40+ minutes without movement while a job sits on
  one step is hung, not slow.
- **Read the steps before calling it slow:** four provisioning steps in 27 seconds followed by 53 minutes on one step
  is a hang, and with no `timeout-minutes` the job inherits the platform's 360-minute default, so hung and slow stay
  indistinguishable for six hours.
- **Price it, do not describe it:** runner-minutes held (`completed_at - started_at` per job × count) is the argument
  that gets a timeout added; "it was slow" is not.

## Who may approve — identity, not permission

An approval must come from an account that is **not the PR author**. Where every bot pushes with the owner's PAT, every PR is owner-authored, `gh pr review --approve` answers `Can not approve your own pull request`, and the board sits `BLOCKED/REVIEW_REQUIRED` with green checks — which reads as "waiting on the owner" when the real problem is one identity doing everything.

- **A workflow's own token is a different account** (`github-actions[bot]`, distinct from the owner PAT) and **can** approve with `permissions: pull-requests: write`. The review does not have to be an owner action.
- **A `pull_request` run from a fork receives a read-only token**, so approve/merge logic belongs in a `workflow_run` workflow: that executes in the **base** repository with the base repository's token — the same reason the merge PAT lives there at all.
- **The guard is "approver ≠ author"**, never "use token X": a PR opened by the workflow's own bot needs the other identity, so a hard-coded token assumption reds or silently no-ops on exactly that PR.
- **`allow_auto_merge` is a repository setting, not code**: `PATCH /repos/<o>/<r>` returns 404 for a `write` token and only admin flips it. Check `collaborators/<user>/permission` before promising an auto-merge fix is deployable, and say plainly which half is code and which half is a click only the owner can make.

Diagnose a "nobody can merge" board in this order: author identity vs approver identity → the repo switch → whether the runs that would do the approving are themselves queued.

## A completed run with zero jobs is a broken workflow, and no rollup shows it

`timeout-minutes` is **invalid on a `uses:` job**. The workflow fails to load before any job exists, so the run ends
`completed/failure` with **0 jobs and 0 check-runs**, every `statusCheckRollup` reads `fail=0`, and the PR looks clean
while it can never be tested:

```bash
gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '.total_count'   # 0 ⇒ the file did not parse
```

Ceilings belong on the jobs *inside* the called reusable workflow, never on the caller. So: when a PR's only run is
`failure` with no jobs, read the workflow shape before suspecting a flaky test — and a workflow-shape gate forbidding
`timeout-minutes` on `uses:` jobs is worth more than any per-PR check, because this is the one failure mode no rollup
reports.

## Arming auto-merge is a step at creation, not a decision per PR

```bash
gh pr merge <n> --squash --auto          # immediately after gh pr create
gh pr view <n> --json autoMergeRequest  # verify: enabledAt must sit beside createdAt
```

A `workflow_run` sweep arms nothing retroactively — a PR armed *after* its run concluded waits for the next sweep, so
arming late loses the very event it needed. Never arm a draft, a `do-not-merge` PR, or one based on a non-`main` branch;
report those as **deliberately unarmed with the reason**. Arming is neither approving nor a verdict: the merge decision
still refuses anything red.

## A queued run owes no verdict; a running one owes all of it

Superseding a **queued** run by pushing a corrected head destroys nothing — it never acquired a runner, so there is no
verdict to lose. Superseding a **running** run discards every success it already paid for. The push rule is therefore
state-dependent, not a blanket ban:

- run at the head `queued` or `completed` → a push is affordable (name the state you checked);
- any job at the head `in_progress` → frozen until it concludes, whatever licence is in hand.

## Repairing a run without burning a matrix

```bash
gh run rerun <id>                       # same sha, all jobs, run_attempt+1
gh run rerun <id> --failed              # same sha, failed AND cancelled jobs only
```

Order of preference when a PR has no verdict:

1. **Rerun** at the same sha — no commit, no matrix rebuild, and `scope`/`docs`-style gates keep their successes.
2. **Retarget or re-fire the trigger** if no run exists at all (see below).
3. **Push** only when the code changed. A push is the most expensive option: it cancels the in-flight run, discards
every success already paid for, and restarts the whole matrix.

A PR under review gets **no cosmetic pushes**. Batch review feedback into one push after the current verdict lands, and
put text-only changes in a comment — a body edit does not need a commit.

## A pause leaks through pull-request triggers

Disabling the bot workflows does **not** pause pull-request CI. They are separate: `pull_request`/`push` triggers stay active, so every new branch push or PR opened by a lane starts a run and the queue refills behind your back — a second sweep found five unrelated branch runs competing with the two PRs the owner had named. Three consequences:

- **Disabling bots is not a freeze; the freeze is a message.** Every lane needs the "no new pushes, no new branches" line explicitly, and expect it to be broken — measure the active-run list before concluding a run is stuck.
- **Cancel a doomed head on purpose, and say why.** When the head is already known-red for a reason a rewrite will fix (a bad commit author, a missing file), its matrix only holds runner slots. Cancel it and state the reasoning out loud, so a later reader does not read it as another sweep.
- **Two kept PRs serialise; they do not parallelise.** Under a limited concurrency budget, the first PR's matrix holds the slots the second needs (`guard` queued with no other job created, for twenty minutes). That fixes the order verdicts arrive in — usually the one you did *not* expect — so never promise a verdict time.

## Carry the ref and the sha in every finding, and close the issue when the fix lands

"The default branch is broken" is a claim about a moment, and it is wrong as soon as the fix merges. Two habits end
that class of re-litigation:

- **Quote `main=<sha>` measured at a time, plus PR heads beside the PR numbers.** Nearly every disagreement in a long
  session is a stale read — the `main` sha, a PR head, a worktree's contents, whether a branch has a remote — and each
  one ended with a sha plus a command anyone could re-run.
- **Close the issue on the merge, with the merge sha and the evidence**, and drop the `agent:implement` label. An issue
  left open after its fix lands is worse than no issue: every dispatch quotes a tree that no longer exists and lanes
  re-derive a failure that is already fixed.

## A stacked PR produces no CI run

CI that triggers on `pull_request: branches: [main]` never fires for a PR whose base is another PR's branch. The
symptom is a PR with **zero runs**, not a red one. Fix without pushing code:

```bash
gh pr edit <n> --repo <o>/<r> --base main     # retarget
gh pr close <n> --repo <o>/<r>; gh pr reopen <n> --repo <o>/<r>   # fires a fresh pull_request event
```

Say in the PR body that it is stacked and which PR must merge first — a retargeted stack now carries the base PR's
whole diff, which is a duplicate unless the body says so.

## Trigger config is read from the default branch, not from your PR

`paths` / `paths-ignore` are evaluated by GitHub from the **default branch's** workflow file, not from the copy in the
PR under test. A probe PR cut from `main` **before** the filter exists therefore schedules the full matrix, and reading
that as "the filter is broken" is a false negative that costs a matrix:

- **Trigger half ⇒ measurable only after the merge.** File the probe, run it the minute the merge lands.
- **Classifier half ⇒ measurable now.** `python3 scripts/ci_scope.py jobs --paths <p>` runs from any checkout and is
the only half a pre-merge PR can prove.
- **The filter and the printed selection must be one source.** When a workflow's ignore list and a classifier's class
  list are written twice, the printed one is the only place a human sees the truth and it will drift. Pin them equal
  (`assert set(CLASSES["docs"]) == set(paths_ignore)`), not merely compatible — otherwise the next refactor derives
  the ignore list from the class and the extension-wide pattern is back with a green guard.

### An always-on report check must listen to every event that can produce a diff

A check whose job is to *state* what a diff selected — the thing that makes a skipped stage legible — is worthless if
it is absent on the ref shapes where the selection is least ordinary. `pull_request` alone misses three: `merge_group`
(the queue builds a merge commit nobody pushed), `workflow_dispatch` (a human re-running), and a force-push that nets
to nothing. All three legitimately have empty or unusual diffs, which is exactly when a reader needs the report.

```yaml
on:
  pull_request:
    branches: ["main"]
  merge_group:              # no path filter on any of the three
  workflow_dispatch:
```

**`github.base_ref` is empty on `merge_group` and `workflow_dispatch`.** Any step building `BASE="origin/${BASE_REF}"`
then becomes `origin/` and dies before the classifier's widening logic runs, so the trigger and the fallback are only
correct together, in one commit:

```yaml
env:
  BASE_REF: ${{ github.base_ref || 'main' }}
```

Two gates bite in the same edit: a bare `workflow_dispatch:` fails the dispatch-form check unless it carries a column-0
`# dispatch: no inputs — …` line, and that check also wants the generated dispatch table in `docs/BOTS.md` regenerated
(`make dispatch-forms-report`). Adding triggers without them turns a two-line change into a red `ci-unit` — measured,
on a PR whose classifier half was already green.

Verify from the pushed ref, not the working tree: `grep -cE "^  (merge_group|workflow_dispatch):" .github/workflows/<f>.yml`
should be 2. Then prove the fallback by **behaviour, never by spelling**: `${{ github.base_ref || 'main' }}` and
`BASE_REF="${EVENT_BASE_REF:-main}"` are the same contract, and a grep or a test pinned to the first false-reds the
second — the shell form is arguably better because it logs *why* it fell back. Dispatch the workflow and cite the run:

```bash
gh workflow run <f>.yml --ref <branch>          # a real run id for the dispatch half
gh run view <id> --json status,conclusion       # plus: "No github.base_ref for event ...: reporting against main."
```

`merge_group` stays *"not exercised — no merge queue configured"* on a repo without one; that is a different sentence
from "impossible", and the difference is the whole reason to say it out loud.

## Pausing a fleet: cancelling is not free

An owner instruction like "only these two PRs should run" needs three steps, in this order, or the queue refills
itself:

1. **Disable the reactors first.** Every cancelled run emits `workflow_run`, so `auto-merge`, `run-failure-reactor`
   and `fix-bot` each spawn a run *because* you cancelled something. Twenty automation workflows is normal for this
   fleet; `gh workflow disable <id|name> --repo <o>/<r>` stops the cascade at the source.
   List what is callable and what is not before disabling: reusable ones
   (`on: workflow_call`, e.g. a shared `pipeline.yml`) must stay enabled or the workflows that call them break.
2. **Cancel what is live**, in passes, re-measuring between them — a cancel request is asynchronous and lands
   seconds later:

   ```bash
   gh run list --repo <o>/<r> --limit 400 --json databaseId,status,headBranch
   gh run cancel <id> --repo <o>/<r>
   gh api -X POST repos/<o>/<r>/actions/runs/<id>/cancel    # when CLI says nothing
   ```

   Keep a keep-set of head branches (the PRs the owner named) and re-filter every pass; runs created *during* the
   sweep are not in the first list.
3. **Record the rollback.** `gh workflow enable <id|name>` for each, and keep the disabled list in the report — a
   paused fleet with no written rollback is an outage.

**Collateral to state out loud, every time:** jobs cancelled inside a run that is otherwise green leave it
`completed/cancelled`, so the PR's build has no clean verdict even though 18 jobs passed, and a job cancelled by the
sweep also silences the repair path (`fix-bot` gates on `conclusion == failure`, and `cancelled` is not `failure`).
Repair afterwards with `gh run rerun <id> --failed`, not with a push.

## What a pause does to a monitor

A tally that reports `0 green · 0 owner-ready` during a pause is reporting the pause, not the code. Any report made
while runs are cancelled must say which zeroes are yours.
