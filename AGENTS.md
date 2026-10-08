# Project Instructions for Hermes Agent in llgenie

MUST: follow this file over habit and memory.
NEVER: skip these rules to be “helpful.”
If unsure, ask before acting.

You are working in a small, self-contained repository that serves GGUF models
locally via llama.cpp's `llama-server`. This file defines the agent's durable
workflow. Follow it for any change.

## Execution environment

- **Foreground `terminal` calls run on the real host** (`~/repository/git/llgenie`).
  This is a plain macOS host with `node`/`npm`, `nerdctl` (Colima containerd),
  a gguf Python 3.10 venv at `~/llama-gguf-tools/.venv`, and a populated
  `~/models/**/*.gguf` tree. There is no separate sandbox — the host is canonical.
- Verify through the Makefile with real output. Prefer `make <target>` over
  hand-running the underlying tools so the defined gates are exercised.

## OpenSpec is the checklist of record (MANDATORY)

Before implementing/answering a work request, convert it into an OpenSpec change
in this repo and drive it with the Dockerized CLI:

```bash
make openspec-new NAME=<kebab-name>        # openspec new change <name> via the container
# write proposal.md[/design.md] + specs/<cap>/spec.md + tasks.md
make openspec-validate NAME=<kebab-name>   # must pass before you claim done
```

Rules:

- **OpenSpec change + tasks FIRST, then implementation.** For every change,
  create the OpenSpec change (`make openspec-new NAME=<name>`) and write
  `proposal.md` + `specs/<cap>/spec.md` + `tasks.md` BEFORE implementing any code
  and BEFORE creating the feature branch or opening the PR. This keeps every
  change spec-tracked from its start (review-required discipline).
- **Create/validate through the CLI, never by hand-writing the change dir.**
  The CLI runs inside the `openspec/` container with the repo mounted at `/repo`
  (RUNTIME auto-detected: nerdctl → docker). `openspec/` Dockerfile +
  `docker-compose-files/openspec.yaml` define it; `make openspec-image` builds it.
- **Every implemented step maps to a task.** Keep `openspec/changes/<name>/tasks.md`
  as a tracked `- [ ]` checklist. **Tick each task the moment the work is verified** —
  never complete work while leaving the checklist item unticked.
