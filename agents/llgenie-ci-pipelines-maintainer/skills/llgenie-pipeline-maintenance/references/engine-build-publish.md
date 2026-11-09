# Publishing a pinned engine image (the vllm 5df63a72 class)

## The publish path
- The ONLY way to ship a pinned engine image is the CI workflow, never a local build:
  `gh workflow run engine-build.yml --repo asimov-agent/llgenie -f engine=vllm -f arch=cuda -f push=true`
- `push` defaults to **false**. A `push=false` run is build-and-verify ONLY — it never
  pushes to GHCR, so a "successful" push=false run does NOT close a missing-pinned-tag gap.
  Always dispatch with `-f push=true` to publish.
- Expected tag for pin `5df63a72` = `ghcr.io/asimov-agent/llgenie/vllm:5df63a72-<variantarch>-<arch>`
  (e.g. `...-0ddd57cc-cuda`). Verify with `docker manifest inspect`; missing = `manifest unknown`.

## Cache write-back: a `push=false` cell recompiles cold every run unless it WRITES the layer cache

A build-and-verify cell (`push=false`) already reads a registry layer cache
(`--cache-from type=registry,ref=<name>:buildcache`), but if nothing WRITES that ref, the cache is empty
on every fresh `ubuntu-latest` runner and the whole compile is redone from zero each run — the cold-wall
class that pushes a first rocm/vllm build past the job `timeout-minutes` with no test ever reaching a summary.

The write half is ONE flag on the non-push branch, and it must be GATED so a fork can never publish:

- `scripts/engine_image.py::_buildx` appends `--cache-to type=registry,ref=<name>:buildcache,mode=max` on
  the non-push branch ONLY when `LLGENIE_CACHE_WRITE=1`.
- Only the owner-guarded build job sets `LLGENIE_CACHE_WRITE: "1"` — it already carries
  `packages: write` and logs into GHCR, so it is the one cell that can write. A PR / fork / local runner
  never sets the flag and stays strictly read-only (fork heads get no repo secrets — `#155`/`#638`).
- The regression test drives `_buildx` WITH and WITHOUT the flag: the read-only default is as load-bearing
  as the write, and the assert is on the flag branch, not the shell spelling.

Two things worth stating in the PR body:

- The write warms the **NEXT** run of the same cell, not the current one — a first cold compile has nothing
  warm to reuse. So cache write-back is the verdict-INDEPENDENT half of a cold-wall issue: it lands safely
  under a moving engine tree while a first-completion verdict (an arch trim, a cap raise) is still being
  measured, and its merge is held only if that verdict can move the same files.
- Never gate the write to `push=true` only, and never to a trigger type. The build-and-verify cells are
  exactly the ones that need a warm second run, and a privileged ENV flag (set only by the owner-guarded
  job) is what keeps the write reachable from the base repo but never from a fork.

## The concurrency deadlock (#621 class) — measured 2026-11-01
- engine-build serialises runs of the SAME engine/arch selection in one concurrency group.
- A stuck or abandoned `push=false` run of `engine=vllm arch=cuda` (status `in_progress`,
  `updated_at` frozen for tens of minutes, publish job never started) HOLDS that group.
- A fresh `push=true` run of the same selection then sits `pending` with **zero jobs**
  — indistinguishable from a dispatcher that does not work. This is the #621 class:
  "created with zero jobs and no runner — indistinguishable from a dispatcher that does not work."
- Remedy: the stuck run's OWNER must cancel it (never cancel another lane's live run yourself);
  or that lane takes the publish and you stand down rather than duplicate. Then the queued
  push=true run starts on its own.

## Ownership read (which lane owns a publish gap)
- A missing pinned-image tag is a CI-publish concern, not a pipeline-file defect — but the lane
  that FILED the issue often disclaims it in the body ("pipeline lane's CI-publish matter").
- When the filing lane disclaims publish and its own publish run is frozen, the publish vehicle
  is legitimately the pipeline lane's: the planner's re-dispatch plus the filing note both point there.
- Never re-claim over a genuinely LIVE run of another lane; a frozen (updated_at stuck) run is not live.

## The trigger's reuse rule is DISPATCH EFFICIENCY — it never satisfies a head-sha-bound acceptance criterion

`scripts/engine_build_trigger.py` will skip a re-dispatch when a producer for the same pins already
exists. Two functions decide it, and reading them wrong is how a lane talks itself into "no fresh
build needed":

- `_params_match(sha)` — true when the diff of `containers/engines/params` between that run's
  `head_sha` and HEAD is empty. A commit-message-only rewrite or a rebase that touches no params
  matches. Its own docstring states its purpose: *"Reusing that producer avoids a second multi-hour
  build of the same pins."*
- `_reusable_producer(...)` returns a run only when it is still active
  (`queued|in_progress|waiting|pending|requested`) **or** `conclusion == "success"`. A completed run
  whose conclusion is `failure` is **not** reused, regardless of params.

So adjudicate two different questions separately:

1. **"Will the trigger re-dispatch?"** (mechanism) — yes exactly when no active-or-success producer
   exists. If the only same-params producer is heading to `failure`, reuse does not apply and the
   queued trigger (whose group releases when the holder concludes) auto-dispatches a FRESH producer at
   the current head. No manual `gh workflow run`, no rerun — the design provides it.
