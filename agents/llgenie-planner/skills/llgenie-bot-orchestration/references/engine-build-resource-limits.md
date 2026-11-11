# Engine-build reds: classify by exit signal, not "hang"; the levers are RAM, timeout, prebuilt wheels

## A red engine-build cell is not a hang — read its log and classify by the exit signal

A single `engine-build-<engine>-<variant>` cell that ends red without a gate message is almost never a
deadlock. Read the failing step's tail and classify:

```bash
gh run view --job=<jobid> --log | grep -iE 'Killed|exit code|Operation was canceled|out of memory'
```

- `make: *** [Makefile:…: build-engine] Killed` + `##[error]Process completed with exit code 143` = **OOM
  kill**. 143 = 128+15 (SIGTERM); the runner's memory limit reaped the compile. A short 20–40 min job that
  dies mid-compile is an OOM, not a slow build — confirm by `started_at`→`completed_at`.
- `##[error]The operation was canceled` after the job reached its wall-clock `timeout-minutes` = **timeout**.
  The clock ran out; nothing finished wrong.
- `no space left on device` while the log shows `exporting to docker image format` / `importing to docker` /
  `sending tarball` = **buildx export-driver disk blowout**, NOT a config defect and NOT the image being too
  big to build. See the next section — a re-dispatch alone reproduces it.

Neither is "the build is broken". A `Killed` cell proves the runner is under-provisioned for that engine's
compile; a timed-out cell proves the budget is short. Report the measured signal, never "it hangs" — the two
have different remedies and a wrong label sends the lane chasing the wrong fix.

## ENOSPC mid-export is the docker-container driver's ~3x copy — fix it in NO_CACHE_EXPORT, not by re-running

An ENOSPC that fires during **export/import/sending-tarball** — the build itself already succeeded — on a
“push=false” verify build is the documented issue-#1915 class, already encoded in `scripts/engine_image.py`:

- The `docker-container` buildx driver writes the whole image as a **tar**, then unpacks that tar into dockerd
  **on top of** the builder's own content store — about **3x the unpacked image** on disk. A big base cell
  (a prebuilt `rocm/vllm`, a `rocm/pytorch`+torch tree) needs ~3x its size free and dies mid-load even at
  ~106 GiB free, though the build itself pushed fine.
- **Prove the 3x math before dispatching a fix**: `docker manifest inspect <base>` sums the layers (a 22.8 GB
  pytorch/ROCm layer makes a 31 GB compressed base → ~90+ GiB export need). Quote the compressed total and
  the biggest layer digest — that blob is the one named in the ENOSPC error.
- **The fix is one registry entry, not a re-dispatch.** Add `("<engine>", "<variant>")` to `NO_CACHE_EXPORT`
  in `scripts/engine_image.py` (it already carries the `freetoken`/`rocm` precedent with its measured
  footprint and the run ids). That entry flips `_buildx`'s `cache_export` gate so the cell builds on the
  `default` (docker) driver — straight into the daemon, no tar, no second copy — losing only the registry
  cache read/write on that local path. Then re-dispatch the verify.
- A plain re-dispatch on the same driver fails identically: the disk cost is the driver, not a transient. Say
  so on the PR so nobody burns a run proving it.

## The real levers are runner RAM and prebuilt wheels — not the matrix parallelism

- **Lowering `MAX_JOBS` / `HIP_PARALLEL_JOBS` helps but is not sufficient.** A vllm-scale CUDA/HIP compile
  OOMs even at `MAX_JOBS=2` on a 16 GiB runner. The OOM side is fixed by a bigger runner, not a smaller job
  count.
- **Check prebuilt wheels before assuming a source build is required.** `prebuilt: false` in
  `containers/engines/params/<engine>.json` means the Dockerfile compiles from source (multi-hour CUDA/HIP).
  Many engines publish wheels on PyPI; confirm before arguing for a source build:

```bash
python3 -c "import json,urllib.request;d=json.load(urllib.request.urlopen('https://pypi.org/pypi/<engine>/json',timeout=10));print(d['info']['version'], any(u['packagetype']=='bdist_wheel' for u in d['urls']))"
```

A published wheel covering the target archs sidesteps BOTH failures (no multi-hour compile, no compile-time
OOM). Route "switch engine X to its prebuilt wheel" as its own refined issue when the wheel covers the archs.

## Separating an engine into its own pipeline buys isolation and budget — NOT speed

Moving a heavy source-built engine out of the default `make engine-build` matrix into a dedicated pipeline
does not make the compile faster — the compile is the bottleneck. It buys exactly three things, and the design
case must name them:

1. a bigger runner (more RAM) for the OOM side,
2. a longer per-engine timeout for the wall-clock side,
3. failure isolation, so one engine's OOM/timeout does not red the whole sweep.

Frame the proposal that way. "Separate = faster" is false and a lane will (correctly) reject it — the honest
case is that the standard runner does not fit the engine, so the engine needs its own budget.

## Planner move

- Read the engine's params from `origin/main`, not the primary clone: `git show
  origin/main:containers/engines/params/<engine>.json` (the clone is owner-mediated and lags).
- Measure the evidence per cell (job id, started/completed, exit signal) — a conclusion without a job id is a
  claim about time.
- Route the design change (prebuilt wheel, bigger runner, dedicated pipeline) as a refined six-section issue
  to the architect/ci-pipelines owner; the planner files and dispatches, it does not implement.
