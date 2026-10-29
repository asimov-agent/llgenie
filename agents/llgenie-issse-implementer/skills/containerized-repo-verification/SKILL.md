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

Repo-specific depth lives in `references/`: `references/agent-profile-tree.md` (keeping a host agent's
SOUL and skills in the repo: re-seed by allowlist, the larger-but-dropping-lines trap, an audible skip),
`references/llgenie-engine-pipeline.md` (how a registry
engine becomes a built, published image, and which bot/gate owns each step).

Use whenever `make <gate>` shells into a test image (`docker run … <repo>/test:latest python -m pytest …`)
and the repo runs its own tooling the same way (an `openspec` image, a generator image, a linter image).
The full `make test-unit` can be 15-20 minutes; the pitfalls below are what cost the time, not the code.

## Iterate on ONE test file in the repo's own test image

Never hand-type the whole suite to check a change, and never trust a host `pytest` (the repo's deps live
in the image). Reproduce the `make` target's container shape with a single file:

```bash
make -n <target>        # FIRST: copy the exact docker invocation the target uses
```

Then run that same shape with one file instead of the roster — **including every `-v` and `-e` the
target adds**, not just `-v "$PWD":/repo`:

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  -v "<every extra mount make -n printed>":<same path>:rw \
  <test-image> python -m pytest tests/test_<thing>.py -q -p no:cacheprovider
```

- **A missing mount turns real passes into a cluster of failures.** When the checkout is a git
  WORKTREE, `.git` is a file pointing at the main clone's admin dir; a make target mounts that main
  clone at its own absolute path so the pointer resolves. Drop that mount and every test shelling out
  to git fails at once (`captured stderr: Command '['git', 'ls-files']' returned non-zero exit status
  128`) — dozens of reds that look like a broken change and are an artefact of your invocation.
  **Read the `Captured stderr` of a suspicious failure cluster before believing any of it**: a gate
  script that dies on its own subprocess is the invocation's fault, not the diff's.
- **A per-file loop over `tests/test_*.py` is not a substitute for the suite.** Tests that need the
  harness env (tokens, `make` targets, fixtures the conftest builds) fail in isolation by the dozen, so
  batch it through the repo's own runner (`python scripts/unit_tests.py run`) instead of naming files.
- **A file you named by hand may be one the suite DESELECTS by design.** llgenie's
  `tests/fixtures/unit-suite.json` records each exclusion with its reason and target: hardware/network
  end-to-end tests (a real `llama-server`, a live Hugging Face download) fail as *hard* errors when their
  prerequisite is absent — by design, "missing prerequisite is a hard failure, never a skip". So a hand-made
  batch reports a red that no diff caused. Check the roster for a file before believing its failure, and
  prove it environmental by running the same node on `main` (measured: `test_top_tier_serve.py` fails
  identically at `798cbee`, 1 failed / 202 passed in the real batch). Narrow a slow sweep with the
  roster's own selection (`python scripts/unit_tests.py argv`, `-k`, or the target's group/`--deselect`
  list), never by enumerating files yourself.
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

## A long suite that looks hung, or dies at 9x %

A 20-45 minute containerized suite prints one dot per test, so a slow stretch and a hang look identical
when you only look at the last line of the log. Diagnose before killing:

- Run it as a tracked background job with completion notification, and poll the log file — never a
  foreground call long enough to hit the tool timeout, and never `sleep` loops in place of the job.
- If you must know WHERE it stalled, wrap pytest in faulthandler instead of guessing:
  `python -c "import faulthandler,sys,shlex; faulthandler.dump_traceback_later(180, repeat=True); import pytest; sys.exit(pytest.main(shlex.split(sys.argv[1])))" "<args>"`
  — every 180 s it prints the live stack, so the hanging test names itself.
- **`Error 137` / exit 143 is the HOST killing the run (OOM or an external SIGTERM), not a test
  failure.** Report the count reached and the kill, and fall back to the targeted files plus the
  reasoning that the failures seen were invocation artefacts — do not present a killed run as a red
  gate, and do not re-run the same 40 minutes hoping for a different ending.
- **`pkill -f "<pattern>"` kills your own shell** when the pattern appears in the command line you are
  running (it matches the wrapper that launched it). Use a bracket pattern — `pkill -f "[u]nit_tests.py run"`
  — and `docker rm -f` the orphaned test containers so the next run does not share the CPU.
- A `sudo` inside a `background=true` command has no tty and fails after the job starts; do privileged
  cleanup in a separate foreground call.
- **On a host shared with other agent legs, NEVER clean up by image: `docker rm -f $(docker ps -q
  --filter ancestor=<repo>/test:latest)` kills every leg's run, and each survivor then re-kills the
  rest.** Symptom: your own suite dies at 3-90 % with `Error 137` while `docker ps` shows several
  containers of the same image started minutes apart, from worktrees under `<repo>/.worktrees/t_*` —
  other sessions on the same profile, not yours. Protect the run instead: `docker tag <image>:latest
  <image>:<branch-slug>` and start it with `--name <unique>` so a future cleanup by ancestor misses it;
  kill only your own by name. Verify the name is still up before believing a killed log.

## Prove a red gate against a pristine base before you believe it

When the full gate is red on your branch, run the SAME gate on a **detached worktree of the merge
base** with none of your changes, then diff the failure lists:

```bash
git worktree add --detach ../<repo>-wt/baseline <base-sha>
# same image, same mounts, same invocation — only the tree differs
docker run --rm -u root -v "$BASELINE":/repo:rw -w /repo -e HOME=/root \
  -v "<main clone>":<main clone>:rw <test-image> python -m pytest <the failing files> -q --tb=no -rf
