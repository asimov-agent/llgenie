# Local engine image build & verification (vllm/rocm and friends)

When CI is the only thing failing, or you need to prove a container change before
pushing, build the engine image on this host instead of waiting on a runner. The
entry is a make target that shells out to the image driver and then
`docker buildx`:

    make build-engine ENGINE=vllm ARCH=rocm > /tmp/vllm_rocm_build.log 2>&1; echo "rc=$?" >> /tmp/vllm_rocm_build.log

## Preflight (cheap, do it first)
- Docker/disk healthy, and the base image already local so you do not blind-pull
  multi-GB: `docker images | grep base-rocm` (e.g. `base-rocm:<sha>`, 20+ GB).
- Read the EXACT install command the build will run from the params file — do not
  guess it: `containers/engines/params/vllm.json` -> `variants.rocm.install[...]`
  (an array of shell steps). Confirm the env var / launcher / flag your change is
  supposed to exercise is actually present in that command; otherwise the local
  build proves nothing about your change.
- Run the build in the BACKGROUND (`background=true`, `notify=true`), never a
  foreground `sleep` poll (see `terminal-and-guard-pitfalls.md`).

## UV_HTTP_TIMEOUT: raise it before the first build
`uv`'s default HTTP timeout is 30s. A multi-GB ROCm resolve trips it — e.g.
`Failed to download mpmath==1.3.0 ... network timeout ... UV_HTTP_TIMEOUT (current
value: 30s)` while resolving torch->sympy->mpmath, or the amd-torch/rocm-sdk device
sdists (one is ~1.5 GiB). It fails the install step long before any compile and is
a TRANSIENT network flake, not your change. Fix + retry in one step:

    export UV_HTTP_TIMEOUT=180 && make build-engine ENGINE=vllm ARCH=rocm ...

## A durable timeout is a skill env, per backend — not an export
The `export` above fixes only YOUR local build. The committed build reads the timeout from
`containers/engines/params/<engine>.json` -> `variants.<b>.env`, which is GENERATED from the
skill's `env:` map keyed by backend in `skills/engines/<engine>/SKILL.md`. So a durable fix:

- Edit `skills/engines/<engine>/SKILL.md` `env:` and add `UV_HTTP_TIMEOUT: "180"` under EVERY
  backend that runs uv (`cuda`, `rocm`, `cpu`). Adding it to ONE backend leaves the others on uv's
  default 30s — they flake identically on the same slow link. A cross-variant concern must cover
  ALL variants; read the `env:` map and confirm a block per backend, not just the one your build used.
- Regenerate the committed params: `make generate-engine-params ENGINE=<engine>` (writes only that
  engine's params JSON; `binaries.json` and the rendered Dockerfiles are untouched when the change
  is env-only — confirm via `git status`).
- Prove parity with the committed tree: `make check-engine-params` -> `0 file(s) stale`. The gate
  regenerates params from the skills and diffs against what's committed, so hand-editing the params
  JSON alone reds it.
- A change under `containers/engines/params/**` on `pull_request synchronize` fires
  `engine-build-pr-trigger` (its `paths` filter is literally `containers/engines/params/**`) -> the
  engine build restarts at the new head on its own. Pushing the params change is what "restart the
  build engine" means; no manual `workflow_dispatch` is needed to restart it.

## Monitoring a multi-hour build
A single `tail` hides the failure. Poll with a milestone grep after each wait:

    tail -8 /tmp/<build>.log
    grep -nE "Downloading|build_rust|building.*bdist|editable|hip_offload|Compiling|Killed|FAIL|network timeout|Successfully built|rc=" /tmp/<build>.log | tail -20

Poll discipline: run ONE consolidated status command per check (a single
execute_code/terminal call that prints clang/cc1 count, host memory, buildx
liveness and the `rc=` marker together) and let a single background watcher with
`notify=true` fire on the `rc=`/`BUILD_ENGINE rc=` line drive the wake-up. Do NOT
fan out a dozen near-identical parallel status calls — they burn context, race the
same log, and add nothing over one snapshot. Foreground `sleep`/`tail` polls clamp
at ~420s; the long wait belongs in the background watcher.

