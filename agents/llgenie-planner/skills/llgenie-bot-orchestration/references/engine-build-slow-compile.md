# engine-build vllm cells: why the build "download" takes hours

Measured run `41767119317` (head `11f9b272`), run #102.

## The cells are already independent — don't re-shape the matrix
engine-build.yml runs each engine x variant as its own parallel matrix element
(`max-parallel: 20`, `fail-fast: false`). vllm rocm / cuda / cpu launched
simultaneously at 06:43:00Z. One cell dying does NOT cancel the others. So "pull
rocm/cuda out of the matrix into a separate stage" is NOT the fix — they already
are separate stages.

## The cost is the COMPILE, not the download
- rocm: cancelled at exactly 4h00m = hit `timeout-minutes: 240` on a 16 GiB
  `ubuntu-latest` HOSTED runner ("hosted runner lost communication"). The 8-gfx
  HIP compile never finishes -> compile layer never lands in registry cache ->
  every rerun is cold -> always cancelled.
- cuda: SIGKILL / runner comms lost at ~1h13m mid-compile of 6 CUDA archs
  (75;80;86;89;90;120).
- cpu: was CACHED; its failure is only the serve-smoke readiness budget
  (>1200s cold boot on CPU-only hosted), not compile.
- `Dockerfile.cuda` is `FROM llgenie/base-cuda` and the base is already GHCR
  layer-cached (`engine_image.py` `--cache-to type=registry mode=max`), so the
  base download IS reused on a cache hit. The multi-hour cost is one fat `RUN`
  -> `engine_runner.py install` -> `uv pip install -e .` (editable, per-arch
  compile), not network bandwidth.
- Layer trap: that fat `RUN` sits right after `COPY ... params.json`, so ANY
  committed params edit invalidates the whole compile layer -> fix-PRs that
  move the pin/arch list re-run cold every commit.

## Options when the owner asks to speed it up (engine-lane owns implementation)
(a) Route GPU/recompile cells to a self-hosted runner (NVIDIA + ROCm>=7) OR a
    GitHub paid larger hosted runner (8-16 core / 32 GiB). Biggest win: removes
    both the 240 wall and the comms-loss. OWNER-BLOCKED: needs provisioning
    (#1694). A `runs-on` route change, not a gate weakening.
(b) Split the fat `RUN` into stable-deps layer (keyed on requirements file hash)
    + volatile-source layer. Cuts recurring-edit wall, not the cold wall; touches
    `engine_runner.py` (re-tags every engine). Safer in-repo choose.
(c) Trim the arch set — drops a DECLARED gpu_target (skill declares
    gfx90a/gfx950/gfx1150 uncompiled) = product-coverage decision for owner.
(d) Scope the engine-build merge gate tighter so one slow cell does not stall
    the whole PR's boxes (ci.yml ~332: "pin gate waits for engine-build to publish").

## Planner's role
Dispatch the diagnosis to @llgenie-engine-improver as a bounded task (name the
run id + measured cell timings so the lane doesn't re-prove them; list options
with acceptance criteria; flag the owner-provisioned runner as the owner call).
Do not implement. Relay the owner-blocked provision to the owner for the
(a)/(b)/(c) decision.
