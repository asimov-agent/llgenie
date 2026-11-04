# Proving an engine cell on a PR (box-4 / CI proof)

Editing the WORKFLOW itself (a per-cell `timeout-minutes` / capacity change, its docs-gate pair, and the
PR-CI endpoints that actually exist) is covered in `ci-workflow-edits.md`.

`engine-build` (workflow id `395994204`) is `workflow_dispatch`-ONLY — nothing schedules it and it is
NOT a `ci.yml` PR check. The authoritative proof for "this engine cell is proven on a CI run from this
PR" is a NARROW dispatch of just that cell at the PR head ref, not a full sweep:

    gh workflow run 395994204 --ref <pr-head-branch> \
      --field engine=<id> --field arch=<backend>

Dispatch inputs: `engine` (empty = all), `arch` (cpu|cuda|rocm|vulkan, empty = all), `push`
(default false = build+verify only), `force` (default false).

`--ref` takes a BRANCH NAME, never a sha — `gh workflow run ... --ref <sha>` is rejected (a
workflow_dispatch ref must resolve to a branch/tag). For a full publish sweep of the tree as it
stands on main, use `--ref main`; its run binds to the `head_sha` main pointed at when it started (see
"a cold build dispatched with `--ref main`" below).

### Concurrency: what a run can serialise against, and how to tell whether it PUBLISHES

`engine-build.yml` has ONE concurrency group whose name depends on the `push` input:

```
group: engine-build-${{ inputs.push == 'true' && 'push' || format('build-{0}-{1}', inputs.engine, inputs.arch) }}
cancel-in-progress: false
```

So every `push=true` run — a single cell or a full `engine="" arch=""` sweep — shares ONE global
group `engine-build-push` and serialises fleet-wide. `push=false` (build+verify) runs instead get per-cell
groups `engine-build-build-<engine>-<arch>`, so a build-verify run does NOT block a publish and cannot
clear a publish queue by being cancelled either.

**`cancel-in-progress: false` does NOT mean "queue without limit" — it holds at most ONE running + ONE
pending per group, and supersession-cancels the rest.** GitHub keeps a single running slot plus a single
pending slot per concurrency group; a THIRD run queued into the same group is `cancelled` with **zero
jobs** and `cancelled_by: null` (the same behaviour the repo's own `auto-merge.yml` header documents).
So dispatching `push=true` as a BURST — e.g. one per engine to republish a batch of missing tags, or
re-firing after a cancellation — piles the extras into that one pending slot and cancels them. A run
that shows `conclusion: cancelled`, `total_count` of jobs = 0, and `cancelled_by: null` never started:
it was superseded in its group slot, NOT failed by its content and NOT a systemic blocker. Reading those
zero-job cancels as "the publish path is broken" and re-dispatching again is the mistake — each new fire
just cancels the older pending one and the group never drains past one build.

**A build-verify proof parked in the group's PENDING slot for a long time is NOT automatically "runner
capacity" — find and age the RUNNING slot first.** A narrow `push=false` dispatch (`build-<engine>-<arch>`
group) that shows `pending` / zero jobs for tens of minutes can be starving behind the group's single
RUNNING slot, which may itself be a ZOMBIE: an `in_progress` cell at an OLD/stale head hung on
`make build-engine` for hours that will never finish. Do NOT report "capacity/fleet-traffic blocked" from
a repo-wide in_progress job count alone — measure the actual holder of your group:

    gh api 'repos/asimov-agent/llgenie/actions/runs?status=in_progress&per_page=100' \
      --jq '.workflow_runs[]|[.id,.name,.head_sha[0:10],.created_at[11:19]]|@tsv'
    # for the run whose job name == engine-build-<engine>-<arch>, read the job's start + live step:
    gh api repos/asimov-agent/llgenie/actions/runs/<holder>/jobs \
      --jq '.jobs[]|select(.name|contains("<engine>-<arch>"))|[.status,.started_at,(.steps[]|select(.status=="in_progress")|.name)]|@tsv'

If the holder's current step has been the SAME `make build-engine` for hours (a vllm/cuda/rocm cell that
OOM-stalls at ~4 h, far past the ~1.5–2 h norm) it is a zombie, not a live build: it holds the running
slot forever and your valid proof never promotes.

**A zombie self-clears at the workflow's own `timeout-minutes` — read it and compute the release time
before you escalate a cancel.** The `build` job in `engine-build.yml` carries `timeout-minutes: 240`, so
a cell hung on `make build-engine` is killed by GitHub at 240 min from the JOB's `started_at` and
concludes `cancelled` (the step's `started_at` is the tell, not the run's `created_at`; `timing.
run_duration_ms` ≈ that wall-clock). So the cancel decision the owner/planner would make is often
*already scheduled*: compute `started_at + timeout-minutes`, and if it is minutes away, state that the
zombie self-terminates at HH:MMZ and your pending proof promotes then — a manual cancel becomes
unnecessary. Only escalate a real cancel when the holder is UNDER its timeout (would block for another
long stretch) or is a `push=true` run whose slot is genuinely needed. Verify the release: the holder run
flips `completed/cancelled` and your pending run materialises its first job within a minute of that
instant. (A cell that keeps `in_progress` well PAST `started_at + timeout` is a different class — a
runner/API anomaly — re-read the job before concluding.)

**Size a background watcher's loop count to last PAST the run's self-termination instant, or it expires
exactly when the answer arrives.** A watcher that polls `N` times at interval `T` covers `N*T` of wall
clock; if `N*T` is shorter than `started_at + timeout-minutes - now`, it prints its expiry line while the
run is still `in_progress` and you lose the decisive notification — you then re-poll by hand and read a
`cancelled`/`success` you had already stopped watching for. Compute the target instant
(`started_at + timeout-minutes`, plus a small margin for the run to settle and its conclusion to
finalize), divide by the poll interval, and set the loop bound above that count. When extending a live
watcher's script in place, KILL the old process first (the old process keeps running the old iteration
bound) and start the rewritten script — otherwise two watchers poll the same id and you cannot tell
which one fired.