Expected vllm/rocm stages: apt/base setup -> rust frontend (`build_rust`) -> the
large amd-torch/rocm-sdk device sdists download -> the `-e .` editable install ->
C++/HIP compile -> image load. Dependency resolution is NOT verification: a
HIP/concurrency change is governed by the C++ compile step, so do not state a
verdict until that step reports success or failure. Between polls, report the
honest interim stage rather than an estimate.

## Layer cache: the second local build is fast (same inputs)
`make build-engine` builds LOCALLY by default — `engine_image.py` `_buildx` with no
`--push`/no `REGISTRY` uses `[RUNTIME, buildx, build, -t <tag>, --load]` on the
`default` (docker) builder. That tags the image into local `docker images`
(`llgenie/<engine>-<variant>:<sha>`); "publish locally" = that local tag, not a
registry push. The `default` builder keeps a BuildKit layer cache on this host, so:
- **Unchanged inputs → near-instant re-tag.** Re-running the same
  `make build-engine ENGINE=... ARCH=...` with the SAME params + Dockerfile reuses
every cached layer (base pull, dep resolve, even the multi-hour HIP compile layer)
  — only the final tag step re-executes. This is the answer to "will the next build
  be faster": yes, seconds, *provided the build inputs did not move*.
- **Changed inputs → slow path returns.** A moved `params.json` pin / Dockerfile
  edit invalidates the affected layer and everything after it, so the single-core
  HIP compile re-runs from scratch. `make ... --force` (`--no-cache`, issue #638)
  is a real rebuild and also drops the cache read.
- The registry `--cache-from/--cache-to type=registry` ref is for cross-machine CI
  reuse and is read-only on the local path; on this host the `default` builder's own
  layer cache is what makes the rebuild fast.

### Cache WRITE reds a first-ever build: `--cache-to` errors "not found" when the package is absent

A cold build of an engine whose image package does not exist on the registry yet fails at the
`--cache-to type=registry,ref=…/buildcache-<arch>` step with `not found` — the cache ref can only
be written once the package it lives under exists, so the very first publish dies on the WRITE,
not the build. The read side (`--cache-from`) already tolerates a missing cache (build cold); the
write side must too. Fix pattern in `scripts/engine_image.py`: a `_cache_write_args()` helper that
probes the ref and OMITS `--cache-to` when the package is absent (build cold, log a one-line note),
used on BOTH the push path and the local `CACHE_WRITE=1` path — never a silent skip. A build that
reds on `--cache-to … not found` is an infra tolerance defect, not a compile error: read the log
for the literal `not found` on the cache ref before blaming the Dockerfile. A per-engine build
failure that cites a cache ref and "cold build" in its own line is this class — the fix is in the
image driver, and the regression test asserts the write is SKIPPED when the ref is absent and STILL
HAPPENS when it is present.

### Refactoring cache args to "probe once, thread through": audit EVERY call site
When a helper (`_cache_exists` / `_cache_read_args` / `_cache_write_args`) is refactored so the
registry probe runs ONCE per build and its result threads through both cache sides, the trap is a
value computed unconditionally at the top of `_buildx` while a branch computes its OWN copy at the
point of use. If both the push branch and the local branch can reach the same helper, computing
`cache_args = _cache_read_args(...)` above the branch AND calling `_cache_read_args(...)` again
inside the local branch DOUBLE-INVOKES it — and on an absent cache it prints the cold note TWICE
(a real duplicate-log defect that reads as a harmless refactor). Rule: compute the shared probe once,
thread it into every helper, and compute the derived arg list ONLY in the branch that appends it
(`cache_args = [] if force or not push else _cache_read_args(...)`), so each side is built exactly
once. This is the same call-site audit the guard-pitfalls "compute once, thread it through" rule
demands (grep every helper call); the ADDITIONAL failure mode here is a DUPLICATE SIDE EFFECT — the
helper prints its cold note on every invocation, so the second call duplicates the log line, not just
a harmless second probe. A forced local build consults neither side and must issue no probe at all.

**Assert the PROBE COUNT, not just the cache FLAGS, per force/push combination.** A regression can
keep every flag right (`--no-cache`, `--push`, write args present, `--cache-from` dropped) while the
registry is inspected twice or zero times — the flag assertions pass and the duplicate/missing probe
ships silently. The probe is `docker buildx imagetools inspect`; count it in the recorded calls:
`probes = [c for c in calls if c[:4] == ["docker","buildx","imagetools","inspect"]]`. Contract
across the four combinations: unforced push → ONE probe (read+write threaded through one probe);
forced push → ONE probe (read dropped, write only); unforced local read-only (`CACHE_WRITE=0`) → ONE
probe (read side); forced local → ZERO probes (consults neither side). Assert the exact count in each
test so a double-invoke (the duplicate-log defect above) or a dropped probe reds a test instead of a
log nobody greps. A test that only checks the emitted flags leaves this whole class unguarded.

### Proving "printed exactly once": `print` is a builtin, use `capsys`
`print` is a builtin, not an attribute of the module under test, so
`monkeypatch.setattr(ei, "print", ...)` fails with
`AttributeError: <module 'scripts.engine_image'> has no attribute 'print'`. To assert a message is
emitted exactly N times, take pytest's `capsys` fixture and filter stdout:
`notes = [l for l in capsys.readouterr().out.splitlines() if "cache read skipped" in l];
assert len(notes) == 1`. This is the clean regression guard for a duplicate-print defect and needs
no module-level patching.

## Is it stalled? Judge by process, not log mtime
A build log that has not been appended in 10+ minutes is NOT necessarily hung.
`uv` and docker buildx `--progress=plain` are line-buffered per artifact/step, so
a 1.5 GiB device sdist pull or a single giant C++/HIP translation unit emits
nothing until it completes. Before calling a stall, check the live processes:

    echo "clang=$(pgrep -fc '^clang-20$') cc1=$(pgrep -fc cc1) buildx=$(pgrep -fc 'docker-buildx')"
    ps -eo etime,pcpu,args | grep 'clang-20.*cc1' | grep -v grep | head -1
    ps -eo rss | awk '{s+=$1} END{printf "host_mem=%.1fGB\n", s/1024/1024}'

A `clang-20 -cc1` at ~99% CPU with growing `etime` and stable host memory means it
is compiling, not stalled — keep waiting. (Seen: 38+ min on ONE translation unit
at 99.4% CPU, host memory flat at ~15 GB, ~all other cores idle.) Only a dead
buildx (no process) or a rising OOM/`Killed` line is a real failure.

## vllm/rocm HIP compile and HIP_PARALLEL_JOBS
- The rocm variant's `-e .` install step carries `PYTORCH_ROCM_ARCH` (fat build:
  gfx942/gfx1100/gfx1101/gfx1201) and
  `CMAKE_HIP_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py`.
