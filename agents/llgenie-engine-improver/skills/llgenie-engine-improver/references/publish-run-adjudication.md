# Adjudicating a force=true publish run

## Quote the FULL job matrix, never a subset
`guard` + `matrix` completing green does NOT mean the run is green — they are the first two
jobs of a 29-cell matrix. Read every job's `status`/`conclusion`
(`GET /actions/runs/<id>/jobs?per_page=100`) and quote the whole tally. Reporting guard+matrix
as "the run is green" while build/verify legs are red is a subset-verification error that
gets corrected publicly — always enumerate all legs.

## Classify each leg by WHICH step failed — it changes what "published" means
The publish job runs, in order: `build-engine` → verify gate (`test-engine-stage TEST=detect`)
→ `push-engine` → `install-leg` / host-verify. The step that failed decides the verdict:

- **`build-engine` failure** → the image was never built (real publish-path defect).
- **verify gate red** → `push-engine` is SKIPPED → image is NOT published (acceptance gap).
- **`push-engine` success, later `install-leg` red** → the image IS in GHCR; the red is
  verify-class only.

Acceptance (`make check-engine-launchers`, N ok) needs only the host-cuda image **tags present
in GHCR**. Verify-class reds do NOT fail acceptance; a skipped push DOES. So a run can be RED
overall yet still satisfy acceptance once the host-cuda pushes land — and a green build with a
red detect gate leaves the tag missing. Never equate run-red with acceptance-red, or run-green
with acceptance-green.

## You cannot read buildx layer output from a live run
Per-job logs 404 / truncate while the run is `in_progress`; the Actions log captures the `make`
passthrough echo, NOT docker buildx layer output, even after the job completes. Do not keep
re-polling for the build stack trace — it will not appear. Wait for the job to settle, then
reason from the step conclusion (which step failed) rather than an unrecoverable error.

## Did a tag move between heads? Diff the four hash inputs, not per-engine loops
An image tag hashes four inputs: the variant params JSON (canonicalized/sorted) under `params/`,
`dockerfiles/<id>/Dockerfile.<variant>`, `containers/engines/entrypoint.sh`, and
`scripts/engine_runner.py`. To prove a later main head publishes the SAME tags:
`git diff --stat <old>..<new> -- params/ dockerfiles/ containers/engines/entrypoint.sh scripts/engine_runner.py`
— an empty diff means identical tags for every engine, conclusively. Per-engine hash loops trip
on variant-name assumptions (some engines have no cuda/vulkan variant); the whole-path git diff
is authoritative and covers all engines at once.

## Do not fix on a disproven theory
Editing a params JSON "because the build deps look missing" shifts the content-addressed tag
mid-flight AND fabricates a wrong fix. Verify the theory against the committed files first — a
source-build engine may already list `setuptools-rust`/`wheel`/`cmake` in
`requirements/build/*.txt`, so "missing build-backend deps" is pre-satisfied and NOT the cause.
If unproven, the honest, verifiable mutation is the change-record note+fragment (see the
change-record gate), not a blind params edit. Polling is not a mutation; the guard will fire
when you read instead of act. The one honest action available on a red run is the accurate,
non-green change record.

## A publish-order red has a two-step close: publish, then re-run the gating run

When main is red because a bumped pin's image was never published, the red is the pipeline's own
publish-order test ("every image an install row pulls is published"). Closing it is NOT a code change:

1. **AC1 — the tag exists.** Dispatch `engine-build` `push=true` at `ref=main` (it is
   `workflow_dispatch`-ONLY, so no merge ever publishes on its own), then probe the exact awaited tag:
   `scripts/ghcr_publish_probe.sh <leaf> <pin[:8]>-<hash[:8]>-<variant>` → `PUBLISHED`. Compute the
   awaited hash from a clean worktree at the very sha being published, never from the dirty primary
   clone — the tag hashes the four committed inputs, so a stale tree yields a tag that does not exist
   and a probe that reads ABSENT for a correct build. **Compute one hash PER VARIANT**: the Dockerfile
   input is per-variant, so the `<hash[:8]>` differs across cpu/cuda/rocm/vulkan — probe
   `scripts/engine_image_tags.sh <engine-id> <worktree> --probe` and never carry the cpu hash onto a
   sibling (a sibling 404 from a reused hash proves nothing).
2. **AC2 — the gate goes green at the same head.** `gh run rerun <red-run-id> --failed`, confirm the run
   flips to `in_progress`, and quote the green run id. Only the CPU install row needs the CPU tag, so
   the CPU cell reaching its push step is enough for AC1 even while cuda/rocm cells still build; do not
   hold the verdict hostage to the slow cells, and do not quote a measured number from the still-running
   run.

Report AC1 and AC2 as two separate facts with their own evidence (probe output, run id). "Publish
dispatched" is not AC1 and "rerun queued" is not AC2.

## Background watchers: absolute gh path, explicit cwd, verify a tick
A watcher launched with a stale/persisted cwd or a bare `gh` in a non-login shell dies silently
with no log. Launch with the absolute `gh` path and an explicit `cwd`, then read the log back to
confirm at least one tick before trusting it owns the settle.