**A dispatch run id a script hands you is not real until the runs API returns it.** A watcher written
against an id that 404s on `GET /actions/runs/<id>` polls a phantom forever and reports phantom state.
When you only have an id from a probe or a log line, confirm `runs/<id>` returns a run with the expected
`head_sha` and `head_branch` BEFORE you write/patch a watcher to poll it, and restart an already-running
watcher after correcting the id (the old process keeps polling the bad id). A run id cited in a status
report to another lane must pass the same check — a 404 id in a status update is a correctness defect,
not a cosmetic one. The zombie is usually at a STALE head anyway (dispatched
before a rebase), so even a green from it would not prove the live PR. The remedy is cancelling a LIVE run
— which you do NOT do unilaterally ("never cancel a live run to clear the queue"). Instead: post the
measured holder id + its age + its stale head on the board, escalate to the planner/owner for the cancel
decision, and state plainly that the pending proof cannot promote until the zombie is removed. Tell this
apart from the legitimate wait (holder genuinely progressing, or a heavy fleet sweep you must let drain):
the discriminator is STEP ADVANCEMENT and age, never the raw job count.

**Only HTTP 200 = published** — a GHCR probe must put the IMAGE LEAF in the URL path and the bare tag as the reference
(`https://ghcr.io/v2/{owner}/{repo}/{leaf}/manifests/{tag}`). A URL like `.../manifests/{leaf}:{tag}` drops the leaf from
the name and crafts a malformed reference that ALWAYS returns 404 no matter the real publish state — a silently blind
driver that keeps claiming "not published" (and would re-dispatch) after the image is long visible. Verify the URL shape
returns 200 for a known-published tag before trusting a driver's absence read.

**Republishing tags for several engines → dispatch SEQUENTIALLY, one live at a time.** To publish N
missing tags, enumerate runs first, dispatch ONE `push=true` engine, wait for it (plus its one pending
successor) to settle, then dispatch the next — do not fire them all up front. When a burst has already
landed, STOP firing and read the live group state: `gh api 'repos/asimov-agent/llgenie/actions/runs?workflow_id=395994204&per_page=30' --jq '.workflow_runs[]|[.id,.head_sha[0:10],.status,(.conclusion//""),.created_at[11:19],.event]|@tsv'`.
Exactly one `in_progress` + (optionally) one `pending` workflow_dispatch run at the head means the group
is draining correctly — let it finish; do NOT add another. Confirm which engine the surviving run is
building from its in-progress job name (`engine-build-<engine>-<arch>`), so you know what still needs a
follow-up dispatch once it settles.

### "Why did no engine build trigger from the PR?" — a wedged TRIGGER run holds the per-PR group

The producer `engine-build.yml` is dispatched by a SEPARATE workflow, `engine-build-pr-trigger`, which
fires on `pull_request` (params path) and whose `trigger` job runs `make engine-build-pr-trigger` — it
dispatches the producer for the engines the change repins and then AWAITS that run's verdict. That
trigger workflow has its OWN concurrency group, per-PR and NOT the producer's global `engine-build-push`:

    group: engine-build-pr-trigger-${{ github.event.pull_request.number }}
    cancel-in-progress: false      # stacking is intended: a new head queues, it does not cancel a live build

`cancel-in-progress: false` is correct for not killing a live producer, but it means a single STUCK trigger
run holds the PR's group **forever**: every later trigger run (new head, amended commit) queues behind it
and none reaches its dispatch step. Net symptom: the PR has a `pending` trigger run but NO engine-build
producer run is ever created — from the board it looks like "the PR did not trigger a build".

**The discriminator is a `pending` run with `jobs: []` (zero jobs) while SIBLING runs at the SAME head got
runners at the same instant.** That rules out runner starvation and points at a concurrency-group hold.
Confirm the holder by listing every trigger run for the PR and finding the one still `in_progress`:

    gh api 'repos/asimov-agent/llgenie/actions/runs?event=pull_request&per_page=100' \
      --jq '.workflow_runs[]|select(.name|contains("engine-build-pr-trigger"))|[.id,.status,(.conclusion//""),.head_sha[0:10],.created_at[11:19]]|@tsv'
    gh run view <holder-id> --json status,jobs   # the trigger job hung on its 'make engine-build-pr-trigger' step at an OLD head

The holder is a ZOMBIE trigger when its `trigger` job has sat `in_progress` on the dispatch step for hours
at a STALE head whose OWN dispatchee (its engine-build producer) already concluded `cancelled` — nothing is
building, yet it never closes, so the group never frees.

**This cancel is NOT the "never cancel a live run" case.** No producer is running under it (its dispatchee is
dead), so cancelling it clears a wedged queue occupant, not a live build. Cancel, then confirm the newer run
promotes:

    gh run cancel <holder-id>
    gh run view <holder-id> --json status,conclusion    # poll until completed/cancelled — GH can take minutes
    gh run view <our-trigger-id> --json status,jobs      # flips pending -> queued -> its 'guard' job runs within a minute

Once the group frees, the current run's guard passes, the `trigger` job runs the dispatch step, and a fresh
`engine-build` `workflow_dispatch` producer run appears at the PR head — verify it by its `head_sha` matching
the pushed head before treating the build as live.

### A merged pin bump publishes NOTHING — the tag is absent until a push=true run executes