- ROCm clang 20 accepts several `--offload-arch=` and compiles each device arch
  **serially**; there is no `--offload-jobs`. The launcher runs the per-arch groups
  (distinct outputs) concurrently, then the offload bundler and host compile in order.
- The fat build is dominated by long SERIAL compile of a few huge translation
  units: a single `clang-20 -cc1` can hold one core at 99% for tens of minutes
  while the rest idle. This is the wall a fixed build timeout dies inside; the
  load-bearing remedy for a compile-timeout failure is a larger timeout, not a
  memory cap. A cap (below) is a memory guard, not a speed lever.
- `HIP_PARALLEL_JOBS` is the launcher's cross-process slot budget (shared with
  ninja); unset it defaults to `os.cpu_count()`. A cap (e.g. `HIP_PARALLEL_JOBS=6`)
  bounds concurrent cc1 HIP jobs so a 16 GiB CI runner does not OOM.
- `HIP_PARALLEL=0` forces the plain passthrough path (exec the compiler unchanged).

## Proving the change locally with the repo's unit tests (containerised)
Before spending ~44 minutes on a cloud matrix, prove the touched code with its own unit
tests. The repo has no host `pytest`; tests run inside the `llgenie/test:latest` image:

    docker run --rm -u root --network host \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "$PWD":"$PWD":rw -w "$PWD" -e HOME=/tmp \
      llgenie/test:latest python -m pytest tests/test_<a>.py tests/test_<b>.py \
      -p no:cacheprovider -q 2>&1 | tail -20; echo "PYTEST_RC=$?"

