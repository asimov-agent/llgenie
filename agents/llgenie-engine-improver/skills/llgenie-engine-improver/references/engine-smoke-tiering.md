# Engine smoke tiering: gate on the BINARY, serve only on request

A build-time engine smoke must prove the engine **binary runs**, not that a served endpoint came up within
some readiness budget. Validating only by serving turns a slow/flaky endpoint — or an exhausted runner
budget — into a red engine build (`llgenie-smoke-<id> not ready after 1200s`), which says nothing about
whether the artifact is good.

## The two tiers

| tier | what it runs | cost | when |
|---|---|---|---|
| **binary smoke (DEFAULT)** | `docker run --rm <tag> <binary> --version` and `<binary> -h` (or the flags the skill/plan declares), each requiring **exit 0 AND non-empty output** | near-instant, deterministic | every engine build; `make test-engine`; the `TEST=serve` matrix cell |
| **serve tier (`--serve`)** | an actual image run + ready-poll + OpenAI-SDK conformance | minutes, flaky | only where serving IS the contract: the AS-PUBLISHED push serve-leg (`test-published-engine`) and an explicit `make test-engine-serve` |

The extra `test-engine-serve` target keeps the old behaviour reachable; opting the push serve-leg into
`--serve` means no serving coverage is lost, it just stops being the build gate.

## Pitfalls

- **`probe: device` variants (vllm cuda/rocm) cannot binary-smoke** — they need a device at startup. Detect
the policy and SKIP them in the binary tier (report it), letting the serve tier answer; do not fail the
build on a device-only engine.
- **Require non-empty stdout, not just exit 0.** A binary that exits 0 with no output has not proven it
  can run; treat empty output as a failure.
- **A change to `TEST=serve` semantics leaves the matrix rows untouched** — the matrix still says
  `serve` for cpu / `detect` for GPU; only what `serve` *means* changed. Do not "fix" the matrix to make
  a smoke pass; the matrix values are asserted by a unit test.
- **Proving this PR restarts NO engine build.** `engine-build` is `workflow_dispatch`-only, so a PR that
  edits the smoke script/Makefile/docs runs only `ci.yml` (unit/lint/openspec, no engine images). Say that
  explicitly when a stop-all-CI order is in force — this PR cannot restart the engine-build storm.

## A readiness timeout is blind unless you dump the engine's own log

`engine_runner.py serve` redirects the engine's real output to `$TMPDIR/engine-runner-serve.log`
**inside** the container, so `docker logs` carries only the launcher banner. A failed readiness wait
therefore reports `not ready after Ns` with no reason at all, and the evidence is gone before anyone can
ask for it: `engine_smoke.py` removes the container in a `finally`.

- **Dump the in-container log on the failure path, before returning.**
  `docker exec <name> sh -c 'tail -c 4000 "${TMPDIR:-/tmp}/engine-runner-serve.log"'` plus
  `docker logs --tail 60`, printed ahead of the FAIL line, on BOTH the timeout and the early-exit branch.
  A best-effort dump that prints `EMPTY/absent` for a genuinely silent engine is still the right verdict —
  "the engine produced no output" is a finding, not a non-answer.
- **`[entrypoint] …` and `[engine-runner] serve …` lines in a job log are the failure DUMP, not live
  output.** They arrive from the harness's `docker logs --tail 20` on the give-up path, so their
  timestamps sit at the END of the wait, not at container start. Never compute a boot duration from them
  (a 600 s gap between `docker run -d` and the banner is the poll window, not a slow start), and never
  read "only two lines" as "it crashed immediately" — the container may have been Running the whole time.
- **A serve red is not an image red.** The binary tier passing (`--version`/`--help` answered, image
  `available -> no rebuild`) plus a serve timeout means the artifact runs but never answered the health
  probe: state that split before blaming params or a pin.
- **`engine_image.py` is not one of the four tag inputs**, so adding diagnostics there moves no image tag
  and re-tags no engine — it is the safe place to fix a blind red, unlike params/Dockerfile/`entrypoint.sh`.

## Hermetic test recipe (no docker, no GPU)

Exercise the tier logic in-process by monkeypatching the module the smoke reads:

- patch the runtime constant + the manifest lookup to return `{"binary": ..., "flags": [...], "probe": "device"}`
  and assert the device case returns 0 (skip) with no `subprocess` call;
- unit-test the verdict helper directly: exit 0 + text => pass, exit 1 => fail, exit 0 + empty => fail;
- assert the no-binary-in-plan case fails loudly.

Run it with the repo python from the PR worktree; `check-docs`/`check-workflows`/`check-engine-params`/
`lint_linefeeds` are the local gates a smoke-script change must also pass before push.
