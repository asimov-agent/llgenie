# The engine build sweep, the binary probe, and "from source"

Hard-won rules from building/verifying every engine x arch cell (llgenie issues #614/#615).

## Running tests in this repo

The host venv has no pytest: run pytest through the test image, never `python -m pytest` on the host.

```bash
docker run --rm -v "$PWD":/workspace -w /workspace llgenie/test:latest python -m pytest tests/x.py -q
```

Image builds are idempotent — a second `make build-engines` re-uses the built image and only
re-probes, so a re-run for a green sweep is cheap. A first full sweep with `JOBS=3` takes over an
hour (fat CUDA/ROCm bases).

## The binary probe: `flags`, `device`, `help`

`scripts/engine_image.py::decide()` proves a built image's binary. Policies come from the skill's
`binary_probe:` map, written to `containers/engines/binaries.json` by
`scripts/engine_skills.py::probe_policy()` (which passes through only `device` and `help`; anything
else falls back to `flags`).

- `flags` (default) — the documented flags must answer AND the version family (`--version`/`-V`) must answer.
- `device` — the CLI needs its device; containment, version from `detect`.
- `help` — the CLI's parser has **no version flag at all** (argparse). The help family must answer; the
  version comes from the image's `detect`. Use it for `mlx_lm.server` (mlx cpu) and `sglang` (cuda/rocm).
  Without it the probe reds an engine for a flag it never had; `flags` stays right for everything that
  does have `--version`.

Adding a policy needs three edits or `ci-unit` reds: `BINARY_PROBES` in `scripts/engine_skills.py`
(the validator), the `entry["probe"]` tuple in `tests/test_engine_skills.py`, and the skill's
`binary_probe:` map.

### What a green `device` row proves — and how to prove more on a GPU host

A `device` cell is green when the binary FILE exists in the image and the entrypoint `detect` printed a
version. That is **not** "the server starts": on a GPU-less runner every flag exits 1 with
`ImportError: libcuda.so.1: cannot open shared object file`, and some `detect` lines end in
`|| python3 -c 'import importlib.metadata…'` — a pip-metadata fallback that answers even when the CLI cannot
load. Report it as "wheels installed + version line", never as "serves".

The real proof of a GPU-only image is a host with the card (Metal cannot reach a container; NVIDIA can):

```bash
nvidia-ctk cdi list                    # nvidia.com/gpu=all must be listed
#   missing: sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
docker run --rm --device nvidia.com/gpu=all --entrypoint bash <image> -c '<binary> --help; echo exit=$?'
docker run --rm --device nvidia.com/gpu=all --entrypoint python3 <image> \
  -c 'import mlx.core as mx; print(mx.default_device())'   # Device(gpu, 0)
make test-engine ENGINE=<id> ARCH=<arch>                   # serves a tiny model, chats on /v1/chat/completions
```

The contrast is the evidence: WITH `--device` the probe answers and `default_device()` is `Device(gpu, 0)`;
WITHOUT it the same command raises the `ImportError` the runner reports as `NO ANSWER (exit 1)`. Quote both
so "the image is broken" is never concluded from a runner limitation.

### A pytest in a make recipe must carry a container/venv seam

Stronger than "do not run pytest on the host": at recipe level, any line invoking `python3 -m pytest` (or a
bare `pytest`) must carry `$(TEST_RUN)`, `$(ENGINE_TEST_RUN)`, `$(call engine_test,…)`,
`llgenie/test:latest`, or a venv interpreter (`$(PY)`, `$(VENV_GUARD)`, `$(NATIVE_GUARD)`,
`.../bin/python`). The runner has a `python3` and no pytest, so a bare call fails with
`No module named pytest` AFTER the pull and digest check pass — which reads as an engine defect in the
engine-named job. A guard test that joins `\`-continuations, skips recipe comments and checks this is cheap;
write it so a bare `pytest tests/x.py` line is caught and a venv line is not.

## `test-engine-stage` order: flags first, then serve

`TEST=serve` runs `make test-engine-image` (flag probe) and only then `make test-engine`, joined with
`&&`. Otherwise every cpu cell is published without its binary ever being executed. `TEST=detect` is
the flag probe alone.

## "From source" is a checked claim: `make check-engine-source`

`scripts/engine_source_guard.py` (in `ci-unit`) reads the committed params and fails a
`prebuilt: false` cell that:

1. has no build command in its install steps (cmake/make/cargo/go/nvcc/`setup.py`/
   `pip install <tree>`/`get_llama_cpp(`/`CMAKE_ARGS=`),
2. downloads a built artefact (curl/wget/tar/unzip of `.tar*`/`.whl`/`.zip`),
3. clones an unpinned reference (no sha / version tag / `checkout`),
4. generates a Dockerfile whose first `FROM` is an upstream build of that same engine (the llama.cpp
   regression). Shared `llgenie/base-*` and toolchain images like `rocm/pytorch` are fine — strip
   backend words (`rocm`, `cuda`, `vulkan`, `cpu`, `metal`, `gpu`) from the tokens or
   `exllamav3-rocm` false-positives on `rocm/pytorch`.

Cells that genuinely have no source build yet live in `KNOWN_NOT_SOURCE` with a reason and an issue;
they are reported, not fatal, so the gate reds only on a NEW false claim. Converting a cell =
deleting its entry. `make engine-source-report` prints the census.

## Shape of an engine skill's params

The generated Dockerfile does NOT inline the build: it copies `params.json` and runs
`python3 engine_runner.py install params.json`, so the params `install` list IS the build script —
the single place to check or fix. Grepping the Dockerfile for `cmake` finds nothing; do not "fix" a
build by editing the Dockerfile.

## Publish only after the test

The dispatch workflow builds with no `PUSH=`, runs the row's test, then `make push-engine` (gated on
`push=true`); `push()` re-runs `test_image` before tagging/pushing. Never put `PUSH=$PUBLISH` back on
the build step.

## The four local scopes

`make build-engines` (every CI cell, 27), `ARCH=cuda` (7), `ENGINE=vllm` (3), `ENGINE=… ARCH=…` (1);
`VERIFY=1` adds each image's binary test in the same parallel fan-out.
`make engine-build-matrix [ENGINE=] [ARCH=]` is the workflow's only source of rows.

31 committed cells = 27 CI cells + 4 `DISABLED` (#103) cells; `prebuilt: true` cells are pulls and
are verified like any other.

An engine whose only variant is `DISABLED` has NO row at all (e.g. `exllamav3-rocm`), so a sweep of 27 rows
covering 12 engines is complete even when `containers/engines/params/` holds 13 files — name the excluded
cell and its tracking issue instead of calling the sweep partial.

The `test-published-*` jobs reuse the SAME changed-engine matrix, so a push that touches only the harness
(`Makefile`, a test, a workflow) runs zero real published rows — just the `test-published-none-none`
placeholder. That is why a broken `test-published-engine` recipe can sit latent for weeks and first shows up
in an unrelated engine PR: when counting published coverage, check whether the matrix had rows at all before
trusting a green run.

## A dispatch that never starts jobs is a CONCURRENCY queue, not a broken dispatcher

`pending` with an empty `jobs` array (0 jobs, no runner, checker notes never moving) means the run is
waiting on its `concurrency:` group — not that the trigger is misconfigured. Confirm before debugging the
dispatcher:

```bash
gh run view <run> --repo asimov-agent/llgenie --json status,jobs --jq '{status,n:(.jobs|length)}'   # -> pending, 0
gh workflow list --repo asimov-agent/llgenie | grep -i engine-build                                  # -> active: the surface is fine
```

A CONSTANT `group:` with `cancel-in-progress: false` serialises every dispatch: with a 27-row sweep running
for hours, a narrow `engine=… arch=…` dispatch queues behind all of it and looks dead. Key the group by what
the run does instead — publishing runs share one group (two pushes must not race on the same `:<arch>` tag),
build-and-verify runs keyed by the selection:

```yaml
concurrency:
  group: engine-build-${{ inputs.push == 'true' && 'push' || format('build-{0}-{1}', inputs.engine, inputs.arch) }}
  cancel-in-progress: false   # a sweep is never killed by a dispatch
```

Prove it with the sweep still running: dispatch the narrow selection and watch it go `in_progress` with
`guard` + `matrix` + one build row inside a minute, then green in ~3 minutes (the build is a no-op when the
pin's image already exists). A lock test belongs next to the other concurrency tests: assert the group is
keyed on the inputs, that publishing runs share one group, and that `cancel-in-progress` is false.

## `make build-engine` pulls the hash tag instead of compiling — by design

`engine_image.build()` starts with `_available(tag)`: local image, else `docker pull
<registry>/<name>:<pinned>-<hash>-<arch>` + retag + `available -> no rebuild`. The tag IS the build
identity (hash of Dockerfile + params + engine pin), so pulling it yields exactly what a rebuild would
produce. It compiles only when the tag is absent (new pin/params/Dockerfile → pull 404 → `buildx build`
with the registry layer cache), when `FORCE=1`, or when the registry is unreachable.

- Read the log correctly: `[engine-image] $ docker pull …` then `available -> no rebuild` is a **verify**,
  not a build that ran. Do not "fix" it by forcing a rebuild when the question was just "is the pin good?".
- The hash does NOT cover a moving base image (`FROM nvidia/cuda:…`) or what `pip`/`uv`/`npm` resolve at
  build time, so a warm GHCR hides a base-image or dependency regression until the pin or params change.
  When the question is "does this still build?", use `make build-engine ENGINE=… ARCH=… FORCE=1`.
- The dispatch surface carries `engine`/`arch`/`push` only — there is no `force` input, so a dispatched
  run can verify the published artifact but cannot demand a real compile. Say that plainly instead of
  claiming a sweep rebuilt anything; a `force` input wired to `FORCE=1` (default false) is the shape of
  the fix.
- `push-engine` is skipped when `push=false` and re-checks the binary's flags before publishing, so a
  pushed image is never one whose binary failed to answer.

## Known trap: SKILL.md size

This skill's SKILL.md is ~103k characters, over the 100k limit, so `skill_manage(patch)` on it is
rejected and rolls the whole batch back. Put new lessons in `references/*.md` (like this file) or
split the body — do not attempt a patch until it is under the limit.
