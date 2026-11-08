# engine-build dispatch at the branch ref, and a cold cell's log streamed (issue #2089)

## Why

Two defects sit on the same path — the engine-build dispatch and the engine-build log — and both
make a failing cell impossible to act on.

**1. A `pull_request` run of `engine-build-pr-trigger.yml` dispatched nothing.** The workflow called
`make engine-build-pr-trigger BASE=<sha>` with no branch, so the script dispatched at
`git rev-parse --abbrev-ref HEAD`, which on a `pull_request` checkout is the literal `HEAD` — and
`gh workflow run --ref HEAD` is rejected with `HTTP 422 No ref found for: HEAD`. So a repin PR was
never actually built: the verdict read "refused" rather than red-or-green. Measured on `main`
before this change (run `42423190271`, job `128555865778`, head of PR #1982's branch):

```
[will] dispatching engine-build push=true engine=surogate @ agent/issue-1962-surogate-skill
[will] FAIL engine=surogate: run  concluded queued/None
```

An EMPTY run id and no reason — the dispatch was rejected and the rejection's own text was dropped.

**2. A second, independent defect in the same call.** The dispatch argv was
`["--field", *fields]`, i.e. `gh workflow run … --field engine=x push=true`. `--field` takes ONE
value, so `push=true` was passed as a POSITIONAL argument; the CLI rejects the invocation and no run
starts. Fixing only the ref would still have produced `run  concluded queued/None`.

**3. A cold engine cell's log was silent until the step ended.** `scripts/engine_image.py` ran every
build step through `_sh`, which CAPTURES stdout/stderr (`run_ok`). A 30-60 minute HIP/nvcc compile
therefore printed nothing on the run log until it finished, and when the runner SIGKILLed it
(`make: Killed`, run `41696864556`) the log carried no compiler progress to say which step died — so
every rerun was a 1-4 hour blind experiment.

These are the two unowned survivors of the closed PR #1696 (its AMD-index route is disproven; the
disposition table is on PR #1696 `#issuecomment-6716790356`).

## What changes

- `.github/workflows/engine-build-pr-trigger.yml` — pass `BRANCH="${{ github.head_ref }}"`.
- `Makefile` — `engine-build-pr-trigger` forwards `$(if $(BRANCH),--branch "$(BRANCH)",)`.
- `scripts/engine_build_trigger.py` — `_dispatch_ref()` resolves the dispatch ref in order
  (explicit `--branch`, `GITHUB_HEAD_REF`, the checkout's own branch) and returns `""` when the
  checkout names none; `check()` then REFUSES with a message naming both inputs instead of
  dispatching at a ref GitHub cannot resolve. `_workflow_run_args()` gives every input its own
  `--field`. A non-zero `gh workflow run` is reported as `dispatch-failed` carrying the CLI's own
  error text, and the failure line prints it.
- `scripts/proc.py` — a fourth named policy, `run_live`: the child inherits the caller's descriptors
  (no capture buffer), so its lines land on the log as they are written; same non-raising `rc`
  contract as `run_ok`.
- `scripts/engine_image.py` — `_sh_live` (the streaming twin of `_sh`) wired at BOTH `buildx build`
  call sites (the `--push` build and the local build). Short post-build `pull`/`tag` calls stay on
  the capturing `_sh`, where a failure is re-surfaced in one block.

## Impact

- No image tag moves: `engine_image.py` is not one of the four tag inputs (variant params JSON,
  `Dockerfile.<variant>`, `containers/engines/entrypoint.sh`, `scripts/engine_runner.py`).
- No gate is weakened: the readiness/exit-code contracts are unchanged, and the trigger's exit code
  for a real failure is unchanged (a rejected dispatch was already a failure — it now says why).
- Not carried from #1696, deliberately: the rocm gfx trim (its 240-minute justification is gone from
  `engine-build.yml`, and it silently drops gfx1030/gfx1102/gfx1151/gfx1200), the AMD
  `--extra-index-url` hunk (disproven) and the 240→480 fold (obsolete).
