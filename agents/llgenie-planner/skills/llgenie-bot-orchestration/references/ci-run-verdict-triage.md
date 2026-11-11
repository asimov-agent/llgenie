# Triage a CI run before you believe or re-dispatch it

Applies when you are reading a red/dispatch verdict on a `main` workflow (engine-build, ci-verdict,
registry-liveness, auto-merge sweep) and about to report it, re-dispatch it, or delegate it.

## `cancelled` is not a failed run — find the run that SURVIVED

A `workflow_dispatch` run that reads `cancelled` is usually **not** a failure. It is a concurrency casualty:
when several runs of the same workflow land in the same minute (engine-bump PR pushes + your own manual
dispatch + a parallel lane's dispatch), they collide on the workflow's global `concurrency.group` and one
sibling is cancelled — **even when `cancel-in-progress: false`** (a queued run can still be superseded/aborted
in the pile). Re-dispatching into that same burst only multiplies cancelled runs.

Before you re-dispatch or report a red:

1. List the workflow's recent runs and their verdicts:
   `gh run list --repo <owner>/<repo> --workflow <file> --limit 10 \
     --json databaseId,status,conclusion,event,createdAt`
2. Find the sibling still `in_progress` / `pending` (not the cancelled one).
3. Prove it is building the cell you need by reading its LIVE jobs:
   `gh api repos/<owner>/<repo>/actions/runs/<id>/jobs --jq '[.jobs[]|{name,status,conclusion}]'`
   (a running job name like `engine-build-vllm-rocm` is the proof it is the publish you wanted).
4. Cite THAT surviving run id in the tracking issue and monitor it — never the cancelled one.

Also check `gh api repos/<owner>/<repo>/actions/runs/<id>` for `.cancelledBy` — but note the field is
often `null`/"not visible" on a concurrency cancellation; the burst + sibling `in_progress` is the real
signal, not `cancelledBy`.

## Record the `head_sha` the run actually built, not the one you assumed

`gh workflow run <file> --ref main` resolves to whatever `main` was at dispatch time. `main` moves every
few minutes here, so a run's `head_sha` can be a commit NEWER than the one you meant (and, on a
concurrency pile-up, different from a sibling's). Read `gh api .../actions/runs/<id> --jq .head_sha`
and quote that sha in every report — never a remembered or assumed `main` sha.

## A `conclusion` is a verdict, not a cause

Before any dispatch/green/red claim, open the failing step's OWN log (run id + job id + head sha) and
quote its error line. If the run is still `in_progress`, say exactly: "error line not yet retrievable —
unlocks at run completion" and never invent a cause.

## When the run is a publish and the red is a missing tag

A registry-liveness red naming an un-published committed image tag is fixed by **publishing**, not by
re-filing the tracker. Dispatch the push build for that engine (`push=true`), confirm the surviving run
is building the right arch cell (above), monitor it to `completed`, then re-measure the liveness check
at the current head. Correct the tracking issue's first dispatch line if it was cancelled in a pile so
the board reflects the surviving run id.