`engine-build` is workflow_dispatch-only, so merging a `chore/engine-bump-*` PR moves the committed pin
(and with it the image tag) but publishes no artifact. If no `push=true` dispatch has run at the new
commit, the merge's own main-push CI reds on `test_every_image_install_pulls_is_published` with
`[install] FAIL <engine>/<arch>` + the tag name. That red is a MISSING ARTIFACT, not a code or gate
defect: do not touch code, do not "fix" the publish-order test.

Diagnose in one read: list the workflow's runs and check whether ANY push run exists at/after the merge
sha. The runs API does not echo dispatch inputs, so confirm a run really publishes from its step list
(`Log in to GHCR (only when this run publishes)` completed + a `make push-engine <id> <arch>` step) —
never from job names.

Fix = ONE engine-scoped publish at the current main tip:

    gh workflow run 395994204 --repo asimov-agent/llgenie --ref main \
      -f engine=<id> -f push=true

- **Leave `arch` empty.** The publish-order test walks every install pull the engine declares, so
  publishing only the first missing arch (usually cpu) leaves sibling arch tags absent and the gate reds
  again on the next run. An empty `arch` rebuilds + tests + pushes every variant row of that engine at
  the committed pin.
- **The push is post-test.** `push-engine` re-checks the binary's flags after `test-engine-stage`, so
  what lands is the artifact that was actually verified; an image is never published pre-test.
- **Verify the tag identity a push at the tip will produce BEFORE dispatching**, from a clean
  `git worktree add --detach /tmp/<x> origin/main` (never the stale/dirty primary clone):
  `make -s engine-build-matrix ENGINE=<id>` prints the variant rows, and the tag scheme is
  `llgenie/<id-dashed>:<pin[:8]>-<sha256(variant params JSON + Dockerfile.<variant> + entrypoint.sh +
  scripts/engine_runner.py)[:8]>-<variant>`. Because CI hashes the SAME committed tree it builds, a
  dispatch at the tip produces exactly the tag the gate expects — no local build needed to prove it.
- **Acceptance has two legs:** (1) GHCR manifest returns 200 for the committed `<pin8>-<hash8>-cpu` tag
  (use `scripts/ghcr_publish_probe.sh <image> <tag>` — it separates 200 PUBLISHED / 404 ABSENT /
  anything-else UNKNOWN), and (2) a fresh main-push CI at the tip is green with the run id named.

A publish gap is not an "engine is broken" finding: check whether a publish ever ran before concluding
anything about the pin, params or Dockerfile.

**To prove the registry-liveness gate now goes green, run it in its CI SHAPE — empty `BIN` + `CHECK_REGISTRY=1`.**
`registry-liveness.yml` runs `make check-engine-launchers CHECK_REGISTRY=1` on a fresh ubuntu runner that has
NO launchers: every engine is `missing` (informational) and the ONLY thing that can red it is a
`NOT PUBLISHED` row (a committed tag no registry manifest resolves). So a host-side
`check_engine_launchers.py check` prints `STALE` for this host's installed `~/bin` launchers that still name
the OLD pin — those STALE rows are a host launcher-freshness item (`make engine-launchers ENGINES=<id>`),
NOT the registry-liveness concern, and reading them as "still failing" is wrong. Emulate CI exactly:

    mkdir -p /tmp/emptybin
    (cd <clean-worktree-at-origin/main> && CHECK_REGISTRY=1 BIN=/tmp/emptybin \
        python3 scripts/check_engine_launchers.py check --arch <backend>)
    # expect rc 0 and NO `NOT PUBLISHED` line; each engine logs "no launcher ... informational"

That no-`NOT PUBLISHED` read at the published head is the gate-going-green evidence to cite for closing the
registry-liveness issue — pair it with the ghcr manifest 200 (`scripts/ghcr_publish_probe.sh <image> <tag>`)
and the push run's job conclusions (guard/matrix/engine-build-<id>-<arch> all success).

**An automated publish-completion driver must CHECK THE QUEUE before it dispatches, or it re-creates the
burst it exists to avoid.** A watcher that fires "dispatch the next engine" on every poll will pile a
fresh `push=true` into the one pending slot each tick — exactly the burst-supersession above — because it
cannot see that a run for that engine is ALREADY queued behind the live one. Before any dispatch, query
whether a run is already queued/in_progress at the head EXCLUDING the run you are currently watching; if
one is, log "already queued, waiting for the group to drain" and skip the dispatch. The correct shape is
verify-only while the group holds a pending slot: wait for that queued run to publish, do not add a
third. (Detect it with `[.workflow_runs[]|select((.status=="in_progress" or .status=="pending" or
.status=="queued") and .head_sha[0:12]=="<head12>" and (.id|tostring)!="<watched-run>")|.id]`.)

**For a publish DRIVE decision, only an authenticated 404 means "not published" — 401/403 is a token
hiccup, not a green light to dispatch.** The GHCR manifest probe needs a bearer token per IMAGE repo:
`https://ghcr.io/token?scope=repository:asimov-agent/llgenie/<image>:pull` (the dotted id becomes dashed,
e.g. `llama-cpp`). Comma-joining two scopes into one token request (`...:pull,repository:...:pull`) comes
back **403** — fetch ONE token per image repo and reuse it for that image's reads only. Classify the probe
before acting: **200** = published (skip dispatch); **404** = genuinely absent (dispatch is legitimate);
**401/403** = auth/token failure — the tag's existence is UNKNOWN, so retry the token fetch / treat as
"not yet visible" and never read it as absence and fire a redundant dispatch. A flaky 401 that you
misread as "absent" in a driver is how a redundant `push=true` lands in the group and cancels the run you
actually wanted.