- Mount at `-w "$PWD"` (the SAME absolute path) rather than `:/work`: `engine_image.py` and the
tests resolve repo paths from the module location, so a remapped path breaks the fixtures.
- `-e HOME=/tmp` keeps the container from writing root-owned caches into your real home.
- Target the FILES the diff touches (`git diff --name-only origin/main...HEAD` → the
  `tests/test_*.py` rows) plus the nearest neighbours. The FULL `scripts/unit_tests.py run`
suite exceeds the 300s `execute_code` cap and will kill your kernel — run either the targeted
  subset in a cell, or the whole suite as `terminal(background=true, notify=true)`.
- Report the count (`N passed in Xs`, rc 0) with the head sha, and say plainly that a local
  unit green is not the acceptance witness when a criterion demands a real build/run.

## Local green is not a CI verdict
The host (e.g. 32 cores / 62 GB) is not the CI runner (typically 16 GiB). A local
build proves the AMD-index resolve works and the launcher path runs; it does NOT
reproduce the runner's memory ceiling. Report it as evidence, and still get the
actual CI cell (build-and-verify, `push=false`) before claiming a gate.

## Getting the CI cell: dispatch `push=false` build-and-verify yourself
When the acceptance criteria demand a REAL build passing in a workflow run and the
only witness is a stuck producer run, you are allowed to dispatch the safe shape
instead of waiting:

    gh workflow run engine-build.yml --repo <owner>/<repo> --ref <branch-or-tag> \
      -f engine=vllm -f arch=cuda -f push=false

**`--ref` takes a BRANCH or TAG name, never a bare commit sha.** A `workflow_dispatch`
ref is a git ref, not a revision — a sha (e.g. a PR head you were handed) answers
`No ref found for: <sha>` / 422. To verify ANOTHER lane's PR at its head, dispatch at
the PR's HEAD BRANCH name (`gh pr view <n> --json headRefName -q .headRefName`), which
resolves to that head sha. Then read the run back and confirm `.head_sha` equals the
target — the branch may have moved between your lookup and the dispatch, and a run at
the wrong head proves nothing:

    gh api repos/<owner>/<repo>/actions/runs/<run> --jq '.head_sha'

Dispatch from `gh api` (not `gh workflow run`) needs `--input`, never curl's `-d`: the API
endpoint is `POST repos/<o>/<r>/actions/workflows/<workflow_id>/dispatches` with a JSON body
`{"ref": "<branch>", "inputs": {...}}`. `-d` is a curl flag and is rejected (or silently
mistaken for `--raw-field`); pass the payload from a file: build `/tmp/dispatch.json` with
`write_file`, then `gh api repos/<o>/<r>/actions/workflows/<id>/dispatches -X POST --input /tmp/dispatch.json`.
`gh workflow run <file>` is the friendlier shape when the workflow lives in the default branch;
use the API when you need the numeric workflow id or an exact `ref`.

`push=false` is build-and-verify: it builds the image and runs the install step but
publishes NOTHING (no `:tag` push, no merge). That is the difference from a live
producer run — a `push=false` dispatch is the one you may fire without the
producer lane's go; a `push=true` run is the release path and is theirs.

Two facts that make this safe and fast:
- **Concurrency is per-selection, not global.** The group is
  `engine-build-push` only when `push == 'true'`; a narrow build-and-verify run gets
  `engine-build-build-<engine>-<arch>` (e.g. `build-vllm-cuda`). So your `push=false`
  dispatch runs on its OWN group — it does NOT queue behind a stuck `push` anchor that
  holds a rocm cell open for hours. Verify the group shape in the workflow's
  `concurrency.group:` before assuming a dispatch will be blocked.
- **The cell log only unlocks at cell completion.** `gh run view <run> --log --job <id>`
  answers `job <id> is still in progress; logs will be available when it is complete`
  while the cell runs. You cannot read a build cell's progress mid-flight; arm a
  background watcher on the RUN's `.status` and read the cell log the moment it is
  `completed`.
