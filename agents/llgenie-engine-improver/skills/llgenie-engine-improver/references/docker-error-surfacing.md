# Surfacing a real docker-layer build error from CI

## Problem
A `docker buildx build` failure inside an engine image build is UNREADABLE in GitHub Actions logs: BuildKit's default `auto` progress writes `\r`-collapsed updates, and GitHub's plain-text log storage keeps only the terminated line — so the log shows the `docker buildx build ...` command line and then a bare `[engine-image] FAIL build <tag> (exit 1)`, with ZERO steps in between. Per-job log retrieval (`gh api /actions/jobs/{id}/logs`) reproduces the same collapse (28.9KB, nothing between cmdline and FAIL). This is why a vllm build failure once had to be diagnosed statically.

## Fix — TWO parts, both required
1. `scripts/engine_image.py::_buildx` passes `--progress=plain` to BOTH buildx invocations (push + local). Plain progress writes newline-delineated plain text GitHub's log storage preserves, instead of `\r`-collapsed `auto` progress.
2. `scripts/engine_image.py::_sh` prints the failing command's CAPTURED stdout/stderr on a non-zero rc. **`--progress=plain` alone is NOT enough**: `run_ok`→`_cmd` runs the child with `capture_output=True`, so buildx's streams land in the CompletedProcess and `_sh` printed only the command line — the per-job log still showed the cmdline then a bare `FAIL`, zero buildx output in between (measured: a 14 s gap with no docker lines). Surfacing the captured streams on failure is what makes the real layer error (`#9 [x/y] <cmd>` then `=> ERROR ...`) visible.

## A `failed to configure registry cache importer … not found` line is a WARNING, not a build failure

A local `make build-engine` run can print, right after the `docker buildx build` line:

```
#4 ERROR: failed to configure registry cache importer: ghcr.io/.../vllm:buildcache-cuda: not found
```

BuildKit could not import the remote build cache because CI has not published that
`buildcache-<variant>` tag yet (a fresh variant, or CI has not run). Buildx **skips cache import and
builds from scratch** — the build continues normally and `#11`, `#12` … steps keep flowing. Do not read
this `ERROR:` line as the reason a build died: the same log will show the real terminal failure later
(`=> ERROR [stage N] …` / `[engine-runner] FAIL <id>/<backend>: step exited N`). Only a line that ends
the run is the failure; a cache-importer miss is expected on any variant CI has not cached.

## Watching a build IN PROGRESS: the log stays quiet by design — that is not a hang

The same `capture_output=True` seam has a second consequence, which reads as "the build is stuck / the log
is broken" when it is neither: **during a long SUCCESSFUL build the `make build-engine` log does not grow**
beyond the `[engine-image] $ docker buildx build --progress=plain ...` command line. The entire buildx
step stream is buffered in memory inside `run_ok`→`_cmd`'s `CompletedProcess` and is written out ONLY on a
non-zero rc (the `_sh` re-emit on failure). So a clean multi-hour compile produces a log that ends at the
buildx invocation and no more — expected, not a hang and not lost output.

- **Prove it is alive, don't judge from the log.** Check the child process tree (`ps -ef` for
  `cmake --build` / `hipcc` / `git clone` under the runc builder) and `docker ps` for the build container —
  a running compile with an unchanging log is healthy.
- **For live per-step detail, watch docker directly**, not the make log: `docker ps --format '{{.ID}}
  {{.Image}} {{.Status}}'` and `tail -f /var/lib/docker/buildkit/executor/runc-log.json`. The buildx
  `#N [stage]` lines come from BuildKit, not from `engine_image.py`.