- **Validate before declaring done:** `make openspec-validate NAME=<name>` must exit 0.
- **A change is "done" only after the loop gate is green** (see below). The final
  task in `tasks.md` MUST be a verification you can tick the moment the work is
  done — never a command like "run make phase7-archive" (which doesn't exist here)
  and never the loop command itself.
- **All changes MUST be committed and pushed to the current feature branch.** Do
  NOT wait for a human to ask. Commit each batch of completed work with a typed
  Conventional Commit message and push it to `origin feat/<branch>` as you go, so
  work never sits uncommitted. Never force-push / rewrite history, never commit
  `.env` or real secrets, and never push directly to `main`.
- **Every work item's GOAL lives in the GitHub issue; the issue drives the whole
  lifecycle (MANDATORY).** Each work item starts as a GitHub issue (the *issue
  file*). The issue's goal, the feature branch, the OpenSpec change, and the PR
  that closes it are one pipeline — the issue is the root, and every downstream
  artifact must trace back to it and describe the SAME objective:
  - **Issue → feature branch → OpenSpec change → code → PR.** Creating an issue
    means a feature branch will be created off `main` for it, that branch carries
    the OpenSpec change (created first) + the implementation, and the work ends
    by opening the PR against `main` from that branch. The PR body MUST reference
    the issue so the issue and PR are linked.
  - **Sync-back is bidirectional and continuous — even when BOTH an issue and a
    PR already exist.** If you change the OpenSpec change (`proposal.md`,
    `specs/**/spec.md`, `tasks.md`), you MUST update the issue body AND the code /
    files accordingly so the implementation reflects the OpenSpec change — and
    vice-versa. The OpenSpec change is the checklist of record and the driver of
    the code; the issue is what a reviewer reads to understand the PR. They must
    NEVER contradict each other. Any change to one MUST be mirrored in the others
    in the same commit batch:
    - change **goal** (scope/objective/acceptance, the `Why`/`What Changes` of
      the proposal) → update the issue body AND the OpenSpec change AND the code
      it implies, together;
    - change **code** (implementation) → make sure it matches the OpenSpec spec
      and is reflected in the issue;
    - change **OpenSpec** (proposal/spec/tasks) → update the issue and, where the
      spec implies a code change, the code.
  - Treat any drift between the issue, the OpenSpec change, and the code/files as
    a workflow defect. The OpenSpec change is the referee: if there is a conflict,
    the code and the issue must conform to the OpenSpec change, not the reverse.
  - **Alignment is a checked step, not an assumption (do it at every "done" claim).**
    Before reporting an issue/PR as ready (and before `make loop` finalization),
    *actively verify* the three artifacts agree: read the current issue body and diff
    the key claims (goal, interface, requirements, acceptance) against
    `proposal.md`/`spec.md`/`tasks.md`. Flag and fix any contradiction — do not assert
    "aligned" without running the check. This applies to naming, requirements
    (ADDED/MODIFIED/REM), constants/logic terms (e.g. dynamic-vs-hardcoded), and
    acceptance wording.
  - When starting/resuming work, if the issue's goal and the OpenSpec change are
    out of sync, reconcile them FIRST (update whichever is behind to match the
    intended goal) before implementing.
  - If a work request arrives without an issue (e.g. ad-hoc chat), create the
    GitHub issue as part of converting it into an OpenSpec change and a feature
    branch, so every OpenSpec change and PR trace to a GitHub issue that mirrors
    the goal.

## Git workflow — feature branch + PR (MANDATORY)

Every piece of work (bug fix, feature, tooling, docs) MUST be developed on a
**dedicated feature branch** off `main`, never directly on `main`. Work is only
merged into `main` through a **pull request**. This matches the remote's branch
protection (direct pushes to `main` are not allowed for new work).

**ALWAYS SYNC TO LATEST `main` — EVERY time, before and during any work (MANDATORY, unconditional).** This is NOT optional and NOT "on resume only" — it runs at the START of every session AND before you create/resume a feature branch AND immediately before you push/PR:

```bash
git fetch --all --prune
git fetch origin main
git merge-base --is-ancestor origin/main HEAD 2>/dev/null \
  || git rebase origin/main        # if not already at/after main, rebase onto it
# if rebase fails on conflicts: resolve them yourself (edit the conflicted files,
# git add, git rebase --continue) — resolving conflicts on the branch is YOUR job,
# not something to hand back.
```

- **NO git worktrees (MANDATORY).** Never run `git worktree add` and never work in
  `../llgenie-wt/` or any other second checkout. All work happens in the ONE clone
  (`/home/asimov/repository/git/llgenie` on Linux, `/Users/andy/repository/git/llgenie`
  on macOS) with the feature branch checked out there. A worktree splits the state
  (uncommitted changes, built images, `.ci-home`, the user's own checkout) across
  two directories, so the user cannot see or test what was changed.
- **Before creating a feature branch**, FIRST pull the latest main so the branch is cut from the newest tip:
  ```bash
  cd /home/asimov/repository/git/llgenie && git fetch origin main
  git switch -c feat/<kebab> origin/main
  ```
- **Before resuming an existing feature branch**, check it out in the same clone and refresh it against the latest remote main BEFORE touching any code — never start from a stale tip:
  ```bash
  cd /home/asimov/repository/git/llgenie && git switch feat/<kebab> && git fetch origin main \
    && { git merge-base --is-ancestor origin/main HEAD 2>/dev/null || git rebase origin/main; }
  ```
- **Right before you push / open a PR**, re-run the fetch+rebase above ONE final time so the PR is never behind.

- **Why:** `main` moves whenever another PR merges. A branch that falls behind
  `main` will be rejected at the merge gate (issue #9: never merge a PR that is
  behind main) and blocks itself on later work. Rebase (replay your commits on
  the new tip) rather than `merge` when you can, so history stays linear and the
  diff stays minimal; resolving merge conflicts from a rebase on your OWN branch
  is your responsibility.
- **Force-push is allowed ONLY on your own unpublished/PR feature branch** after
  a rebase you just performed — never force-push a shared branch or `main`, and
  never force-push to rewrite another commit's history. After rebasing a
  branch that already has an open PR, `git push --force-with-lease` is the
  correct way to update it.
- **Squashing your own PR branch before review is allowed (when the user asks).**
  While the PR has no approving review yet and every commit on the branch is your
  own, you may squash the branch into ONE Conventional Commit that references the
  issue (`git reset --soft origin/main && git commit`, after the fetch+rebase above)
  and update the PR with `git push --force-with-lease origin feat/<name>`. Once a
  reviewer has engaged, review fixes go on top as normal commits again (see "PR
  review comments"); never squash `main` or a branch someone else pushed to.

1. **Before starting, branch off the latest `main`:**
   ```bash
   git checkout main && git pull origin main
   git checkout -b feat/<kebab-name>     # one branch per change/PR
   ```
2. **Do the work on that branch** — create/update the OpenSpec change, write
   `proposal.md` + `specs/<cap>/spec.md` + `tasks.md`, implement the code, and
   tick each task as it's verified.
3. **Run the loop gate** (`make loop`) — it must be GREEN, and
   `make openspec-validate NAME=<name>` must pass, and every task in
   `tasks.md` must be ticked (`- [ ]` → `- [x]`), before the branch is ready.
4. **When all tasks are completed AND verified**, push the branch to the **fork**
   (`origin`) and open a PR against the **UPSTREAM** (`asimov-agent/llgenie`):
   ```bash
   git push -u origin feat/<kebab-name>
   # PR must ALWAYS target the upstream main, from the fork's branch:
   gh pr create \
       --repo asimov-agent/llgenie \
       --base main \
       --head andyholst:feat/<kebab-name> \
       --title "feat: <kebab-name>" \
       --body "Completes OpenSpec change <name>.<br>Issue: [#84](https://github.com/asimov-agent/llgenie/issues/84)<br>Loop gate GREEN, openspec validate passes, all tasks ticked."
   ```
   **Rules (MANDATORY, every single PR):**
   - The **base** repo is ALWAYS `asimov-agent/llgenie` (the upstream/mainstream).
   - The **head** repo is `andyholst/llgenie` (the fork). Use `andyholst:feat/<name>`
     (not just `feat/<name>`) so `--repo asimov-agent/llgenie` finds the branch.
   - Push the branch to `origin` (the fork) with `git push -u origin feat/<name>`.
   - NEVER create a PR against `andyholst/llgenie` (the fork). The PR always goes
     to the upstream.
   - NEVER push directly to `main` on either repo.
6. Keep each PR to one change/OpenSpec change. Rebase or merge `main` in when the
   PR goes stale; never force-push shared branches.
7. **Merging needs an approval — the agent NEVER merges (MANDATORY, durable).**
   - A PR is merged into `main` only after a human reviewer has **approved** it
     (`gh pr view <n> --json reviewDecision` == `APPROVED`). Green CI alone is not
     enough.
   - The agent never runs `gh pr merge` (no squash, no rebase, no merge commit,
     no `--admin`, no auto-merge) and never pushes to `main`. When the work is done
     it pushes the branch, updates the PR body, requests review, and **stops**,
     reporting the PR URL and what it waits for.
   - "Push to mainstream" means: the PR targets `asimov-agent/llgenie:main` and is
     ready for review. The merge itself is the reviewer's action.
   - Images reach GHCR only through that path: after the approved PR is merged,
     the CI run on `main` builds, tests and then pushes each engine image.
   - Even when asked to "merge", "ship" or "push to main", the agent stops at the
     open, reviewable PR and says it is waiting for an approval.

## PR review comments — check them and reply yourself (MANDATORY, durable)

When a feature branch has an OPEN PR, review commentary is a first-class source
of work. You MUST proactively read every comment/review thread on the PR for the
current branch, act on each one, and reply to it — WITHOUT waiting for the human
to paste the comment into chat.

1. **Check the PR for the current branch at the START of the session.** When work
   begins (or resumes) on a branch with an open PR, read its comments and review
   threads first:
   ```bash
   gh pr list --head <current-branch>            # find the PR number
   gh pr view <N> --json reviews,comments        # PR-level comments + review summaries
   # all inline (diff) review threads + any replies:
   _auth="Authorization: Bearer ${GITHUB_TOKEN}"
   curl -s -H "$_auth" \
     "https://api.github.com/repos/<owner>/<repo>/pulls/<N>/comments" | python3 -m json.tool
   ```
   Review threads live in the **pull-request comments endpoint** (inline
   `diff_hunk` comments), not just PR-level comments — check BOTH.

2. **Every comment is a work item.** Treat each review thread as an obligation:
   - Reproduce/verify what the comment flags (run the relevant `make` gate). The
     comment may be a genuine defect even when the CI stage is green — e.g. a
     lint that silently skips a file (an extension-less `Dockerfile`) and thus
     never turns red. Find the root cause, don't dismiss it.
   - Fix the root cause, add a regression test if applicable, verify with real
     `make` output, and **commit + push** the fix as a NORMAL (non-squashed)
     Conventional Commit — never a squash/rebase/force-push on an open PR.

3. **Reply to each thread yourself (B29a).** After the fix is pushed, post a
   reply on the SAME thread (`in_reply_to` the original comment) that states the
   fixing commit sha, the root cause, the change, and the verification:
   ```bash
   _auth="Authorization: Bearer ${GITHUB_TOKEN}"
   curl -s -X POST -H "$_auth" -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/<owner>/<repo>/pulls/<N>/comments/<COMMENT_ID>/replies" \
     -d '{"body":"Fixed in <sha>: ..."}'
   ```
   Reply to EVERY comment/thread — including informational questions — with a
   direct answer. Do not wait for the human to relay them.

4. **Push / API auth.** The `gh` keyring token may lack push + private-write
   scopes. Use the repo's gitignored `.env` `GITHUB_TOKEN` (from `LLM-AI-TOKEN`
   in `~/zshrc`) for `git push` and `gh api`/`curl` calls — load it in-memory,
   never print it, never commit `.env`.

5. **CI must reflect the resolution.** If a review thread points at a violation
   that should have gone red, verify the *exit-code contract* end-to-end (broken
   file → non-zero → job RED; fixed → zero → job GREEN) and confirm the
   re-push triggers CI. Report the actual CI job result, not an assumption.

6. **An APPROVED PR is merged.** When the PR for the current branch is reviewed
   and **approved** (a reviewer's `APPROVED` review, or an explicit human
   approval phrase), do NOT leave it sitting open — merge it to `main` once the
   merge prerequisites hold, and clean up the branch:
   ```bash
   # prerequisites first — loop gate green, all jobs on the PR pass, no
   # unresolved review threads:
   make loop
   gh pr checks <N>                       # every job must be green
   # merge (squash or merge as the repo policy prefers) then delete both branches:
   gh pr merge <N> --merge --delete-branch
   git branch -D feat/<branch>           # local clean-up
   ```
   Do NOT merge a red PR, a PR with open/unresolved review threads, or a PR whose
   CI is still running — approval is a green light, not a waiver of the gate.
   Verify the merge landed on `main` (e.g. `git fetch origin && git log origin/main -1`)
   and report the merge commit sha. If the reviewer engaged but did NOT approve,
   keep resolving threads (see above); only a genuine approval triggers the merge.
   This mirrors the obsidian-timestamp-utility B32 (review-approved squash +
   finalise): "once a reviewer has approved, the agent may finalise".

## Loop gate (run before claiming done — B20-equivalent)

Never report a change done without running the loop:

```bash
make loop            # runs: download-test-model -> lint -> test-unit -> test-install
                     #      -> test-health -> test -> openspec-validate
# or the explicit runner:
python3 scripts/loop_harness.py
```

- `scripts/loop_harness.py` runs the seven stages in a fixed order and **fails
  closed** (any failed stage → non-zero exit even if later stages run and pass).
- **`lint` stage (`make lint`) is mandatory:** every tracked text file must end
  with a trailing newline. `make lint-fix` appends the missing newlines
  reproducibly. (.editorconfig enforces this in-editor.)
- **`health` stage (`make test-health`) is mandatory and end-to-end real:** it
  launches the installed `~/bin/llgenie` with a lightweight model
  (`~/models/Qwen/8GB/qwen2.5-0.5b-instruct-q4_0.gguf`, auto-fetched by
  `make download-test-model`), waits for `/health`, POSTs `"hi"` to
  `/v1/chat/completions`, and asserts a real text reply. This proves the host
  install serves a model from ~/bin.
- The hermetic gates (`make test-unit`) need no external dependency and MUST be
  green before any "done" claim.

### NO fallback implementations — one code path through the container, everywhere

There are NO fallback/dual implementations in the repo. Each stage has exactly
ONE code path that runs through the **same test container image** on CI and on
the local host, so behaviour is byte-identical in both. Concretely:

- **Model download** = the official `hf`(huggingface_hub) CLI with the
  resume/retry-throttle logic in `scripts/hf_download.py`. `hf` is bundled into the test image
  (`huggingface_hub[cli]`) and found via `shutil.which("hf")` — never a
  `requests`/`urllib` downloader, never a host-path or secondary-CLI branch.
  `download_test_model.py` resolves `hf` from PATH only and aborts if absent
  instead of falling back.
- **Runtime (`RUNTIME`)** is `nerdctl` by default but resolves to `docker` only
  because that's a *tool-availability* check for the same container engine on
  non-Colima hosts (CI uses docker). This is not a second implementation of a
  *stage*; the command shape is identical via either.

Anything that adds a second, differently-implemented path for the SAME resource
(downloader, HEALTH check, model resolution) is a regression and will be
rejected, even when it "would just work" as a fallback.

### Inference servers run ONLY in their container images (mandatory, durable)

Every inference server (llama.cpp, the Prism and LaurentZuijdwijk forks, vLLM,
Ollama, SGLang, ...) is built, run and tested **only through its engine image**.
No engine is compiled or pip-installed on the host.

- **A real OpenAI server always gets an image. Never opt it out.** Every engine the
  trending-local-llms registry lists that serves an HTTP API (`servable: true`) gets
  `container:` entries for each of its backends, a generated Dockerfile, a CI
  `engine-image` job and a version test. `container: false` is only for an engine that
  is not a server at all (a drafter, a benchmark harness, a browser library). An
  interactive upstream installer is not a reason to skip the image: compile the engine
  into the image the way the upstream project builds it, and leave the model download to
  the first start. An engine with no image is invisible to `llgenie` — it never appears
  in the trend list and is never offered — so dropping one silently hides the README's
  top pick.
  are read by ONE target only: `make generate-engine-params`. It writes the frozen
  per-arch params, one Dockerfile per engine × arch
  (`containers/engines/dockerfiles/<id>/Dockerfile.<arch>`) and the shared bases.
  Commit the result. `make build-engine ENGINE=<id> ARCH=<arch>` builds strictly from
  those files with plain make: no LLM, no skill reading. Use the engine's official
  image (or the shared llgenie base) as the base whenever one exists.
- **Disabled images:** an engine x arch image that cannot build or finish in CI goes into
  `DISABLED` in `scripts/engine_image.py` with its tracking issue (now #103). It is then
  left out of the CI matrix, `make install`, `llgenie --pick` and the tests; never leave a
  red or endless job in the pipeline instead.
- **CI pipeline per engine × arch, in parallel:** build -> test -> publish.
  1. `make build-engine` (registry layer cache; unchanged params are not rebuilt).
  2. Post-build test stage, driven by python test files through make:
     cpu images serve a tiny model and must answer on the OpenAI API
     (`make test-engine` -> `tests/test_engine_runs.py`, run inside
     `llgenie/test:latest`: `GET /v1/models` lists `llm-local`, a chat completion
     answers). Images that cannot serve on a GPU-less runner must at least print
     their engine version (`make test-engine-image` -> `tests/test_engine_version.py`,
     `docker run <image> version`).
  3. `make push-engine` publishes to the repo's GHCR (`ghcr.io/<owner>/llgenie/<name>`)
     on EVERY push run (feature branches too, default for now, #101) and ONLY after
     build + tests passed. `pull_request` runs (read-only token) never push.
  4. The separate `engine-published-test` matrix (jobs `test-published-<engine>-<arch>`) (every push run, after all builds) pulls
     every image back from GHCR with no build and no cache, checks the digest, checks
     the binary version, STARTS the container and chats "hi" on
     `/v1/chat/completions` (cpu images, and the GPU images of engines with a CPU
     fallback run without GPU devices; GPU-only engines get the version test; no
     self-hosted runner), then installs it from the registry + `make test-built-engine`
     (issue #102).
- **`make install`** builds nothing natively. It PULLS this host's backend's published,
  CI-tested images (`LLGENIE_REGISTRY`, default `ghcr.io/asimov-agent`; never builds unless
  `BUILD=1`), the llama.cpp core by default (`ENGINES=all` for every engine; llgenie pulls
  any other engine on first use). CI tests it last, per backend, against the published
  images (`install-published`). It writes a start script per engine into `~/bin`
  (`llgenie-engine-<id>`, plus the container shims `~/bin/llama-server` (stock
  llama.cpp image) and `~/bin/prism-server` (Prism image), picked by card tree by
  `llgenie`), then runs `make test-built-engine`: every start script must print its
  engine version via its image. Only Metal (Apple-Silicon, cannot run in a container)
  is exempt.
- **Native Metal engines (issue #114) — the one exception to "only in images".** On an
  Apple-Silicon Mac (`host_arch()` = `metal`) the engines whose skill has a `metal`
  install (TensorFold first) run natively, because Metal cannot reach a container. They
  are never installed by `make install`; **the llgenie pick makes them ready**:
  interactive `llgenie` is hardware → README trend list that fits → model → its engines
  → engine, and picking a Metal engine runs its skill's install script whatever is on
  the host: missing → install, installed at another version than the skill's pinned
  `version:` → update to the pin, at the pin → reuse
  (`engine_skills.native_status` / `install_engine_launchers.ensure_native`). The
  engine list shows which (`(installs X on pick)` / `(installed A -> updates to X on
  pick)` / `(installed X)`), `--dry` never installs, a failed install fails loudly and
  leaves no start script. Never add a second install path for them.
- **Native engine tests are hardware-scoped.** `make test-native-engine`,
  `test-native-engine-serve`, `test-native-engine-light`, `test-interactive-tensorfold[-ci]` run their real cases
  (real `uv`, isolated `UV_TOOL_DIR`, real install, Metal serve) only on an
  Apple-Silicon Mac — locally and in the CI job `native-engine-macos-arm64`. On any
  other host (every Linux job) they print that native engines are Metal-only and exit
  0; that host's engines are tested in their images. Never call them from a Linux job
  and never make them run Metal cases elsewhere. The picking logic itself is covered
  on every host by hermetic tests in `make test-unit` (`tests/test_tensorfold_seamless.py`,
  incl. the interactive pty pick of Qwen3.8-27B → TensorFold).
- **Tests never run an engine on the host.** All engine tests go through the engine
  images; the only host artifacts are the files `make install` writes. Python test
  tools come from the test image (`containers/test/Dockerfile`, deps from
  `tools/requirements*.txt`), so the test environment is the same everywhere.
- **GPU images use the host driver.** cuda images never contain a driver; every
  `docker run` (make run-engine, the start scripts, the llama-server shim) passes
  `--device nvidia.com/gpu=all`, the CDI device from nvidia-container-toolkit
  (`sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`), which mounts the
  host's `libcuda.so.1`/`nvidia-smi` into the container. ROCm passes `/dev/kfd` +
  `/dev/dri`, Vulkan `/dev/dri`. `make install` on a cuda host fails loudly without
  the toolkit.
- **The test image holds no inference server.** `make test-install-ci`,
  `make test-health` and `make test-top-tier-serve-ci` run pytest in the test image
  with the host docker socket mounted (`$(ENGINE_TEST_RUN)`); the servers they talk
  to are the engine images. Never add a llama-server build (or any engine) to
  `containers/test/Dockerfile`.

### NO SKIPPED TESTS — every test must run and pass (mandatory, durable)

A skipped test is a **loud FAILURE**, never a silent skip. There are NO
`pytest.skip()`, `@pytest.mark.skipif`, or conditional-skip in the test suite —
a test that cannot run because a prerequisite is missing (a llama-server binary,
`~/models`, `make install` artifacts, network, etc.) FAILS the run loudly with a
clear message telling you what to provision. This exists so a broken/absent
prerequisite can **never silently pass CI** while the real behavior is unverified.

Mechanics of the guarantee:
- The conftest `pytest_report_teststatus`/`pytest_runtest_logreport` hooks turn any
  skipped test into a failure in the exit code.
- The test HARness provisions prerequisites so tests genuinely run:
  - `make test-install-ci` performs a REAL `make install` + seeds a model, then runs
    `tests/test_install.py` — all in ONE container, no skip.
  - `make test-health` / `make test-top-tier-serve` download their model/server first.
  - If you genuinely cannot provision a prerequisite (e.g. no GPU), you do NOT skip —
    you run the CPU/container equivalent and report it as an explicit limitation.
- If a prerequisite is structurally impossible to provide, the test must assert a
  meaningful behavior that CAN run (e.g. the error message / CLI contract), never
  `pytest.skip("needs X")`.

### EVERY spec scenario must have Given / When / Then (mandatory, durable)

Every spec-driven change (`openspec/changes/<name>/specs/**/spec.md`) must express each
behaviour as a strict behavior-block in the **Given / When / Then** style — the OpenSpec
scenario is the contract the tests are written against, so it must read like an example:
- Each **Requirement** carries a top-level `WHEN … / THEN …` block defining the behaviour.
- Each `#### Scenario:` has **separate lines** for `Given`, `When`, `Then` (and `And` where
  steps accumulate) — NOT one big inline sentence. Example:
  ```markdown
  #### Scenario: gated repo is skipped
  Given a repo that requires approval is trending,
  When   we pre-flight its file,
  Then   it is skipped as `access-denied` and never triple-retried.
  ```
- Every `Scenario` that implies a test MUST have matching pytest/acceptance test(s) in the
  repo (no scenario without a test, no test without a scenario), and those tests must be
  wired into the Makefile/CI gate. A validator that confirms the spec is valid (`make
  openspec-validate`) is required before a "done" claim, and the strict G/W/T block format
  should be used so the scenario is unambiguous.
- **Every `#### Scenario:` MUST carry a `- **Test:**` reference line** naming the exact
  test file + test case that locks it (e.g. `- **Test:** \`tests/test_detect_server.py::test_choose_tree_24gb_inclusive_is_prism\``),
  or — for a live end-to-end scenario that hermetic unit tests cannot run — the CI job +
  make command that exercises it (e.g. `CI jobs \`server-build-*\` -> \`make test-serve-variant TREE=… BACKEND=…\``).
  A scenario with no `- **Test:**` line is a defect: a reviewer must be able to jump from
  the spec scenario straight to the test that proves it. (See
  `openspec/changes/feat-server-clone-build/specs/llama-server-build/spec.md` for the
  reference format applied to every scenario.)
- **The Python test itself must mirror the scenario:** each acceptance/behavior test's body
  MUST carry `# Given / # When / # Then` **comment markers** at the corresponding code steps so
  the behavior is readable in-place (a test whose body is a bare wall of asserts with no
  Given/When/Then markers is a defect). **Separate each marker+code group from the next with a
  blank line** (and use a blank line after the docstring), so the Given / When / Then sections
  read as distinct blocks. Docstring may carry the prose, but the markers go in the code block.
  Example:
  ```python
  def test_real_probe_ok_on_public_downloadable_repo():
      """A public repo is downloadable over an authenticated 200."""

      # Given a public GGUF repo/file on Hugging Face
      _real_hf()

      # When  we pre-flight it with the probe
      result = llama_ai._probe_file_downloadable(...)

      # Then  it returns 'ok' (real GGUF chunk over an authenticated 200)
      assert result == "ok"
  ```
  This keeps the spec scenario and the test in lock-step: a reviewer reads the `# Given/# When/
  # Then` markers in the test body and confirms each maps to the spec's `#### Scenario`.

### README must always be kept in sync

Any change that adds, renames, or alters a user-facing feature, `make` command,
target, or workflow MUST be mirrored in `README.md` **in the same change** —
document how to navigate and use it (commands, layout, behaviour). The README
is the user's navigation/usage doc, so it must never drift from the code. When
you add a make target, feature, or stage, update the README's corresponding
section in the same commit before the PR is ready. A "done" report that makes a
code change without an accompanying README update is incomplete.
- If the full loop can't complete, still run `make test-unit` + `make
  openspec-validate` and report their real results. Never hand-edit artifacts to
  fake green; fix the root cause and re-run.

### Local GPU verification is MANDATORY (the "exercise the GPU" rule)

The CI pipeline runs a **CPU-only** health check (bare GitHub runner, no GPU).
That alone does NOT fully verify the real hardware path. Before you report any
change that touches the model launcher / health / serving as "done", YOU must
also run the check **on the host with the actual GPU (Metal)** and record it:

- The host's Metal `llama-server` (built by `~/repository/git/llama.cpp`) backs
  the `~/bin/llgenie` launcher. Run the qwen lightweight model's health check
  through the GPU path, not just the container/CPU path:
  ```bash
  # 1. the full containerized loop (fast, CPU+container proof):
  make loop            # == make loop-harness (download->lint->unit->install->health->test->openspec)

  # 2. the GPU/Metal proof — launch the host launcher (which uses the REAL
  #    Metal llama-server at ~/bin) with the Qwen/8GB model and curl its
  #    /health + a chat "hi":
  "$HOME/bin/llgenie" 0.5b --port 18080 &      # uses the Metal (GPU) binary
  curl -s "http://127.0.0.1:18080/health"
  curl -s -X POST "http://127.0.0.1:18080/v1/chat/completions" -H 'Content-Type: application/json' \
       -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":16}'
  ```
  Even simpler: `tests/test_health.py` already launches the **host**
  `~/bin/llgenie` launcher, which uses the **Metal llama-server** (GPU) — so on
  a host with the venv installed, `make test-health` IS the GPU/Metal
  verification.
- **Mandatory, not optional:** do NOT declare "green/done" from the container
  loop alone. You must additionally run the host/Metal `test-health` (the one
  that uses `~/bin/llgenie` with the Metal binary) against the `Qwen/8GB`
  model and see the GPU reply. Record the GPU/Metal result in the loop summary.
- If the host GPU (Metal) backend is genuinely absent, state that explicitly and
  report the CPU/container result Honesty instead of pretending the GPU path ran.

## Makefile targets (source of truth)

**All verification — locally and in CI — MUST run through the Makefile, never by
hand-running `pytest`/`nerdctl`/the container directly.** This is unconditional:
every stage (lint, unit, install, health, top-tier, **e2e**, openspec) is invoked
via `make <target>` both on the host loop and in the GitHub Actions jobs, so the
command executed is byte-identical in CI and locally. A Python test that exists
with no corresponding `make` target to drive it is a defect; a CI job that calls
`pytest` (or any tool) directly instead of `make <target>` is a defect. The e2e
tests (`tests/*_e2e*.py`) are ALWAYS run by the `test-agents-e2e` make target,
and the CI `dispatch-e2e` job invokes exactly that target — never a bare pytest
path.

Each verification step is an independent target; `make loop`/`loop-harness`
chains them all.

- `make install` — build gguf venv, pull/build every engine image for this host,
  write `~/bin/llgenie`, `~/bin/llgenie-engine-<id>` start scripts and the
  `~/bin/llama-server` container shim, then `make test-built-engine` (each start
  script prints its engine version through its image).
- `make test-built-engine` — run every installed `llgenie-engine-*` start script with
  `--version` (docker run of its image); fails unless each prints a version.
- `make generate-engine-params` — skills -> frozen params + Dockerfiles (the ONLY
  step that reads skills). `make check-engine-params` fails when they are stale.
- `make build-engine ENGINE=<id> ARCH=<arch>` / `make build-engine-<id>-<arch>` /
  `make build-engines ARCH=<arch>` — build engine images from the generated files.
- `make test-engine` / `make test-engine-image` — post-build image tests (endpoint /
  version). `make push-engine` — publish a built + tested image (CI, every push run).
- `make uninstall` — remove launcher + symlinks (keeps venv).
- `make venv-install` / `make -C tools venv-install` — build the gguf venv.
- `make download-test-model` — fetch the lightweight health-check model
  (`Qwen/Qwen2.5-0.5B-Instruct-GGUF` q4_0, ~340MB) into `~/models/Qwen/8GB` (idempotent).
- `make lint` — linefeed lint: fail closed if any tracked text file lacks a trailing newline.
- `make lint-fix` — append the missing trailing newline to tracked text files.
- `make test-unit` — hermetic unit tests only (no `~/bin`/`~/models` needed).
- `make test-agents-e2e` — REAL agent-spawn e2e (issue #63): runs ONLY
  `tests/*_e2e*.py` via a glob. A fake worker does README issue-work, a hung
  worker is killed+respawned, and the README wording is asserted — all in <1 min,
  no GitHub API/LLM/network. Wired into CI as the `dispatch-e2e` job AND the
  loop-harness `agents-e2e` stage. **Must always be run through `make`, never by
  invoking the e2e pytest file directly.**
- `make test-install` — host install tests (verify installed launcher runs a model).
- `make test-health` — **end-to-end**: launch the tiny model from `~/bin`, answer
  `"hi"` on `/v1/chat/completions`, assert a healthy reply.
- `make test-native-engine` — Apple Silicon only (else prints why, exits 0): REAL
  TensorFold install / update / reuse through the llgenie pick + start script version.
  `make test-native-engine-serve` adds the real Qwen3.8-27B download + Metal serve (context
  65536) + "hi". `make test-native-engine-light` serves the lightest TensorFold model
  (Qwen3.5-9B MLX 4-bit) through the start script on Metal, or proves TensorFold's budget
  refusal on a host too small for it (the 7 GB macos-15 runner).
- `make test-interactive-tensorfold` — Apple Silicon only: plain interactive `llgenie`
  in a pty, picks Qwen3.8-27B then TensorFold from the printed lists, real install,
  Metal serve, "hi" (`TEST_LAUNCHER=~/bin/llgenie` tests the installed launcher).
  `make test-interactive-tensorfold-ci` — the macOS CI runner variant (`--dry`, 48 GB
  emulated, real install, no serve).
- `make test` — fast suite (unit + install; health excluded from `test` — run
  `test-health` in the chain).
- `make loop` / `make loop-harness` — run the chained `scripts/loop_harness.py`.
- `make chained` — run each verification step explicitly in sequence, fail-fast.
- `make generate-requirements` — recompile `tools/requirements.in` →
  `tools/requirements.txt` (container or venv pip-compile).
- `make openspec-image|new|validate|status|shell` — Dockerized OpenSpec CLI.

## Dependencies & lockfiles

- `tools/requirements.in` (numpy, gguf==0.19.0) and `tools/requirements-dev.in`
  (pytest) are the single sources of truth. **Never hand-edit** the compiled
  `requirements[-dev].txt`; regenerate via `make -C tools generate-requirements`
  / `generate-requirements-dev`. `make -C tools venv-dev-install` installs
  runtime + dev deps into the venv.
- `.venv`, `*.gguf`, `.run.log`, `*.progress.log`, `__pycache__` are gitignored.

## Model downloads & secrets

- `hf_dl.py` reads `HF_TOKEN` from `~/.zshrc` at runtime — never store a token in
  the repo or commit one. Prefer documented example shapes in docs/tests.

## Record of work

Track progress in `agent-wiki/` as dated `YYYY-MM-DD-<name>.md` entries (what was
verified against the spec, key decisions, current status). Keep entries concise;
don't over-engineer.
