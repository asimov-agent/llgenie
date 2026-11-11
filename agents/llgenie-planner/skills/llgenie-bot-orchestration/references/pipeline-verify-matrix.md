# Per-pipeline verify matrix: N workflows → N provable tickets + a verified dispatch loop

**Trigger:** the owner asks "do we have an issue per CI pipeline so each can be re-tested by owner / collaborator / bot via manual dispatch" — i.e. pipeline *verification* coverage, not a defect audit. Answer by measuring first, then filing, then proving the loop on one instance.

## 1. Measure before answering; the answer may be "no"

```bash
gh api 'repos/<owner>/<repo>/contents/.github/workflows' --paginate --jq '.[].name'   # every workflow file
gh issue list --state open --limit 200 --json number,title,labels                      # what already exists
```

Distinguish the two kinds of pipeline issue before filing anything: a **gate-coverage / defect audit** ("this gate cannot see X") is not a **verify ticket** ("prove this workflow runs correctly when dispatched"). If the board has only the former, the honest answer to the owner is "that set does not exist" — say so with the counts.

## 2. Enumerate from the tree, never from memory, and reconcile EXACTLY

Build the workflow list from the API/tree (`git ls-tree origin/main .github/workflows/`), not from a remembered dict. A remembered map drifts (renamed files, API-only deleted workflows), and it will silently miss or invent one.

Normalise with a real basename (`os.path.basename(p)` / `p.split("/")[-1]`-style is fine *only* on the full path — a hand-rolled `x.split("/")[-1]` applied to an already-basename string re-joins its characters and produces garbage keys that abort the run).

**Reconcile both directions before creating any issue:**

```python
assert set(dict_keys) == set(tree_names)   # report both diffs explicitly
```

Both set differences must be empty; print them (`keys-in-tree`, `tree-in-keys`) rather than a bare assertion so a mismatch names the offender. Only then create.

## 3. One ticket per workflow, canonical six-section shape

Title pattern: `ci(verify): prove <workflow-file> works as intended via manual dispatch`. Label `continuous-improvement`.

Body MUST use the repository's **canonical** headings, in this order, `## Technical` LAST — the `issue_body` gate rejects anything else (see `references/issue-body-canonical-gate.md` for the full gate rules):

- `## Problem` — what "works" is unproven for this workflow
- `## Why it matters` — the consequence of the gap
- `## How we fix it` — dispatch via `gh workflow run` from Actions; read the completed run + jobs (this is the old `## Proposal`)
- `## Benefit` — what closing it buys
- `## Acceptance criteria` — every item a `- [ ]` checkbox row, never a numbered `1. 2. 3.` list (the gate requires checkbox rows; a numbered list fails as "Acceptance criteria is missing"). One row per outcome: a completed run id, its conclusion, which guard/jobs passed, and — if red — that the red names a real defect.
- `## Technical` — evidence location / run-id log, ownership note (verification by owner/collaborator/bot in the normal queue; fixing any defect found routes to the owning lane), and Related refs.

**Do NOT invent extra `##` sections.** The gate treats any `##` heading that is not the canonical set (plus an allowed `## Not covered`) as `unknown section(s): \`## ...\`` and fails the whole body. Evidence, ownership, ledger lists and Related are NOT their own `##` headings — fold them under `## Technical` (as bold label paragraphs, e.g. `**Ledger — …:**` followed by the `- [x]` list). This was the specific defect that failed the whole ci(verify) marriage: the bodies used `## Proposal` / `## Acceptance` / `## Ownership` / `## Related` and a separate `## The N tickets` heading.

Verify the shape locally before posting and on the live wire after:

```bash
python3 -c "import sys;sys.path.insert(0,'scripts');import issue_body;print(issue_body.missing(open('<body>.md').read()) or 'NONE — gate-clean')"
````

Read one issue body back as a sample to prove the shape survived the CLI.

## 4. If every ticket cites an umbrella, the umbrella must exist

Tickets that reference a "verify-matrix umbrella (N tickets)" in Related create a dangling reference when no such issue exists — the matrix then has no at-a-glance status surface. File the umbrella: checklist of all N tickets, the dispatch-verify loop definition, the acceptance (a ticket is verified only when it carries a `verify` comment citing a completed run id), the close condition (all boxes checked), and ownership. Put the ticket list under `## Technical` as a bold-labelled ledger, NOT a `##` heading (see §3 unknown-section pitfall).

**Ledger ticks are verify state, not filing state — never un-tick without evidence.** A `- [x]` row means that ticket carries a `verify` comment; confirm a couple directly (`gh api --paginate repos/<o>/<r>/issues/<n>/comments --jq '.[]|.body' | grep -c verify`) before trusting the ledger, and if they hold, PRESERVE the ticks — un-ticking an honest ledger destroys real state (the inverse of the fabricated-pre-tick trap on an in-progress issue, where untraceable `[x]` criteria SHOULD be un-ticked). A buggy count loop (`gh api --paginate … | paste -sd+ | bc`) under-reports paginated comments — prefer `grep -c verify` on the concatenated bodies.

## 5. Prove the loop end-to-end on one pipeline — and read the result before calling it broken

Dispatch a **read-only report sweep** first (a gate that reports and never mutates: an arms/holds-style alarm). Never prove the loop with a workflow that merges, arms auto-merge, cancels runs, or deletes branches.

```bash
gh workflow run <wf>.yml --ref main && sleep 20 && gh run list --workflow <wf>.yml --limit 1 --json databaseId,status,event,headSha
gh run view <run> --log --job <jobid>      # job-scoped log; /actions/jobs/<id>/log answers 404 — it is /logs and needs curl -L
```

### REST-dispatch quirks (`gh api …/dispatches`)

- **`ref` is a branch or tag, never a commit sha.** `-f ref=<40-hex>` returns `422 No ref found for: <sha>`.
  Dispatch against the branch (`-f ref=main`) and read the run's `headSha` back — it is whatever `main`
  was at that instant, which may be **newer** than the sha you last measured. Confirm `headSha` before you
  reason about the run.
- **Input keys must be declared in `workflow_dispatch.inputs`.** Sending a key the workflow does not
  declare (even a plausible one) returns `422 "<key>" is not a permitted key`; it is not silently dropped.
  Read the real input names from `git show origin/main:.github/workflows/<wf>.yml` first, and omit any
  input whose default already matches what you want (a verify sweep usually wants the `push=false`
  default — sending nothing is correct).
- A dispatch whose HTTP call returns empty/`204` is accepted; it is not the fact. Confirm with
  `gh run list --workflow <id> --limit 1` that a fresh run id appeared.
- **`run.inputs` is `null` in the Actions API for `workflow_dispatch` runs.** Neither the run object
  (`actions/runs/<id>`), `jobs`, nor `gh run view --json inputs` exposes the inputs you dispatched
  (`gh run view` rejects `inputs` as "Unknown JSON field"). You therefore CANNOT read `engine`/`arch`/`push`
  back from the run itself, and a 0-job pending run cannot tell you either. Confirm the dispatch parameters
  from the dispatcher's own start/bookend comment, or wait for jobs to appear and read the cell name
  (`engine-build-vllm-cuda` vs `-rocm`) — never infer arch/push from the workflow name alone.

### Verify the AC's ARCH/PUSH axis before accepting a producer as its evidence

A run only satisfies an acceptance criterion whose `engine`/`arch`/`push` axis it actually matches. Before
letting a lane tick ACs on "the new-head producer":

- Read the AC text — `#1694-AC2` wants a **rocm** COMPLETED-SUCCESS run (`engine-build-vllm-rocm` job);
  `#1558-AC2` wants `arch=rocm push=false` green; `#1558-AC3` wants `arch=rocm push=true` publish; `#1832`
  AC1/AC2 want **cuda**. A `cuda push=false` run (a verify run, not a producer, concurrency group
  `engine-build-build-vllm-cuda` — NOT `engine-build-push`) satisfies none of the rocm ACs.
