---
name: containerized-repo-verification
category: software-development
description: "Use when repo gates run in containers via make/docker."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [docker, make, pytest, ci, devcontainer, permissions]
    related_skills: [pr-landing-on-moving-master, worktree-branch-hygiene, github]
---

# Verifying changes in a repo whose gates run in containers

## When to Use

Repo-specific depth lives in `references/`: `references/llgenie-engine-pipeline.md` (how a registry
engine becomes a built, published image, and which bot/gate owns each step).

Use whenever `make <gate>` shells into a test image (`docker run … <repo>/test:latest python -m pytest …`)
and the repo runs its own tooling the same way (an `openspec` image, a generator image, a linter image).
The full `make test-unit` can be 15-20 minutes; the pitfalls below are what cost the time, not the code.

## Iterate on ONE test file in the repo's own test image

Never hand-type the whole suite to check a change, and never trust a host `pytest` (the repo's deps live
in the image). Reproduce the `make` target's container shape with a single file:

```bash
docker run --rm -u root -v "$PWD":/repo -w /repo -e HOME=/root \
  <test-image> python -m pytest tests/test_<thing>.py -q -p no:cacheprovider
```

- Mount the tree at the SAME absolute path the Makefile uses (or at `/repo` with `-w /repo`) — some
  fixtures resolve paths from the repo root and break under a remapped path.
- `-p no:cacheprovider` keeps the run hermetic (no shared cache between host and container runs).
- Name every file the change touched in ONE call; the per-file run is your inner loop, `make test-unit` is
  the final proof. Report both numbers, and report the full suite only for the tree it actually ran on.
- When the repo's rule is "every test runs through make", the per-file `docker run` is for iteration;
  the gate you quote as green must still be a `make` target.
- A test module that imports only the stdlib plus the repo's own `scripts/` needs no image: any
  installed `pytest` runs it in milliseconds (`/path/to/some/.venv/bin/pytest tests/test_x.py -q`),
  which is the right inner loop while you shape the code. Quote the `make` target, not this, as green.

## Root-owned artifacts are the normal case, not a crash

A container tool run as `-u root` leaves the files it creates owned by root on the host, so the NEXT
host-side write fails with `Permission denied` even though the directory is yours:

- a scaffold/new-change tool (`make openspec-new NAME=…`) creates its directory root-owned, and the
  follow-up `write_file` of `proposal.md` is refused;
- a container `pytest` run writes `__pycache__`/`.pytest_cache` owned by root, and `rm -rf` fails.

Fix through the same image rather than assuming host permissions (the agent may have no interactive
password prompt) — on a host that grants passwordless `sudo`, `sudo chown -R "$(id -u):$(id -g)"
<path>` is equivalent and shorter; use the image form when sudo may prompt:

```bash
docker run --rm -v "$PWD":/repo -w /repo alpine:latest chown -R "$(id -u):$(id -g)" /repo/openspec/changes/<name>
docker run --rm -v "$PWD":/repo -w /repo alpine:latest rm -rf /repo/tests/__pycache__ /repo/scripts/__pycache__
```

Order that avoids it entirely: run the container scaffold FIRST, `chown` its output, then author the
files it created. Do the same whenever a container step must delete or rewrite what a previous container
step made.

**A root-owned WORKTREE cannot be cleaned up, and `git worktree remove` reports only `Permission
denied`.** A gate run inside a per-branch worktree leaves `__pycache__`/build output owned by root, so the
removal fails and the branch stays registered. Fix the ownership through the image (`alpine chown -R
"$(id -u):$(id -g)"`), or on a host that grants sudo `sudo rm -rf <worktree-path> && git worktree prune &&
git branch -D <branch>`. Deleting the directory by hand without `prune` leaves the branch recorded as
checked out elsewhere, and the next `worktree add`/`resume` for that branch refuses — prune is the step
that releases it.

## A new make target: prove every documented knob reaches the CLI

A target can accept `OUT=`/`DRY=`/`REGISTRY=` in its help line and silently not forward them, so a
"preview" writes into the real tree, or a run pointed at a scratch dir writes into the repo. The bug is
invisible: the target exits 0 and prints a path.

- Exercise the target itself (not the script) once per knob, with an output directory outside the repo:
  `make -s <target> ENGINE=… ID=zz-test OUT=/tmp/scratch DRY=1`, then confirm nothing was written and
  that a non-dry run with `OUT=` lands under `/tmp/scratch`.
- Pin it with a test that reads the Makefile recipe and asserts each `VAR=` appears next to its `--flag`
  and that the target is in `.PHONY` — a wiring gate proves the target exists, not that it forwards.
