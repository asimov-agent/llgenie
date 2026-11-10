# Adjudicating a force=true publish run

## Quote the FULL job matrix, never a subset
`guard` + `matrix` completing green does NOT mean the run is green — they are the first two
jobs of a 29-cell matrix. Read every job's `status`/`conclusion`
(`GET /actions/runs/<id>/jobs?per_page=100`) and quote the whole tally. Reporting guard+matrix
as "the run is green" while build/verify legs are red is a subset-verification error that
gets corrected publicly — always enumerate all legs.

## A run can end `cancelled` — a cancelled sweep is NEITHER an all-green witness NOR a complete red

The run object's `conclusion` is a verdict, not a cause, and `cancelled` is a third verdict besides
success/failure. A default sweep killed mid-flight leaves a MIX: the cells that had already finished keep
their real `success`/`failure`, while the cells still building read `cancelled`. So always enumerate the
per-cell tally — `gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '[.jobs[]|{name,conclusion}]'` — and never
judge from the top-level `conclusion` alone. Rules for the verdict:

- A **`failure` cell that completed** still carries valid evidence AT that head: route it with its job id +
  the quoted error line from the run the failure was measured in.
- A **`cancelled` cell proves nothing** — not failed, not "still needs a rebuild", not a re-confirmation of
  an earlier root. Only a fresh un-cancelled run at that head can re-validate it. Do not carry a prior
  run's classification forward as if the cancelled cell had re-manifested it.
- Report the run as `cancelled, per-cell: N success / X failure / Y cancelled` and state the AC is
  UNPROVEN. Do not round it up to "all-green" (it panics a merge) or down to "N red" (it over-reports and
  re-opens closed findings).
- Establishing WHY it was cancelled: list recent dispatches (`actions/runs?event=workflow_dispatch`) — if a
  NEWER engine-build run exists, concurrency superseded it; if none does, it was killed externally (an owner
  stop or concurrent PR traffic). A cancellation timestamp coinciding with some PR's `updatedAt` is the tell
  that external traffic killed it. Never re-dispatch a full `engine="" arch=""` sweep merely to "clear" a
  cancelled run.

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

## Comparing a red cell against green siblings in the SAME run — the comparison IS the measurement

When cells of one engine-build run disagree (one engine's cuda/rocm red while every other cell stays
green), "why does this one fail?" is answered by diffing the cells, not by inspecting the diff again.

- **Pull every cell's log with `gh api repos/<o>/<r>/actions/jobs/<jid>/logs --allow-escape-sequences`.**
  The plain form lands a ~99-byte escape-suppressed file that looks like an empty log; the flag yields the
  real text (see `references/ci-run-watching.md`).
- **Build the authoritative step order from a GREEN cell's log, not from the workflow YAML:**
  `grep '##\[group\]Run ' <green>.log` lists the steps actually executed, in order — e.g. checkout →
  setup-buildx → docker login → `make build-engine` → test-image-pull → setup-uv → `test-engine-stage` →
  `push-engine` → `test-published-engine` → `test-engine-image` → `test-engine-install` →
  `test-engine-host`. Diff each red cell against that roster to find the FIRST step that diverges.
- **Classify each red by the STEP it died on, never by cell colour.** A `build-engine` /
  `engine_runner.py install` red is a build defect; a `test-engine-install` red whose log prints
  `[install] FAIL cuda host without the NVIDIA CDI spec` is a **GPU-less-runner infra red** (its image
  built and tested green first — own it to the pipeline/runner lane, do not weaken the CDI check); a
  `test-engine-image` / `test-published-engine` red is a publish/registry defect. **A red at a LATER
  stage than the one under investigation is not corroboration of it** — an install-leg infra red in the
  same run says nothing about whether a build defect exists, so do not count it as evidence either way.
- **The prime divergence suspect for a source-build engine is the `uv pip install --no-build-isolation -e .`
  layer inside `build-engine`.** Sibling GPU engines that install prebuilt wheels share no such layer,
  which is exactly why they stay green while the source-build rows red.
- **Post the interim measured note while the slow cells build; post the final diff only at conclusion.**
  Record the stages, which cells are still `in_progress`, and the comparison inputs already on disk; never
  quote a still-running cell's outcome, and never present the interim note as the verdict.