- A `push=false` run is never a producer and is never queued behind a `push=true` producer's cell — different
  concurrency group. "Pending 0 jobs behind the producer" is a misread; it is pending for runner availability.
- Ticking a rocm AC on a cuda run is a false write-back (the #745 class). Correct it durably on the issue
  before any tick and DM the reviewer.

### Sequence an arch/engine-specific evidence run AFTER the rebase, at the post-rebase head

A run binds only the head sha it ran at. If the PR still owes a rebase (base `behind_by > 0` vs live
main, even when `mergeable=True` — a clean 2-commit catch-up is still a rebase owed), an arch-specific
evidence run dispatched at the PRE-rebase head is superseded the instant the rebase force-pushes: the
new head has no run at it and the AC is void again. So the order is fixed:

1. **Confirm whether a rebase is owed first** — `merge-base --is-ancestor <base> <live-main>` + `rev-list
   --count <base>..<live-main>`. `mergeable=True` says no CONFLICT; it does not say the base is current.
2. **Land the rebase** (rebase lane, sole refresh owner) onto live main, force-push with
   `--force-with-lease --force-if-includes`, and read the new head sha back.
3. **THEN dispatch the evidence run at the post-rebase head** — never "authorize a run at the current
   head" while the rebase is still owed; that authorization is superseded before it can be credited.

When you authorize such a run, write the gate into the authorization itself: "dispatch at the
post-rebase head, not the pre-rebase `<sha>`." A bare "go ahead and run rocm" reads as "run it now" and
the lane will bind it to the stale head.

**A red is not automatically a pipeline defect.** Read the failing step's own output: a gate that fails *naming a real board state* (e.g. finished PRs that carry no auto-merge) is a **correct red** = PASS for the pipeline. Verify the named objects actually hold that state before recording it. Only a gate that fails while the board is clean is a defect.

## Do NOT dispatch a producer while one is already LIVE at the head (double-burn guard)

Before `gh workflow run`-ing a producer to *prove* a fix, sweep the runs at that head — a second dispatch of a
full matrix at the same head burns every cell twice for identical inputs (the one-vehicle rule, #824, at the
workflow layer). The implementer handoff ("dispatch a fresh engine-build for #N") can be stale by the time it
reaches you:

```bash
gh run list --workflow <wf>.yml --limit 10 --json databaseId,status,conclusion,headSha,createdAt \
  --jq '.[]|select(.headSha|startswith("<head8>"))|{id:.databaseId,status,conclusion}'
gh run view <id> --json status,conclusion,headSha --jq '{status,conclusion,head:.headSha[0:8]}'
```

- **A run `in_progress` at the same head == do NOT dispatch.** Record the de-dup call on the tracker (durable
  comment naming the live run id + head), and let it conclude — a second manual dispatch is waste, not progress.
- **A post-conclusion fresh dispatch is the AUTHORING/ci lane's call on a genuinely-new head**, not the planner's,
  and never a re-dispatch at the same head (it re-reds identically). The planner holds; it does not dispatch a
  duplicate producer.

## A `cancelled` run binds nothing — never a verdict, and re-point acceptance bound to it

A run that concluded `cancelled` proves neither green nor red for the fix; any acceptance criterion bound to it
binds nothing, exactly like an un-run. Two consequences:

- **Never read `cancelled` as failure or success.** Measure `gh run view <id> --json status,conclusion` —
  `conclusion: cancelled` is a void gate, not a wall. Record "cancelled, binds nothing" with the run+job id.
- **A tracker re-pointed to a run that later got cancelled is stale AGAIN — re-point it at the live run.** When an
  earlier planner re-scope bound a monitor/tracker's acceptance at run `R` and `R` is now cancelled, the acceptance
  has drifted back to void; post a second re-scope naming `R`'s cancellation and the live producer that supersedes
  it (with a read-back on the comment id). Do not leave acceptance pointing at a cancelled run.

### Sweep health in two reads — counts, not the parent badge

A multi-cell matrix run's own `status` stays `in_progress` until every child ends, so "the run is not done"
tells you nothing about whether it is draining clean or filling with reds. Read the children directly, twice:

```bash
R=<run-id>
gh api repos/<o>/<r>/actions/runs/$R/jobs --jq '[.jobs[].status]|group_by(.)|map({(.[0]):length})'
gh api repos/<o>/<r>/actions/runs/$R/jobs \
  --jq '.jobs[]|select(.status=="completed" and .conclusion!="success")|"RED: "+.name+" "+.conclusion'
```

The first gives `[{completed:N},{in_progress:N},{queued:N}]` — a shrinking `queued` with a growing `completed`
is draining in the runner pool; a frozen `queued` with a flat `completed` is a runner-starvation stall (and a
parallel run stuck `pending` with 0 jobs is the same signal — do not read it as a broken dispatch). The second,
empty, is the all-green proof even while the sweep is still in flight; quote the counts and the fact that the
red query returned nothing, not the parent run's badge.

### One failed cell makes an all-cells-green gate deterministically RED — record now, do not wait for the sweep to conclude

When an acceptance criterion requires the WHOLE matrix green, a single `completed`/`failure` cell
already settles it: no still-`in_progress` sibling can turn a failed cell into a success, and the
conclusions of the cells that already finished are final. The gate is therefore unmet **now** — the
verdict, and any "record the not-all-green outcome" obligation, is owed immediately, not gated on the
remaining cells draining. Waiting for the parent run's `status: completed` burns a pass and lets a lane
claim "awaiting the sweep" over a decision already made. State it explicitly: "the failed `<cell>` cannot
pass; the sole in-flight `<other-cell>` is unrelated to that failure and cannot flip the requirement, so
all-green is irrecoverable for this sweep." (Do not confuse this with sweep *health* — see 'Sweep health
in two reads' — draining clean is a different question from whether the verdict is already determined.)

### A cell running past the wall-clock at which a sibling was killed is at the SAME infra-shutdown risk — not a build defect or a hang

Compare each in-flight cell's elapsed time against the cells that already ended in the SAME run. If a
`success` sibling finished at ~14 min and another sibling ended `Killed` / exit 143 ("runner received a
shutdown signal… manually started runner is canceled") at ~40 min, a still-`in_progress` third cell now
past 40 min is **not** automatically a hang or an engine-build failure — it is in the same runner-shutdown
risk class and will likely die the same way. Measure `elapsed = now − job.started_at`, and read
`job.steps[]`: a cell sitting at step N/total with the later steps `pending` and no `updated_at` is
*progressing*, not stalled (pending final steps is normal until the job finishes).

- **`exit 143` / "runner received a shutdown signal" is an INFRA kill, not a build red.** State it as such
  ("cell killed by runner shutdown mid-download at step X — not an engine-build defect") so the sweep's
  not-all-green is not misattributed to the fix under test.
- **The sibling-kill elapsed time is the baseline for predicting the next kill.** A cell exceeding the
  wall-clock at which a sibling was infra-killed is infra-risk; record the comparison ("47 min vs sibling
  14 min green / 40 min infra-killed → same shutdown class") as the honest diagnosis.
- **Do not cancel the slow cell to "clear the queue".** A job that never starts and a job cancelled
  mid-flight look identical from an alarm; finishing one matrix beats freeing slots, and a cancel voids the
  evidence the run exists to produce.

## Discipline

- Every verify record carries the run id, job id, workflow head sha and the workflow file — a conclusion without an id is a claim about time.
- Record the evidence as a `verify` comment on that workflow's own ticket and read the comment id back from the API; then log the pass.
- Never arm auto-merge or merge from the planner seat while proving a loop: the planner verifies, it does not close the deal.
- "Tickets exist" is not the deliverable the owner asked for — a dispatch that ran and whose output you interpreted is.