- Path arguments passed as `$(if $(OUT),--out "$(OUT)",)` are the shape to copy; a bare `$(OUT)` inside a
  quoted string is the shape that silently drops the flag when the var is empty.

## An artifact no caller reaches is not a pipeline — name the caller and prove it

Before reporting automation as "done", grep for what INVOKES it. A target, script or helper that only
appears in its own file (plus a doc line) is a dead end: the human is the only caller, and a later reader
will ask "which bot runs this, and when". Close the loop in code, in this order:

1. the producer writes the work item (issue/label/file);
2. a deterministic step in the consuming bot calls the new artifact (a dispatch/claim/discover step, not an
   instruction inside a prompt the agent may skip);
3. a test asserts that call path end to end (the fake external system records the invocation).

Then state the answer explicitly in the report: `<workflow> -> <make target> -> <what exists before the
next step starts>`. If step 2 does not exist, say so plainly — "nothing calls it yet" — rather than
describing the mechanism as if it were wired.

## Wiring a new gate into a mega-target: classify it, and prove both exit codes

A repo whose CI is one `make ci-<job>` that chains many `make check-*` gates usually also carries a
ROSTER module that classifies each gate (something like `FAST_GATES` / `DEFERRED[gate] = "why not"`).
Adding a gate to the mega-target without touching the roster reds the full suite at the very end — after
the 20-40 minute run — with a message naming the unclassified gate. So:

- grep the repo for the roster (`check-*_gates.py`, `*_gates.py`, `FAST_GATES`) and the test that pins its
  list BEFORE wiring the target, and run that test file first; the roster's list is often deliberately
  fixed, so read its reason strings and put the new gate in the side the repo documents (adding to a
  "fixed list" reds its own pinning test).
- Wire by ORDER, not by appending: the gate belongs immediately after the step that produces its input
  (generator -> freshness check -> new verdict) and before the gate that scores the same artifacts.
- Prove the exit-code contract on both trees before claiming it: run the gate on the committed tree
  (exit 0), then on a COPY with the defect injected into a scratch dir (`--skills`, `--params`, `OUT=`
  knobs exist for this) and quote the non-zero run that NAMES the offender. A gate only ever seen green
  is an assertion, not a verification.

## Audit against the fetched tip, not the working checkout

Before reporting a gap and starting a change: `git fetch origin && git log --oneline origin/main -10`, and
read the newest commits touching the files you are about to edit. A checkout one commit behind turns a
freshly landed fix into a "missing gate" you then re-implement; the same fetch also shows whether the
helper you plan to widen already grew that branch. When the user's premise about which component owns a
behaviour disagrees with the code, correct the premise from the call graph (which workflow calls which
`make` target calls which script) instead of implementing around it.

## Editing a Makefile with a patch tool

A recipe or `.PHONY` line that ends in a line-continuation backslash trips escape-drift guards: anchor the
edit on a SHORTER unique substring inside the line (`check-engine-params check-engine-source`) and leave
the surrounding backslash alone, rather than quoting the whole line into `old_string`.

## Report the tree the number came from

A background/full suite started before your last edit measures a tree that no longer exists. Either
re-run it on the final commit, or label the number with the commit it ran on and give the per-file result
for the current tree. A green full-suite quoted for the wrong tree is the same defect as a fabricated one.

## A gate that scores a stored REPORT measures the OLD tree

A gate whose input is a saved artifact — a scanner's `*-reports/*.json`/SARIF, a stored SBOM, a
coverage or benchmark file — scores the image/tree that artifact was produced from. Re-running the
verdict after you change the pins answers with the OLD findings by construction: the artifact is a
snapshot, so a still-red verdict is neither a retry signal nor evidence the fix failed.

- Prove the fix with the repo's own COMPARISON command, the one that reads the artifact's target
(`fixed`/desired) versions and compares them with the current pins — a `<scanner>-bumps-plan`, a
`--dry` repair, a changelog diff target. Quote its verdict line (e.g. *every floor is already satisfied
by the compiled pins*); that output, not the gate, is the evidence.
- Pin it hermetically: a test that parses the input files AND the compiled/generated outputs and asserts
each entry is at or above the version the report named. The artifact stays old; the test reads the tree.
- Fix the ACCEPTANCE CRITERION when it demands the impossible. An issue/task that says "re-run the
verdict and see zero findings" can never be satisfied from a stored artifact — rewrite it to the
comparison plus "the next scheduled run produces a fresh artifact", and say in the PR body that the
artifact is a snapshot. A reviewer who tries the verdict themselves will otherwise read the red as a
regression you failed to fix.