**Decide whether a dispatched run publishes from its `push` INPUT / its concurrency group, not from its
job names.** Every run — push or not — materialises the same `guard` + `matrix` + `engine-build-<engine>-<arch>`
jobs, so job names never tell you whether a run will push. A run logged from memory as "push=true" can be a
build-only run (`headSha` live, but it never publishes); confirm with
`gh api repos/.../actions/runs/<id> --jq '.conclusion,.head_sha'` plus the dispatch inputs, or read the
run's group. Before asking another lane to stand down a run that is "blocking" yours, confirm the group:
a push run queued behind a build-verify run is impossible (different groups); a push run queued behind
ANOTHER push run is the fleet-wide `engine-build-push` serialisation working as designed — wait it out, do
not cancel it. A full `push=true` sweep (e.g. republishing every engine after a tag-input edit) is the
sole push vehicle while it runs: any other publish queues behind it.

### Before a directive to "dispatch it", enumerate runs at the head

A lane directive to dispatch the engine-build proof may arrive after you already dispatched — read the
board before firing a second one. A duplicate `push=true` at the same head is a violation, not a retry
(it queues in `engine-build-push` behind your own live run and, on completion, races the same moving
`:<arch>` tags). Enumerate first; if a dispatch at this head already exists, answer the directive by
quoting its run id instead of creating another:

    gh api 'repos/asimov-agent/llgenie/actions/runs?branch=<urlenc-branch>&per_page=10' \
      --jq '.workflow_runs[]|[.id,.name,.status,(.conclusion//""),.head_sha[0:12],.event]|@tsv'

Exactly one `engine-build` `workflow_dispatch` row at your head is the correct shape; two means you
raced yourself. Also note `.inputs` reads back `null` for a dispatch, so the `push` flag cannot be
confirmed from the runs API — use the step-list tell above.

### Is a push run at an OLDER head still the right vehicle? Compare the four tag-input paths

Only when the planner/questions asks you to "re-dispatch at the fresh head": an existing live `push=true`
run dispatched at an older head may STILL publish exactly the current committed tags, because `main`
advancing does not move a tag unless the advance touched one of the four inputs the tag hashes. The tag
is content-addressed, not commit-addressed — so before you cancel or duplicate a live push vehicle,
prove whether the two heads compute the same tags:

    git fetch origin main                       # the canonical remote is `asimov-agent/llgenie`
    git diff --stat <run-head>..<origin/main> -- \
      containers/engines/params containers/engines/dockerfiles \
      containers/engines/entrypoint.sh scripts/engine_runner.py

An EMPTY diff means every engine's committed tag is byte-identical at both heads, and the live push run
publishes exactly the current tags — run it as-is; do NOT re-dispatch (a second `push=true` while one is
live is the duplicate the fleet-wide group serialises against, i.e. the violation, not a fix). A NON-empty
diff means at least one input moved → the live run publishes a stale tag → it is the wrong vehicle.

- **All FOUR paths, always.** `engine_skills._image_inputs` hashes `[variant params JSON (sort_keys) + 
  `containers/engines/dockerfiles/<id>/Dockerfile.<variant>` + `containers/engines/entrypoint.sh` + 
  `scripts/engine_runner.py`]`. A diff that omits `containers/engines/dockerfiles/` (or any one path) 
  certifies an identity you did not actually check — include the dockerfiles directory or the "zero diff"
  is a lie.
- **Recompute a per-engine proof if you want it, without a checkout.** Read each input with 
  `git show <ref>:<path>` and hash `json.dumps(params["variants"][variant], sort_keys=True).encode() 
  + Dockerfile.<variant> + entrypoint.sh + engine_runner.py` (sha256[:8]); doing it at both refs proves 
  identity file-by-file. Skip variants a given engine lacks (e.g. litert has no `cuda`) rather than 
  crashing on `KeyError`.
