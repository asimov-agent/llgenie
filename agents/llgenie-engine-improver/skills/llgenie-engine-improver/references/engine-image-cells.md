# Engine image cells: enabling one, and what each can prove on this host

Depth for `SKILL.md` Step 3 / 3b — load it when a cell is missing, disabled, or newly enabled.

## Which backends this host can actually verify

`cpu` and `cuda` run here (NVIDIA card + CDI `nvidia.com/gpu=all`) — serve a model on them and read
real timings. `rocm`, `vulkan` and `metal` have no device: the only honest check is the PUBLISHED image
answering `docker run --rm <image> version` (plus `<binary> --help` for the flag surface), which proves
the binary and its arguments, **not** the compute path. Say exactly that in the report; never let a
`--version` on a foreign-backend image read as "verified on this card".

## A DISABLED cell is a cell that does not exist

`engine_image.DISABLED` removes a cell from `--engines`, from the launcher's choice **and** from the CI
matrix, so the engine silently resolves to its `cpu` variant on a GPU host — a slower run, not an
error. That is how an engine whose only reader is a fork-specific quant had no GPU image at all.

Enabling a cell is three things, in this order: the code change (drop the `DISABLED` entry), a params
change so the tag actually moves, then a publish:

```bash
gh workflow run engine-build.yml --ref <branch-in-the-upstream-repo> \
  -f engine=<id> -f arch=<v> -f push=true
```

A branch pushed to the canonical remote publishes; a **fork-head branch does not**. If the awaited tag
is absent, the answer is "the cell has not published yet" — check the run, never build it here.

## Enabling a GPU cell needs the install recipe to survive a GPU-less runner

An engine skill's install step usually ends with a `{binary} --help` probe. A CUDA binary links
`libcuda.so.1` eagerly, so on the hosted runner that probe dies **inside the build**:

```
error while loading shared libraries: libcuda.so.1: cannot open shared object file
[engine-runner] FAIL <engine>/cuda: step exited 127
```

Same class the `DISABLED` table already records for one fork's cuda cell. Either verify the binary
without executing it at build time and let the post-build `detect` / `test-engine-stage` prove it where
a device exists, or keep the cell disabled with that reason recorded. Do not "enable" a cell whose
build probe needs the card.

## A change to a tag input invalidates every image, and one gate knows it

