# Distinguish concurrency-gated "pending" from a producer stall — read updated_at, never the status alone

Discovered 2026-11-06: a peer corrected my #1696 engine-build misread, and I verified the correction
on the wire before retracting. Lesson is a direct wire-read: for a workflow_dispatch/push run whose
`status` shows `pending` for an extended time, the single most load-bearing field is **`updated_at`**.

## The read

- `gh api .../actions/runs/<id> --jq '{status,conclusion,created_at,updated_at}'`
- If `updated_at` is pinned (≈ `created_at`, e.g. 10:16:06Z / 10:16:08Z) the run **never started**.
  It is NOT "transitioning" and NOT building — it is **queued behind a `concurrency` group** whose
  holder is still in_progress. It has been gated, whole time.
- If `updated_at` advances (minutes after creation), the run is genuinely progressing — a stall then
  has a different cause (producer not emitting cells / backend drop).

## Which gate

- Read the runner's own `concurrency:` block in `.github/workflows/<wf>.yml` (near the `group:` key,
  which is usually `format(...)`).
- The holder = the in_progress push/run that created the group. Read ITS jobs: the still-running
  cell (e.g. `engine-build-vllm-rocm` job, subprocess building) is what holds the gate.
- Documented class: engine-build push group (#917/#621) — push runs must not race on the same
  `:<arch>` tag; this is intended, authored behaviour, NOT a trigger-script defect.

## Consequences for verdicts

- A re-dispatch / trigger "repair" will NOT emit cells — a fresh push dispatch queues behind the
  SAME held group. Only the holder concluding (or owner cancel) frees the gate and lets the
  already-dispatched, already-gated run auto-emit.
- Do NOT report a concurrency-gated pending run as "producer stall" or "dispatch drop" — that sends
  the wrong owner to the wrong lane and cancels the right analysis. Check `updated_at` first.
- The verdict (unprovable) is unchanged by the attribution: no AC tick until a concluded run at an
  ancestor-of-the-required-head passes all-green.

## One-line rule

A run `pending` for hours with `updated_at ≈ created_at` is concurrency-GATED (never started), not
producer-stalled — verify `updated_at`, name the gate holder, and never recommend a re-dispatch that
will queue behind the same held group.