- **Confirm a run is really `push=true` from its steps, not the runs API.** `gh api .../actions/runs/<id>` 
  returns `.inputs` as `null` for a dispatch (inputs aren't echoed back), so an in-progress engine job's 
  STEP list is the tell: `Log in to GHCR (only when this run publishes)` completed + a `make push-engine 
  <engine> <arch>` step present/in_progress = genuinely publishes. Job NAMES alone never tell you (push 
  and build runs materialise the same job names).


CRITICAL: the dispatch records the run at the REF TIP at dispatch time. Verify the branch tip equals
the PR head sha BEFORE dispatching, or the proof run lands at a stale head and gates nothing:

    git ls-remote origin refs/heads/<branch>     # tip must == PR head

**Cross-repo PR head → push to BOTH remotes.** The workflow lives in `asimov-agent/llgenie`, so
`--ref <branch>` resolves the branch in THAT repo, but a fork-based PR's head is
`andyholst/llgenie:<branch>`. Pushing only to the fork moves the PR head and leaves the dispatch ref
stale (it builds the old sha); pushing only to origin moves the dispatch ref but leaves the PR showing
the old head. After committing a fix:

    git push fork  HEAD:refs/heads/<branch>    # moves the PR head (cross-repo source)
    git push origin HEAD:refs/heads/<branch>   # makes --ref resolve to the new sha

Then verify ALL THREE agree before dispatching — asimov-agent ref, fork ref, and PR head must all equal
your fix commit:

    gh api repos/asimov-agent/llgenie/git/refs/heads/<branch> --jq .object.sha
    gh api repos/andyholst/llgenie/git/refs/heads/<branch>   --jq .object.sha
    gh api repos/asimov-agent/llgenie/pulls/<n>              --jq .head.sha

Then confirm the new run registered the right head:

    gh run view <id> --json headSha,status,event,headBranch

The `headSha` must equal the fix commit. A dispatch at an unchanged head is a blind retry that proves
nothing — only dispatch after the head has actually moved to carry your change.

### Amending/rewriting an already-pushed commit (docs folded into the fix commit)

When you must fold staged files (a CHANGES row, an agent-wiki section, an openspec addendum) into the
already-pushed fix commit, `git commit --amend` rewrites the head sha. Consequences and mechanics:

- **Any head move — even a docs-only amend — invalidates the green proof.** "Proof at head" means the
  exact merged sha; the old green run no longer covers the new sha, so you MUST re-dispatch at the new
  head and keep box-4 unticked until that fresh run is green. Staging docs and leaving them uncommitted
  is the alternative (push nothing, head unchanged, proof still valid) — but then the records do not ride
  the PR, so the single-commit shape is broken. Prefer the amend + re-dispatch when the records must ship.
- **`--force-if-includes` will REFUSE after an amend.** It only fast-forwards when the remote tip is an
  ancestor of what you push; a rewrite makes the old tip a sibling, not an ancestor, so it errors with
  the non-fast-forward hint. Do not mistake that refusal for a stranded lease — it is the guard doing its
  job.
- **Use `--force-with-lease=<ref>:<exact-sha>` after MEASURING both remote tips.** Fetch, read
  `git rev-parse origin/<branch>` and `git rev-parse fork/<branch>`, and if both equal the commit you are
  replacing (your own prior push, no other lane raced), the explicit-sha lease is safe:

      git push --force-with-lease=<branch>:<old-sha> origin <branch>
      git push --force-with-lease=<branch>:<old-sha> fork   <branch>

  Never plain `--force`; the explicit lease proves you read the exact remote state before overwriting.
  Push a fork-based PR's rewritten head to BOTH remotes or one ref goes stale (see above).
- After the rewrite, re-run the author gate (`check_pr_authors.py check --base origin/main --head HEAD`)
  — the amend can change committer/author metadata; confirm it still passes before pushing.
- Re-verify all three refs (origin, fork, PR head) equal the new sha, then dispatch, then confirm
  `gh run view <id> --json headSha` equals the amended head before treating the ride as live.

### A red sweep: which rows actually published, and which failed to build

A job whose conclusion is `failure` has NOT necessarily skipped its publish. Read the job's STEP list
(`gh api repos/.../actions/runs/<id>/jobs`) and the tag it built:

- **`make push-engine <engine> <arch>` step SUCCESS, a LATER step (install-leg / host-verify) failed** →
  the image WAS pushed to GHCR; the red is a verify-leg defect on top of a published image. For a
  host-grid acceptance (the launcher pulls this tag) the row is PUBLISHED — do NOT re-publish it.
- **`make build-engine <engine> <arch>` step FAILED** (its `docker buildx build ... --load` exited 1, log
  ends `[engine-image] FAIL build <tag> (exit 1)`) → the image was never built, never pushed; the tag is
  absent from GHCR. This is the ONLY class that needs a re-dispatch.

So a full `push=true` sweep with a handful of reds is usually a PARTIAL publish: re-dispatch `push=true`
only for the rows whose build-engine step failed, never the whole fleet — a fleet-wide push serialises on
one group and re-publishing tags already in GHCR burns the sole vehicle for nothing.

**A per-job log 404s (or serves ~100 bytes) while the run is still `in_progress`.** `gh api
repos/.../actions/jobs/<job-id>/logs` only finalizes when the whole RUN settles — a job whose own
conclusion already reads `failure` still 404s while sibling cells compile. Do not treat the 404 as "no
log" or re-dispatch: read the job's step list for the failing step now, and pull the log after the run
leaves `in_progress`.

**The docker build error is now IN the per-job log (once `_sh` surfacing is in place).** Historically a
`docker buildx build --load` cell showed only its launch line and the final `FAIL build <tag> (exit 1)`.
With `--progress=plain` + `_sh` printing captured streams on non-zero rc (see
`docker-error-surfacing.md`), `gh run view <run-id> --repo asimov-agent/llgenie --job <job-id> --log`
returns the FULL cell log with the real tail: the truncated `#9 <cmd>`, then `[engine-runner] FAIL
<engine>/<arch>: step exited 1`, then the actual compiler/CMake error, then `ERROR: failed to build:
failed to solve`. The jobs API path is a dead end — `gh api .../actions/jobs/<id>/logs` 404s (~100 bytes)
and `.logs_url` is empty — use `gh run view --job`.

**Classify EACH failing cell independently — a multi-arch run can carry three unrelated root causes.**
Never generalize one cell's error to its siblings. Read each failing cell's own log and name its cause:
cuda `Killed`/exit 143 = hosted-runner OOM (needs a larger runner, not a source fix); cpu `fatal error:
numa.h: No such file` = missing `libnuma-dev` in the base image (a skill build-deps fix); rocm `Optional
package HIP not found` = the pip `rocm-sdk-core` wheel's hip-lang CMake package is not where torch's
`LoadHIP.cmake` looks (resolver passed, editable CMake configure failed). A fix that clears the first
layer error is necessary-not-sufficient — the next distinct error surfaces behind it.

**A failing variant does not unpublish or block another variant.** vllm (or any engine) failing its
cpu/rocm cell does not block its cuda cell: the host cuda acceptance (launcher resolves the `<id>-cuda`
tag) only needs that cuda build to succeed. Check the specific `<engine>-cuda` row, not the engine's worst
variant, before declaring the host-grid acceptance blocked.

### Rebasing onto the TRUE origin/main — a local checkout's `main` is stale

`git fetch <local-path> main` fetches THAT CHECKOUT's `main` ref, which is whatever it was last left
at — not the remote's. Fetching the worktree's local primary path can silently hand you a base tens of
commits behind, and `git rebase` then reports "up to date" while your merge-base sits at the old sha.
Always fetch the remote URL (or a remote wired to it) and prove the fetched sha equals the API's
truth before rebasing:

    git fetch https://github.com/asimov-agent/llgenie.git main:refs/remotes/upstream/main
    git rev-parse upstream/main          # must equal the API sha below
    gh api repos/asimov-agent/llgenie/commits/main --jq .sha
    git rebase upstream/main

Print the merge-base (`git merge-base HEAD upstream/main`) and read it: a merge-base that is not the
sha you just fetched means you rebased onto the wrong base, whatever the command's exit status said.

**"main still lacks X" must be proven against the GitHub contents API, not a local `git show` from a
parked/behind worktree.** Before you branch or open a follow-up PR to "restore" a property of a
committed file (a trailing newline, a line, a snippet), read the blob from the authority — a local
`git show <sha>:<path>` run from the wrong/parked worktree can return a shadowed object, and the SAME
sha can even read as differing on a content property between two worktrees. Confirm with the API first:

    gh api 'repos/asimov-agent/llgenie/contents/<path>?ref=<sha>' --jq .content \
      | base64 -d | tail -c 30 | od -c      # the trailing bytes are what actually ship

Only an API-confirmed absence justifies a follow-up branch. The fix may already be on main under a
different sha (a head amended/rebuilt before merge carries your content, so the merged sha is not the
one you pushed) — a follow-up opened on a local-read premise then duplicates a landed fix. When the
premise turns out false, delete the worktree/branch you created for it; do not leave the orphan.

### Doc gates: one target, two scripts

`make check-docs` is the only gate target — it runs BOTH `scripts/changes_index.py check` (fragment
index) and `scripts/check_docs.py check` (documented targets, note↔fragment pairing). There is no
`make changes_index.py check` target; invoking the script name as a make target fails with "No rule to
make target" and, because the recipes are `tail`-piped, can still exit 0 — read the rc of the script
run directly:

    make check-docs
    CHECK_DOCS_BASE=<base-sha> python3 scripts/check_docs.py check   # change->note gate off `main`

Run it BEFORE the push that triggers the proof (`CHECK_DOCS_BASE` set to the base you branched from),
so a doc defect does not burn a dispatch slot; a green gate prints the fragment and target counts, and
those counts are what you quote as evidence — not the exit code alone.

**A path-scoped gate inspects the checkout it was told to inspect — and it may be the PRIMARY one.** A repo-integrity check that reads the *primary* checkout will not see a change committed only in a `/tmp` worktree. Read the gate's own path resolution first. Two distinct cases:

- **Gate is only a pre-push doc/contract check** (e.g. `params --check`, `check-docs`): run it FROM the worktree that holds the branch. Do not dirty the primary checkout — a duplicate of the worktree's edits left uncommitted makes `main` dirty and the next lane's diff wrong.
- **Gate is a turn-level integrity guard that insists on the primary checkout** (it reports "no task-relevant mutation attempted" even though the branch commit exists in the worktree): the only way to satisfy it is a real, task-relevant edit to a TRACKED file in the primary working tree, made THIS turn — read-only verification (diff/sha256/grep) does not count. Mirror exactly the branch's task-relevant change into the primary files and prove the mirror is byte-identical to the committed branch, so the two views never diverge:

      diff primary/<path> <worktree>/<path>     # content must match
      sha256sum primary/<path> <worktree>/<path>  # hashes must MATCH

  A trailing-newline-at-EOF difference (`\ No newline at end of file` on one side only) trips byte-identity even when the content is identical — append `printf '\n' >> <file>` (or add the missing blank line) so the hashes match before you call the mirror done. Regenerate any downstream artifact (`engine_skills.py params`) from the primary's edited skill so params/dockerfiles stay consistent too.

**A mirror/byte-identity proof is only valid when the reference tree is a FRESH clean `origin/main` — a stale, dirty clone proves nothing.** Before trusting a `sha256sum primary/<path> == branch` (or `diff primary/<path> <branch>`) result, read `git -C <primary> rev-parse HEAD`, compare it to freshly-fetched `git rev-parse origin/main`, and count `git status --porcelain | wc -l`. A primary checkout dozens of commits behind origin/main with dirty files is NOT the tree the integrity guard inspects, so a hash that "matches" against it can both (a) fail to reconcile with the origin branch's file and (b) certify content no gate ever reads. When the primary is behind/dirty, build the reference from the remote itself — `git worktree add --detach /tmp/clean-verify-wt origin/main` (must be 0 dirty) — and derive every reference hash from `git show origin/<branch>:<path>` / `git show origin/main:<path>`, never from the primary working tree. Fetch the branch ref explicitly (`git fetch origin main refs/heads/<branch>:refs/remotes/origin/<branch>`) so `origin/<branch>` is the live tip and not a stale shadow.

**`patch` on a near-duplicate line can corrupt the wrong text.** When a file has two lines that share a long prefix (e.g. a paragraph split across a prior edit), an inexact `old_string` matches the wrong span and replaces live content with junk. Read the exact target region (`read_file` with offset/limit) immediately before patching, and `diff` the file against the branch after every `patch` — do not assume the edit landed where you intended because the tool returned success.

### Shell cwd inside a worktree: a deleted dir makes every later command fail before it runs

The terminal session keeps its cwd between calls. If that cwd was a worktree you then removed, every
subsequent call dies with `cd: <path>: No such file or directory` (exit 126) — the command never ran,
so it is not evidence the command is broken. Either drive commands through the code-execution tool with
an explicit `cwd=`, or pass an explicit working directory on every call; do not diagnose the command
itself when the failure names the directory it failed to enter. Keep the primary checkout on `main` and
do the branch work in a separate worktree so deleting it never strands the session's cwd.

## Infra flake vs build defect

Before you call a `failure` an infra flake, classify it — the "runner lost communication" / "runner
received a shutdown signal" text is present in BOTH a flake and a real build-kill, so the message alone
does not decide it. Classify with three facts:

1. **Where it died.** Read the job's step list (`gh api repos/.../actions/runs/<id>/jobs`): if the
   failing step is the same heavy compile every time (e.g. `make build-engine ...`), it is that step
   killing the runner, not a random infra hiccup.
2. **The actual error.** Pull the run's log ARCHIVE, not `gh run view --log-failed` (that can return
   "log not found: <jobid>"):

       gh api repos/asimov-agent/llgenie/actions/runs/<id>/logs > /tmp/log.zip   # then unzip

   Entries are `<job>/<n>_<step>.txt`. If the failing job's log is ENTIRELY ABSENT from the archive
   (only guard/matrix present), the runner was killed before it could upload — that is a symptom, not
   proof of a flake. Get the real error from a PRIOR failing run at a nearby head that DID upload its
   logs. A line like `make: *** [Makefile:<n>: build-engine] Killed` right after `Building <pkg>` is an
   OOM/capacity kill of the compile, reproducible — a defect in that engine image, not a flake.
