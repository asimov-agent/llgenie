# make / build / publish pitfalls (llgenie engine images)

Rules that cost real debugging time in this repo. Each is a mechanism plus the move that avoids it.

## A literal comma inside `$(call ...)` truncates the command

GNU make splits `$(call …)` arguments on commas in the **unexpanded** text. So
`$(call scrubbed_run,… bash -lc 'hermes -z "…" -s a,b --yolo')` keeps only `-s a`; the closing quote is
dropped with the rest, the shell reports `unexpected EOF while looking for matching '`, and the leg
exits 2 **before any agent runs**. The bot then reports "agent failed", which looks like the conflict
and is not.

- Fix: give the comma-bearing value a variable — `LEG_SKILLS := a,b`, then `-s $(LEG_SKILLS)`. A
  variable reference contains no literal comma, so the call splits correctly and expands to the list.
- The other legs never hit it because their comma lives inside a `_<leg>` target that the container
  runs (`bash -lc 'make _issue-refiner'`); only a leg that inlines its whole `hermes` command (it must
  when the container's `Makefile` is the file being resolved) is exposed.
- Diagnose with `$(MAKE) -n <target>` and count single quotes in the printed line: **odd = truncated**.
  A guard should derive its target list by scanning the Makefile for `$(call scrubbed_run`, expand each
  with `make -n`, and fail on odd quotes or an `-s` list that lost its second entry.
- A checker that reads legs textually must expand simple Makefile assignments first, or it reports the
  variable name as a missing skill.

## FORCE that still reads the cache is not a rebuild

`build(force=True)` that skips the "available" check and then still passes
`--cache-from type=registry,…:buildcache-<variant>` re-tags the previous layers: the forced build
prints `built …`, compiles nothing, and the run proves only that the cached image is good.

- Force must add `--no-cache` **and** omit `--cache-from` (keep `--cache-to` so later runs benefit).
- Forward force to the shared base build too — a rebuilt engine on a stale toolchain base is still
  stale.
- A sweep target fans out with `xargs … $(MAKE) build-engine …`: the flag must be forwarded per row,
  or the whole-matrix force is impossible.
- Prove it from the log's buildx argv (`--no-cache` present, `--cache-from` absent) and from compiler
  output lines, not from the "built" message.

## Publish three names, and let exactly one variant own `:latest`

Every published image is named three ways: the immutable hash tag (`<sha8>-<hash>-<variant>`), the
moving `:<arch>` tag, and `:latest`.

- `:latest` must be claimed by **exactly one variant per engine** (the `cpu` variant when the engine
  has one, else its only/first variant). Letting every variant push `:latest` makes parallel rows race
  and the tag flap between backends.
- Rollout: a `:latest` that does not exist yet is a **note and a skip**; a `:latest` that exists with a
  different digest is a **failure**. Failing on a missing one reds the published-image stage for every
  engine nobody rebuilt.

## Verify before publish, and verify serving cells too

Per row the order is: build (no push) → probe the binary → push. A build step that publishes lets an
image reach the registry before anything tested it, and `push-engine` should re-check the binary as a
second gate.

A `TEST=serve` branch that jumps straight to serving never probes the binary of the cpu rows. Run the
flag probe first, joined with `&&` so a binary that does not answer stops the stage.

## `grep -q` under `set -o pipefail` reports a healthy binary as missing

Every runner step runs under `set -euo pipefail`. `… | grep -q '^pattern'` exits at the first match,
the writer upstream takes SIGPIPE, and the pipeline returns **141** — the engine is then reported
`missing (detect exited 141)` while its image test passes.

- Use plain `grep` with `> /dev/null` (it reads to EOF), or capture the output first and match it
  without a pipe.
- Symptom shape to recognise: image test OK + `docker run <image> version` exits 1 with `exited 141`.
- Guard it: refuse `| grep -q` anywhere in the skills/scripts the runner executes.

## Probe policy belongs to the engine's CLI

- `flags` (default): both the version family and the help family must answer.
- `device`: the CLI initialises its GPU at start, so it cannot answer on a GPU-less runner; the file
  must still exist and `detect` proves the version.
- `help`: an argparse CLI with **no version flag at all** — the help family must answer and `detect`
  supplies the version. Declaring it is not a weakening: a CLI that does have a version flag and breaks
  it still fails.

Declaring the policy is the fix; loosening the strict policy for everyone is not.

## "Built from source" is a claim to check, not a label

A `prebuilt: false` cell must (a) run a real build command (cmake/make/cargo/go/setup.py/install of the
checked-out tree — not a wheel), (b) pin its reference (sha or version tag, never a branch), and (c) not
start `FROM` an upstream build of that same engine. Backend words are not engine names, so
`exllamav3-rocm` on `rocm/pytorch` is a legitimate toolchain base.

Genuine exceptions get one recorded entry each with a reason and its tracking issue; the gate then
reds only on a NEW false claim. Converting a cell means deleting its exception entry.

## Prove a regression test detects the defect before you claim it locks it

Revert the fix in place (`git checkout -- <file>`), run the new test, watch it fail (record the count),
restore the fix, run it again. A test that passes both before and after locks nothing, and saying
"pinned by a test" without this step is a claim you have not verified.

## Reading a failing GitHub job's real output

```bash
gh api repos/<owner>/<repo>/actions/runs/<run-id>/jobs --paginate          # job ids + step statuses
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences
```

- `gh` refuses a log that contains terminal escape sequences unless `--allow-escape-sequences` is
  passed; the failure looks like empty output if stderr is suppressed.
- The **step list** answers which dispatch inputs were set: a gated step showing `success`
  (e.g. the GHCR login) means `push=true`; `skipped` means it was not requested. Don't infer inputs
  from the run object — `inputs` is often `null` there.
- A `0-job` run whose `name` is the workflow file path is a startup refusal, not a failed job.

## Docker-created OpenSpec change dirs are root-owned

`make openspec-new` runs in the container and can leave `openspec/changes/<name>/` owned by root, so
`write_file` fails with `Permission denied`. `sudo chown -R "$(id -u):$(id -g)" openspec/changes/<name>`
before writing the proposal.

## Push to `fork`, not `origin`

In a worktree of this repo `origin` is the upstream (`asimov-agent/llgenie`) and `fork` is
`andyholst/llgenie`. Push the feature branch to `fork` and open the PR with
`--repo asimov-agent/llgenie --base main --head andyholst:<branch>`; a branch pushed to `origin`
produces "No commits between" and needs deleting afterwards.