- **A fresh dispatch sits `pending` with an EMPTY `jobs: []` for a minute or two while
  GitHub allocates a runner — that is normal scheduling, not a stall.** The real
  stalled-runner signature is `pending`/`in_progress` with `updated_at == created_at`
  frozen for ~1.5 h (a dispatch that never got a runner) — the same dead-runner shape
  as a frozen CI check. Do not wait on that run for a verdict; dispatch a FRESH
  `push=false` run at the right ref (the earlier one stays harmless, no need to cancel)
  and verify the new run's `.head_sha`. A `push=false` dispatch never publishes, so
  abandoning a stalled one costs nothing.

If the cell SUCCEEDS, that run IS the acceptance-criteria evidence (real build at a
current head) — cite the run id and head sha. If it FAILS, the now-readable log gives
the actual first-failing command to fix — never guess the cause from the conclusion.

## Proving a DEFAULT-matrix change: dispatch with EMPTY inputs, and re-dispatch after any rebase

When the criterion is about what the DEFAULT sweep emits ("the default build sweep is
green without the GPU cells"), the witness is a dispatch with the selectors left EMPTY —
`-f engine= -f arch=` right after the ref — so the workflow resolves the default matrix
itself. Passing `engine=vllm arch=cpu` proves a cell, not the default; it cannot witness
a DEFAULT-matrix criterion. Before dispatching, prove the same claim cheaply in-tree by
calling the matrix builder directly and reading the `engine`/`arch` fields of the emitted
cells (an empty/default call must emit no cuda/rocm cells; an explicit `arch=cuda`/`rocm`
call must), so the heavy sweep is a confirmation rather than an exploration.

A rebase re-mints the head, so a default-sweep run dispatched at the OLD head is
SUPERSEDED even though its cells were still green — the criterion asks for a run at a
commit that is on the branch. Say so explicitly in the bookend (name the superseded run
and head), re-dispatch at the new head, and re-read `.head_sha` to confirm the new run is
at the new head before citing it. Do not let an in-flight sweep at a superseded head be
quoted as current evidence once you have rebased.

### A mid-build push CANCELS your dispatch — confirm the run is `cancelled`, then re-dispatch at the settled head
A long build (a multi-GB CUDA image ran ~40+ min on the `make build-engine` step here) is
vulnerable to a concurrent lane pushing a new commit to the same branch: the workflow's
`cancel-in-progress` cancels your in-flight run the moment the head moves, and the run ends
`cancelled` — not `failed`. Symptoms: your watcher sees `in_progress` for many iterations,
then the run reports `cancelled`, and the PR's `headRefOid` is now a DIFFERENT sha than the
one you dispatched at. This is not your bug and not a build failure — never diagnose it as
one.

- **Before re-dispatching, confirm the branch has SETTLED.** Read `gh pr view <n> --json
  headRefOid` and the last commit author-date; if the rebase lane is still pushing, a fresh
dispatch at the current head will be cancelled again the same way. Wait for the head to
stop moving (a fresh `headRefOid` that matches the branch tip and is unchanged across two
reads) before spending another 40 minutes.
- **Re-dispatch at the CURRENT head, then verify the run's `.headSha` equals it.** A dispatch
  whose head has already moved is worthless for the criterion even if it were to finish.
- **Use the `bind-proof` step (#1293) as the self-binding check.** `engine-build.yml` ends with
  a `bind-proof: record the head_sha this build-and-verify run proved … the verdict a reader
  quotes is self-binding only when the run's head still equals the PR's current head` step.
  On a `success` run, read that step's conclusion from the jobs API:
  `gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '.jobs[]|select(.name|test("<engine>"))|.steps[]?|select(.name|test("bind-proof"))|.name+" -> "+(.conclusion//"")'`.
  A `bind-proof -> success` plus run `headSha` == PR `headRefOid` is the pair that makes the
  run quotable; a run whose head no longer equals the PR head is not evidence regardless of
  its cell colour.
