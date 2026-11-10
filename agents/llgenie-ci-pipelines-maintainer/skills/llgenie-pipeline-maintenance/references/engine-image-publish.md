# Publishing a pinned engine image (and the concurrency trap)

> The same publish path reds differently for a **fork PR's** CI-image hash (read-only GHCR token,
> denial after the build) — see `references/fork-pr-image-publish.md`.

When `make check-engine-launchers` reds because a launcher demands an engine image
pin that is not yet in GHCR (e.g. `ghcr.io/.../vllm:5df63a72-...-cuda` resolves to
`manifest unknown`), the fix is **not** a local build. The pinned image is shipped
by the `engine-build` workflow, and you dispatch it with `push=true`.

## The publish dispatch

```bash
# acceptance path: build at the committed pin, test, push to GHCR
gh workflow run engine-build.yml --repo asimov-agent/llgenie \
  -f engine=vllm -f arch=cuda -f push=true
```

- `push` defaults to **false** (build-and-verify only). A run with the default flag
  will NEVER publish — completion of a `push=false` run does not clear a
  missing-image red. Read the workflow header's trigger-surface block; it spells out
  `push`, `force`, `engine`, `arch`, `model`.
- `force=true` + `push=true` rebuilds from a clean `--no-cache` and is how a tag is
  republished.
- Never build the image locally to "prove" it works: the pipeline header forbids it
  and the publish must happen through the workflow so the tag lands in GHCR with its
  digest == `:<arch>` tag verified by `test-published-engine`.
- After the run completes: confirm the pushed tag resolves and `make
  check-engine-launchers` returns rc 0 at a fresh head.

## The concurrency trap (zero jobs, pending forever)

`engine-build` serialises **same `engine`/`arch` selection** in one concurrency
(narrow dispatches run concurrently; publishing runs share a global group so two
pushes cannot race the same tag). Consequence: an earlier run for the **same
engine/arch** that is stuck (`status: in_progress` with `updated_at` frozen for many
minutes, its build job never reaching `completed`) HOLDS the group. Your new
`push=true` dispatch then sits `status: pending` with **`total_count: 0` jobs** —
indistinguishable from a dispatcher that does not work.

Diagnosis:
```bash
gh run view <NEW_ID> --json status,createdAt          # pending, old createdAt
gh api repos/OWNER/REPO/actions/runs/<NEW_ID>/jobs --jq .total_count  # 0
gh api repos/OWNER/REPO/actions/runs/<STUCK_ID> --jq '{status,updated_at}'  # in_progress, frozen updated_at
```

Do NOT cancel the stuck run yourself when it belongs to another lane — the live-run
rule holds even for a run that looks abandoned (a job that never starts and a job
cancelled mid-flight look identical from the alarm). Instead:

1. report the block on the issue with both run ids and the frozen `updated_at`;
2. message the lane that owns the stuck run to cancel it (or to say it owns the
   publish, in which case stand down rather than duplicate);
3. message the planner so the block has a consumer.

Only the run's owner cancels it; your queued publish then starts. A zero-job
`pending` run you dispatched is a block to report, not a failure to retry.