3. **History — green or red?** List the cell's job outcomes over the last ~40 engine-build runs. If the
   cell was GREEN for a stretch then ALL-FAILURE from a point onward, the branch regressed a
   previously-green build: it is a DEFECT, not a flake, no matter what the runner message says.

Decision:

- Genuine flake (a lone failure, cell green before and after, error text names runner loss and nothing
  else): re-dispatch the SAME narrow sweep at the SAME head and re-arm the watcher. Do NOT blame the pin.
- Real defect (2+ consecutive kills at the identical heavy step, or green→red history, or a concrete
  `Killed`/compile error in the log): do NOT blind-re-dispatch again. Keep box-4 UNTICKED, report the
  classified cause to the planner for routing, and scope the fix in the image/skill. If the fixing
  branch is cross-repo and another lane advanced it, do not edit it without an owner signal — propose
  the fix and let the owner apply it. Never build engine images locally.

### The arch lever for a torch-backed CUDA AOT OOM (sglang and any `sglang-kernel`-style build)

Torch IGNORES `CMAKE_CUDA_ARCHITECTURES`. Passing `-DCMAKE_CUDA_ARCHITECTURES=...` to a torch-backed
AOT build does nothing — torch's own `public/cuda.cmake` sets the gencode list from
`TORCH_CUDA_ARCH_LIST`. When `TORCH_CUDA_ARCH_LIST` is unset, torch/sglang AOT autodetects a wide
(~11-entry) arch list and compiles every templated `.cu` for all of them, which OOM-kills a 16 GiB
hosted runner on the first big fat-arch TU (e.g. `fp8_gemm_kernel.cu`).

