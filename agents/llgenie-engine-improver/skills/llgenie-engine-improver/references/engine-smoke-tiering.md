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

## Hermetic test recipe (no docker, no GPU)

Exercise the tier logic in-process by monkeypatching the module the smoke reads:

- patch the runtime constant + the manifest lookup to return `{"binary": ..., "flags": [...], "probe": "device"}`
  and assert the device case returns 0 (skip) with no `subprocess` call;
- unit-test the verdict helper directly: exit 0 + text => pass, exit 1 => fail, exit 0 + empty => fail;
- assert the no-binary-in-plan case fails loudly.

Run it with the repo python from the PR worktree; `check-docs`/`check-workflows`/`check-engine-params`/
`lint_linefeeds` are the local gates a smoke-script change must also pass before push.
