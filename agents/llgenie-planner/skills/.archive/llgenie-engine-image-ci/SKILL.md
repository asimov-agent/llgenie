---
name: llgenie-engine-image-ci
description: Use when changing llgenie CI or doing llgenie repo work — engine-image CI, tests, OpenSpec, GitHub Actions bots, worktree+fork PR handling. Triggers llgenie.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llgenie, ci, github-actions, dockerfile, ghcr, engine, matrix, testing]
---

# llgenie engine-image registry pipeline

## When to Use

Changes to llgenie's engine-image CI: bumping an engine pin, re-scoping the
publish matrix, deriving or testing image tags, or adding a hermetic test that
round-trips against git refs or a real release download. Just running the make
loop without touching the pipeline? Not this skill. For the watch-loop
dispatcher (now REMOVED — only the CI engine-bump rebase remains) and how to
check/remove a stale host-crontab entry, see
`references/watch-loop-invocation.md`.
For GitHub Actions workflow YAML validation (files GitHub refuses, the
`${{ ... }}`-in-`run:` block-scalar pitfall, the 0-job startup-run diagnostic,
actionlint, `make check-workflows`): `references/github-actions-workflow-validation.md`.
For running `make loop` in the background (freeze the commit, read LOOP_EXIT from the log, a mid-run edit invalidates the run): `references/loop-gate-background-run.md`.
For the run-failure-reactor bot pattern: `references/run-failure-reactor.md`.
For a commit-author allowlist gate (identity+scope, self-matching scanner, non-mocked git tests): `references/commit-author-guard-work.md`.

## The repo contract

Maintain the CI pipeline that builds, tests and publishes llgenie's engine
images (one Dockerfile per engine x arch, pinned versions). The repo's
AGENTS.md is the source of truth for the make gates and the one-path-through-
container rule — this skill carries the pitfalls that cost time and are NOT
in AGENTS.md.

## Engine pin bumps: a version bump is more than a tag move

A bump workflow updates the pinned version and re-derives params. The frequent
failure class is NOT a stale tag — it is that a major engine release CHANGED
THE INSTALL MECHANISM (e.g. TensorFold 1.0 dropped `uv pip install` for a Zig
binary distributed as release archives). When a bump PR fails, do not just
move the tag over and re-push: read the engine's actual release assets and
check the install recipe still holds. If the recipe changed, the fix is to
switch the install path (archive download from the release page, verify the
checksum, extract, run the binary), not to keep fudging the old pip step. A
A release that cannot serve via the new recipe is not a valid bump.

