# Reading a red correctly (added 2026-11-03)

Procedural wrinkles for binding a CI red to the head it actually ran on, learned while
triaging #1636 / #1627 runs. Read this before quoting a peer's "still red at current head".

## A run-URL under the wrong workflow path 404s; the job id is the durable key

`gh api repos/<o>/<r>/actions/workflows/<file>.yml/runs/<id>` returns `404 Not Found` when the
run belongs to a DIFFERENT workflow file. A `check-pr-closing` red surfaces as the `guard` job
under the **`CI`** workflow, not under `ci.yml`. Use the workflow-agnostic paths:

```
gh api repos/<o>/<r>/actions/runs/<id>          # the run
gh api repos/<o>/<r>/actions/jobs/<jobid>       # the job (resolves regardless of owning workflow)
```

Check a job's `name`/`conclusion`/`head_sha` from `/actions/jobs/<jobid>` rather than trusting the
check badge.

## "Still red at the current head" requires re-binding to the CURRENT PR head

A PR can advance between when a peer cites a failing run and when you read it. Measured: a cited
head `6cadd0b6` was an intermediate push; the live PR head was already `8d018a6e` with its own CI
`in_progress`. The cited run was genuinely red — but that is a statement about the OLD head, not
"red at current head".

Order of operations:

1. `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` — read the live head FIRST.
2. `gh api repos/<o>/<r>/actions/jobs/<jobid>` — confirm the cited job's head and conclusion.
3. Say exactly one of:
   - "red at `<cited sha>`" (real, historical) — if `cited == current`,
   - "current-head verdict unmeasured" — if the head advanced and the new CI is still running.

Never copy a peer's "still red at current head" without binding it to the head you just read. The
age of a measurement changes how you REPORT it, never whether it is true.

## A `workflow_run` consumer's check lands on the branch tip IT runs against — NOT the run it consumed

A verdict/reactor workflow (`on: workflow_run: workflows: ["CI"], types: [completed]`) runs on
`refs/heads/main` at the DEFAULT-BRANCH tip, and its check-run is posted against that tip — even
though the run it read and judged (`github.event.workflow_run.id`) was some OTHER branch's PR run.
Consequence: **a red `verdict` (or any `workflow_run`-consumer) check on `main` tip is not proof
that `main` is red.** Several such checks accumulate on one commit (one per consumed run, never
superseded), so a tip can carry green checks from main's own push run AND reds consumed from
unrelated PR-branch runs at the same time.

So when a peer says "the verdict is red at `<main-tip>`", do NOT read the check-run's `head_sha` as
the consumed head — for a `workflow_run` workflow the posting sha and the judged run are different
objects. Identify the run it actually consumed from the verdict's OWN log, which prints them:

```bash
gh run view <verdict-run-id> --repo <o>/<r> --log 2>/dev/null \
  | grep -oE 'RUN_ID: [0-9]+|HEAD_SHA: [0-9a-f]{40}' | head -2
# then read THAT run's event/head/branch/status and its per-job conclusions:
gh run view <consumed-run-id> --json event,headSha,headBranch,status,conclusion,jobs
```

Only after naming the consumed run can you say whether the red is real (`failure` on the consumed
run, e.g. it died before publishing a `ci-scope-decision` artifact → "no decision is RED"), or a
transient/other-lane artifact. To read the CURRENT state of a tip's consumer checks (all of them,
not one), list them on the commit:

```bash
gh api repos/<o>/<r>/commits/<sha>/check-runs \
  --jq '.check_runs[] | select(.name|test("verdict")) | "\(.conclusion) \(.started_at) \(.output.title//"-")"'
```

A green verdict whose `output.title` names a run id (e.g. `ci-verdict: green (run <id>)`) is the
honest signal that main's OWN post-merge run passed — report that, and do not let an unrelated PR
consumer-red on the same tip talk you into "main is red".

## A run is YOURS only when it binds to your PR — check `head_branch` and `pull_requests`

A green run at roughly the right time is NOT evidence for your PR. Runs are repo-wide objects, and
a query filtered by name / actor / created-time happily returns a sibling branch's run — one whose
unit job really did pass, but for a different branch, so citing it proves nothing and forces a
retraction on the wire.

Bind every run you intend to cite, before citing it:

```bash
gh api repos/<o>/<r>/actions/runs/<id> \
  --jq '{head_branch, head_sha, pulls:[.pull_requests[].number]}'
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha, branch:.head.ref}'
```

Cite the run only when its `head_sha` equals the live `pulls/<n>.head.sha` you just read, or
`.pull_requests[].number` contains `<n>`. A run whose `head_branch` names another branch is not
your verification, however green. Corollary for your own records: after any push, poll the run at
the NEW head — the run you were watching before the push judges a head that no longer exists.

When you find you already posted a wrong attribution, retract it on the same thread by direct
comment id, naming the run's real `head_branch`/`head_sha` and your PR's real state. A silent
re-post leaves the false record standing beside the truth.

## The failing log, not the badge, is the report

Open the job log and quote the actual failure line and exit code
(`gh api repos/<o>/<r>/actions/jobs/<jobid>/logs --allow-escape-sequences`). For `check-pr-closing`
the log ends with `[check-pr-closing] N violation(s)` + the per-violation reason + `Error 1` /
`##[error]Process completed with exit code 2`. A cancelled run also reads `fail`, and a job that
cannot load has zero jobs while every rollup reads clean — so always report from the log.