- **Do not "fix" this by streaming** unless you mean to change `scripts/proc.py::_cmd` — that seam runs
  EVERY subprocess, so switching it to stream is a versioned-tree change (a PR), never a live-profile hack.
  The capture is intentional (#797 policy: caller inspects rc).

image tag digests do NOT shift when `engine_image.py` changes: `scripts/engine_skills.py::_image_inputs` hashes only the variant params + committed Dockerfile + entrypoint.sh + engine_runner.py — NOT engine_image.py.

## Tests that cover the buildx invocation
`test_engine_force_rebuild.py` (10), test_engine_skills.py buildx/cache/driver (2), test_ci_images.py buildx/publish/cache/push (19). None assert absence of `--progress` (substring checks on --no-cache/--cache-from/--cache-to/--push/-t/--load), so the flag is safe.

- **Re-routing the build through a NEW helper silently breaks tests that patch the OLD one.** These tests monkeypatch the seam to RECORD the build command (e.g. `ei._sh = recorder`) and then assert its flags. If you change which helper the production path calls — e.g. `_buildx` now builds via a streaming `_sh_live` instead of `_sh` (see the proc-streaming policy below) — the recorder attached to `_sh` never sees the build, captures a different call (`buildx inspect`), and the flag assertions fail even though the flags themselves are correct. Before changing the seam, `grep -rn '_sh\b' tests/` and update EVERY recorder to patch BOTH helpers (same flags asserted, never weakened). Symptom: several tests in `test_engine_force_rebuild.py` + `test_engine_skills.py::test_push_targets_only_the_registry_tag` red on `make ci-unit` right after the streaming change.
- **A bare `python3 -m pytest tests/test_x.py` returning rc 2 with EMPTY stdout AND stderr is a harness-invocation quirk, not a test failure.** The repo suite is only representative when run through its make target / the hermetic `llgenie/test` container (the container is the authoritative unit path; a host pytest can be a broken env). Judge a fix by `make ci-unit` — assert the pytest summary line (`N passed`) before blaming a code failure — never by a hand-typed bare pytest whose empty RC-2 proves nothing.

## Diagnostic use
When an engine image build fails in CI, fetch the per-job log and grep for `=> ERROR` / `error:` / the failing `#N [step]` layer. That is the change-record-worthy fact. If still invisible, combine with the static recipe check from vllm-rust-build-defect.md.

### The working per-job retrieval path (jobs API needs `--allow-escape-sequences`)

The reliable ways to read ONE cell's full log are `gh run view --log` OR the jobs API with the escape flag:

    gh run view <run-id> --repo asimov-agent/llgenie --job <job-id> --log > /tmp/cell.log
    gh api --allow-escape-sequences 'repos/asimov-agent/llgenie/actions/jobs/<job-id>/logs' | sed $'s/\x1b\\[[0-9;]*m//g' > /tmp/cell.log

- **`gh api .../jobs/<id>/logs` DOES serve the full log** — but only with `--allow-escape-sequences`. The
  action log carries ANSI colour codes, and plain `gh api` refuses to print a body containing terminal
  escape sequences (that refusal, not a missing endpoint, is what looked like an empty/404 result before).
  Add `--allow-escape-sequences` and strip the codes (`sed`/`re.sub(r'\x1b\\[[0-9;]*m','',s)`); this served
  a full 40 KB cell log where the plain call had returned nothing usable.
- **`--allow-escape-sequences` is a flag of `gh api`, NOT `gh run view`.** `gh run view --job <id> --log
  --allow-escape-sequences` fails with `unknown flag: --allow-escape-sequences`. Use it only on `gh api`.
- `gh run view --job <id> --log` returns the FULL cell log (measured in the hundreds of KB) and, with the
  `_sh` surfacing fix in place, the real docker-layer tail — the truncated `#9 <cmd>` line, then
  `[engine-runner] FAIL <engine>/<arch>: step exited 1`, then the actual compiler/build error, then
  `ERROR: failed to build: failed to solve`.
- `gh run view <run-id> --log-failed` (no `--job`) also returns the failed cells' logs in one archive
  (measured 1+ MB) — fine for a quick sweep, but per-job is cleaner when you need one cell.
- These are only readable once the RUN has left `in_progress`; a per-job `failure` while siblings still
  compile does not mean the log is available yet.

### Each matrix cell fails for an INDEPENDENT reason — classify per-cell, never from one cell

A multi-arch build (e.g. `engine-build-<id>-{cuda,rocm,cpu}`) can have THREE unrelated root causes in the
same settled run. **Pull and read EACH failing cell's own log and classify them separately** — do not
generalize the first cell's error to the other two, and do not stop at the first cause you can name.
Recurring, distinct classes seen in one run of a torch-backed source build:

- `<cmd> Killed` + `##[error]Process completed with exit code 143` at a heavy compile step → **identify the
  signal before naming the cause**. `143` = `128+15` = **SIGTERM** (the process was cancelled/killed
  externally); an OOM kill is `137` = `128+9` = SIGKILL. Confirm memory pressure with
  `dmesg | grep -iE 'killed process|oom-killer'` — **no OOM in dmesg + a multi-hour compile means the
  compile was SIGTERMed (runner timeout, or a manual/local `kill`), not that RAM ran out.** A `143` is not a
  code defect and no source fix changes it; the true unblock is whatever cancelled the compile, and an OOM
  kill (137) means the cell needs a larger/self-hosted runner or a prebuilt base.
- `fatal error: <hdr>.h: No such file or directory` (e.g. `numa.h`) → a **missing system dev package in
  the base image** (e.g. `libnuma-dev`). This IS a skill/base-image fix: add the package to that variant's
  build-deps and regenerate — it is not the pin's fault.
- `Optional package HIP not found` / `does not contain the HIP runtime CMake package` when the pip
  `rocm-sdk-core` wheel is installed → torch's `LoadHIP.cmake` expects `hip-lang-config.cmake` at a path the
  wheel does not populate; the editable build fails at CMake configure even though the uv resolver passed.
- `[engine-image] FAIL <name> not ready after Ns` (the SERVE smoke, distinct from a build failure) → read
  the timestamps AND the N in the message, not just the verdict. The serve smoke's readiness budget is
  `--timeout` (default **600s** in `scripts/engine_smoke.py`), but a cell that passes `--timeout 1200`
  (measured on the vllm cpu cell) fires at 1200s — so read the actual `not ready after Ns` number rather
  than assuming 600. If `docker run -d` and the entrypoint banner (`<engine>/<arch> -> OpenAI API on ...`)
  are ~N apart, the container took the ENTIRE budget just to reach (or never reached) the serve-exec line
  — a **cold-start slow-boot timeout, not a code defect**. Confirm the image itself is sound: the build,
  `--version`/`--help` probe, pytest, and smoke-model download all pass BEFORE this step in the same cell.
  The CI runner removes the container, so `docker logs` is not readable remotely — but **do not assume the
  failed image is unpublished**: a ready-wait-failed cell's image CAN be pullable from the registry (the
  vllm cpu cell's `ghcr.io/asimov-agent/llgenie/vllm:<tag>-cpu` pulled cleanly after its ready-wait
  failure). Check the registry before concluding there is nothing to inspect.