```

- **A gate that is red on the base is not your diff, and no amount of re-running will turn it green.**
  Measured in llgenie: after the macOS CI group was deleted (#871), four tests still asserted the old
  job graph, so `origin/main` itself failed `make test-unit` and every open PR read
  `linux / unit` red for a reason no PR caused. Report it as a pristine-base differential (file,
  count, test names) instead of claiming a green you cannot produce, and file it as one issue rather
  than "fixing" it on a feature branch.
- **Re-point the assertion, don't resurrect the deleted thing.** When a job/OS/stage was removed by an
  intentional change, the stale test is the defect; re-adding the removed job to make the test pass
  reverts a decision someone made on purpose.
- **A per-file timing run is the right tool to separate "slow" from "hung", and only for that.**
  Under host contention a 20 s file took >150 s; a per-file loop with `timeout 150` named the slow file
  in minutes while the same suite's `-q` dots looked identical to a hang. Never quote such a loop as a
  gate result — it exists to locate a stall, not to verify a change.
- **The cheapest differential is head-to-head, not base-to-head.** When a gate reds at your head, diff the
  two heads on the paths that matter: `git diff --stat <red-head> <new-head> -- <workflow> <script>` — an
  EMPTY result proves the red cannot be your change, and every line that does differ is the base's own
  content pulled in by a rebase. One command, no second container run, and it holds even when the base
  moved twice while you were working.

## A new job that runs a make gate must prepare the images that gate runs in

A `make ci-<job>` mega-target chains gates whose recipes each `docker run <some-image>`. A new workflow
job that calls the mega-target inherits every one of those image dependencies, but it only prepares the
images its own earlier steps pulled — so it dies seconds in, on the ONE gate that needs a different image:

```
Unable to find image 'llgenie/openspec:latest' locally
pull access denied … repository does not exist or may require 'docker login'
make[1]: *** [Makefile:1139: openspec-validate-all] Error 125
```

- **Read the gate's recipe before wiring a job to it**: `grep -n "^ci-<job>:" -A6 Makefile`, then follow
  each chained target to its `$(RUNTIME) run $(…_OPTS)` line and note the image. Add the matching
  preparation step (`make <image>-pull`, or the same `docker tag` the canonical CI job does) before the
  gate step.
- **The failure shape mimics a red base** — a step failing early on a `main` that was red minutes ago. The
  head-to-head differential above is what separates them; do not conclude "the base" without it.
- A step-level read beats a conclusion-level one: `gh api repos/<o>/<r>/actions/jobs/<id> --jq '.steps[] |
  "\(.number) \(.conclusion)\t\(.name)"'` names the failing step in one call, where the run's
  `failure` says nothing. Job logs may come back truncated; the step list never does.

## Adding a make target to a repo whose `.PHONY:` is a continuation list