The tag hashes four inputs: the variant's params, its committed Dockerfile,
`containers/engines/entrypoint.sh` and `scripts/engine_runner.py`. Because the Dockerfile is
per-variant, **the `<digest8>` differs per variant** — compute a tag per variant
(`scripts/engine_image_tags.sh <engine-id> <root> --probe` prints each variant's tag and probes it) and
never reuse one variant's digest to probe a sibling: `llama.cpp` at one pin measured
`…-5b7be358-cpu` 200 while that same digest on `-rocm` 404'd, the real rocm tag being
`…-dd3549eb-rocm` (cuda `…-af7a7d90-cuda`, vulkan `…-fcf234e2-vulkan`). A sibling 404 is not evidence
until you have computed that sibling's own tag from the tree. So a PR that edits the runner, the
entrypoint or a Dockerfile moves **every** engine's tag — and
`tests/test_ci_publish_order.py::test_every_image_install_pulls_is_published` then demands published
images for engines its notion of "repinned" (params files only) does not cover:

```
AssertionError: an image make install pulls and this change did not repin is not published on GHCR
```

No such PR can go green until that test learns the same four inputs. Name that on the PR (missing
artifact → the job that did not produce it → the issue that closes the gap) instead of hunting the diff
for a bug that is not there.

**Recompute the expected tag at the exact head you publish from — a tag quoted from an older head goes
stale the moment another lane merges a tag-input edit.** The four inputs are content bytes, so even a
comment-only edit to `scripts/engine_runner.py` (e.g. a lint-suppression comment) shifts every engine's
hash. A publish run is bound to the `HEAD` it was dispatched at: if main advances past that sha while the
run is in flight, the run publishes the OLD head's tag, which the new main no longer computes — a green
run then does NOT fix the gate. So before dispatching or trusting a publish: `git fetch origin main`, then
compute the tag at that exact sha (read the four inputs via `git show <sha>:<path>` and sha256 the
concatenation exactly as `_image_inputs` frames it — params JSON of the variant, then the committed
Dockerfile, `entrypoint.sh`, `engine_runner.py` — or run `scripts/check_engine_launchers.py report` in a
worktree checked out at that sha). Never reuse a tag number from an earlier turn or another lane's
measurement. When `make check-engine-launchers` reds many engines on "other params (same pin)" at once,
classify it as another input having moved (republish the fleet) versus a single pin moving — the fixes
differ.

## A from-source (AOT) kernel dependency needs its whole build toolchain in the params install row

An install row that does `uv pip install -e '.[all]'` can end up BUILDING a kernel extension (an AOT
wheel) rather than downloading it. That build reads only what the image has, so every build backend and
build tool the wheel's `pyproject.toml`/CMakeLists assumes must be preinstalled in the row — and a
missing one surfaces as a red build cell, never at params authoring time:

- `ModuleNotFoundError: No module named 'scikit_build_core'` — the PEP 517 backend is absent even though
  the row already installs `wheel_stub`; `wheel_stub` is not `scikit-build-core`, so install both.
- `CMake Error: Policy CMP0169/CMP0177 is not known to this version of CMake` — the wheel's CMakeLists
  calls a CMake **4.x** policy unguarded while the base image ships a 3.28 distro cmake. Install the
  `cmake` PyPI wheel (4.x) in the same row: it shadows the distro binary on PATH, which is the fix; the
  alternative "let the engine fail" is a cell that can never publish.

Regenerate the variant's params from the engine skill after editing the row (the tag hashes the params),
and expect one red stage to reveal the next: fixing the backend exposes the toolchain error, and each is a
separate defect in the same cell.

## A transient `uv pip install` wheel-download timeout: raise `UV_HTTP_TIMEOUT` via the variant `env`

A CUDA torch install (`torch==…` + ~34 nvidia wheels, several hundred MB each) can die mid-download with a
transient `Failed to download … network timeout` / `error sending request` — a *network* flake, not a pin or
recipe defect. `uv`'s per-request HTTP timeout defaults to 30 s; a stalled 139 MiB `nvidia-cusparse`
download exceeds it and uv aborts. Raise it without touching the engine recipe:

- `scripts/engine_runner.py::install()` computes `pre = env_prelude(p.get("env") or {})` and runs every
  install step as `_bash(pre + step)` — so **anything in the variant's `env` dict is exported before each
  step**, including the `uv pip install` lines. Add `"env": {"UV_HTTP_TIMEOUT": "120"}` to the variant in
  `containers/engines/params/<engine>.json` and uv inherits it.
- The `[engine-runner] <id>/<backend>$ <step>` log line prints only the STEP command, not the prepended
  `export …`; the env IS applied even though it is invisible in the log. Confirm by reading
  `install()` / `env_prelude()` in `engine_runner.py`, not by grepping the log for the var.
- **This is a local-only diagnostic lever unless the flake is chronic** — for a one-off prove-the-build
  run, edit `params/<engine>.json` in the worktree, build, then `git checkout` the file so it never rides
  the PR (the params file is generated; its committed value should not carry a timeout bump for one flake).
  If the registry or a mirror is *persistently* slow, that is a real params change with its own PR.

## The publish flag gate requires a HELP spelling unconditionally — `binary_flags` cannot waive it

The publish gate (`scripts/engine_image.py::decide()`) probes `TYPED_FLAGS` (`--version`, `-h`,
`--help`, `-V`) and applies two failures independently: **(1)** every entry in the manifest's
`flags` (from `binary_flags`) that does not answer, and **(2)** "the help family answers to neither
`-h` nor `--help`" — and that second branch fires for **every** `probe` policy. So a CLI that answers
`--version` but exits non-zero on `-h`/`--help` is genuinely **unpublishable**: narrowing
`binary_flags` to `["--version"]` does NOT clear it, because `TYPED_FLAGS` still probes the help
family and the family check still reds. The `probe: help` policy is for a CLI with **no version flag at
all** (help must still answer); `probe: device` is for a CLI that needs the card to answer **any** flag.
Neither covers "answers version but no help." Per #687, do not patch upstream — a cell blocked this way
stays blocked until upstream's CLI adds a help spelling; report it as blocked-at-this-pin, and never
re-dispatch expecting the gate to pass.

**Read the flag surface from the binary the BUILD actually installs, not a sibling `main.zig`.** A
`zig build` can install a CLI (`zig/src/cli/cuda_main.zig`) as `<id>` while the *server* main
(`zig/src/server/main.zig`) — which does handle `--help`/`-h` — is a different artifact. Confirming
`--help` in the server main proves nothing about the installed `<id>` binary the gate probes. Before
correcting a skill's `binary_flags`, trace which `installArtifact`/executable the pinned build produces
for the container cell, and read THAT source's argv handling. The measured (`--version` answers, `-h`/
`--help` exit 2) result is the ground truth; a source file that appears to handle help is not.