2. **"Does an existing params-identical producer satisfy the issue's acceptance criterion?"**
   (evidence) — NO when the criterion is head-bound. Text like "head sha bound", "COMPLETED-SUCCESS
   at true head", or "named run id at <head>" binds to a run whose head IS the current PR head;
   params-identity is a build-input identity, not a provenance identity. Answer 1 (reuse) never
   answers 2 (binding). A lane that cites `_params_match` to claim an old-head cell satisfies the AC
   has conflated the two.

**A producer run's verdict is the RUN conclusion, never one matrix cell.** One failed cell (e.g.
`engine-build-vllm-cuda`) reddens the whole run even while a sibling cell (rocm) is still building and
may itself pass. Read `runs/<id>/jobs` for every cell's `conclusion` before saying what the run will
conclude — and distinguish a genuine red from a documented GPU-less SKIP (`#1240` legs SKIP with a
reason; a `make build-engine` failure is a real red that repeats at any head).

**Provenance check for a cell you intend to cite as a witness:** the workflow's own `bind-proof` step
records the `head_sha` it proved *"self-binding only when the run's head still equals the PR's current
head"* (`#1293`). Quote that, plus the run's head, before citing a cell as evidence.

## Closing criteria (what "shipped" means)
- Report the real pushed tag name + `make check-engine-launchers` rc 0 measured at a FRESH canonical head.
- Never mark done on a dispatch alone; a `pending`/`in_progress` run is not a completed publish.

## Triage: a red build-and-verify cell vs a downstream pin gate vs a hang

When the user says "the engine build hangs / cuda fails", triage the WHOLE run, not one cell — the reds
are usually one deadlock chain, and reporting them apart sends the next lane to the wrong file.

- **Read each cell's conclusion from `runs/<run>/jobs`, then fetch the FAILED cell's log.**
  `gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|"\(.name) \(.status) \(.conclusion)"'`
  gives the per-cell verdict and the job id; then `gh api --allow-escape-sequences
  repos/<o>/<r>/actions/jobs/<id>/logs > /tmp/<cell>.log` and strip ANSI
  (`sed 's/\x1b\[[0-9;]*m//g' | grep -niE 'error|fail|killed|make: \*\*\*|##\[error\]'`) to reach the
  actual failure line — never quote a check colour.
- **An `in_progress` job's log is NOT retrievable** (`actions/jobs/<id>/logs` returns BlobNotFound until
  it completes). Measure a hung cell by its `status` and `started_at` age against the cell timeout, say
  "in_progress <N> min, will hit the wall at <time>", and do not fabricate progress you cannot read.
- **Even a COMPLETED job's log can 404 (`BlobNotFound`) — blob retention expires, and a red conclusion
  does not guarantee a readable log.** Do not stall on it: read the per-step verdict instead,
  `gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|select(.name=="<cell>")|[.steps[]|{n:.name[0:40],s:.status,c:.conclusion}]'`,
  which names the failing STEP even when the streamed log is gone. Report the step name + conclusion; if
  the root cause genuinely needs the log line, re-run the cell and read it live, and say which you did.
- **`engine-pins` red is a DOWNSTREAM symptom, not an independent bug when its log says
  `[pins] NOT PUBLISHED ghcr.io/...:<pin>-<arch> (HTTP 404)`.** The pin gate can only pass once the
  build-and-verify cells publish those tags; if the cells OOM/hang, the pins stay unpublished and the
  gate reds. Chase the CELL, not the gate — "publish the missing tag" is not a remedy when the build that
  produces it is the thing failing.
- **The in-tree sources routinely disagree about the key build knob — the EXECUTED COMMAND in the log is
  the arbiter.** Measured: a PR body said "the CUDA install now sets `MAX_JOBS=2`", an agent-wiki note
  repeated `MAX_JOBS=2`, a skills doc argued `MAX_JOBS=6` is correct, and the params json actually built it
  (`containers/engines/params/<engine>.json`) carried `MAX_JOBS=6` — which is what ran, and OOM-killed the
  16 GiB runner on a 6-arch CUDA compile (`make: *** [Makefile:...] Killed` + `runner has received a
  shutdown signal`). So: grep the params json AND read the `cd .../src && MAX_JOBS=... uv pip install ...`
  line from the log before believing any documented value, and report the contradiction with all the
  `file:line`s — a claimed fix that is not in the tree is a red, not a success.
- **A "hang" is a duration question — build the band, do not guess.** Compare the cell's age against
  completed cells of the same engine (see `references/measuring-job-duration-bands.md`); a rocm cell that
  the tree's own notes say completes in ~60 min sitting at 160+ min with no readable log is either stuck or
  running past its evidence — say which and cite the 240-min wall. Never call it green because the log is
  unreadable.
- **Routing:** the params json / skills / dockerfiles are the engine-improver lane's product files, not
  this lane's — report the measured red with run/job id + sha + the executed command, route to the
  implementer/planner, and do NOT edit `containers/engines/params/*.json` to "fix" another lane's build.
