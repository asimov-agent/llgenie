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
`containers/engines/entrypoint.sh` and `scripts/engine_runner.py`. So a PR that edits the runner, the
entrypoint or a Dockerfile moves **every** engine's tag — and
`tests/test_ci_publish_order.py::test_every_image_install_pulls_is_published` then demands published
images for engines its notion of "repinned" (params files only) does not cover:

```
AssertionError: an image make install pulls and this change did not repin is not published on GHCR
```

No such PR can go green until that test learns the same four inputs. Name that on the PR (missing
artifact → the job that did not produce it → the issue that closes the gap) instead of hunting the diff
for a bug that is not there.

## What a Prism cell proves once published

`llama.cpp-prism` is the only build that reads a fork-specific ternary quant (`PQ2_0 = 142`,
`PTQ1_0 = 143`); stock llama.cpp refuses such a file at load (`invalid ggml type 142`), which surfaces
as a silent hang rather than an error. Its cpu image loads a 27B ternary and serves it at roughly
10 prompt / 2.5 gen t/s — proof the engine pairing and the launch line are right, and the reason the
cuda cell matters.
