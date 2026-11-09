# Wire truth, make gates, and skip guards

## Floating payload vs wire vehicle (measured #1746/#1747, 2026-11-05)

A fix commit that exists only in a local worktree — prepared to ride a lease-pushed PR
(#1696's `ff5e19e1`), never pushed, never on a remote branch — has NO wire presence.
If another lane opens its own PR (#1747, `fix/engine-build-cache-write-driver`) for
the same root cause at a remote head, THAT PR is the sole wire vehicle; a floating
superset of it becomes moot once theirs lands. Accept the adjudication when it's
posted on the PR's own issue (planner comment 6648710317): no duplicate close, no
re-push of the floating payload, message the overlapping lane directly. Before
flagging overlap, check whether the wire PR's fix is a SUBSET of yours:

- #1747's fix = gate `--builder default` on `not CACHE_WRITE` (one-liner in `_buildx()`).
- `ff5e19e1`'s fix = `_buildx_active()` (picks the `*` active docker-container
  builder from `buildx ls`) + `_buildx_driver()` (gates `--cache-to` to that driver),
  then integrates into `_buildx()`.

Both target the same root cause (`Cache export is not supported for the docker driver`
from forcing the classic `default` docker driver over the container builder), same file
`scripts/engine_image.py`, same function `_buildx()`. The wire vehicle wins.

## Make skip-guard pitfall (measured #1745, 2026-11-05)

A make recipe line ending `...; exit 0` — even split across `\` continuations — only
terminates THAT recipe-line's own shell. GNU make treats exit 0 as success and runs
the NEXT recipe line. To short-circuit a make target, the follow-up commands must be
gated in the same shell branch (e.g. the `make engine-launchers` / `test-built-engine`
/ `ci-install-uninstall` recipe lines sit in the `else` of an `if [ -n "$$reason" ]`
guard), or they still run.

Measured: `Makefile:287-288` of llgenie's `test-engine-install` printed the #1240
cuda install-leg SKIP reason verbatim, then line 289 `make engine-launchers ...`
still ran, and `install_engine_launchers.py:563`
(`if arch == "cuda" and not LLGENIE_NO_GPU and not cuda_cdi_ready():`) printed
`[install] FAIL cuda host without the NVIDIA CDI spec` and returned 1 → exit 2. Both
freetoken-cuda (job 127017336344) and sglang-cuda (127017336425) red this way, while
CPU cells (no CDI guard) were green. Where the guard should live: the `if` must gate
the launcher-install calls themselves (the `else` branch), or the workflow
(`engine-build.yml` step running `make test-engine-install`) pre-computes
`--install-leg-skip-reason` and skips the step.

## Serve-readiness vs chat-probe timeout (measured #1745 mlx-cpu)

`test-engine-host` (Makefile:1378) can red when the published image's container
reports READY at the HTTP-listen level but the first inference (a CPU model load,
4-bit) takes longer than the host-verify chat probe. mlx-cpu job 127017336294:
`docker run -d` 03:01:20.512, READY 03:07:29.163 (6m09s later — 4-bit model load),
`TimeoutError: timed out` right after at `engine_host_test.py:117` (urlopen) via
`serve_published:165` → `_chat:124` (retries=2/sleep3; line 166 caps the probe
budget to `min(timeout,120)`). This is a readiness/serve-timing divergence at
`test-engine-host`, distinct from install-leg reds — classify separately and add
the evidence to the serve-gate tracker (#1748), not an install-leg tracker.

CLASSIFICATION (re-verified, pipeline lane corroborated 2026-11-05): mlx/cpu is a
CAPABLE serve cell — documented `--help`, probed `--help --version -h -V`, reached
READY with served-ids, `mlx.archs=[cpu,cuda,metal]` — that timed out on its
`/v1/chat/completions` first-token probe (issue #1322 contract), NOT a de-scope
case. The defect is a warm-up/model-load timing gap in the probe budget
(`engine_host_test.py::_chat`), so the fix is in the probe/retry/timeout budget,
NOT a gate change (no second vehicle on `engine_host_test.py`).

## buildx FROM-local-load vs registry-cache write (measured #1753, 2026-11-05)

docker-container buildx driver can EXPORT a registry cache (`--cache-to`) but cannot
resolve a base image that a SEPARATE earlier `buildx build --load` put only in the
docker daemon — buildkit solves `FROM <base>` against its OWN store and falls through
to the registry, denying access on a private pull. The docker `default` driver sees
daemon-local images (FROM works) but cannot `--cache-to`. The two properties are
mutually exclusive per driver; a derived-cell `FROM <base>` and a capped `--cache-to`
cannot both ride one driver. A fix must make the base resolvable on the cache-capable
driver without a daemon push (single buildx invocation with the base as an internal
stage, or a registry the builder can pull), NOT by re-gating `--cache-to` — re-gating
only the cache write does nothing for FROM-base resolution. Measured: run 41971301136,
job 127060077658 (mlx-cpu): base `--load` onto docker-container (log 389), derived
FROM resolves against buildkit store, absent, pulls docker.io → `pull access denied
insufficient_scope` (402–415), Makefile:1306 exit 1. `_buildx_active()` returning the
docker-container builder on CI reproduces this on the CACHE_WRITE path. PROVEN FIX (PR
#1756, single-invocation): fold Dockerfile.<backend> in as the first stage (`AS
llgenie-base`) and rewrite the derived `FROM llgenie/base-cpu:<sha>` -> `FROM llgenie-base`,
lifting base+derived in ONE buildx call; the read-only verification cell has NO push rights
so a pullable-registry FROM is impossible — internal stage is the only shape. Local probe
(Docker 29.9.2): on docker-container a prior-invocation base via `-t`/`--load`/`--output
type=image` is NEVER `FROM`-resolvable; only an internal-stage base resolves. NEVER hold
FROM-base work on a --cache-to re-gate (it changes no FROM-resolution line). base
Dockerfile byte-identical to render (hashes d0eb107fa0, the failing sha).

## Same root cause, different terminal failure (measured #1745 vllm cells)

Two cells for one engine can red on DIFFERENT terminal causes even when they share
the same diagnosed root cause. Both vllm cells forced `--builder default --no-cache`
(`_buildx()`; lines 388–392 verbatim) yet: vllm-rocm (127017336436) died on
`ModuleNotFoundError: No module named 'poetry'` → uv `rocm@0.1.0 … doesn't declare it
as a build dependency` at Dockerfile:18 (code/build-dep fix — add poetry to
`[tool.uv.extra-build-dependencies]`), while vllm-cuda (127017336439) ran 32 min on
the forced docker driver then `##[error]… exit code 137` (OOM/shutdown kill, no diag
line). So a fix that resolves the driver (the #1696/#1747 `--builder default` gate)
does NOT necessarily resolve both cells — always confirm each cell's terminal failure
separately, and tell the reader each distinct follow-on. The driver fix is the
prerequisite (the docker driver is why the fresh `--no-cache` build exceeds budget),
but rocm additionally needs its poetry build-dep declared.
