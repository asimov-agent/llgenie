# engine-build cuda install-leg vs a plain runner

## The defect class

`engine-build.yml` runs every matrix row on `runs-on: ubuntu-latest` and provisions no
`nvidia-container-toolkit` / CDI spec. But an `ARCH=cuda` row's **install-leg** docker-runs the
image with `--device nvidia.com/gpu=all`, which needs the host NVIDIA driver exposed through CDI
(`AGENTS.md` "cuda CDI", `README.md` backend selection, `Makefile:install-prism-cuda`).

Consequence: a cuda install-leg can **never** go green on a GitHub-hosted runner as configured —
it fails at `engine-launchers` with `[install] FAIL cuda host without the NVIDIA CDI spec`.
This is a workflow infra gap, **not** a regression in the PR under test. Before imputing a cuda
install-leg red to a diff, check whether the run is a plain `ubuntu-latest` workflow_dispatch
sweep (it usually is) and confirm the failure sits at the CDI check, reproducibly at two heads.

## How to report it

- Quote the workflow line (`runs-on: ubuntu-latest`) plus the repo's own required CDI path
  (`AGENTS.md`, `README.md`, `docs/ENGINES.md`, `Makefile:install-prism-cuda`).
- Give the run ids at two heads to prove it is pre-existing, not the diff.
- Ask for one of: a CDI setup step (`nvidia-container-toolkit` + `sudo nvidia-ctk cdi generate
  --output=/etc/cdi/nvidia.yaml`) on a GPU/CDI-capable runner, **or** a documented run-on gate so
  the cuda install-leg **skips, not reds,** on a GPU-less runner. Never weaken a gate to go green.

## Distinguish from the neighbouring issues

A cuda install-leg red is *not* the same as the producer being `disabled_manually` (engine images
never publish) or the engine-install refactor — those are separate, already-tracked gaps. File the
CDI-too-missing class on its own if untracked.

## SKILL.md is at its size ceiling

`SKILL.md` is ~100,000 chars (the hard limit). Do not try to patch it — a pointer add fails and
rolls the whole batch back. Land lessons as reference files and rely on `skill_view`'s
`linked_files` index; fold pointers into existing lines only when the edit is size-neutral.