### Reproduce a ready-wait failure locally (gives the real reason CI's log hides)
When a serve-smoke cell fails on readiness and its image IS pullable, reproduce it on the host rather than
reporting an opaque timeout. This is running a published artifact, not building one — allowed by the lane.
1. `docker pull ghcr.io/asimov-agent/llgenie/<engine>:<tag>-<arch>` (the exact tag/head the cell used).
2. **Alias the registry tag to the bare local name CI's smoke uses** — the smoke `docker run`s
   `<engine>:<tag>-<arch>` (no registry prefix), so `docker tag ghcr.io/.../<engine>:<tag>-<arch>
   <engine>:<tag>-<arch>` first, else `docker run` errors `pull access denied ... repository does not exist`.
3. `docker run -d --name smoke -p 127.0.0.1:<port>:11434 -v ~/models:/models --shm-size 2g -e
   LLGENIE_MODEL=/models/smoke/<model> <engine>:<tag>-<arch>` (the host mirrors the smoke model tree under
   `~/models/smoke/`).
4. Probe `curl -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/v1/models` over the window; and
   `docker top` the container. A real cold-load shows `VLLM::Worker`/`Worker` at ~100% CPU with RSS
   climbing (e.g. past 9.8 GB) while the port stays unbound (`000`) — **wedged in model-load/warmup, not a
   hang and not a port/model-path mismatch**. `docker logs` stays silent after the serve line because the
   engine's progress lines do not flush before ready; the process tree is the liveness proof, not the log.
5. `docker rm -f smoke` when done. File it as its own finding (cold-start latency in the engine backend)
   separate from any build/cap narrative — this is orthogonal evidence.

  Distinguish a genuine slow-load from a dead server: a dead/crashed engine exits and leaves no worker;
  a slow-load leaves a high-CPU worker with rising RSS and no bind. Classify cpu as a flake only when a
  prior run's cpu cell passed and this PR touched no cpu knob.

A resolver fix that turns the FIRST error green does not prove the cell green — the next, different layer
error surfaces behind it. Keep box-4 unticked and report each cell's classified cause honestly.

### Before blaming "the flag is missing", read the build CONTEXT actually used

An exit code and a missing build flag are two separate facts — prove the second before concluding it from
the first.

- **The `llgenie-ctx-*` dirs on the host go stale.** `engine_image.py build` materializes a build context
  (`/tmp/llgenie-ctx-*`, or under the profile cache) from one worktree's params. Contexts left over from
  earlier work LACK recent params changes, so grepping an on-disk context's `Dockerfile`/`params.json` for
  the flag (e.g. `MAX_JOBS`) and finding 0 hits proves **nothing about the PR head** — only that the dir is
  old. Read the flag from the committed head instead: `json`-load the PR worktree's params file and print
  the exact `variants.<arch>.install[…]` entry that carries it.
- **A local build proves nothing about the artifact users pull.** CI (`engine-build`) is the sole publisher
  of engine images; a locally built or locally killed image says nothing about the tag in the registry.
  Reproduce the *gate* (the params/eval unit test at the committed head) rather than rebuilding the image
  locally.
- **Report the two facts separately** in the PR comment: "exit N is <signal classification>" and "flag X is
  present at head <sha> in `variants.<arch>.install[k]`" — never "the build failed so the flag is missing".