`.PHONY:` in this repo spans several lines joined by trailing `\\`. Appending a new name to the end of
the **first** line silently drops names that live on later continuation lines, and the target still
runs — so the failure surfaces as unrelated targets being refused:

```
[check-wiring] `make workflows-report` is not declared .PHONY …
[check-wiring] `make worktree-prune` is not declared .PHONY …
```

**Fix:** declare the new target on its own line (`\n.PHONY: bot-preflight\nbot-preflight: ## …`)
instead of editing the existing block, and re-run `make check-wiring` to prove the other names came
back. Read the whole continued block (`sed -n "${L},$((L+3))p" Makefile`) before touching it.

## Queue mechanics, suite reproducibility, a PR's blockers

Three failures that all look like something else — a starved sweeper, a suite whose two runs
disagree, and a PR called unapprovable on a rule of thumb. Full text with the measurements:
`references/queue-and-pr-mechanics.md`.

## Commit before you touch anything else in a worktree

An uncommitted worktree is not storage — it is a file nobody saved, in a directory a branch switch, a
sweep, or a container permission error can empty. **Commit and push before the next action of any kind**
(the next file edit is fine; checking out another branch there, reusing the directory, or starting a
second task in it is not), and prefer committing through a message that names the issue.

- **A branch ref can be empty while the work is fine.** Before believing "it is gone", check the *remotes*:
  `git ls-remote fork <branch>`, `git ls-tree -r <remote>/<branch> | grep <path>`, and the PR's own file
  list (`gh pr view <n> --json files`). A local branch at the base commit plus a published PR is a
  repurposed checkout, not data loss — measured on a repo where the local branch had zero commits while
  the fork branch carried the whole change and an open PR.
- **Quote byte sizes when arguing about a file's identity.** A reported "16.6 KB / 14.5 KB" matched
  `git cat-file -s` on the committed blobs exactly, which settled a "lost work" claim in one command.
- **Never re-invent lost work from memory to satisfy a request for deliverable.** If a file truly is gone,
  say so in one line and restart from the spec; a half-remembered re-implementation is worse than an
  honest restart.

## A file tree that is the source of truth for files living OUTSIDE the repo

When a repo holds copies of files that also exist outside it (agent profiles, deployed configs, generated
skills), the sync direction decides what a mistake costs. Copying tree → live can only lose content; so:

- **Refuse to shrink.** The sync tool must refuse to write a target file that is smaller than the live one
  (a fraction such as 75 % is enough) unless an explicit `--force` says it is deliberate, and name both
  byte counts when it refuses. A seed taken from a doc excerpt or a truncated paste is a PREFIX of the
  real file, and copying it over the live copy deletes rules silently while every gate stays green.
- **Gate the direction that loses content, not just equality.** A gate that compares sizes and fails when
  the LIVE file is longer catches the next truncated seed before a sync, not after. Skip the comparison
  where the live files do not exist (a CI runner) rather than failing — say in the docstring that the
  invariant holds on the host that holds them, so the silence is a stated limitation, not a blind spot.
- **Guard the WRITE by age, not only the read by content.** The live copy is a moving reference: its owner
  edits it while the change is under review, so a sync into a file modified after the source commit is a
  silent merge in the wrong direction, and no read-time caveat can see a write it already allowed. Refuse
  unless `--force`, naming both times, both sizes and the lines the overwrite would cost. Take the source
  time from the **commit** that last touched the tree path (`git log -1 --format=%ct -- <path>`), never
  the file's mtime — a fresh clone stamps every file with checkout time, which makes the guard pass on
  exactly the checkout that runs the sync.
- **Re-read the source at commit time and quote the sizes in the PR body.** A byte count taken from a
  message or an earlier turn is already stale when the live file grows; two `git cat-file -s` / `stat -c
  %s` lines that match are the evidence a reviewer needs.
- **A line that reports what changed must read a snapshot taken BEFORE the write.** Asking after the copy
  answers "all of them" on every run — a property the instrument never checked, which is the same defect
  as a green gate over a truncated seed.

Full recipes (re-seed by allowlist, the larger-but-dropping-lines trap, the audible skip, the age guard
and its negative controls): `references/agent-profile-tree.md`.

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
