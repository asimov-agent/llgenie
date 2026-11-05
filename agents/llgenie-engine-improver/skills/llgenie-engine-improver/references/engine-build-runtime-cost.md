# Engine-build runtime cost: why a cell is slow, and which lever to pull

This is the "the build takes too long / is it broken" diagnosis, adjacent to (but distinct from) the
box-4 proof mechanics in `engine-build-proof-dispatch.md`.

## The cold-compile death spiral (the cell that never warms up)

A cell whose compile EXCEEDS the job's `timeout-minutes` is cancelled mid-compile, and a cancelled build
never finishes its layer — so the layer never lands in the registry build cache. Every rerun is therefore
COLD and recompiles from zero, hitting the identical wall again. A rocm/cuda cell cancelled at *exactly*
the wall time on every run is not "unlucky infra" — it is this loop. Raising the per-job timeout is NOT
the fix (and may be closed as out of scope); the loop only breaks when the cold compile fits under the
wall (fewer archs, or a faster host) or runs on a host that outlasts it.

## Distinguish runner death from a compiler error from a boot cost

Read the job's STEP list — `gh api repos/<owner>/<repo>/actions/runs/<id>/jobs` — and classify by the
step's own timestamps, not the run's overall text:

- **Step has `started_at` set but `completed_at: null` / `conclusion: null`, while the job ended
  `failure`** → the runner DIED mid-step (comms loss / SIGKILL). There is no compiler error and no log
  tail to grep; a bigger or self-hosted runner is the only cure. Do not go hunting the source for a compiler bug.
- **Step concluded `failure` with a real log tail** → a genuine build error; classify it (OOM `Killed`/
  exit 143, missing header, CMake configure). This is the class a source/skill fix can address.
- **Image was already CACHED (`available -> no rebuild`, i.e. its compile succeeded on an earlier run)
  yet the cell still fails** → the failure is downstream of the build (the serve/smoke step), e.g. vLLM on
  a CPU-only hosted runner needing >1200 s just to cold-boot a tiny model. A BOOT-budget problem, not a
  compile problem — do NOT carry the GPU-compile diagnosis onto the cpu cell.

`gh run view --log` for a whole run may OMIT a job that already finished (only the still-running/failed
cells appear), so absence from that stream is not "no log". Pull the step list from the jobs API for the
classification, and the per-job log with `gh run view --job <id> --log` after the run settles.

## Which lever to pull — in-repo vs owner

- **(a) Bigger / self-hosted runner.** The ONLY lever that clears BOTH the cold-compile wall and mid-step
  runner death, and it gives a cell a mutable layer the registry cache can actually land (breaking the
  spiral). NOT implementable from the repo: needs owner/org provisioning — a self-hosted GPU runner, or a
  GitHub paid larger hosted runner. Route the exact provision (cores/RAM/GPU+ROCm) to the owner; once a
  runner exists the `engine-build.yml` change is a `runs-on`/matrix-label ROUTE, not a gate weakening —
  say that explicitly in the PR body.
- **(b) Dockerfile layer split** (stable deps layer keyed on toolchain pins only + volatile source compile
  keyed on params). Reduces RECURRING wall across pin/arch edits (a params edit no longer re-downloads /
  re-resolves the toolchain) but does NOT reduce the first cold compile — so it does not break the spiral.
  Note: any change to `scripts/engine_runner.py` re-tags EVERY engine.
- **(c) Arch trim.** Directly shortens the cold compile (fewer nvcc/HIP targets). Before trimming, diff the
  compiled FAT list (`FAT_CUDA_ARCHS` / `FAT_GPU_TARGETS` in `engine_skills.py`) against the skill's
  DECLARED `requires.gpu_targets`: dropping an UNDECLARED arch (compiled but not advertised) is a safe
  cleanup; dropping a DECLARED arch is a product-coverage decision the owner must make. Watch the reverse
  too — a declared target MISSING from the fat list (declared-but-uncompiled) is a coverage gap to fix,
  not fat to trim.

  **Do (c) per-engine, never by editing the global fat constant.** The skill's `container.<backend>` block
  may carry a `gpu_targets` key that `_arch_variants` reads in place of `FAT_GPU_TARGETS`
  (`spec.get("gpu_targets", FAT_GPU_TARGETS)`); setting it there moves ONLY that engine's arch list, so
  every other engine's generated `params/<id>.json` + Dockerfile stays byte-identical. Procedure:
  1. Set the trimmed list under `container.<backend>.gpu_targets` in the engine's `SKILL.md`.
  2. Align `requires.gpu_targets.<backend>` to the built set — that field is the ONLY one that BLOCKS a
     host GPU at check time; the build list alone does not.
  3. Regenerate with `make generate-engine-params ENGINE=<id>` — never hand-edit `params/*.json` or the
     Dockerfile, they are generated.
  4. Prove determinism with `make check-engine-params` (must report 0 stale) instead of wrestling a local
     pytest — it is the deterministic regeneracy gate and needs no test harness.
  5. Confirm blast radius with `git diff --stat`: exactly the skill + its params + its Dockerfile should
     move. Any OTHER engine's file changing means the trim leaked into the global constant — revert and
     scope it to the per-container override.

  **An arch trim degrades coverage to a warning, not a block.** `pick_variant` still returns the
  `<backend>` variant for a host GPU whose gfx is outside the built list, emitting a stderr note
  (`<id>/<backend> image targets ...`). So trimming alone never blocks a mismatched host; only step 2's
  `requires.gpu_targets` does — pick deliberately. Before trimming, grep the test tree for the fat/arch
  symbol: a test may lock the exact string for some engine; a per-container override leaves that lock
  untouched as long as the locked engine is a different one.
- **(d) Tighten the merge gate.** Weakens a guard — never without owner sign-off.

Never pick (b)/(c) silently as a "fix" for an (a)-class wall: they trade product coverage or build
complexity for wall time and need an explicit owner call. Report which lever, why the others were
rejected, and the measured facts that drove it (cells cancelled at *exactly* the wall; a step with no
completion) — not a guess.