Symptom to recognise (llgenie issue #172): the deriver interpolates the new version into
the skill's pip git URL (`'tensorfold @ git+{repo}.git@v{version}'`), so the generated
Dockerfile installs a ref upstream refuses — `TensorFold 1.0.0 and later install as a
native binary ... The Python engine stays at 0.6.6` → `[engine-runner] FAIL
tensorfold/cuda: step exited 1`. `main` keeps building only because its frozen recipe still
points at the last Python release. A bump whose recipe cannot build must be flagged in the
PR body, not opened red.

## Publish matrix: only images whose tag changed
(`<pin8>-<image-hash>-<arch>`), so it doubles as the change detector. Scope the
build/publish matrix to images whose tag differs from the parent commit
instead of comparing whole params files (which misses variant-only edits) and
instead of the full matrix on every push. Two rules that bite:

- A shared build file that every image loads (entrypoint, runner) must be part
  of EVERY tag's hash — then a change to it correctly rebuilds all images.
- An empty include list must be replaced with a `none` placeholder row, or the
  workflow fails on an empty matrix.

## Hermetic matrix tests: NEVER touch the working tree

Tests that derive tags / compare against git refs must build their OWN scratch
git repo (temp dir, commit a fixture tree, query it) and must never run
`git reset --hard` in the real checkout — a reset during a debug loop
irreversibly wipes uncommitted code (recovered only by re-writing it, the code
does not come back). Keep scratch test dirs out of `git add -A`.

## Triage a failing run from its failed-job list first

Start a failed-run investigation from the machine-readable job list, not the web page or the whole log. `gh run view <id> --json jobs` returns each job's name + `conclusion` + `databaseId`; filter to the failures and fetch each failed log with `gh run view <id> --log-failed --job <databaseId>`. `--job` takes the numeric id, NOT the name, and a broken run has many jobs sharing a name prefix — the build job `engine-image-<engine>-<arch>` can be green while its `test-published-<engine>-<arch>` post-build gate is red. Map name→id programmatically (jq/python filter by name substring) instead of copying a raw run. State the exact failing job-name + id and whether the gate is a build job or its post-build test when you attach a fix, so a reviewer opens the matching log.

When a bump turned the job red, `git show <sha> --stat` shows whether the same commit carried the frozen recipe (skill + per-arch Dockerfiles + params) together with the tests it shipped — a bump that fails `test-published-*` is often a frozen-recipe/mismatch whose fix belongs in that same commit, not a separate one.

## A dry-run dead because the backoff outlives the subprocess budget

When a CI test spawns a dry run as a subprocess with a hardcoded `subprocess.run(... timeout=N)` and the Hub returns a 429, the process sleeps through the shared `rate_limit_wait` and pytest kills it — stdout/stderr never captured. One attempt-1 backoff alone (measured 278 s) already exceeds the budget (120 s/300 s), so a dry run cannot survive a 429 as written. GitHub Actions then reports a bare `subprocess.TimeoutExpired` with no HF error line, which reads as a hang, not a rate limit.

- Prove the mechanism from the SAME run's own failed log (`gh run view <id> --log-failed --job <jobid>`), never from a sibling job's stderr. For `--download-top-tier` the stderr does print the retry (`attempt 1/8); retrying in 278.0s`); for a `--pick --auto --dry` kill the log shows only the timeout with empty streams — then say the backoff is the LIKELY cause, not assert it as proven.
- Fix shape: ONE named dry-run timeout constant that every dry-run subprocess test reads, so the budget and the permitted backoff stay in step. A per-test hardcoded literal fixed in one path leaves the other dry-run tests (e.g. the `--pick --auto` model+engine pick) red on the same class.
- Before claiming "an in-flight PR fixes this red job", map that PR's changed-file list to the failing test file. A fix that edits `test_top_tier_acceptance.py` + `hf_auth.py` but not `test_model_engine_pick.py` does NOT cover the `timeout=120` there. Comment on the fix PR with the specific uncovered job + test and offer to land the gap, rather than opening a competing PR that edits the same contract.

Always mount the repo read-only when running the suite in the test image so it
physically cannot mutate the tree:
`docker run --rm -v "$PWD":/repo:ro -w /repo llgenie/test:latest python -m pytest ...`
The test image has network, so real-download tests (fetch the release archive,
verify checksum, run the binary) run there, not on the host.

## Import-time constants escape monkeypatch

A module-level constant computed at import (`PARAMS_DIR`, `REPO_ROOT`) is bound
once and a later `monkeypatch.setattr` on the module has no effect — call sites
that read it keep the original. Thread the path through as a parameter (with
`root=None` defaulting to the real root) so tests can point at a scratch tree.

When a test helper redirects a whole CLUSTER of these constants
(`CONTAINER_DIR`, `PARAMS_DIR`, `DOCKERFILES_DIR`, `BASE_DIR`) to a scratch
checkout, every new constant added to the module afterward must be added to
that SAME batch list. A path (e.g. the probe manifest `BINARIES_PATH`) left
pointing at the real repo makes `generate-params` write to the real tree while
`path.relative_to(scratch_root)` later raises `not in the subpath of`. The
failure reads like a path bug at the point of `relative_to`, but the cause is a
one-line omission in the batch setter — grep the setter when you add any
module-level path constant.

## Engine binary probe: match whole flags, and verify the REAL image

Two rules around the push/published binary gate that look trivial and cost a
red CI run:

- **Never match a flag by substring**. `"-h" in "--help"` is true, so a test
  that collects which flags a skill's `detect` uses by `f in haystack` reports a
  false `-h` on any engine that uses `--help`. Match whole tokens (a word
  boundary that excludes `-`), e.g.
  `re.search(r"(?<![A-Za-z0-9-])" + re.escape(flag) + r"(?![A-Za-z0-9-])", haystack)`.
- **The probe passes each flag as its own argv element** to the binary (so
  positional argv is fine in production); only the TEST that scans skill text
  needs the whole-token fix.
- **Never hardcode GNU-only commands in the probe script.** A host-side run on
  macOS lacks `timeout`, so `try() { timeout 30 "$path" "$1"; }` dies with
  `timeout: command not found` (exit 2 = "present but no flag answered") and
  fails the hermetic test only on macOS. Pick a portable timeout once at the top:
  `command -v timeout` (Linux/production container) else `command -v gtimeout`
  else empty, then invoke as `$TO python3 "$path" "$1"` (unquoted so it splits;
  empty = no timeout). Production runs the probe inside a Linux image where
  `timeout` exists; only the macOS host-side test hits the fallback.

The ``publish gate (`test_image` -> `binary_file_works`) is the thing that
proves the file answers a flag before any `docker tag`/`push`. For the
published images add a REAL no-mock test that pulls the latest GHCR tag
(`pull_published`: drop local, digest-match against the moving `:<arch>` alias)
and runs the same probe inside that exact image, per engine x arch in the
published matrix. Skip a variant in the DISABLED set — there is no published
image to be its truth.

- A `probe: device` variant (a CLI that needs its device to answer a flag) is a
  deliberate rc-2 tolerance, never a skipped probe: the probe must STILL run the
  binary file with its documented flags first (then the fallback trio), and a
  missing file (rc 1) still fails. Lock the argv + rc semantics at the
  `binary_file_works` level, not just the exemption.

- The probe manifest is an AGGREGATE file: `write_params` regenerates
  `binaries.json` even for a single-engine `generate-engine-params ENGINE=<id>`
  (it keeps every other engine's entry verbatim and updates only the bumped
  one). So a bump's regen-scope guard must treat `binaries.json` as in-scope,
  and the bump test fixture must SEED a committed manifest (with an "other
  engine" entry) so the test models production — a brand-new untracked file
  fails the guard as scope creep, and a fixture that starts empty hides the
  preservation invariant. Assert the other engine's entry survives the bump.

## ci.yml supersedes its own PR runs (don't re-add a group, don't cancel a main run)

The pipeline declares `concurrency: {group: ${{ github.workflow }}-${{ github.ref }},
cancel-in-progress: ${{ github.event_name == 'pull_request' }}}` (#288/#289). Two consequences worth
remembering before touching it:

- The group is deliberately **per-ref**: `github.ref` for a `pull_request` run is `refs/pull/<n>/merge`,
  so one PR supersedes its own predecessor and two PRs never cancel each other. A constant group (`ci`)
  or an unconditional `cancel-in-progress: true` is a regression — the latter would kill a `main` run
  mid-publish and half-push a content-hash image tag, and kill a bot 180-min agent job. `pipeline.yml`
  and `published.yml` are `workflow_call` files; the group belongs in the CALLER.
- **Verify it live rather than from the YAML**: a force-push to the PR must flip the previous run to
  `completed/cancelled` while the new one queues (`gh run list --workflow ci.yml --branch <b>`). Do not
  conclude "not working" from the first poll — the cancellation lands a few seconds after the new run
  is created (measured: the old run showed `in_progress` for ~90 s, then `cancelled`).

## This clone's remotes are inverted vs AGENTS.md — push to `fork`, PR to `origin`

AGENTS.md says "push the branch to the fork (`origin`)", but on this Linux clone
`origin` = **asimov-agent/llgenie** (upstream) and `fork` = **andyholst/llgenie**. Check `git remote -v`
before pushing: `git push -u fork feat/<name>` then `gh pr create --repo asimov-agent/llgenie --head
andyholst:feat/<name>`. Guessing from the AGENTS.md wording pushes the branch at the upstream.

A `git push origin feat/<name>` that reports `* [new branch]` means the branch was just
created ON the upstream repo — a stray that does not belong there. Recover before it becomes a
footgun for another session: `git push origin --delete feat/<name>`, confirm it is gone with
`git ls-remote --heads origin` (upstream should list only `main`), then push the branch to the
fork and update the PR head. Verify the PR's head owner matches the fork before force-pushing an
`--force-with-lease`: `gh pr view <N> --repo asimov-agent/llgenie --json headRepositoryOwner,headRefName`
— head owner must be `andyholst`, and the remote you push to must be `fork`.

## Host `pytest` collection boots the engine — verify in the test image or CI

`tests/conftest.py` imports `scripts.llama_serve`, and that import runs engine
setup/launch side effects (it will start the Strata server and hang). Running
the suite with host `pytest` (even `--collect-only`) produces near-empty output
and a timeout, so it looks like a crash, not a hang. For this repo the standing
rule is: do not run the engine test suite locally — start a fresh-commit push
and monitor the CI pipeline (`gh pr checks <n> --watch`). Locally you may only
static-verify (`py_compile`, `lint_linefeeds`) — never expect a hosted-suite
pass on the host.

## Hash committed bytes, not a live render

To make a tag hash match `git show <ref>:<path>` for an unchanged tree, hash
files READ RELATIVE TO the params/commit root. Read each input file from the
repo root so a scratch git repo and the real checkout produce identical hashes
for identical trees. (In llgenie the committed Dockerfile IS `render_dockerfile`
output byte-for-byte — verified for all 31 engine×variant pairs — and
`make check-engine-params` keeps params/Dockerfiles from going stale, so
hashing the committed file preserves the published digests.)

## The tag hash is BOTH the change detector and the pull target

`engine_skills._image_inputs` (variant params + committed Dockerfile +
`entrypoint.sh` + `engine_runner.py`, concatenated) is the single definition of
the tag bytes. The matrix scoping (`engine_image._tag_at` / `_current_tag`) and
`image_spec` (the tag `make install` pulls) must both go through it.

- Changing what is hashed, **or how the parts are joined** (`b"\0".join` instead
  of the published concatenation), moves every engine's tag at once. The scoped
  matrix compares the new framing against itself, sees no change, publishes
  nothing — and every install job dies with `not published` while CI's
  engine-image jobs happily build nothing. A tag-scheme change can NEVER be
  bootstrapped by a scoped matrix; it needs its own change plus a full-matrix
  push. Pin the digest in a hermetic test so a scheme change is deliberate.
- Recomputing a ref's tag: read the ref's bytes with `git show <ref>:<path>` and
  pass them into `_image_inputs` through its `dockerfile=` / `entrypoint=` /
  `runner=` overrides. Never re-implement the framing inside the matrix code —
  that is how the two definitions drift apart.
- A same-repo `pull_request` run DOES publish what it built: `make push-engine` is an
  unconditional step of every `engine-image-*` job, so `PUBLISH` only gates the buildx
  `--push`, not the publish step (measured: run 38121659510 pushed
  `llama-cpp:23b0202a-021e11d2-cuda` on a PR run). A fork PR (read-only token against the
  base registry) is the case that cannot push, and it must fail loudly.
- The real failure is ORDER, not publishing: `pipeline.yml`'s `install` job needs only
  `ci-images`, so it pulls while `engine-image-*` is still building. The first run of a
  new pin dies with `[install] FAIL <engine>/<variant>: not published` while its own build
  job pushes that tag minutes later; a branch pushed several times looks green by accident
  because an earlier run already published it. Gate: `make ci-wait-engine-images ARCH=<b>`
  before `make ci-install` — manifest lookups for exactly the tags install pulls
  (`install_engine_launchers.install_plan` is the one place that list is built), no pull,
  no build, no fallback. Diagnose by comparing job timestamps: `gh run view <id> --json jobs`
  and read `linux / install` start/end against `engine-image-<engine>-cpu` end.
- EVERY pipeline job runs exactly one `make ci-<job>` target — do NOT add the gate as a
  second step of a workflow job. A new workflow step means the job runs a second bare
  command instead of one `make ci-*`, and the one-target check turns the PR red at the
  perfectly-mapped `unit`/`top-tier` stages before the gate even runs. Put the gate inside
  the make recipe it should precede (`ci-install`'s Linux branch runs the wait, then
  `ci-install-run`), and exempt the platform that pulls no engine images (macOS/Metal
  prints its skip and exits 0) so the check stays honest for every OS in the matrix.
 - GNU make evaluates `ifeq`/`$(if)` while it PARSES the file, not when a recipe runs. Put any conditional that branches on a `:=`-computed variable (`HOST_OS := $(shell uname -s)`) strictly AFTER that assignment — a conditional defined earlier sees the empty value and silently takes the wrong branch (e.g. the Linux registry-lookup branch on macOS). A command-line override (`make -n TARGET HOST_OS=Darwin`) does NOT expose this: the override applies for the whole parse, so the dry run looks right while real macOS still hits the wrong branch. Lock the order in a hermetic test (`mk.find('<target>:')` after `mk.find('HOST_OS := ...')`).
 - When a test reads the Makefile's OS conditional, never take "the first `ifeq ($(HOST_OS),Darwin)` block" — any target may branch on the OS, so the first block in the file is not necessarily the recipe under test. Select the block by CONTENT (a marker string unique to the recipe, e.g. `TEST_RUN :=`), never by position.

## A mocked `subprocess.run` in a persistent kernel hijacks real calls

When you verify a probe by monkeypatching `ei.subprocess.run = fake` in a
persistent `execute_code` kernel, you are mutating the SHARED `subprocess`
module — every later `subprocess.run(["gh", ...])` in that same kernel is
intercepted too and silently returns the fake (rc 2, no-op). The PR edit / issue
comment "succeeds" with rc 2 and nothing happened. Restore the real function
(`ei.subprocess.run = subprocess.run`) or start a fresh kernel before running any
real subprocess call, and run `gh` bookkeeping from the shell, not the kernel.

## When `patch`'s fuzzy matcher keeps corrupting a file, rewrite it deterministically

`patch` with context-aware matching can mis-indent a block (nesting a new
top-level `def` inside the previous function) and then keep re-mangling the same
region on retry. Stop retrying `patch` on that file: do a line-based rewrite in
Python — locate the block by a unique marker line, splice in the replacement
list, write the file — then `py_compile` to confirm. This is faster and cannot
re-nest.

## A run id is not an issue number, and `gh run view --json` has no `pullRequests`

A bot/reporter that wants to attach its finding to "the run" must resolve a REAL subject, and both
obvious routes fail (measured live, gh 2.102.0, issue #294/#297):

- `POST /repos/{repo}/issues/{run_id}/comments` **404s** — a workflow run's `databaseId` is not an
  issue number. It fails silently if the caller discards the return code (`subprocess.run(...)`
  without a check), so the reporter looks green while writing nowhere.
- `gh run view <id> --json pullRequests` → `Unknown JSON field: "pullRequests"`. The field does not
  exist; the fake-`gh` stub answered it happily, which is how the bug shipped.
- The REST run object (`/repos/{repo}/actions/runs/<id>`) does carry `pull_requests`, but it is
  **EMPTY for a fork-PR run** — and every bot PR in this repo is a fork PR.
- What works: the run object's `head_branch`, then `gh pr list --repo <r> --state all --head <branch>
  --json number,state` (no `owner:` prefix — `--head andyholst:<branch>` returned `[]` where
  `--head <branch>` returned the PR). Verified: run `38761102690` → PR 277, `38731475236` → PR 170.

So: assert the TARGET of a delivery (which URL/number was written to), never just the call count, and
stub the CLI's REAL constraints — pin the refused argv in a test of its own. A fallback that is also
visible (one deduped issue per stuck runner label) plus a loud exit (3) is the right shape when the
intended target cannot be resolved.

## Docs are gated now: a new user-facing target must land in README in the same commit

`make check-docs` (`scripts/check_docs.py`, run by `ci-unit` next to `check-wiring`, issue
#257) fails when a make target with a `##` help line (what `make help` prints) is not
named in `README.md` (whole-token: `docs-report` does not document `docs`; a pattern
target `run-engine-%` is documented by its stem), when a recording in
`tests/fixtures/docs-exceptions.json` goes stale, or when an `agent-wiki/*.md` entry
references no issue/PR. So adding a target/script/test means three edits in ONE commit:
the target, its README line, and the work record citing `#<issue>`. `make docs-report`
lists what is missing. A new test file still needs `test-unit` (the wiring guard fails
otherwise; `check-docs` is the docs half of the same contract).

The gate is deliberately mechanical: it guards make targets against the README and work
records against an issue reference. It does NOT compare a prose sentence to the code it
describes — a README paragraph about when CI runs (`ci.yml`'s `on:` block) can drift
invisibly and no gate catches it. When you find such prose drift, file it as an issue and
name the gate's blind spot in the body, rather than assuming the gate will catch the next
one.

When main merges a PR that added user-facing targets with no README sentence, YOUR
rebased branch goes red on `ci-unit` at `$(MAKE) check-docs` even though nothing of yours
is wrong (measured: PR #253's fix-bot added 8 undocumented targets; the rebase of a docs
PR caught all 8). That is the gate working on a merge artifact — document main's targets
in your PR (or record each as a dated exception) instead of reaching for the exception
list, and say so in the PR body so the reviewer sees why an unrelated target appears in
the diff.

## Writing AGENTS.md is approval-gated — a timed-out prompt is a refusal

The file tools refuse writes to `AGENTS.md` ('protected agent-instruction file') until
the user approves a prompt; if that prompt times out, the write is refused and the
instructions forbid retrying or routing around it (no terminal/patch workaround). Ask
the user explicitly, then make a fresh attempt — do not silently drop the mandate edit
and do not fake it in the PR body. `AGENTS.md` is also scanned for Hermes context-file
threat patterns by `make test-agents-read`; verify a new section locally with
`python3 -c "from tools.threat_patterns import scan_for_threats; ..."` (the Hermes venv
python has it) before pushing.

The loop gate's `agents-read` stage runs `make test-agents-read`, which needs `python3.12` — but
Arch ships 3.14 only, so the stage fails on this host until you provision it. Fix (user-local, no
system touch): `uv python install 3.12` (lands in `~/.local/bin/python3.12`), then re-run the loop.
A red `agents-read` on Arch is a missing interpreter, not a threat-pattern finding.

## Rebasing a batch of open PRs onto latest main: measure first, rebase only what moved

Before touching anything, `git fetch origin main` and compare each branch to the tip:
`git rev-list --left-right --count origin/main...fork/<branch>` (left = behind, right =
ahead) and the head commit's parent — a PR whose head's `parent=` IS `origin/main`'s tip
is already rebased, so there is nothing to do and no conflicts to invent. Confirm with
`git merge-tree --write-tree origin/main <ref>` per branch. A stale LOCAL branch name
(`feat/x` still at an old sha while `fork/feat/x` sits on a rebased commit, or the rebase
living on a `tmp/rebase-<issue>` branch that was force-pushed over the fork ref) is the
is the common state: the pushed fork ref is the source of truth, never the local ref's distance.

- **Fold a small fix into the RIGHT commit of a multi-commit PR with autosquash**, not a third
  commit and not a manual reorder. `git commit -m "fixup! <subject of the commit it belongs to>"`
  then `GIT_SEQUENCE_EDITOR=true GIT_EDITOR=true git rebase -i --autosquash origin/main` — the
  `fixup!` marker makes the interactive editor auto-place it under its target and the two env vars
  run the whole thing non-interactively. This keeps a 2-commit PR at 2 commits (e.g. a lint break
  introduced by a rebase integration folds into the commit that owns the file) instead of shipping a
  noise commit. Verify the commit count is unchanged after (`git log --oneline origin/main..HEAD`).

## The bot container: nerve/JEV supervision, and how to verify it on the host

Full detail in `references/bot-container-supervision.md`. Anything the host's Hermes has that the
agent image lacks is a gap the bot silently works around; verify a plugin by its pinned ref and a
host-side check, not by the image build succeeding.


## A checker exemption that skips a whole block hides the violation (scan per command)

`scripts/code_review.py`'s `workflow-inline-scripts` skipped a whole `run:` block as soon as it contained
a make call **or** any `gh api`/`gh pr`/… — the exact shape (`registry-sync.yml`: `git config … "$(gh api
user)"` + `gap="$(python3 scripts/engine_skill_gap.py report --md)"` + `gh pr create …`) where a second
script call grows. Rule: an exemption must be PER COMMAND (per line), and a `make` on the same line is the
only thing that clears a script call. Prove it on the real files both ways (pre-fix checker → 0 findings,
per-line checker → 1). Same class as the `gh api` guard exemption in #270/#277.

## A scanner that 'stops at unindented text' may only ever see the LAST block

Measured on `code_review.py`'s `workflow-inline-scripts`: `_steps()` tried to end a `run:` block at the
first unindented line after it, but in a workflow document the first `run:` block's own parent is the
top level — there is NO line less-indented than it — so the extractor ran to the end of the file and
yielded only a workflow's LAST `run:` block (measured `ci.yml`: `current=1` vs `real=20`). Fixing the
per-command scan (#296) is correct but stays nearly dead while the extractor feeds it one block per
file. When you harden a block scanner, PROVE the yield count against the source (`len(_steps(text))`
vs `text.count("run:")`) rather than only that it finds the one block you were chasing. The
self-consistency test added with the fix proves the LAST block of each workflow is clean — say that
limitation plainly instead of implying the whole tree is scanned.

## A script NAME in prose is not a violation — strip code from comments before scanning

Once a check inspects every line of a block, it regresses into false positives on script NAMES that
appear in prose — a quoted commit message, a `#` comment, or a heredoc describing a command
(`python3 scripts/fix_loop.sh` inside a multiline quoted message). The fix is a `code_only` pass that
keeps only lines that are actually COMMANDS (a `run:` body / command-substitution / a line that
starts an executable token) and drops quoted/commented prose, before the script-call scan runs. When
you add such a filter, pin BOTH directions: prose mention of a script is not a finding, but a real
command substitution inline is still caught.

## Stale nested worktree copies inside the checkout pollute repo-wide scans

`git worktree add ../llgenie-wt/<x>` run FROM INSIDE the working tree lands the worktree at
`<repo>/llgenie-wt/<x>` — a copy nested under the repo that is TRACKED as untracked content (the
`.git` here is a file, so it is invisible to the outer tree's worktree list until it is prunable, and
the outer repo's `git status` does not tell you it is there). A repo-wide `pytest`/grep scan then
reads every nested copy, and a handful of tests fail on stale branch content while the real tree is
clean — misleading you into hunting a regression that is only the copies. Before declaring a
repo-wide suite red, confirm the failures trace to live tracked files, not to `llgenie-wt/*`
(and any other nested repo dirs) nested inside the checkout; move them out (or exclude them)
non-destructively and re-run. A "regression" that vanishes once the nested copies are out of reach
is environmental pollution, not the change under test.

## Trigger guards drift: three shapes and one hole, all found by a table-driven test

An audit of every `workflow_dispatch` workflow (#295) found four guard shapes for the same #122 rule. The
antipattern to look for: `curl` on `/repos/{repo}/collaborators/<user>` expecting **204** — that endpoint
answers 204 for ANY collaborator level (read/triage included), so the check is not a write-level check;
the real one is `gh api /repos/{repo}/collaborators/<u>/permission` and a `case` on
`admin|maintain|write`, run for BOTH `github.actor` and `github.triggering_actor`. Two more findings from
the same audit, both worth checking in any fleet:

- **A `guard` job nothing `needs` protects nothing** — resolve the job graph, not the presence of a job.
- **A declared-but-unread `guard.outputs.allowed`** makes a reviewer believe a value is consulted while the
  refusal is really the step's non-zero exit. Scan EVERY workflow for dead guard outputs (the finding was
  `ci.yml`, which is not dispatchable, so a "dispatchable only" filter misses it).

GitHub already refuses `workflow_dispatch` without write access, so this is defence-in-depth — say that
plainly in the issue instead of implying an open door.


The PR that closed this — #300 for issue #295, its merge commit and the #306 review finding —
is recorded in `references/pr300-issue295-context.md`.

## A fake CLI on PATH must encode the CLI's CONSTRAINTS and REAL VALUES, not just answers

The bots' suites drive a fake `gh` on PATH that answers whatever the product asks. Two bugs shipped
green because of it (issue-box dispatch, PR #268): the product built `gh issue view <n> --comments
--json ...`, which **real gh rejects** (`specify only one of --comments or --json` — gh 2.102.0), and
it compared `state != "open"` while `gh issue view --json state` returns the CLI's enum `OPEN`/
`CLOSED`. The fake accepted both, and the fixtures used the wrong case, so the product agreed with
its own fixture instead of with the CLI. Rules that follow:

- Add a **second alarm** that does not depend on the fixture's mood: run the real code path and scan
  every argv it built for the combination the CLI refuses (`tests/test_issue_implementer.py::test_no_gh_call_combines_comments_with_json`).
- Fixtures carry the CLI's **real** values (uppercase `OPEN`/`CLOSED`), never a tidied-up version.
- Before claiming a bot path works, run its deterministic half against the LIVE CLI from the repo
  (`make issue-bot-dispatch REPO=asimov-agent/llgenie FORCE_ISSUE=<n> DRY=1`, `python3
  scripts/issue_refiner.py pick --repo asimov-agent/llgenie --dry`) — seconds, no model spend, and
  it is the only thing that proves the argv.
- A bot workflow can fail for a reason no code change fixes: the job env printing an empty key
  (`NOUS_API_KEY:` blank) means the referenced secret does not exist (`NOUS_PORTAL_API_TOKEN` was
  missing), and the step guard says so loudly. Read the failed run's env block before hunting code.

## A bot whose runs are all green may be a bot that never ran — `set +e` hides the crash

When a bot reports SUCCESS every run, verify it actually did its work before trusting the green. The highest-value defect in a fleet is a bot that CRASHES in its decision step and rises green because the step swallows the crash. Two swallow shapes, both measured in the llgenie fleet:

- **`set +e; out=$(make <bot>-sweep/pick)` then `action=${action:-unknown}` → `go=false`/`dispatch=false` → green no-op.** The crashed command's rc is discarded and the empty `action` is read as "nothing to do". A rebase bot had never rebased a single PR while reporting green because its sweep crashed every run and the step turned the crash into `action=unknown`. The specific argv that crashed it, and a real-CLI field-name trap: `gh search prs --json comments` is REFUSED (`comments` is not a field; it is `commentsCount`). The `--comments --json` clash is already documented above — this is the same class on the FIELD side of a `--json a,b,c` query: `gh` rejects an unknown field on a valid verb, PyYAML/plain Python accept it, and a fake `gh` that happily answers any `--json` ask hides it.
- **The step captures `rc=$?` but never consults it** — it writes `rc=$rc` to `GITHUB_OUTPUT` and moves on, converting a crashed decision into an EMPTY `action=` which a `[ "" = "cap" ]`-style branch treats as "proceed". Worse than a no-op: it runs downstream steps with no picked subject.

Fix shape: the decision step must treat a non-zero target exit as a FAILURE of the step (a loud red run naming the target and its rc), never as `action=unknown`/empty. Pin it with a table-driven test over every bot workflow — each `make …-sweep`/`pick`/`dispatch` step must capture the rc AND `exit` non-zero on it — so the next crash is red immediately. Prove any fake-`gh`-driven suite by making the fake refuse the refused argv/figure the real CLI refuses (verify field names with `gh <verb> --json <field>` live, not `--help` prose).

Corollary — a tokenless step silently skips its checks: exercise the bot's deterministic half against the LIVE CLI (`make <bot>-scan`, `make <bot>-pick DRY=1`) from the repo and compare finding/runs counts against what CI reported. A scan step that runs with no `GH_TOKEN` has `gh` refuse and silently skip each check, so the run prints "no findings" while the same check WITH a token (the filer half) finds N. Give every step that reads `gh`/`gh api` the token, and exercise the exact step CI runs, not a hand-rolled easier one.

- A live deterministic half is NOT read-only. `make <bot>-pick REPO=...` claims its subject: it posts a claim COMMENT on the issue and writes the gitignored `refine-in.md`/`comment.md` into the tree. For a pure read use the `--dry`/`DRY=1` path; if you run the real pick against a real repo, expect the claim (a claim with no `done` ages out on the bot's own TTL, and the local artifacts must be deleted before commit — check `git status -sb`).
- A workflow file GitHub REJECTS is invisible to a green CI pass on the runners... if the run never starts. "This run likely failed because of a workflow file issue" before any job runs = GitHub's parser refused the file. The docs-read tool and PyYAML READ duplicate YAML keys silently (last wins); GitHub refuses them. When a run dies at submission with no job output, diff the workflow for duplicate keys (`yaml.safe_load` won't tell you) before hunting code — a manual `workflow_dispatch` of a scheduled-only workflow that never starts, or a fresh commit that spawns no run, is usually the file being rejected, not the pipeline.

Opening a bot-fix PR: verify the commit AUTHOR before creating the PR. A worktree inheriting a `github-actions[bot]` global identity files commits as that bot, which GitHub flags as a first-time contributor and HOLDS the PR's own workflows for approval — pitch all green PRs the moment they open. Force `user.name`/`user.email` to the repo owner locally before committing bot-fix branches.

## Bot artifacts at the repo root are gitignored now (`issue.md`, `refine-in.md`, `refine.md`, `comment.md`)

These are run inputs the dispatchers/reviewers write next to the code, and the workflows have to undo
`git add -A` with `git reset -- issue.md`. They are in `.gitignore`; still check `git status` before
an `amend`, because a DRY dispatch written while you work lands in the tree and rides into the commit
(measured: a stray `issue.md` in a PR until `git rm --cached`).

A `--dry`/`DRY=1` path must leave the tree untouched — running it is how you prove a dry run is really
dry. When its writer sits OUTSIDE the `if not dry:` block (`out_path.write_text(...)` on the indent
after the dry guard returns), a dry run still emits the file. Verify DRY is pure by running it and
then confirming NO new untracked file appeared (`git status -sb` before/after); `--dry` producing
a new `refine-in.md`/`comment.md`/report is a bug, not a convenience. The write must be inside the
dry guard or the output path must be conditionally chosen.

These gitignored scratch files are INVISIBLE to `git status` but VISIBLE to repo-walking guards: a
guard that enumerates the tree with `REPO.rglob("*")` (e.g. a rename/scope guard) does NOT respect
`.gitignore`, so a stray `refine-in.md`/`issue.md` left from a manual run trips it and reddens the
`make loop` rename stage even though the tree is clean (`git status` shows nothing). If a loop/guard
fails on a file you did not intentionally create, check the gitignored root input names (`refine-in.md`,
`issue.md`, `comment.md`, `refine.md`) with `ls`/`find` — a leftover scratch artifact from an earlier
manual bot run is the usual cause. Remove it and re-run; do not chase it as a code regression.

## A workflow a human can dispatch must state the work it will do (#276)

`scripts/check_dispatch_forms.py` (`check` in `ci-unit`, `report` generates the README table) holds every
`workflow_dispatch` workflow to: a `name:` that describes the work (not the file stem), a documented
dispatch form (each input with a `description:` and a `default:`/`required: true`; a bare
dispatch allowed only with `# dispatch: no inputs — <reason>`), and a `Trigger surface` / `Flow` /
`Never` header. The README table is generated from the workflows and verified against them.

Rules that follow from building it:

- **An input the form offers must reach code**, or the form lies: `engine-bump-rebase`'s `dry` goes
  through a `make engine-bump-rebase DRY=1` target that passes the script's `--dry`.
- **A workflow step calls a make target, never a repo script** — and a guard that exempts a whole
  `run:` block because it contains `gh api` will MISS an inline `python3 scripts/…` in the same block
  (measured: `engine-bump-rebase.yml` and `registry-sync.yml` both hid one that way). Exempt per
  command line, not per block.
- **Rebasing a guard-introducing PR can CATCH a workflow main merged after the PR opened.** When you
  rebase the PR that adds the dispatch-form guard (or any bot guard), main's newly-merged workflows
  may violate it — the guard is new, so nothing enforced them. Fix each violating workflow (name,
  header, `# dispatch: no inputs — …`) IN the guard commit and fold it with `fixup!` + `--autosquash`
  (the `fixup!` marker auto-places it under the guard commit), keeping the PR atomic instead of
  shipping a second, unrelated-looking commit.
- **Updating a workflow's step breaks tests that assert its text**: `tests/test_engine_bump_rebase.py`
  asserted `"engine_bump_rebase.py" in text`, which kept passing while the step bypassed make. Update
  such a test to assert the make target and, explicitly, that the run block does NOT call the script.
- Generating a doc table from code and verifying it in CI (the `docs`-gate pattern) is the cheapest way
  to stop a README from describing a pipeline that no longer exists.
- **A header that names a TIME is a claim the guard must verify.** `header_block()` returns only the
  KEY NAMES it found (`['Trigger surface', 'Flow', 'Never']`) — the line TEXT that would let a rule
  check what a claim says is invisible to it. A time-integrity rule must therefore read the comment
  LINES (the leading `#`-block, blank lines inside it tolerated) and match each `HH:MM UTC` the block
  names against the minute+hour of a `cron:` in the SAME file; a file with no schedule must not claim a
  time at all. This is the only way stale prose minutes (a header saying one time over a cron that
  starts at another, after a global minute reallocation) get caught at all — the guard cannot see them
  if it only has the key names.
- **A guard that bans a class must be proven to FIRE.** The pass-path is "the real workflows stay
  green", so a never-triggering rule looks correct. Run the negative direction too: a fixture whose
  header names the wrong minute → violation, the SAME file with the matching minute → clean, and no
  schedule + a claimed time → violation. A rule you cannot make trip is vacuous.
- **The conditional-suffix `run:` idiom appends a flag only for manual dispatch.**
  `${{ inputs.dry == 'true' && 'DRY=1' || '' }}` yields `''` for a SCHEDULED run (no `inputs.dry`
  exists) and for the input's `"false"` default — so the scheduled path runs the REAL action (here a
  forward-merge + `--force-with-lease` push), and only a dispatcher ticking the box gets the preview
  flag. The `== 'true'` comparison is against a STRING input; switching the input to `type: boolean`
  silently breaks it (GitHub coerces boolean-vs-string to numbers, `true == 'true'` is false), so the
  input must stay a string.
- **That idiom is correct but cryptic — a reviewer reads the diff `-`/`+` lines as TWO coexisting calls.**
  Stacked side-by-side, the deleted independent line (`python3 scripts/x.py` on main today) and the new
  inline conditional look like a workflow that both runs the real action AND a dry run, and the
  conditional reads as "dry when == 1" instead of "dry only when ticked" (`== 'true'` is a STRING
  compare, never the number 1). When asked "why does the workflow do X and Y", first check whether the
  two are one hunk before assuming the branch is wrong. Because it costs a question to explain, make it
  self-documenting instead: pass the input through `env: DRY_INPUT: ${{ inputs.dry }}` and branch in
  shell, each arm `echo`ing which mode it took (scheduled arm: "REAL REBASE: … force-with-lease
  push"; dry arm: "DRY RUN: … nothing pushed"). Behavior is identical, the mode is now in the log, and
  the `env:` line still contains `inputs.dry` so a guard that greps the text for the input keeps
  passing.

## A bot that only files issues (the code-review bot, #269) — and the checks that must not cry wolf

`scripts/code_review.py` reviews the tree + the pipelines and files ONE issue per finding. The shape
worth copying: **deterministic checks** (no model anywhere, so a scan is free and cannot invent a
finding) + a **marker-dedup filer** (`<!-- code-review:<key> -->` in the body, so a re-run on an
unchanged tree files nothing) + a **per-run cap**. The suite asserts the narrowest promise — its only
`gh` verbs are `issue list` and `issue create` (`test_the_bot_never_writes_code`) — and a
self-consistency test runs every check over the real repo and requires none of them to name the new
workflow. Copy that test: it is what stops a checker from flagging its own file.

Before adding a check, MEASURE the platform; two candidates were wrong:

- **A reusable `workflow_call` file's run count is meaningless.** `ci.yml` calls `pipeline.yml` three
times and reports 892 runs while `pipeline.yml` reports **0** — GitHub counts a reusable workflow's
runs under its caller. A naive "0 runs = neglected" check files false claims against healthy
pipelines (use `reusable-orphan` instead: nothing references it).
- **Only fixed minute+hour cron slots can collide.** An hourly cron fires many times a day by design.
- `gh workflow list --json name,path` — the runs endpoint takes the FILE name (`pipeline.yml`), not
the display name; querying by display name 404s whenever they differ (`bench-disk` vs `bench-disk.yml`).
- The two API-backed checks need admin (`gh secret list`); degrade with a loud `SKIPPED this run`
  warning instead of `SystemExit`, or a token without admin means the bot files nothing at all.

## Align a bot PR with the open issues that touch the same files — implement now, not later

When finalizing a bot/CI PR, the user's standing rule is to pull in the NOT-yet-implemented issues
that target the same files or mechanisms the PR already touches, and implement them NOW inside that
PR — not defer them. The reason is refactor-avoidance: a later PR that reworks the same module (e.g.
adding a claim protocol to a bot whose picker the current PR already edits) forces a major refactor
on top of freshly-merged code. So before finalizing:

- **Sweep the open issues for ones whose acceptance touches the files in your diff** (`gh issue list
  --state open` and match against `git diff --name-only main...HEAD`). For each hit, implement its
  data/mechanism in the current PR and update the issue with a pointer to where it landed.
- **A PR that only carries the guard half of a two-part issue is a deliberate scope cut** — say so in
  the PR body and on the issue, naming the part that stays out and why (e.g. the ordering half ships,
  the target-claim half is a separate gate PR). Do not silently leave the other half unaddressed.
- **Update the issue bodies** with a short "implemented in this PR" note so issue, OpenSpec change and
  code agree (same rule as the "issue body is part of the change" section).

## Multiple bots on one repo: verify mutual exclusion on BOTH axes, by mechanism not by docstring

Full detail in `references/bot-fleet-mutual-exclusion.md`. A fleet of bots can all touch the same
issue/PR branch; audit each on TWO axes — (a) does it claim BEFORE its first mutation, and (b) does
its picker read ALL sibling bots' claims — by mechanism, not by docstring.


## One worktree, one PR: never commit new work on a branch that already has a PR

Measured slip: a worktree was on `fix/bots-gh-json-argv` (PR #268 open, branch pushed) and the next
task was committed there. `git branch feat/new && git rebase --onto origin/main fix/bots-gh-json-argv
feat/new` then produced an EMPTY branch — the upstream ref already pointed at the new commit, so the
range was empty and the rebase silently reset the branch to main (the commit survived only as the tip
of the old branch). Fix: `git branch -f new <commit>` then `git rebase --onto origin/main <parent> new`.
Prevention: `git worktree add ../llgenie-wt/<topic> -b <branch> origin/main` for each new PR, so a
pushed branch is never the one you are standing on.

## Scratch file hygiene

Debug probes named `probe_*.py` or similar get swept up by `git add -A` and
committed by accident. The same bites a gh body file: a `.pr-body.md` / `.issue-body.md`
written for `--body-file` is untracked but NOT ignored, so a later `git add -A && git
commit --amend` ships it inside the squashed commit while the worktree shows it as
`D` (deleted) — always `git log -1 --name-only` after an amend and delete the body file
(keep its text in a variable or re-read the PR body) before amending. Delete scratch files (and `git reset` anything already
staged) before committing; check `git status -sb` first to catch strays.

## Two Hermes sessions share ONE clone, and forks carry the branch

AGENTS.md MANDATES that each agent work in its OWN git worktree
(`../llgenie-wt/<kebab>`, cut from the latest `origin/main`; #216/#217, enforced
by `tests/test_agents_worktree.py`) — it does NOT forbid worktrees. The hazard
below applies only when an agent ignores that rule and shares the user's
checkout: a parallel session then switches the shared clone to its own branch
and deletes yours from the local refs, without touching the fork remotes. Before relying on the working tree, check
the current branch (`git status -sb`) — if a sibling session owns the clone, do
NOT `git checkout` away from it (that displaces their work); treat the pushed
fork ref as the source of truth instead. Verify your branch by its remote commit
sha (`git ls-remote origin <branch>` <=> what you pushed), and report the
collision to the user rather than fighting for the checkout. `check-engine-params`
still works read-only on whichever branch is checked out, so use it to confirm
no legit params change is pending before you claim there is nothing to mutate.
Prefer GitHub-side operations for verification and bookkeeping — `gh run view
--log-failed`, `gh api`, `gh pr comment`, `gh issue close` all query the REMOTE
and need no checkout at all, so a sibling owning the clone never blocks you from
reading logs, posting diagnoses, or closing an issue. Do the local-file work
(e.g. an `agent-wiki/` note) on your own branch only when the clone is free, or
defer it.

## Resuming an in-flight worktree: the PR and tasks.md are the source of truth

When a session picks up a branch that already has commits, do not re-derive the
plan from the diff. The open PR body and `openspec/changes/<name>/tasks.md` are
the authoritative statement of scope and what is done vs pending. Resume order:
`git worktree list` to find the branch's path, `git status -sb` to confirm the
branch and that it is clean, `gh pr list --head <branch>` to find the open PR,
`gh pr checks <n>` for the live CI state, then read `tasks.md` (all boxes ticked
= the change is complete and only CI/merge remains). A clean tree with a
mergeable PR and all checks green means the deliverable is the reviewable PR —
do not invent new work; report the state and stop.

## Verifying a PR against its issue: evidence on the branch, not the PR body

When asked "are we sure everything for PR <n> is done", do NOT trust the PR body
or a pasted transcript of the work. Re-check the branch files against each
acceptance bullet in the issue. For each bullet, produce concrete evidence:
`gh issue view <n> --json body` for the acceptance list, then grep the branch for
each mechanism (workflow cron line, `ALLOW_UNSKILLED` flag, make target, test
function name, fixture `generated_utc`), and `git diff --name-only main...HEAD`
to confirm scope (e.g. a sync PR must touch NO `skills/engines/**`). Confirm the
branch SHA matches the pushed fork ref (`git rev-parse HEAD` == `git ls-remote
fork <branch>`) and that `gh pr checks <n>` is all green — including the jobs
that were pending earlier, which you must re-list, not assume.

A PR that "closes #179" may not itself apply the change. A weekly-sync PR ships
the workflow + tests + fixtures but leaves the vendored `data/models.json`
stale; the actual data update happens post-merge on the next cron run (or a
manual `workflow_dispatch`), which opens a separate `chore/registry-sync` PR.
So green CI on the feature PR does NOT mean the data is current — say plainly
what the PR does vs what happens only after merge, and that new-engine skill
population is a separate issue, not this PR.

A user's report that work "has been merged" / "is done" is a CLAIM to verify against the API, not
a fact to build on — the premise is often wrong (a PR and an issue can share a number the user
calls merged). Run the checks before accepting it:

- `gh pr view <n>` resolving to `Could not resolve to a PullRequest` means `<n>` is an ISSUE, not
  a PR — you must look it up as an issue, and "merged" is then already wrong.
- Read the closing evidence: `gh issue view <n> --json closingIssuesReferences,stateReason`.
  `stateReason=COMPLETED` with an EMPTY `closingIssuesReferences` = closed BY HAND with no
  implementing PR. Its defect may still reproduce on the current tip (`gh run list --workflow
  <wf> --branch main --limit 3` — a red "0-job" run on the newest sha is the live proof). An
  issue closed with no PR reads as "done" while its defect is live — the exact trap the
  PR-must-close-its-issue rule exists to catch.
- Say the correction plainly (an issue closed by hand is not "merged"), then fix the SUBSTANCE
  the false premise pointed at — here the close-the-issue gap in AGENTS.md and its guard —
  rather than routing around the untrue claim.

## registry-sync red: tests that pin the engine ORDER, not the engine id

A `registry-sync` run that fails its own `test-unit` gate and then skips opening
the sync PR is almost never bad data. The usual cause is a test that addressed an
engine by its POSITION in the offer row. `rank_engines` sorts same-backend engines
by measured t/s (`(rank, -tps, -engagement, id)`), and the engine order is
vendored UPSTREAM data — so a new/updated upstream measurement shifts the order
with no llgenie code change. Measured 2026-10-13: upstream added a TensorFold
measurement on a **DGX Spark** (an NVIDIA/CUDA box, 67 t/s), pushing TensorFold
above llama.cpp (33.7 t/s) for `qwen3.8-flash-next-125b`; `engines[1]` and the
interactive choice `"2"` silently became TensorFold, and two tests in
`tests/test_strata_download.py` went red (`2 failed, 4220 passed`).

- Fix shape: select engines by **id** (`by_id = {e["id"]: e for e in row["engines"]}`),
  and derive an interactive engine's 1-based position from the same `offer()` the
  PTY is driven with — never a hardcoded index/number. `["engines"][0]` meaning
  "the top-ranked engine" is fine; `["engines"][1] == "<named engine>"` is the bug.
- Prove it is a real guard, not a loosened test: run the UNFIXED tests against the
  new registry and confirm they fail exactly as CI did, then the fixed ones pass
  on BOTH the old and new registry (`llgenie/test:latest`, `docker run -v $PWD:/repo:ro`).
  Regenerate the artifacts the sync job regenerates first: `make sync-registry`,
  `make sync-quant-catalog`, `make render-trend-list-matrix`.

## A validation gate that checks a FIXTURE (not the artifact it gates) is not a gate

A `make` target whose inputs default to a fixture in the Makefile validates only that fixture when a
workflow calls it with no overrides. Measured on the registry-sync job: the validation step ran bare
`make skills-validate`, so it checked `tests/fixtures/trending-models.json` (16 engines) while `ci-unit`
validates the real artifact (`Makefile`: `skills-validate REGISTRY=data/models.json
UNSUPPORTED=data/unsupported-engines.json`, 24 engines) — the job's own gate passed while the registry
it was about to push fails the identical check in CI. Two-part trap: `REGISTRY=data/models.json`
WITHOUT `UNSUPPORTED` errors on every engine already recorded in `data/unsupported-engines.json`, so the
earlier form died there and never pushed. Mechanics: PyYAML/plain Python silently accept the fixture
default; only a real run against the real artifact shows the divergence.

- Fix shape: pin the workflow's step to the SAME args `ci-unit` uses, and add a test that reads the
  workflow's step AND the `ci-unit` line out of the Makefile and asserts the two scopes match — so \"which
  data does this gate validate\" cannot drift again. Prove it with rule-6c: swap in the pre-fix workflow
  step and show the test fails.
- Check every `make <gate>` inside a workflow against the Makefile default for its inputs; a gate that
  checks different data than the pipeline it guards produces is the failure shape — report its real
  scope, not the bare target name, in the issue body.

## Removing CI jobs: stale branch-protection checks + tests that hardcode the old shape

When you delete a CI job (or a whole pipeline stage), two things bite that are NOT in the workflow file:

- **Branch protection keeps the dead job as a required check.** GitHub shows it as
  "Expected — Waiting for status to be reported" forever, because the job no longer
  exists to report. This is a repo-settings change, not a code change: an admin must
  remove the dead check from `main`'s required-status-checks list (Settings → Branches,
  or `gh api -X PUT .../branches/main/protection/required_status_checks`). The agent's
  collaborator token gets a 404 reading/writing branch protection on the upstream, so
  it cannot do this — hand the exact command to the user and say it needs admin.
- **Tests that hardcode the old structure fail.** Grep the test tree for the removed
  symbol before pushing: a test asserting the pipeline job count (`len(linux) == 10`)
  breaks when you drop 3 jobs, and a test that slices the Makefile up to a removed
  section marker (`text.index("\n# ---- watch-loop")`) raises `ValueError: substring
  not found`. Update those assertions to the new count / the new following section in
  the SAME commit, or CI goes red on a shard you did not run.

## Cross-PR merge-order testing: run each PR's tests on the MERGED tree

When several PRs are in flight against the same `main`, a green CI on each PR
does NOT mean the merged tree is green. Git can keep a stale copy of a region
that a later PR's test asserts is gone: e.g. PR-A edits a comment block, PR-B
(merged first) removes the flag that comment describes, and PR-B's own test
asserts that flag is gone — but when PR-A merges on top, git keeps PR-A's
context copy of the old comment, and PR-B's test fails on the merged tree even
though both PRs passed alone. The failure is a merge artifact, not a code bug.

- Build the merged tree explicitly and run each PR's test files against it:
  `git merge --no-commit <other-branch>` (or a scratch worktree), run the
  affected tests in the test image (`:ro` mount), then `git merge --abort`.
- When a merge artifact is found, record the exact resolution ("drop these two
  lines when merging") in the PR's merge note so a reviewer applies it — do not
  silently fix it in a competing PR.
- A merge-order failure reads like a code bug at the point of the failing test;
  check `git diff` of the merged region against each PR's own version before
  assuming the test is wrong.

## Run ONE helper without importing the module (import triggers side effects)

Importing `scripts/llama_serve` (or any engine script) runs module-level
setup/launch side effects — it can start a server, or even pull a docker image
(measured: `import llama_serve` kicked off a vllm image pull). When you only
need one helper (e.g. `kv_bytes_per_token`, `read_model_meta_fast`) to compute
real numbers from a model, do NOT import the module. Extract just that function
plus its transitive dependencies via `ast`, `exec` them in a fresh namespace,
and run that in the test image (which has `gguf` + `numpy`):

```python
import ast, pathlib
src = pathlib.Path("/repo/scripts/llama_serve.py").read_text()
tree = ast.parse(src)
want = {"read_model_meta_fast", "kv_bytes_per_token", "_head_dim_pair",
        "_kv_cache_layers", "_gget", "_extract_sampling_from_kv",
        "_extract_sampling_from_fields"}
chunks = []
for node in tree.body:
    if isinstance(node, ast.Assign) and all(
            isinstance(t, ast.Name) and t.id.isupper() for t in node.targets):
        chunks.append(ast.get_source_segment(src, node))  # module constants
    elif isinstance(node, ast.FunctionDef) and node.name in want:
        chunks.append(ast.get_source_segment(src, node))
ns = {"__name__": "kvmod"}
exec("import os, struct, json, sys\n" + "\n\n".join(chunks), ns)
```

- Collect module-level UPPERCASE constants too — a helper often references a
  module constant (`SAMPLING_KEYS`, `KV_QUANT`) that is not a function, and the
  exec fails with `NameError` until you include it.
- Run it in the test image with the model dir mounted read-only
  (`-v /models:/models:ro`), not on the host — the host python lacks `gguf`.
- For GGUF metadata, prefer the repo's tolerant header-only reader
  (`read_model_meta_fast`, struct-based) over `GGUFReader`: the pinned `gguf`
  package's tensor builder raises `ValueError: np.uint32(N) is not a valid
  GGMLQuantizationType` on newer ggml types, while the header-only reader
  parses any file.

For the KV-cache sizing arithmetic (8-bit = fp16/2, q4_0 = fp16/4), the
silent-fp16-fallback pitfall, and why a big window on a small card needs
streaming, see `references/kv-cache-sizing.md`.

## `make ci-install-dry-args` needs `make install` first — a 48/48 fail is environmental

The `tests/test_cli_dry_run_matrix.py` suite runs the INSTALLED command and asserts a
launcher at `<worktree>/.ci-home/bin/llgenie`. Running `make ci-install-dry-args` in a
worktree that has never had `make install` run there fails **48/48 in ~0.2s** with
`AssertionError: no installed launcher at …/.ci-home/bin/llgenie: this test runs the
INSTALLED command. Run `make install``. It fails IDENTICALLY on clean `main`, so it is
environmental, not a regression — do not chase it as a code bug. In CI the `ci-install`
job runs `make install` first in the same HOME, so the suite passes there. To reproduce
locally, run `make install` (into `.ci-home`) before the target. The other suites
(`test_rename_llgenie_serve`, `test_llgenie_serve`, `test_ci_images`, `test_detect_server`)
run fine in the test image directly.

## `make loop` gate needs host prerequisites on Arch (agents-read + install state)

The full `make loop` gate (loop-harness, the B20-equivalent) does NOT pass on a bare host — two stages need host state first, and both silently fail until provisioned:

- **`agents-read` needs `python3.12`.** Arch ships Python 3.14 only, so the stage's `test-agents-read` (which runs against `tools/` under a specific interpreter) dies. Provision user-locally with `uv` (never touch system Python): `uv python install 3.12` puts it on PATH via `~/.local/bin`. Rerun the stage and confirm `n passed`.
- **The `test` / `install` stages need a CURRENT host install.** A stale `~/bin/llgenie` (e.g. still exec'ing the pre-#251 `scripts/llama_serve.py` after the module was renamed) fails the `install` and `test` stages. Run `make install` first and confirm the launcher now execs the current module (`scripts/llgenie_serve.py`). The loop's `test` stage was #317 (it ran `tests/test_install.py` in a `--rm` container with `HOME=/root`, where install artifacts cannot exist) — fixed by asserting the host install via `make test-install-host`.

Consequence: a RED `loop297.log` on `agents-read` / `install` / `top-tier-serve` / `test` with everything else green is usually these host prerequisites, not the change under test. Prove it by repairing host state and re-running only the failing stages before chasing code. This is the sibling of the "`make ci-install-dry-args` needs `make install` first" rule above — the loop gate has the same host-install dependency.

## A new image in the publish set fails its first push: the credential can't CREATE the org package

Adding a brand-new image to `scripts/ci_images.py` (a new `IMAGES` entry) can fail the `ci-images`
job on the FIRST push of that image — the build succeeds, only the push is denied, so it reads like a
code bug in the new Dockerfile when it is a registry-permission issue. The exact verdict varies with
whom the credential belongs to and is NOT captured by any blanket "PAT creates, GITHUB_TOKEN updates"
rule — measure it. Three real verdicts:

- A GITHUB_TOKEN (installation token) pushing a package not yet registered to the repo → `denied:
  installation not allowed to Create organization package`.
- A PAT that carries `write:packages` but whose owner is an OUTSIDE COLLABORATOR on the org (their
  membership lookup 404s) → `permission_denied: create_package`. "Can push an existing image" and "can
  CREATE the package" are different rights: an outside-collaborator PAT CANNOT create an org package.
  Logging in as the org name (`${{ github.repository_owner }}`) does not fix that — it pushes under a
  username that has no create right at all.
- The default GITHUB_TOKEN of a repo whose package namespace it already serves DOES create packages:
  this repo's `test`/`openspec`/`strata` images were all created by its own workflows via GITHUB_TOKEN.

So never assume which credential can create the namespace — MEASURE it, cheaply, before anything costs
minutes. Probe the registry directly with the candidate credential: `GET /v2/<org>/<repo>/<name>/tags/list`
(200 = package exists, 404 = it does not), then get the real verdict with the cheapest write there is, an
empty blob upload `POST /v2/<org>/<repo>/<name>/blobs/uploads/` — a 403 there is the denial you will hit at
the end of the build, quoted in seconds.

- Login that provably works for an org package: the default GITHUB_TOKEN, logged in as the TRIGGERING
  ACTOR, never the org name — `echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u
  "${{ github.actor }}" --password-stdin`, the exact line `ci.yml` uses for the images that exist.
- Diagnose the failure from the failed job's log tail (`gh api .../actions/jobs/<id>/logs
  --allow-escape-sequences`, grep for `denied`) and reproduce the verdict locally with the committed
  docker config so the mechanism is proven before you touch the workflow.

## A publish ends a long job: prove the credential can push BEFORE the build

A job that builds for ten minutes and then discovers at the push that it could never be allowed to
publish burns the whole run on a foregone conclusion. Gate any long-to-a-push job with a seconds-fast
pre-flight that performs the cheapest real write — call the registry with a `:push`-scoped token and
initiate an empty blob upload (no data sent, so a refusal costs nothing and a success leaves no layer),
printing the registry's own `denied:` verdict. Put it as a make target that runs before the build step
in the workflow (and only for the workflow that does the privileged push — ordinary PR/push builds don't
need it). A workflow_dispatch publish on a fork PR is unverifiable end-to-end before merge anyway:
`gh workflow run --ref <branch>` returns `422: No ref found` for a fork-only branch, so the pre-flight +
the sibling-package provenance IS the verification until the PR merges.

## A bot job's `timeout-minutes` must fit the work it may do

A bot workflow that hands a long task to an agent and then re-runs the repo's own gates must budget its job for the WORST CASE, not a round and a half. The fix-bot's job allowed 120 minutes while its own loop can run `FIX_ROUNDS` (default 3) rounds, each round being the failing check PLUS an agent repair: `make ci-unit` is measured at 11-20 minutes on a linux runner (this repo: 4356 passed in 673 s, 4330 in 1170 s) and a repair that reads AGENTS.md, edits and re-runs the gates is 10-30 minutes, so the worst case is 3 x (20 + 30) = 150 minutes. A job killed at the cap ends the run as **CANCELLED** — which reads like an infrastructure hiccup instead of the loop's own "still failing after N attempts" verdict, and discards that round's work.

- **The job budget IS the effective limit** — check that nothing else bounds a round before trusting it: no step-level `timeout-minutes`, no `timeout` wrapping the agent call inside the loop script, and no step or wall-clock cap on the agent invocation. If all of those are absent, the job's `timeout-minutes` is the only thing that can cut a round short, so it has to fit the work.
- **Budget the job for `rounds x (check + repair)`** and write the measured arithmetic in the workflow header where a maintainer reads it, so the number is self-justifying rather than a magic constant.
- **Pin the invariant with a test that reads the loop's OWN default round count** out of the script (`re.search(r'ROUNDS="\$\{FIX_ROUNDS:-([0-9]+)\}', scripts/fix_loop.sh)`), never a copied literal — a copy drifts when the loop's default changes. Assert: every job that runs the agent allows at least an hour (and at most GitHub's 360-minute ceiling); the fix job fits `rounds x (check + repair)`; no STEP may cap below that floor (a step timeout undercuts the job silently); the decision-only jobs (guard/sweep) keep `timeout-minutes` <= 30 so they fail fast rather than hang; and the loop script contains no `timeout` of its own.
- **Falsify before committing**: temporarily set the job to a too-small budget and confirm the round test fails with the exact arithmetic, then restore. A guard that passes at every value is vacuous.
- **A follow-up PR with no issue of its own must NOT end with `closes`** — if the issues it refs close with their OWN PRs, claiming them from here is a false link. Say `Refs #a, #b` and add a short note in the body explaining why it deliberately omits the closing keyword.

## Supersede a PR's previous run with the `concurrency` key — and stop when the user says it merged

To make a push to a PR terminate that PR's previous run (the "old jobs started by the same PR must be cancelled" requirement), use the workflow-level `concurrency` key, not a script:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

- `group` = workflow + ref means each PR (and each `push` to `main`) is its own group; a new run in the same group cancels the previous one. `cancel-in-progress: true` cancels a RUNNING run too, not just a pending one.
- **Conditional cancel on `github.event_name == 'pull_request'`** so a `push` to `main` is never cancelled — a main run mid-publish to GHCR must finish. Bot workflows keep `cancel-in-progress: false` (a bot run that outlives its interval must not be killed mid-work).
- **There is NO repo-level switch.** GitHub exposes superseding only as this per-workflow key; the API can cancel a run but nothing supersedes automatically. Say so plainly when asked for a "pure setting configuration".
- **Verify live, cheaply**: force-push the PR and watch the previous run flip to `completed / cancelled` while the new one queues (`gh run list --workflow ci.yml --branch <branch> --json databaseId,status,conclusion`). That is the proof the mechanism works — put the two runs in the PR body as evidence.
- A run already in progress when the change lands is NOT retroactively cancelled; only runs superseded after the merge are. Note that leftover state.

**User preference — stop when the user says it merged.** The user merges PRs themselves and gets frustrated if you keep polling/verifying CI after they report it merged. The moment the user says "it has been merged" (or reports the merge), STOP watching runs, kill any local background test job, do one verification of the merge state if you need it, and report. Do not keep counting/checking.

## A run stuck in `queued` with `runner=(none)` on a label = no runner matches

When main's CI runs never conclude — every `linux` job `success` but the run stays
`queued` — check the macOS jobs: `gh api /repos/<o>/<r>/actions/runs/<id>/jobs` shows
`status=queued`, `labels=macos-15-intel`, `runner=` empty. Usually no runner matches the
label (offline, not registered under that label, or macOS minutes exhausted — macOS jobs
queue rather than fail at the limit), but that is NOT proof: a PR run can drain macOS
runners while a main `push` run with the same signature sits `queued`. Compare a
`pull_request` run against the stuck `push` run before concluding; report the fact set,
do not claim an unproven mechanism. It blocks every open PR (checks `pending`,
`mergeStateStatus` `BLOCKED`) and blunts a fix-bot whose dispatch keys on a run FAILING.
Do not change the gate unilaterally — scoping macOS to `push` only is the maintainer's
call. Full diagnosis: `references/bot-fleet-audit.md`.

## Verifying a newly-added provider secret is live: run the real smoke, quietly

When a secret (e.g. `NOUS_PORTAL_API_TOKEN`) is added to the repo's Actions secrets, the only proof it
is wired is a REAL call through the implementer's alias inside the agent image — not a config read.
`make hermes-smoke` does exactly that: it refuses to run without the key (`NOUS_API_KEY unset`),
ensures the agent image, then runs `hermes -z "Reply with exactly: ok"` inside it with the key passed
as `-e NOUS_API_KEY` (name only, so the value never appears on the command line).

- **Feed the key from a 0600 scratch file, not the shell history**: `f=$(mktemp ...) && chmod 600 "$f"
  && printf '%s' "$KEY" > "$f" && NOUS_API_KEY="$(cat "$f")" make hermes-smoke; rm -f "$f"`. The value
  then lives only in a file you delete, never in `ps` argv or the transcript.
- **Verify the output, not the exit code**: the smoke's real signal is that the model answered exactly
  `ok` AND that `grep -c 'sk-nous\|sk-'` on the log is 0. A key that is dead (or a call that never
  reached the provider) can still exit 0 on a fallback path — grep the log for the expected answer and
  for key-shaped strings before claiming the secret works.
- **A smoke that falls back to a local image is a finding, not a pass**: if the image for main's
  current inputs is not on GHCR (main moved the preflight script → new input hash), the smoke runs the
  stale local image and proves nothing about the published one. Say so and note that one manual
  dispatch of the publish workflow republishes it.

## Removing a phantom provider key: wiring is exact, the build guard stays broad

GitHub substitutes an **empty string** for a secret that does not exist in the repo — a workflow
reading `secrets.OPENROUTER_API_KEY` that is never defined runs with a blank value, it does NOT
fail at the point of use. So a job can run with a silently-empty provider key and look green. When
you remove a provider the repo never defines, remove it from every **wiring** site — the workflow's
`env:` block, the `-e KEY` forwards in the make recipes, the guard's `SECRET_VARS` list, and the
README secret list — because each is a live reference that forwards a value.

Do NOT narrow the **build guard** to match. A guard that REFUSES a key present in the build
environment (so a token can never be baked into a layer) is the opposite of a wiring reference: it
should match the whole `^(TYPESAFE|OPENROUTER|OPENCODE)_API_KEY=` namespace so a FUTURE provider key
is caught by the same guard. State that distinction in the spec explicitly, or a reader will read
the broad guard as a live reference to the very keys you just removed.

Prove the removal with tests that run the REAL scripts as subprocesses (no mocks): one test reads
each workflow's `env:` block and asserts no undefined secret is referenced; one runs the preflight
and asserts an unsupported provider is refused loudly; one runs the guard and asserts its variable
list matches the repo's actual secret set. Rule-6c proof: overlay the new tests on a throwaway
worktree at `origin/main` and confirm the fix-proving ones FAIL pre-fix, then pass after.

## Changing a workflow's guard/token shape turns MAIN's tests red — grep the test tree first

A CI-only failure can be `main`'s own test pinning the exact text you replaced. Measured on PR #300
("one write-level trigger guard everywhere"): the branch normalized every `curl` `204` guard to
`gh api …/permission` with `GH_TOKEN: ${{ github.token }}`, and `linux / unit` + `macos / unit` went red on
two tests that asserted the OLD mechanism — `test_engine_bump_rebase.py::TestWorkflowYaml::
test_guard_sends_the_token_variable` (`"TOKEN: ${{ secrets.GITHUB_TOKEN }}" in text`,
`'Authorization: Bearer $TOKEN' in text`) and `test_engine_bump.py::test_guard_keeps_default_token`
(`"secrets.GITHUB_TOKEN" in guard`). The GH log masks the token, so the assertion reads
`assert 'Authorization: ***' in '…'` — that `***` is the VALUE being masked, not a typo in the test.

- Before pushing a workflow-mechanism change, grep the test tree for the mechanism you are removing
  (`grep -rn 'secrets.GITHUB_TOKEN\|Authorization' tests/`) and update those assertions to the NEW
  property in the same commit. The intent usually survives the mechanism: "the guard uses the DEFAULT token,
  not the PAT" holds for both `secrets.GITHUB_TOKEN` and `github.token`.
- Read the assertion's STRING, not just the test name: `test_guard_keeps_default_token`'s name still fits
  the new guard, only its literal went stale.
- `gh run view <id> --log-failed --job <jobid>` prints the failing file+line; the same two tests fail
  identically on `macos / unit`, so fix once and re-run both.

## A worktree without the gitignored `.env` fails the ~20 live-lookup tests

Running `tests/test_engine_bump.py` in `llgenie/test:latest` from a fresh `git worktree` gives **23 failed**
with `SystemExit: [engine-bump] tensorfold: upstream lookup failed` (the same file is 71/71 green from the
user's main checkout). Cause: the lookup runs unauthenticated — the worktree has no gitignored `.env`
holding `GITHUB_TOKEN`/`HF_TOKEN` — and the failures are identical with a `:rw` mount, so it is not the
read-only mount. Before chasing it as a regression, run the same file from a checkout that has `.env`; CI has
the token and shows only the real failures. State the environmental failures as such instead of "fixing" them.

## The test suite is discovered, never enumerated — keep the roster the ONE place a file is named

`make test-unit` no longer lists its test files: `scripts/unit_tests.py`
**discovers** every `tests/test_*.py` minus the dated, issue-carrying
exclusions in `tests/fixtures/unit-suite.json`. A new `tests/test_*.py` is in
the gate the moment it exists — there is no line to edit, so two PRs adding
unrelated tests no longer conflict. The fast loop subset (`make test`, the
stage-6 "full fast suite") follows the same doctrine: its six files live in the
roster as the named group `groups.fast`, and the recipe runs
`python scripts/unit_tests.py run --group fast` naming **no test file at all**.
So a target that runs a *subset* of the suite does not name its files either —
the subset is a named group in the roster, validated like any other roster
decision (a group whose file is gone/excluded/repeated, an empty list, a
missing reason/issue/date, or an unknown group a recipe asks for is all fatal).
The wiring guard (`make check-wiring`) reads the `--group` argument from a
recipe and attributes exactly that group's files to the target. Never add a
hand-written multi-file pytest line to a make target; extend the roster instead.
New unit-suite behaviour is locked in `tests/test_unit_suite.py`, not in a
per-file list.

## Every command a CI workflow runs must be a make target

Standing rule (user-mandated): a workflow's `run:` step must call a `make`
target, never `python3 scripts/…` or `scripts/*.sh` directly. The make target is
what makes the command reusable locally AND by the pipeline, and it is what the
wiring guard (`make check-wiring`) can see. Only `gh`/`git` orchestration that
carries no repo logic (guard checks, PR resolution, commit/push, comment) stays
inline. When a workflow needs a script, give it a make target first
(`fix-bot-sweep`, `fix-bot-report`, `agent-image-ref`, `fix-loop-image`) and
call that. Encode the rule in AGENTS.md too, so a future agent does not regress
it. When you move a `docker run`/script call into a make target, the run-time
secrets (`-e NOUS_API_KEY`, `-e GH_TOKEN`) move with it into the recipe — update
any test that asserted the old inline shape to assert the make target and the
recipe's env instead.

## A privileged image publish gets its own guarded workflow

A container that is the toolchain other bots trust (e.g. the Hermes agent image)
should NOT be published on every PR/push like the test/openspec images. Give it
a dedicated `workflow_dispatch`-only workflow with defense in depth: (1)
`workflow_dispatch` is already gated to write-access users by GitHub itself; (2)
a `guard` job re-checks the actor + triggering actor is the owner or a
collaborator with write/maintain/admin BEFORE any secret is read (same shape as
the bot workflows); (3) the GHCR `docker login` uses the default GITHUB_TOKEN
logged in as the triggering actor, not the org name — the credential that
creates org packages for this repo (see the "credential can't CREATE the org
package" section below; an outside-collaborator PAT is refused). The image is hash-tagged, so re-running
the job is a no-op unless its inputs changed. Add a dedicated make target
(`publish-agent-image`) that publishes ONLY that image, plus `agent-image` /
`agent-image-pull` mirroring the test/openspec targets, and wire all into
`.PHONY`. To audit the trigger guards across EVERY dispatchable workflow (which shapes are
strict vs weak, step-level guards, dead guard outputs), see
`references/workflow-trigger-guards.md`.

## A rename PR must also fix main's tests that still import the old name

When a rename refactor is open and `main` lands a new test (or code) that still
imports the OLD module name, the rename's own guard test catches it — the guard
forbids any live file referencing the old name. That is a real cross-PR fix, not
a false positive: update the main-landed test to import the renamed module in
the rename PR, as a separate commit, so the rename guard passes on the merged
tree. Reconstructing the renamed module from main's version + the rename's seam
edits (keeping the old name as a shim) is the way to carry main's concurrent
changes into the renamed file.

## Rebasing when `main` gained the wiring guard: resolve the Makefile as UNIONS

When a `main` commit lands the wiring guard (or any change that adds targets /
test files) while your branch is open, the rebase conflicts in the Makefile are
NOT either/or — they are unions. Root cause of the `.PHONY` collision is a
LOST CONTINUATION on main: a `.PHONY:` line whose trailing backslash was
removed turns every name below it into a make RECIPE line of that target
during the merge, so the declarations silently stop where the backslash
dropped and everything after un-declares. Resolve the block, then verify with
`make -p` that the newly-required names are actually IN `.PHONY` (if `.PHONY`
ends at an old target, the continuation is still broken). Three regions collide and must carry BOTH
sides: the `.PHONY` continuation block (your new targets + the guard's
`check-wiring`/`wiring-report`), the `test-unit` recipe (a stable line — the
suite is DISCOVERED, so a new test file collides in the ROSTER
`tests/fixtures/unit-suite.json`, not on this recipe line; carry both your
exclusion entry and the guard's when both branches touch the same block), and
the `help:` text block (union both target
Overlapping, use context-anchored `patch` (never the whole-block string that contains
>` `>>>>>>>` marker), then `git add` and `git rebase --continue`. After clearing
markers, run `make -n help` to confirm the file still parses AND check for a
stray duplicated `.PHONY` line you may have introduced by anchoring an
overlapping edit (delete the second copy). rerere resolves a later PR's
`README` portion of the same conflict automatically — verify the merged section
exists rather than assuming it applies.

When the merged gate PR is itself a GATE with its own `ci-unit` wiring (docs gate #257, wiring guard,
dispatch-forms guard), the `ci-unit` invocation lines are ANOTHER union region: each gate PR adds its
own `$(MAKE) check-<x>` line into `ci-unit`, so the rebase must carry BOTH
(`$(MAKE) check-docs` AND `$(MAKE) check-dispatch-forms` on consecutive lines), never pick one. After
resolving, re-run EVERY gate on the merged tree — including the gate the other PR just merged
(`make check-docs` now enforces at your new head that every user-facing target you add is in the
README). A gate that passed on the other PR's branch does not prove it passes on your merged head; a
new user-facing `##` target from YOUR PR that the other PR's docs gate then demands will go red on the
merge artifact.

After the rebase completes, re-run `make check-wiring` on the new head: now that
the guard is on `main` at your base, it is the gate that decides whether your new
`scripts/*.py` and `tests/test_*.py` are CI-wired or silently host-only. Confirm
your files appear as CI-wired (the host-only list should hold only the known
Metal/native exceptions), push with `--force-with-lease`, and re-check the PR
head SHA + mergeability after GitHub propagates (a fresh force-push can briefly
turn the PR `DIRTY`/`CONFLICTING`).

## Resolving a Makefile hunk can DROP a target that was only its context

A conflict hunk reaches farther than the two lines you are resolving: the lines you
keep from `ours` are whatever the ORIGINAL target's region happened to contain. When the
other side (your branch) redefines the target by name and you take ONLY the
`frames`/recipe lines for that one target plus a hand-picked subset of what the
other side added nearby, any THIRD target that the merged `main` had both added
AND left in the same hunk silently disappears from your head — with no compile
error, the file just parses to a narrower target set. Verify by diffing the whole
target set against the base, not by eyeballing the hunks
(`set(re.findall(r"^([\w.-]+):(?!=)", open('Makefile').read(), re.M))` vs. `git show
origin/main:Makefile`, and do the same for the `tests/*.py` list). `make check-wiring`
is the backstop exactly because a workflow's `make <target>` call is a PROMISE —
the run step passing while the target is gone is the failure that guard was born
to catch; run it after every Makefile resolution and read its verdict, do not
wait for a job to turn red.

## After a union rebase, re-run the tests: the resolver can duplicate a stanza

A union resolution that lands conflict-free is not proof the tree is correct. It can leave a test
function holding BOTH the stale assertion and the current one, so the test fails on the stale line
first and can never reach the pass. Measured: a bot dispatch-form rebase duplicated a workflow test
stanza that asserted the cron `17 5 * * *`; the slot allocation had remapped the minute to its own
slot, and the function failed on the old assertion while a sibling assertion held the new value.
Before pushing, grep the merged tree for the OLD value: `grep -rn '17 5 \* \* \*' tests/ .github/`.
A hit that is a live assertion (not a deliberate "old value must be gone" check) is a stale
leftover from the resolution — delete the duplicate stanza, do not try to satisfy both.

- **Re-run the AFFECTED test file locally after the rebase**, even when CI only shows a generic
  `unit` failure — the real red is often a stale artifact in your OWN branch (a pre-rename module
  name, a mangled gate invocation, a pinned test literal), not the change you intended. The failed
  job's log (`gh run view <id> --log-failed | grep -E "FAILED|AssertionError|E   "`) names it in
  seconds.
- **Assert the property, not a pinned value a schedule or rank owns.** A test that hardcodes a
  concrete minute (a cron slot) or an engine's position in a vendored order goes stale the moment
  the ownership changes, and the merge cannot see it. Assert what the property actually is — the
  workflow is scheduled, its cron is DAILY, every bot owns a unique slot, the old shared value is
  gone — not the current literal. Where "gone" is the assertion, name WHY in the message
  ("every bot owns its own slot") so it reads as deliberate and not itself stale.

## Testing a bot that shells out to `gh`: a fake `gh` on PATH, no mocks

The no-mock way to test a dispatcher/bot script whose only external dependency
is the GitHub CLI is a fake `gh` on PATH that records its argv and answers the
exact queries the product builds (same shape as `tests/test_ci_images.py` for
`docker` and `tests/test_engine_skill_gap.py` for `issue list`/`create`). Write
a `gh` script to a temp dir that appends `json.dumps(sys.argv[1:])` per line to
a log, branches on `args[:2]` to print canned JSON, then assert the CALLED argv
(`--repo`, `--author`, `--created ">=<date> 00:00Z"`) not a digest. This proves
the product builds the right request without mocking the product code.

Pitfall when generating that fake script with an f-string: do NOT interpolate
the response value as a bare expression on the RHS of a `print()` inside the
template — you'll hit one of two silent failures. (1) `{json.dumps(label)}` in
plain Python source is a SET literal containing one string, so `print(that)
sets` prints Python repr single-quotes and the caller's `json.loads` fails with
`Expecting property name enclosed in double quotes`. (2) An f-string expression
that names a variable only defined INSIDE the generated script (`lab`)
references the OUTER scope's name, which doesn't exist → `NameError` inside the
fake gh, which the product surfaces as a `gh` rc-1 failure that looks like a
product bug. Fix: hoist the canned responses to module-level constants in the
fake script (`PRS = [...]; LABELED = [...]; VIEW = {...}` via `json.dumps`),
and only the dispatch BRANCH (which reads argv and so must be written literally)
stays as normal Python. Assert a second run cannot double-claim and that
`pr merge` is never in the recorded argv.

## Host `pytest` on an isolated test file: `--noconftest` beats a repo conftest

`tests/conftest.py` imports `scripts.llama_serve`, so running ANY test under the
repo rootdir with host `pytest` loads that import and its side effects. Running a
new self-contained test file (no conftest fixtures) may therefore exit 2 with
ZERO output — a silent failure that looks like a crash. Diagnose by copying the
file to /tmp and running pytest there (rootdir changes, conftest not loaded) to
get the real error, and run the isolated file with `--noconftest` to skip the
repo conftest entirely. This is for iterating on a self-contained unit test
only; a test that needs conftest fixtures (or the engine image) still runs in
`llgenie/test:latest` via `docker run -v "$PWD":/repo:ro`.

## Verification order for a change here

1. Run the affected tests in the test image (`docker run` above with `:ro`).
2. `make openspec-validate NAME=<change>` — validate must exit 0.
3. Tick every `tasks.md` box, then commit one Conventional Commit and push,
   updating any open PR for the branch.

The OpenSpec check is a gate on UNCHECKED boxes: `openspec-tasks-check` fails
(red `ci-openspec`) as long as ANY task line is `- [ ]`, including the final
\"CI green\" verification box that can only be true after the run passes. That
is a closed loop — tick the last box in the SAME commit as the fixes you expect
to make CI green, or the openspec gate keeps the whole run red no matter what
`ci-unit` does.

Word each gate box to say EXACTLY what you verified, never a fuller claim. A box that says
`make loop passes` is a lie when you only ran the hermetic subset (`test-unit`, `lint`,
`check-wiring`, `check-docs`, `openspec-validate`) and left `test-health`/`test-install` to CI.
Write the box as "`make test-unit` passes (N passed; the M failures are HF 429 network flakes in
<file>, unrelated)" and a separate box naming the stages that run in CI on this branch. A reviewer
reads the ticked box as evidence; a false claim is worse than an unticked one.

## A closing keyword in PROSE links the issue too — check `closingIssuesReferences`

GitHub parses a closing keyword (`close`/`closes`/`closed`/`fix`/`fixes`/`fixed`/`resolve`/…) followed by
an issue reference ANYWHERE in a PR body or commit message — including past-tense prose that is not a
closing intent. Measured on PR #332: the body opened with "#306 — filed by #300, the change that **closed
#295** and normalized the eleven trigger guards", and
`gh pr view 332 --json closingIssuesReferences` returned **`[295, 306]`** — the PR claimed to close an
already-complete issue it merely referenced as history.

- **Read the reference list back, do not assume your `closes #N` is the only one**: `gh pr view <n> --json
  closingIssuesReferences --jq '[.closingIssuesReferences[].number]'` should name exactly the issues you
  intend. Re-check it AFTER any body edit.
- **Phrase history without a closing verb adjacent to the number.** "the PR that merged #295" /
  "for #295 (already complete)" is safe; "the change that closed #295" is not. Same in the commit message.
- Harmless only by luck: GitHub will not RE-close a `CLOSED` issue, so the false link usually costs
  nothing — but on an OPEN referenced issue it silently closes it when the PR merges. Verify, then fix
  the prose and re-read.
- A merged PR's body can no longer be corrected into its own commit history; fix the link while the PR is
  still open.

## The issue body is part of the change, not a log of it

When the implemented wiring ends up different from the issue's original
acceptance wording (the gate moved into a make recipe, a macOS exemption was
added, the test set grew), EDIT the issue body in place — add a concise
"Wiring as implemented" section naming the actual mechanism and the test files
— so issue, OpenSpec change and code agree. A reviewer reads the issue, so it
must describe what the code actually does, never the plan you started with.
Verify with a read-back (`gh issue view <n> --json body` and grep for the new
section heading).

## Auditing open issues against latest main: verify the claim in the code, not the issue

When asked to review the open issues that have no implementing PR and decide whether each still makes sense:

- **Fetch latest main first** (`git fetch origin main`), then verify each issue's claim against the ACTUAL code at `origin/main` — never against the issue's own cited line numbers or its "hardcoded"/"missing" claims, both of which go stale as main moves. `git show origin/main:<file>` + grep for the exact symbol/flag the issue names. A flag is only "missing" if the symbol has zero hits in the current file.
- **Reproduce ranking/ordering claims live**: for an issue about which engine wins, run the real `rank_engines` against the vendored registry for the exact model + arch and print the ordered list. A symptom that still reproduces is the strongest "still valid" evidence; record it in a dated verification comment rather than editing the body.
- **Verdict discipline**: "close the obsolete ones" does not mean close aggressively. Close only what is genuinely obsolete; most issues are still live and only their framing drifted. Refine the stale ones, leave the valid ones untouched, and say plainly in the report that nothing was closed and why.
- **Refine by prepending, not replacing**: add a dated `## Status YYYY-MM-DD — verified against main@<sha>` block at the top of the body stating what landed and what is still open, and keep the original body below as history (it carries the evidence). Use `gh issue edit <n> --body-file <file>` with the new body written to a scratch file first — avoids shell-quoting hell.
- **Verify the write landed**: `gh issue edit` returns a URL, not confirmation. Read back the body's first line (`gh api repos/<o>/<r>/issues/<n> --jq .body`) and confirm it is the status block.
- **Drift found during the audit is a new issue, not a silent fix**: per AGENTS.md, analysis surfaces gaps → file an issue, never implement. When the drift is a prose claim (e.g. a README sentence about CI triggers) that a mechanical gate cannot catch, say so in the issue — the gate's scope is part of the finding.

Pitfall that produces a false "not implemented" verdict: **`git show` of a large file through the terminal tool returns truncated head/tail output**, so `src.find("def build_command")` returns -1 and every grep silently reports nothing — which would wrongly close a live issue. Write the file to scratch first (`git show <ref>:<path> > $SCRATCH/file.py`), then read it in Python and grep the full text.

## Filing a rename refactor: analyze the name's meanings before the issue

When asked to rename a confusing symbol/file/module, the issue must carry the
measured evidence and a decision table, not a bare request. Disentangle the
name's distinct referents (the tool's own CLI vs an upstream binary vs the
tool's seams wearing the upstream's name), measure scope with grep (excluding
`.git`/`__pycache__`), find the prior rename that deliberately stopped at the
file, and separate what must NOT be renamed (upstream names + masquerading
shims). Full workflow: `references/rename-refactor-analysis.md`.

## A CI job failing with Hub 429 / 5xx is usually the rate window, not auth

When a llgenie CI job dies on `HTTP Error 429` / `HF API still failing`, first check
that `HF_TOKEN` is actually wired into that job's `docker run` (`-e HF_TOKEN`, and the
call routes through `scripts/hf_auth.py:authorize()`) — but a missing token is the odd
diagnosis. The token is a ~1000-req/5-min quota, and every llgenie CI run fetches Hub
cold because the test container's cache (`HOME=/root`) and `.ci-home` are throwaway.
A cold job that lists many models x formats can burn the whole window in one run. The
fix is volume (persist `HUB_CACHE_TTL`) plus the shared 429 wait, not longer retries.
Full diagnostic sequence: `references/hub-rate-limit-ci.md`.

## OpenSpec change dirs are root-owned after `make openspec-new`

The OpenSpec CLI runs in a container as root, so `openspec/changes/<name>/` is created
owned by root and `write_file`/`patch` into it fail with `Permission denied`. After
`make openspec-new NAME=<name>`, chown it back before writing proposal.md /
`specs` / `tasks.md`. `sudo chown -R $(id -u):$(id -g) openspec/changes/<name>`
works only when sudo is non-interactive; when it is NOT (no TTY — "a terminal is
required to read the password"), do it through the image instead, which needs no
sudo:

```bash
docker run --rm -v "$PWD":/repo -w /repo llgenie/openspec:latest \
  chown -R $(id -u):$(id -g) openspec/changes/<name>
```

The `make openspec-validate` container re-runs as root and does not need the
chown, but the agent's file tools (write_file/patch) do.

The same root-owned-files trap bites worktree cleanup: `git worktree remove`
fails on the `__pycache__` the test image leaves behind. See
`references/worktree-cleanup-root-owned.md`.

## PR message substance: write Issue / Fix / Benefit before the guard catches you

The user's standing rule for llgenie PRs: a commit message and a PR body must state the
general purpose — WHAT the issue was, HOW the change solves it, and the BENEFIT — not
just a subject. It is enforced by `make check-pr-hygiene` (wired into `ci-unit`), but
write it right the FIRST time rather than let the guard trip the PR red:

- Subject stays a typed Conventional Commit (`feat:`/`fix:`/`ci:`/`docs:` …).
- Body: **Issue** (with `#N`), **Fix**, **Benefit**, then a **Technical** extension naming
  the files, make targets, tests and gates touched plus any measured numbers.
- Placeholders (`""`, `-`, `wip`, `update`, `fix`) are violations, as are subject-only
  commits with no body and a PR created with no or a placeholder `--body`.
- `make pr-hygiene-report` shows the guard's scope so you know exactly who it scans
  (workflow `run:` steps, the Makefile, shell invocations, and the argv list the repo's
  own `_gh` producer builds). Commit the message and PR body with the SAME three-part
  shape you are enforcing — dogfood it.

## A bot's APPROVED review is not a human approval — never merge

The durable rule wins when AGENTS.md contradicts itself (it does, here): the
"Git workflow" section says the agent NEVER merges and stops at the reviewable PR,
while the "PR review comments" section says an approved PR gets merged. A PR whose
`reviewDecision` flips to `APPROVED` may have been approved by the repo's OWN
automation agent (`asimov-agent`), not by the human maintainer. When that happens do
not click merge (no squash/rebase/auto-merge/admin), even if a section of AGENTS.md
reads like a green light — merge stays the human's action. Report the approval, name
the contradiction, and stop. Check WHO approved before treating green as done:
`gh pr view <n> --repo <r> --json reviews --jq '[.reviews[] | {author: .author.login, state}]'`.

## A red "0-job" run whose name is the workflow's FILE PATH is a startup failure, not your PR

When monitoring "is main green" or a PR's checks, a run with `status=completed,
conclusion=failure`, **zero jobs**, `gh run view --log-failed` → `log not found`, and a
`name` equal to the workflow file PATH (not its `name:`) is GitHub failing to start/parse
the workflow at that ref — a startup failure, never a code failure in anything you own.
The trigger is NOT push-specific: any commit that EDITS a workflow file spawns such a
no-op run for that workflow, under an event the workflow does not subscribe to. Measured
under both `push` to `main` and `pull_request` on a PR branch (a PR that touched six
workflow files produced a 0-job run per edited workflow, `event=pull_request`, even
though none of them declares a `pull_request:` trigger). The repo's ruleset is not the
cause — a `main` ruleset carrying only `deletion`/`non_fast_forward` still produced them.

- Distinguish it from a real failure by the signature: `gh run view <id> --json
  name,jobs --jq '{name, n: (.jobs|length)}'` — name == path AND 0 jobs = startup
  failure. A run with real jobs is a real failure.
- Don't chase it as a regression or spend a merge window on it. It pollutes
  `gh run list --branch main` and any "is main green" dashboard — if you file it,
  state the trigger correlation (a commit that edits a workflow file) and that the
  mechanism is that the workflow's `on:` has no matching trigger, not that the
  pipeline broke. Do NOT claim a cause you have not proven — report the fact set
  (event, head_branch, head_sha, 0 jobs) and the correlation, and stop there.

- **Proven root cause when the offending line is inside a `run:` block**: a `#` line
  inside a `run: |` block scalar is SCRIPT TEXT, not a YAML comment — so a literal
  `${{ ... }}` in it is parsed as an expression, and GitHub refuses the whole file
  when that expression does not parse. `yaml.safe_load` accepts it (PyYAML has no
  notion of `${{ }}`), which is exactly why review misses it. The file's own
  scheduled runs still succeed (the parser only rejects the refs that edit the file),
  so "the file is valid, its schedule runs" is NOT evidence the file is accepted.
- **Guard the class, not the one file.** `make check-workflows` opens every workflow
  file and fails on `bad-expression` (an expression that does not parse — the class
  that shipped), `unterminated` (`${{` with no `}}`), `duplicate-key` (GitHub refuses
  it; PyYAML keeps the last), and `missing-name` (no top-level `name:` — what makes a
  0-job run present itself as a path). The expression rule must be a TOKENISER over
  GitHub's expression grammar, not a `${{` grep, so a real expression inside a `run:`
  block still passes. Wire it into `ci-unit` and prove it with rule-6c: the new tests
  FAIL on a pre-fix worktree at `origin/main` and pass on the fixed tree.