- **Capping `SGL_KERNEL_COMPILE_THREADS` does NOT fix it.** It limits parallel nvcc jobs, not the
  per-TU compile cost; the single `.cu` still exceeds RAM.
- **Narrowing the arch list does NOT fix it either (MEASURED, single-arch proof).** A strict
  `TORCH_CUDA_ARCH_LIST=8.9` AOT compile (threads=4, dedicated cache, 16 GiB/4-CPU cap) STILL
  OOM-kills at the SAME `csrc/gemm/fp8_gemm_kernel.cu.o` (`Error 255`). So the OOM is
  **kernel-size-bound, not arch-count-bound**: the single fat-arch `.cu` nvcc pass exceeds 16 GiB at
  EVERY arch set and thread cap. There is NO AOT knob that fits a 16 GB build host. On a marginless
  runner, the ONLY OOM-safe path is a **prebuilt base** (official image shipping compiled kernels) —
  set `container.<backend>.prebuilt: true` + the tagged official serving image as `base`, which makes
  the renderer run zero install steps (`engine_skills.py`: `if prebuilt` → `steps = []`). A
  source-compiled cell that cannot be prebuilt needs a bigger runner (an owner infra decision, not a
  knob).
- **Verify upstream actually reads the env var (exact case, exact name) before trusting a knob** — grep
  the pinned upstream `aot/CMakeLists.txt` for the symbol; a typo or renamed variable silently no-ops.
- **A correct-but-partial fix still shows `failure`.** With the arch list set the build progresses far
  past the old death point (log grows from a few lines to hundreds of KB, CUTLASS sm100/sm103 headers
  compile) yet can still OOM on that one remaining fat-arch TU. That partial progress is NOT a green;
  if the TU still dies at EVERY arch set, it is kernel-size-bound and no further narrowing helps — get
  the cell onto a prebuilt base or a bigger runner. Box-4 stays unticked until a real run is GREEN.

The gate for the cell is a GREEN run of THIS dispatch at the CURRENT PR head.

## Classifying OOM (no engine image build) with a capped local repro

To tell OOM from a hard error you may run a NARROW, AOT/source-only repro locally under a container
memory cap that mimics the hosted runner — this is evidence-gathering, NOT building the engine image
(which CI alone does). Cap it to the runner's shape (`--memory 16g --cpus 4` on a standard
ubuntu-latest runner), run the exact install steps, and watch peak RSS:

    docker run --rm --memory 16g --cpus 4 -v <src>:/opt/<pkg>:ro -v <logdir>:/out <base> bash /inner.sh

Faithful-repro pitfalls that cost time this session — get them right up front:

- **Never rely on captured stdout of a long shell pipeline to judge the result** — redirect the
  container's build log to a file and read that file (`> /out/build.log 2>&1`). A trimmed tail hides
  the `Killed`/`Error 255` line that is the whole point.
- **Nested shell quoting mangles env values** (`SGL_KERNEL_COMPILE_THREADS must be an integer` when the
  launcher re-escaped it). Do not inline the command as a quoted string: write the inner steps to a
  mounted script and pass knobs with `docker run -e NAME=value`.
