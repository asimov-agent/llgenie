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

### The `docker pull <compute-tag> → manifest unknown` line is the cold-build ENTRY, not a defect
A never-yet-built cell's log opens with `docker pull ghcr.io/.../<id>:<pin>-<hash>-<variant>` failing with
`manifest unknown`, then `imagetools inspect ...buildcache-<variant>` absent → `cold build (cache read
skipped)`. That is the #1842/#1880 cache path working as designed — the tag has not been published because
no build has ever finished, so there is nothing to pull and nothing to warm from. Do NOT report the
`manifest unknown` as the cause or as "tag missing = code defect"; it merely proves this run is cold. The
cause lives in whatever kills the cold compile below.

### Telling a concurrency-cap kill from a per-cell OOM/SIGKILL — the timestamps decide
A cell that ends `Killed` is NOT automatically the concurrency/timeout cap. Compute the two clocks from
`gh api repos/<o>/<r>/actions/runs/<id>` + `/jobs`: `run.created_at` vs the failing step's `completed_at`,
then subtract. If the cell ran LONGER than the workflow's cap window (a ~44-min cell alone under a 30-min
cap), the cap did NOT fire — the process was SIGKILLed from below (OOM-killer / host pressure). Never file
"hit the concurrency cap" when the arithmetic disproves it; cap and OOM are opposite routing classes
(cap = wall/scheduling, OOM = host RAM; both want a bigger runner, but a shorter timeout cures neither).

Read the exit code before naming the root — the two kill classes have different log signatures:

- `make: *** [<Makefile>:<line>: <target>] Killed` + exit **2** → SIGKILL from the OOM killer. Usually NO
docker error line precedes it (the compile was simply cut off); the same cold compile re-hits it every run.
- `wait: No child processes` + exit **143** → SIGTERM, a runner shutdown / cancellation, not OOM.
2-vs-143 is the difference between an OOM tracker and a runner-shutdown tracker — quote the exit code in
the finding so it routes correctly.

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
- **(e) `FROM` an upstream prebuilt engine image** (e.g. AMD's `docker.io/rocm/vllm`). The prebuilt
  bakes the CUDA/ROCm toolchain, torch, triton and vendor QA — exactly the levers that consume the
  ~40-min cold wall. There are TWO shapes and they are NOT interchangeable; pick by whether the pin must
  survive:

  **e1 — thin prebuilt cell (zero compile, pin NOT preserved).** `prebuilt: true` + `base: <upstream
  image>` in the skill's `container.<backend>` block: the generator emits `install: []` and a Dockerfile
  that is ONLY `FROM <base>` + the entrypoint/healthcheck wrap. No `-e .`, no toolchain, no poetry — the
  served engine version is the BASE's baked one, and the pin in the skill is documentation only. Choose
  this whenever the owner says "build a Dockerfile based on the base image, trim it, that's it": it is
  the cheapest cell and the base carries vendor QA. `detect` must probe the BAKED base, not a build
  artifact (`python3 -c 'from vllm import __version__ as v; print(v)'`), and the cell's "separate
  pipeline" is the EXISTING per-cell dispatch (`--field engine=<id> --field arch=<backend>`) — never a
  new workflow. Vendor the pattern from an engine already built this way (`prebuilt: true` precedents:
  sglang, tensorrt-llm) instead of inventing a mechanism.

  **e2 — multi-stage overlay (keeps the pin, keeps a smaller compile).** Build YOUR pinned commit on the
  devel base and land it in a final stage `FROM <prebuilt>` via `runtime_base`, copying the compiled
  site-packages across. Only reach for e2 when the pin MUST be preserved; it still compiles the pinned
  delta, so it is a strictly more complex and slower cell than e1.

  Either shape is a build-strategy / product-coverage decision the owner makes; state the tradeoff
  explicitly ("served version = base's baked one, pin not enforced" for e1) and never silently lower the
  pin without saying so.
  Probe the real state before wiring: `docker manifest inspect docker.io/<repo>:<tag>` plus a local run of
  the base to record its python version, present toolchain (`uv cmake hipcc gcc make ninja git`) and
  baked engine version — see `rocm-build-verification.md` for the measured rocm/vllm version gap and the
  base-probe recipe.

  **The multi-stage seam (e2) is `runtime_base`** — `engine_skills.py` renders `FROM <build base> AS build`
  then a separate final stage `FROM <runtime_base>`. Point `runtime_base` at the prebuilt tag; the build
  stage still compiles your pin. Do not hand-roll this seam when e1 fits — `prebuilt: true` is one
  boolean and no compile. Two defects this shape has shipped before, both silent:
  1. **The final stage must COPY your compiled site-packages, not just `/opt/llgenie/app`.** A runtime
     stage that copies only the entrypoint+params layer bakes the BASE's older engine and never ships your
     pin — the image builds green and serves the wrong version. After generating, read the final stage's
     `COPY --from=build` lines and confirm they carry the installed package tree; prove it by
     `docker run --rm <image> <binary> --version` matching the PIN, not the base's baked version.
  2. **An invented container key is silently ignored.** A field you add to the skill's `container:` block
     (e.g. `install_wheel:`) that `engine_skills.py` never reads produces no Dockerfile change and no
     error. Before relying on any new key, grep the parser for it (`grep -n <key> scripts/engine_skills.py`)
     and confirm the generated params/Dockerfile actually changed — a key the parser does not read is a
     no-op that looks like a fix.

Never pick (b)/(c) silently as a "fix" for an (a)-class wall: they trade product coverage or build
complexity for wall time and need an explicit owner call. Report which lever, why the others were
rejected, and the measured facts that drove it (cells cancelled at *exactly* the wall; a step with no
completion) — not a guess.
