# Jobs sit in `queued` and never start: is it the label, or the account?

GitHub does **not** fail a job whose label matches no runner — it queues indefinitely. The symptom of
both causes is identical (runs that never conclude, checks stuck pending) and the two need opposite
responses, so do not switch labels before this distinguishes them.

## 0. First: did that label EVER run? (this one command often ends the investigation)

A job that *looks* permanently queued may have been **started and then cancelled**, which is a completely
different defect from an unprovisionable label. Read the timestamps, not the status:

```bash
gh api 'repos/O/R/actions/runs/<run>/jobs?per_page=100' \
  --jq '.jobs[]|select(.name|test("<family>"))|
       "\(.name)|\(.["labels"]|join(","))|\(.status)/\(.conclusion // "-")|
        started=\(.started_at // "NEVER")|completed=\(.completed_at // "-")"'
```

| what it shows | what it means |
|---|---|
| one row on the label `completed/success` | **the label provisions** — a label matching no runner cannot produce a green job, so the cause is capacity and/or cancellation, and no label change is warranted |
| rows with a `started_at` and `conclusion: cancelled` | they got a runner, ran for minutes, and were killed — a sweep, not a missing runner |
| `started=NONE` on every row, across several runs | now the label/capacity question is real; continue to §1 |

**The alarm cannot see this.** `queued_run_alarm.py` lists only rows that are *currently* queued, so a run
whose rows started and were later cancelled simply disappears from its output — leaving only the runs
that never got a slot, i.e. the label looks exclusively stuck. Treat "every long-waiting job carries the
same label" as a signal to run §0, never as proof.

## 1. The repo's own instrument answers most of it

```bash
python3 scripts/queued_run_alarm.py --repo asimov-agent/llgenie --minutes 10
```

It lists every job queued longer than the threshold with its **labels**, branch and run id.

| what it prints | what it means | what to do |
|---|---|---|
| every long-waiting job carries the SAME label (`labels=[macos-15-intel]`), while jobs carrying other labels are `in_progress` elsewhere | that label/OS has no runner, or the OS minutes are spent | the label is the defect — fix the workflow |
| long-waiting jobs carry SEVERAL different labels | the pool is saturated end to end | capacity, not a label defect |
| nothing listed, and `in_progress` runs exist | not a queue problem | look elsewhere |

## 2. Confirm the account is not globally stalled

```bash
gh api 'repos/O/R/actions/runs?status=queued&per_page=20'      --jq .total_count
gh api 'repos/O/R/actions/runs?status=in_progress&per_page=20' --jq .total_count
# per unfinished run, the shape of its jobs:
gh api 'repos/O/R/actions/runs/<id>/jobs?per_page=100' \
  --jq '[.jobs[]|.status]|group_by(.)|map("\(.[0])=\(length)")|join(" ")'
```

If **some** jobs anywhere are `in_progress`, the account is not hard-stalled — it is rationing, and the
discriminator becomes which labels get picked up. If **nothing** anywhere is `in_progress` while dozens
are queued, it is capacity/billing/outage: **change no workflow**, and say what the owner must fix on the
account.

## 3. The one-line probe (only when step 1 points at a label)

Cut a scratch branch off `main`, change **one** row's label, open a PR (ready-for-review — drafts are
banned fleet-wide, and a probe is no exception; you close it within the hour), and read the job that
tries to run there:

```bash
git checkout -b probe/<issue>-<label-b> origin/main
# ONE line: `.github/workflows/ci.yml`'s single `runner: <label>` line for that family
git commit -am 'probe(<family>): does <label-b> provision where <label-a> never starts?'
gh pr create --title 'PROBE (do not merge) …'        # never --draft

gh api 'repos/O/R/actions/runs/<id>/jobs?per_page=100' \
  --jq '[.jobs[]|"\(.name)|\(.["labels"]|join(","))|\(.status)/\(.conclusion // "-")"]|.[]'
```

Read it like this:

- **The probe's OTHER rows are also queued.** Nothing is proven yet: the run is waiting for capacity
  regardless of label, and a macOS row queued for ten minutes is still inside the normal provisioning
  lag. Wait past the youngest age seen for the stuck label (one that never starts shows tens of
  minutes; a working one starts within ~20).
- **The probe label picks up, the stuck label does not.** The label is not provisionable on this
  account — switch every row of that family in ONE commit, and cite the probe's run id in the body.
- **The probe label also never picks up.** Capacity/billing, or an offline self-hosted runner: report
  it, cite the probe, change nothing.

Close the probe PR once the job status is captured — it is evidence, not a deliverable — and keep the
diff to that one line: no step logic, no `make ci-<job>` target. Then undo ALL of it, because an evidence
branch is not a deliverable:

```bash
gh run cancel <probe-run-id>                       # a closed PR's run still holds a queue slot
git push <asimov-remote> --delete probe/<issue>    # both remotes: the names flip on this host
gh api -X DELETE repos/asimov-agent/llgenie/git/refs/heads/probe/<issue>
git worktree remove --force <probe-worktree>
```

## 3a. Prefer a SAME-RUN control over two probes (and check §0 first)

Two probes on two branches compare two different moments and two different queue depths, so a difference
between them proves little. Put the control in the SAME run:

```
probe  CONTROL <a versióned hosted label the repo already green-ran>   SUCCESS   3 s   runner "GitHub Actions …"
probe  <stuck label>                                                  queued 7+ min   runner=NONE
probe  <second stuck label>                                           queued 7+ min   runner=NONE
```

One run, one runner acquired in seconds, both candidate labels starved in the same minutes: **scheduling
works, the pool is not issuing, and no workflow edit clears that — it only moves the queue.** That is the
moment to stop labelling and ask the owner about billing/concurrency, not to try a third label.

Before building any probe, run §0: if a job on the stuck label already completed green, the label
question is answered and the probe would only measure capacity — which the alarm and the run's own
`started_at` already show for free.

## 3b. Distinguish LOAD from a queue DEFECT with the shape of the unfinished set

When asked whether the CI queue depth is itself a defect, measure the unfinished set's *shape*, not its size.
Read-only, no runner permission needed:

```bash
gh run list --repo O/R --limit 60 --json workflowName,status,headBranch \
  --jq '.[]|select(.status=="in_progress" or .status=="pending")|"\(.status) \(.workflowName) \(.headBranch)"' \
  | sort | uniq -c
```

| shape | verdict |
|---|---|
| a handful of `in_progress` on **DISTINCT branches** + one `pending` whose own jobs are `jobs=0` | **load / capacity** — a small fixed slot count fully used; the pending run is waiting its turn, not stuck |
| **many `pending` rows of the SAME workflow** | **defect** — a bot queuing behind itself (self-starvation); the tell that a queue alarm and `gh pr checks` both miss |
| a job sitting **> ~110 min** after starting | **defect** — likely an orphan/hang; a bounded wait is normal (1:45 is a legit `linux/unit`), an unbounded one is not |

Two corroborating reads: `95 of the last 100 runs completed` (draining ⇒ load signature, not backlog), and
`gh api .../actions/runners` — which returns **403** without a runner-read token, so say the slot count is
**inferred from shape**, never claimed as read. A shallow distinct-branch queue that drains as runs finish
is the fleet using its runners, not a defect to file; only the same-workflow-stacking or the >110-min job
is a real finding.

## 3c. A CANCELLED suite at the current head is UNTESTED — never green (the board's worst read)

`cancel-in-progress` kills each CI on a new push, so a PR's **current head** can carry only the four
sub-minute guards (`guard`/`scope`/`holds`) completed green while the matrix that actually proves the PR
**never ran**. `gh pr checks` then shows "0 failing checks" and the board calls it green — but the verdict
is **UNTESTED**, and an untested PR can merge. Resolve the CI run whose `head_sha` equals the PR's current
head and classify honestly; print the **run id and head sha beside every verdict** (a "cancelled" without
its id cannot be checked):

```bash
gh api "repos/O/R/actions/runs?branch=<ref>&per_page=10" \
  --jq '.workflow_runs[]|select(.name=="CI")|"\(.id) head=\(.head_sha[0:8]) \(.status)/\(.conclusion//"-") created=\(.created_at)"'
```

| run at the CURRENT head | verdict |
|---|---|
| `completed/success` | green |
| `completed/cancelled` | **UNTESTED (cancelled)** |
| `completed/failure` | red — name it, route to its owner |
| other conclusion, or no run for that exact head | **UNTESTED (no verdict at head)** |

**Recovery is `gh run rerun <id>` — it keeps the sha and produces a verdict.** A **push** cancels it
again (that is how one PR lost three heads in two minutes and its safety argument described a check that
never ran). Never push "to make CI run". This is the sibling of the cancelled-*scope* forging a ``skipped``
decision: a cancelled run is neither a pass nor a fail — the absence of a red is not a green.

## 4. Make the stall visible, whatever the verdict

The alarm only helps if its own workflow is enabled:
`gh api repos/O/R/actions/workflows?per_page=100 --jq '.workflows[]|select(.state!="active")|.name'`.
Say in the report whether it is enabled — a paused alarm is how a silent queue runs for hours.