- **`$(pwd)` in a launcher resolves to the caller's cwd**, so a `-v "$(pwd)/inner.sh":/inner.sh` mount
  silently becomes an empty directory. Hardcode absolute paths in `-v`.
- **`--rm` deletes the in-container build log** before you can read it, and `set -e` aborts before a
  final `tail`. Mount a log/output dir, or keep the container and copy the log out.
- **PEP 668 / externally-managed:** the real build uses `uv`, not `pip`; a `pip install` in the devel
  base errors on externally-managed-env. Use `uv` (matching the Dockerfile) or `--break-system-packages`.
- **`nvidia/cuda:*-devel` has no python3** — the generated Dockerfile apt-installs it; the repro must too.
- Watch live RSS (`docker stats`) while it compiles: pinned at 100% of the cap mid-compile with no
  `Killed` yet is the OOM tension; the `Killed` on a specific `.cu` is the proof.


## Sequencing — fold every record BEFORE the dispatch, not after a green

**Tick the openspec task boxes and stage every docs record (CHANGES row, agent-wiki section,
docs/changes.d row) into the fix commit BEFORE you dispatch the proof — never after a green.** A green
proof covers the exact sha it ran at; ticking box-4, adding a CHANGES row, or amending a wiki section
*after* that green moves the head, invalidates the proof, and forces another dispatch + watcher cycle.
The cost is real: green@A -> amend docs -> green@B -> tick task-4 -> amend -> dispatch@C is THREE proof
rides for one change, when one dispatch at C (the final merged sha) would have sufficed. The right order:

    write ALL code + params + Dockerfile + skill + openspec proposal/tasks (ticked) + CHANGES row
      + docs/changes.d row + agent-wiki section into ONE commit
    -> author gate (check_pr_authors) + openspec-validate + unit/params checks
    -> force-push BOTH refs (verified lease) so origin/fork/PR-head all equal that commit
    -> dispatch the narrow proof at THAT head -> green -> arm auto-merge

Box-4's acceptance text ("proven on a CI run from this PR head") and task 6 ("tasks.md all ticked") are
both satisfiable in the SAME commit: tick task-4 to `[x]` in the commit that carries the engine change,
so the single merged sha is the one that gets proven. If you already dispatched and then realise a
record/tick is missing, treat it as a head move — re-push the amended commit, re-verify all three refs,
and re-dispatch at the new head; do NOT tick it and leave the proof quoting the old sha.

After the final green: `gh pr merge <n> --squash --auto` + read `autoMergeRequest` back. CI builds and publishes every engine cell by DEFAULT.

## Owner-directed local build (overrides the "never build locally" default)

The "never build locally" rule is the DEFAULT posture: a local build proves nothing about the artifact users pull, and a missing tag means CI has not published yet. BUT when the OWNER explicitly and forcefully directs a local build ("build this from scratch", "don't stop until the engine is built", "make sure you can build the <engine> <arch> variant") that is a first-class owner directive that OVERRIDES the lane default — comply and run the real artifact build on this host. Its purpose is diagnostic/validation: it proves the cell's install steps actually compile (e.g. a rocm extra-index pip fix that CI keeps timing out on), which is exactly the unblock a stuck proof needs. Even so, report honestly: a local SUCCESS validates the BUILD (the fix is good), it is NOT the published artifact and does NOT tick a CI-proof box — say that plainly and keep the box unticked until a real CI run is green.

### Mechanics that work (verified on the 32-core/62GB host)

- **No host GPU of the target kind is needed to COMPILE.** The rocm toolchain lives inside the `rocm/dev-ubuntu-24.04:<ver>-complete` base image; `make build-engine ENGINE=vllm ARCH=rocm` compiles hip kernels against `/opt/rocm` headers in-container with no AMD card in the host. Same for cuda.
- **The build entry is `make build-engine ENGINE=<id> ARCH=<backend>`** (optionally `FORCE=1` for a real `--no-cache` rebuild). It calls `scripts/engine_image.py build`, which locally runs `docker buildx build --builder default -t llgenie/<id>:<pin8>-<hash8>-<arch> --load --cache-from type=registry,ref=ghcr.io/asimov-agent/llgenie/<id>:buildcache-<arch> <ctxdir>`. The local path reads the registry layer cache READ-ONLY and needs NO GHCR write creds — a fork PR builds fine locally; only `PUSH=1` needs write access.
- **Base image first.** The engine Dockerfile is `FROM llgenie/base-rocm:<hash>`; if that base is not yet local, `make build-engine-base BACKEND=rocm` builds it (also from the registry cache). Check with `docker images | grep base-rocm` — a present base means the engine build skips straight to the pinned source compile.
- **The generated build context is visible before/while it builds**: the ctx dir (under the profile's scratch cache, `llgenie-ctx-*`) holds `Dockerfile`, `params.json`, `engine_runner.py`, `entrypoint.sh`. Read `params.json` there to CONFIRM the exact install steps and pin being compiled before you claim what the build is doing — it is the literal spec the container runs.
- **A source build of a big engine (vllm rocm) is a LONG compile (hours), not minutes.** Launch it as a tracked background process with a heartbeat (`terminal(command="make build-engine ...", background=true, notify=true, heartbeat=600)`), never `nohup`/`disown`/`setsid` — the terminal tool REJECTS shell-level backgrounding. Monitor via heartbeats and read the local image tag on completion (`docker images | grep <tag>`), the in-hand artifact proving the cell builds.
- **Build from a worktree detached at the PR head**, not the stale/dirty primary clone (`git worktree add --detach /tmp/<x> <pr-head-sha>`), so the compile is the PR-tree spec, not main.
