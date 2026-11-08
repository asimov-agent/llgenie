# A repin PR must actually dispatch, and a cold compile must show its progress (issue #2089)

## The defects

Both sit on the engine-build path, and both make a failing cell unactionable.

**The dispatch.** `engine-build-pr-trigger.yml` called `make engine-build-pr-trigger BASE=<sha>` with
no branch, so `scripts/engine_build_trigger.py` dispatched at `git rev-parse --abbrev-ref HEAD` —
which on a `pull_request` checkout is the literal `HEAD`. `gh workflow run --ref HEAD` is refused
with `HTTP 422 No ref found for: HEAD`, so a repin PR never built.

A second, independent defect sat in the same argv: `["--field", *fields]` handed `push=true` to `gh`
as a POSITIONAL argument (`--field` takes one value), so the CLI rejected the invocation before any
ref was resolved. Fixing only the ref would have changed nothing.

Measured from the failing job's own log on `main` (run `42423190271`, job `128555865778`, the
`pull_request` trigger run on PR #1982's branch — whose workflow half already passed a correct
`BRANCH=`):

```
[will] dispatching engine-build push=true engine=surogate @ agent/issue-1962-surogate-skill
[will] FAIL engine=surogate: run  concluded queued/None
```

An EMPTY run id, averaged over a 90 s discovery window, with the rejection's own text dropped — the
verdict says "refused" and nothing says why.

**The silent log.** `engine_image._sh` runs through `proc.run_ok`, which CAPTURES both streams. Every
build step went through it, so a 30-60 minute HIP/nvcc compile printed nothing until the step ended;
when the runner SIGKILLed it (`make: Killed`, run `41696864556`) the log carried no compiler progress
to say which step died. Every rerun was a blind 1-4 hour experiment.

## What changed

- Workflow + Makefile: `BRANCH="${{ github.head_ref }}"` → `$(if $(BRANCH),--branch "$(BRANCH)",)`.
- `engine_build_trigger._dispatch_ref()`: explicit `--branch` → `GITHUB_HEAD_REF` → the checkout's own
  branch → `""`. `check()` refuses (exit 1) with a message naming both inputs rather than dispatching
  at a ref GitHub cannot resolve; `--branch HEAD` is treated as no ref, not as a ref called HEAD.
- `engine_build_trigger._workflow_run_args()`: one `--field` per input.
- A non-zero `gh workflow run` now concludes `dispatch-failed` and the failure line prints the CLI's
  text (`HTTP 422 …`), instead of awaiting a run that never started.
- `proc.run_live`: a fourth named policy — the child inherits the caller's descriptors, so its lines
  land on the log as they are written; `rc` is returned and a non-zero exit never raises, exactly
  `run_ok`'s contract. `engine_image._sh_live` wraps it and is wired at BOTH `buildx build` sites
  (the `--push` build and the local build); the short post-build `pull`/`tag` calls stay captured.

## Proof

- `tests/test_proc.py` — the child's line is readable from a pipe WHILE the child is still sleeping
  (a capturing policy cannot pass), both streams arrive at fd level (`capfd`), and the exit code is
  still returned (`rc == 7`, no raise).
- `tests/test_engine_build_trigger.py` — a detached checkout with `GITHUB_HEAD_REF` dispatches at
  `--ref <head branch>` and records the dispatched run id (`producer run 77 success`); a checkout with
  no ref anywhere dispatches NOTHING and exits 1; the argv carries three `--field` pairs for three
  inputs; a rejected dispatch prints the CLI's reason.
- `tests/test_engine_image_matrix.py` — both build steps reach `run_live` with `--progress=plain`,
  and the fake `_sh` asserts that no `buildx build` command is captured.
- Discrimination: with `origin/main`'s `engine_image._buildx`, the two new image tests fail (the build
  goes through `_sh`, which the fake refuses); with `main`'s argv, the `--field` test fails.

## What this does not do

It does not carry #1696's other hunks. Deliberately dropped: the rocm gfx trim (its justification was
the 240-minute wall `engine-build.yml` no longer has, and it silently drops
gfx1030/gfx1102/gfx1151/gfx1200), the AMD `--extra-index-url` (disproven), and the 240→480 fold
(obsolete).

## Files

- `.github/workflows/engine-build-pr-trigger.yml`, `Makefile`
- `scripts/engine_build_trigger.py`, `scripts/proc.py`, `scripts/engine_image.py`,
  `scripts/check_proc_gate.py` (the docstring that counts the policies)
- `tests/test_engine_build_trigger.py`, `tests/test_proc.py`, `tests/test_engine_image_matrix.py`
- `openspec/changes/engine-build-dispatch-and-live-log/` — this change.