## A source AOT kernel that OOMs the build host is kernel-size-bound — restore the prebuilt base

When the toolchain is complete but the AOT compile still dies, the failure is the build host's memory, not
a missing knob — and "narrow the arch set" is a dead lever (a strict single-arch compile still exceeds a
16 GiB/4-CPU cap). The measured detail and the repro recipe live in
`references/engine-build-proof-dispatch.md` ("The arch lever for a torch-backed CUDA AOT OOM"); do not
re-derive it. The remedy for a cell that must stay green is to **restore the prebuilt official serving
image**: set `container.<backend>.base = <official serving image>` and `prebuilt: true`. Renderer
semantics that make this safe: `if prebuilt: steps = []` — a prebuilt variant runs **ZERO** install steps,
so a non-empty `install` under `prebuilt: true` is incoherent; the base ships the engine and its compiled
kernels. Keep the sibling backend's source build (e.g. rocm) untouched — the pivot is per-variant. Before
pushing, **verify the detect/version line inside the ACTUAL prebuilt base** (`docker run --rm <base> sh -c
'<binary> --help; python3 -c "import importlib.metadata…"'`), since a prebuilt base is a different binary
surface than a locally-built one; a green detect at the real base is the pre-push gate in place of a local
build (this lane never builds an engine image).

## A per-engine cell query returns MULTIPLE conclusions — red is ANY non-success

When you read an engine's producing cell state from CI (the newest completed `engine-build` dispatch
run, filtered to that engine's jobs), a multi-arch engine yields several conclusions for one id —
e.g. `vllm` → `success` (cpu) plus `failure` ×2 (cuda, rocm) — and the query helper may join them as a
single newline-separated string `"success\nfailure\nfailure"` (unique values, so an all-red dry run shows
one `failure`, not a count). Do NOT equality-compare that whole string to `success`: that silently reads a
red engine as green when only its sibling arches are fine. Split on newlines and treat the engine as RED
if ANY line is non-success (`failure`/`cancelled`/`timed_out`). This is the premise a publish-gated check
must test (a red producing cell → no publish can ever happen → skip the wait), and it matches what the
GHCR tags will show (a red arch leaves that variant unpublished even when a sibling arch published).

## What a Prism cell proves once published

`llama.cpp-prism` is the only build that reads a fork-specific ternary quant (`PQ2_0 = 142`,
`PTQ1_0 = 143`); stock llama.cpp refuses such a file at load (`invalid ggml type 142`), which surfaces
as a silent hang rather than an error. Its cpu image loads a 27B ternary and serves it at roughly
10 prompt / 2.5 gen t/s — proof the engine pairing and the launch line are right, and the reason the
cuda cell matters.