## Classify a red from ITS OWN run's log, then route it to a tracker whose SCOPE matches
A log line seen in an earlier run of the same cell is a witness, not the cause: a cell that
failed on a `poetry`/pyproject build-backend slip in run A can die of a plain cold-build SIGTERM
in run B. Read the CURRENT run's own failed-step log and quote its line before naming a root.
Then route by ROOT CLASS, not by "it is red, it goes where the other red went" — each class has a
different fix owner and a different tracker:

- dependency/build-backend resolution (`poetry` / `pyproject` / `uv` build) → the build-deps tracker
- registry credential / cache-push 403 → the GHCR-login tracker
- cold build killed mid-flight, `wait: No child processes`, exit **143** (SIGTERM / runner shutdown) → the
  cold-build/slow-build tracker (the cross-cell comparison one), NOT the credential tracker and NOT the
  build-deps tracker

Before appending evidence to a tracker, read that tracker's stated scope (its title/body) and confirm
it owns the class. Evidence filed on a tracker whose scope is a different class reads as a duplicate
and gets corrected publicly; a mis-routed cell is also how a real root goes unowned.

## A dispatched red with an INFRA root owes a named-cause verdict, not a fabricated code PR

A dispatch that asks you to "make the cell build" or "fix it or name the cause" does NOT oblige a code
PR when the measured root is infra-class (a never-published tag forcing a cold build that is then
SIGKILLed; an OOM/capacity wall; a runner death). The honest completion is the NAMED CAUSE: read the
cell's own log, quote the verbatim line (the `manifest unknown` pull, the `make: *** … Killed` + exit
code), state which infra class it is, and post it on the issue — then route the fix to its owner. Do
not manufacture a params/Dockerfile edit to have "a PR": it shifts the content-addressed tag mid-flight
and fabricates a fix for a cause that is not in the file. When the only levers are out of this lane's
scope (pin bump, gate weakening, another lane's builder/cache infra), the deliverable is the verdict +
route, and the issue stays OPEN until the owning infra change lands and a fresh run proves green.

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

- **Adding an env var to a variant MOVES that variant's tag and forces a full rebuild.** `env` lives in
  the variant params block, so a `UV_HTTP_TIMEOUT`/`VLLM_*`-style addition re-tags the cell even when the
  install steps are byte-identical. Expect a NEW artifact (and a cold build), not a cache hit — and do not
  read "the install list did not change" as "the image is the same one".
- **Attribute a green→red boundary by hashing the variant block at both heads, not by eye.**
  `git show <sha>:containers/engines/params/<id>.json` piped through
  `json.dumps(variants[<v>], sort_keys=True)` then sha256 gives a per-variant fingerprint; equal at the
  green and red heads means the artifact did not change and the red is environment/timing, not the diff.
  Diff the whole input path set (`containers/engines/params`, `dockerfiles/`, `entrypoint.sh`,
  `scripts/engine_runner.py`) to separate the variant under test from siblings — a branch touching only
  rocm/cuda leaves the cpu tag identical.

## Polling a producer run: a 404 body parses as a run and matches NO terminal branch

`gh api repos/<o>/<r>/actions/runs/<id>` on a 404 prints the error body to **stdout** with rc 1:
`{"message":"Not Found",…,"status":"404"}`. `json.loads` succeeds, so a poll loop receives a dict whose
`status` is the string `"404"` — matching none of the terminal branches (`pending`/`queued`,
`cancelled`/`skipped`, `success`, `completed`). The wait then runs its whole wall-clock bound and fails
with `never concluded, last status 404`, on a producer that may already have SUCCEEDED.

- **Treat a 404 as a visibility race and re-resolve; never as "not concluded".** The run LIST
  (`/actions/runs?per_page=100`, filtered to the id) carries the same `status`/`conclusion` fields, so read
  the verdict from there when the single-run endpoint 404s.
- **Keep the `404` verdict when neither endpoint resolves the id**, so the eventual failure can NAME a
  poll-visibility race — an indistinguishable `None` reads exactly like a real build failure.
- **Print the re-resolution** (a recorded-decision line, never a silent fallback): a silent fallback cannot
  be told apart from a run that was simply visible all along.
- **A hermetic proof needs both endpoints modelled** — a fake `gh` answering 404 on `/actions/runs/<id>`
  while the list still reports the run as `success`, plus a case where the id is absent from both. The
  success-path test should pass a FAR wait bound (so unfixed code visibly hangs rather than silently
  passing); take the RED proof from the instant `--wait-min 0` expiry case, which reproduces the issue's
  own message.

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
