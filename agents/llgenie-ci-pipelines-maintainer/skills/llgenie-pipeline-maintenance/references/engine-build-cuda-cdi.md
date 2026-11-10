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

## A "skip" printed on one recipe line is NOT a gate — make runs each recipe line in its own shell

The banned-to-green remedy ("documented run-on gate so the cuda install-leg skips") has a trap that
looks fixed and is not: a target that prints the skip reason and does `exit 0` on ONE recipe line,
then runs the work (`make engine-launchers …`) on the NEXT recipe line, does not skip anything.
**make invokes a separate shell per recipe line**, so `exit 0` ends only that line's shell (as
success) and make proceeds to the next, unconditional line. Measured: `test-engine-install` printed
`[install-leg] SKIP … (issue #1240)` at log line 704, still ran `make engine-launchers` at 705, and
failed `[install] FAIL cuda host without the NVIDIA CDI spec` at 708 / `Makefile: engine-launchers
Error 1` at 710 — five cuda cells red, no diff implicated. The skip was a printed reason, never a
control.

**Fix shape:** fold the whole body under the `else` of the skip branch INSIDE one recipe line, so a
non-empty reason prevents the work structurally:

```make
	if [ -n "$$reason" ]; then echo "$$reason"; \
	else \
	  make engine-launchers ENGINES="$(ENGINE)" ARCH="$(ARCH)" && \
	  make test-built-engine && \
	  make ci-install-uninstall; \
	fi
```

**Prove it before trusting it (guard-prove rule).** Execute the exact recipe logic with the reason
forced non-empty, assert the work branch does NOT run (SKIP branch), then with the reason empty,
assert it DOES (else branch). Do the same probe against the OLD two-line shape to show the failure
reproduces — a guard only ever run on the fixed tree has demonstrated nothing. This is a
structural-gate fix, not a weakened gate: a GPU+CDI host still exercises the install, a GPU-less
runner becomes an evidence-backed SKIP.

## `make bot-preflight` measures against the CLONE's `origin/main`, which may be the FORK — ancestry-check the emitted `AGENTS:` sha before opening the PR

`bot-preflight` writes `AGENTS: <sha> <bytes>b <lines>l` / `BASE: <sha> (== origin/main at open)`
from whatever the clone's `origin` remote resolves `main` to. On a host where `origin` is the
owner's fork, that sha can be dozens of commits behind canonical `asimov-agent/llgenie` main. The
gate does not require the cited sha to equal the merge target — it requires it to be an **ancestor
of BOTH the PR head and the base**. So before `gh pr create`, run
`git merge-base --is-ancestor <AGENTS-sha> <upstream/main-sha>` and `… <head-sha>`; both must be 0.
A reachable rulebook is legal even if it is not the tip, but an sha that is NOT an ancestor of the
canonical base reds `check-pr-agents-line`/`check-pr-base` on the first run.

## Distinguish from the neighbouring issues

A cuda install-leg red is *not* the same as the producer being `disabled_manually` (engine images
never publish) or the engine-install refactor — those are separate, already-tracked gaps. File the
CDI-too-missing class on its own if untracked.

## SKILL.md is at its size ceiling

`SKILL.md` is ~100,000 chars (the hard limit). Do not try to patch it — a pointer add fails and
rolls the whole batch back. Land lessons as reference files and rely on `skill_view`'s
`linked_files` index; fold pointers into existing lines only when the edit is size-neutral.
