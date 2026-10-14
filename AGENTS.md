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
- **Every command a CI workflow runs must be a `make` target** (or a `gh`/`git`
  orchestration call that has no repo logic). Never call `python3 scripts/…` or a
  `scripts/*.sh` directly from a workflow — that bypasses the Makefile and makes the
  command unreusable locally and by the pipeline. If a workflow needs a script, give
  it a make target (e.g. `fix-bot-sweep`, `fix-bot-report`, `agent-image-ref`,
  `fix-loop-image`) and call that. The wiring guard (`make check-wiring`) enforces
  that every script is wired to a target CI runs.

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
  `docker-compose-files/openspec.yaml` define it; `make openspec-image` pulls it from GHCR
  (or builds it when its Dockerfile hash is not published yet).
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
  - **Out-of-scope work is a SEPARATE, linked issue — never prose (MANDATORY).**
    Every issue and PR body MUST close its scope with an explicit `Not covered` /
    out-of-scope section, and EACH item in it MUST be filed as its **own** GitHub
    issue, linked in BOTH directions: the issue/PR names the side issue (`#N`),
    and the side issue states which issue/PR it came from. Never leave
    out-of-scope work as prose in the original body (a reviewer cannot track it)
    and never fold it into the original scope. Separating them keeps each issue
    one objective: the original PR ships only its own change and the deferred
    behaviour becomes a first-class, linkable work item. Example: #223 fixed the
    order-brittle registry-sync tests and deferred the ranking rule to #225 — the
    PR's `Not covered` names #225 and #225 links back to #223.

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

- **Each agent works in its own git worktree, every time (MANDATORY).** Never edit
  the user's checkout (`/home/asimov/repository/git/llgenie` on Linux,
  `/Users/andy/repository/git/llgenie` on macOS). Leave that checkout on the branch
  the user left there. One agent, one worktree, one feature branch. A second agent
  uses a second worktree. Do not reuse another agent's worktree, and do not
  `git switch` the feature branch in the user's clone.
  ```bash
  git fetch origin main
  mkdir -p ../llgenie-wt
  git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main
  cd ../llgenie-wt/<kebab>
  ```
  All edits, commits, `make` gates, and pushes happen in that worktree. `make test-unit`
  already mounts the parent repo when `.git` is a file, so the unit tests run from the
  worktree.
- **Before creating a feature branch**, fetch `origin/main` and cut the worktree from
  that tip with the `git worktree add -b` command above.
- **Before resuming an existing feature branch**, reuse `../llgenie-wt/<kebab>` when
  it is already a worktree of that branch. If the branch exists and the directory
  does not, attach it, then rebase onto `origin/main` before touching any code:
  ```bash
  git fetch origin main
  git worktree add ../llgenie-wt/<kebab> feat/<kebab>
  cd ../llgenie-wt/<kebab>
  git merge-base --is-ancestor origin/main HEAD 2>/dev/null || git rebase origin/main
  ```
- **Right before you push / open a PR**, from that same worktree, re-run the
  fetch+rebase above ONE final time so the PR is never behind.

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

1. **Before starting, add your own worktree off the latest `main`:**
   ```bash
   git fetch origin main
   mkdir -p ../llgenie-wt
   git worktree add -b feat/<kebab-name> ../llgenie-wt/<kebab-name> origin/main
   cd ../llgenie-wt/<kebab-name>
   ```
2. **Do the work in that worktree** — create/update the OpenSpec change, write
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
   - **Every PR body MUST end with `closes #<issue id>`** (the deliberate closing
     keyword GitHub uses to link a PR to its issue). If the PR does not close an
     issue, still end with the issue reference so the PR ↔ issue link is never
     ambiguous.
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

## Analysis: every change surfaces gaps → issues, never implementation (MANDATORY, durable)

Every change is also an opportunity to see what the codebase is becoming. While
you work, you MUST analyse the change for **real gaps and technical debt** — and
file them as **issues**, never as an implementation inside the current work:

- behaviours the tests pin only by accident (an order, a fixture, a golden value);
- data that is no longer accurate given how the product actually behaves;
- missing coverage, brittle assumptions, unclear or duplicated logic;
- refactor and technical-debt opportunities.

Rules:

- **Analysis ships issues, not code.** Each real finding MUST be filed as its own
  **detailed issue** — title, evidence (the code path / data point / scenario),
  why it matters, and what "done" looks like. The change you are shipping keeps
  its own single objective; do NOT fold findings into it.
- **Separate the issues** (see the out-of-scope rule above): a finding is its own
  issue, linked both ways — never a paragraph in the PR body.
- **A finding must be demonstrable** — a code path, a data point, a missing or
  failing scenario. Vague concerns are not issues.
- **Never implement from this analysis in the same change.** If a finding *is* the
  current task, it is the change; otherwise it is an issue, fixed later as its own
  reviewed change with its own issue and OpenSpec change.
- Do this every time, not on request — the codebase grows on every sync, so the
  re-examination is routine.

Example: fixing the registry-sync gate (#223) revealed the engine-ranking rule
(#225), the scope/filter question (#227), the per-engine list + matrix coverage
(#228) and the unskilled-engine gap (#229) — all filed as separate issues, none
folded into the fix.

## Loop gate (run before claiming done — B20-equivalent)

Never report a change done without running the loop:

```bash
make loop            # runs: download-test-model -> lint -> test-unit -> test-install
                     #      -> test-health -> test -> openspec-validate
# or the explicit runner:
python3 scripts/loop_harness.py
```

- `scripts/loop_harness.py` runs the stages in a fixed order and **fails
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
  Apple-Silicon Mac, locally (no CI job: the macOS runners have no Metal GPU). On any
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

### Engine bump dependencies (issue #186, mandatory, durable)

`make engine-bump ENGINE=<id>` runs before the weekly commit. It pins the skill,
derives, applies, then runs `make generate-engine-params ENGINE=<id>`. That
generator rewrites `containers/engines/dockerfiles/<id>/Dockerfile.<arch>` from
the skill. It does not read the new upstream commit. A package the new pin added
reaches that engine's image only when the skill already installs it, or when
this step writes it onto the skill first.

**Why.** An engine image gets Debian packages from two places. The shared base
(`containers/engines/base/Dockerfile.<backend>`, `BUILD_TOOLS` plus that
backend's defaults) is the toolchain every compiled engine shares. The second
`apt-get install` layer is that engine alone, and its names come from the skill
key `container.<backend>.apt`. The key is written inline in the front matter:

```yaml
apt: [libatomic1, libgomp1, python3-venv]
```

There is no `apt-list` file. `generate-engine-params` copies those names into
that engine's Dockerfile and leaves the shared base alone. A library added to
the base would be installed for every engine. A new name that never lands on
`apt:` is absent from the image, because the generator has nothing else to copy.

**When.** On a bump that has both the old sha and the new sha. A derive with no
old sha does not run this comparison: the whole file would look newly added, and
that is a first import, not a delta. The read is `git show <sha>:<path>` on the
real clone, for the skill's watched `requirements*.txt` (a name containing `dev`
or `test` is skipped), `pyproject.toml`, and `Dockerfile`. When the watch list
has none of those, the repo-root copies of the same three names are used. The
comparison finishes inside `derive`, before `pin`, before `_apply_findings`, and
before `generate-engine-params` and the workflow's `git commit`.

**What — Python.** Names present at the new sha and absent at the old sha are
`python_added`. When the skill install already runs `pip install -r` or
`uv pip install -r` on a requirements file, or the install mentions both
`pyproject.toml` and `pip install`, `python_covered` is true. The bump reports
the names and does not add an install line: the existing line reads the file at
the new pin when the image builds. When the install does not do that, `hard_fail`
names the packages. The bump does not invent a pip line.

**What — apt.** Names newly present on an `apt-get install` line in the pin's
Dockerfile, and not already on any `container.*.apt` list, are the apt delta.
When the skill already has an `apt:` line, they are `auto.apt_add` and
`_apply_findings` appends them to every front-matter line of the form
`apt: [name, name]`. Both backends receive the name, because the Dockerfile did
not say which backend it belongs to. `generate-engine-params` then writes those
names into that engine's Dockerfile only. When the skill has no `apt:` line,
`hard_fail` names the packages and no `container:` block is created.

**What the unit test must prove before a bump (issue #192, mandatory).** One
fixture is the old tag's files and the new tag's files. `bump()` runs on it
through pin, apply, and `make generate-engine-params`. That make target runs
`write_params`. The test reads the Dockerfile and the params JSON that command
wrote in the checkout. A Makefile target of `@true` does not test the bump. A
`render_dockerfile` call after `bump()` returns does not test the bump. The
run does not commit and does not push. These tests live in
`tests/test_engine_bump.py` and run under `make test-unit`, which
`make ci-unit` runs on Linux and macOS.

A release pin is two tags. The test builds both trees in a real git repo, tags
them, and calls `derive` with the old sha and the destination tag. Names
present at the old tag are not new. Names in both trees are not added. Names
only the new tag added are the install delta. The Dockerfile `make` wrote
contains that apt name on its `apt-get install` line. The shared base
Dockerfile does not. The install steps still contain the existing
`pip install -r` line and do not name the new Python package. A hard-fail
leaves that name out of the Dockerfile and out of the install steps. A test
that stops at the skill `apt:` line does not show what the image build will
install.

**What — removed packages.** Names present at the old sha and absent at the new
sha are `python_removed` and `apt_removed`. The bump does not delete them from
the skill and does not invent a pip line. It does print them. The `DEPS` line
is:

```text
[engine-bump] DEPS python_added=… apt_added=… python_removed=… apt_removed=…
```

It is printed when any of the four lists is non-empty. A pin that only removes
packages still prints the line. The TensorFold v1.0.7 pin removed
`huggingface-hub`, `jinja2`, `mlx`, `mlx-lm`, `numpy`, `safetensors`, and
`tokenizers`. The unit test uses those seven names.

**What — the PR.** A dependency `hard_fail` does not abort the bump. The pin
still moves, the PR still opens, the body carries the hard-fail and the `DEPS`
line, and CI goes red until a person fixes the skill. A removed cmake option
or launch flag still raises `HardFail`: derive applies nothing, and the pin
still moves.

**What — a binary that already exists.** `dpkg-shlibdeps -O <binary>` names the
Debian packages that binary links, runtime libraries only. The weekly bump does
not compile and does not unpack, so it does not run this command. Use it once a
binary is on disk. It does not see headers, and `apt-file` is not how this step
finds a package. `cmake` and `tar` do not print apt names.

**What — detect.** The archive install sets `detect` to
`{prefix}/{version}/bin/{id} --version`. A missing file makes bash print
`No such file or directory` with the version inside the path. That line is not
an installed version. A program that prints its own version and exits non-zero
(Ollama with the daemon down) is still installed.

Do not guess a package name. Do not put one engine's package into the shared
base. Do not rewrite the TensorFold unit tests that still expect `git+` as part
of this step. Issue #170 (the install job pulling an image tag before
`engine-image-*` publishes it) is a different change.

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

### Business logic is never mocked (mandatory, durable)

A test that claims to lock business logic runs that logic. It MUST NOT replace
the system under test with a stub, fake, or monkeypatch. `plan`, `derive`,
`pin`, apply, loaders, guards, rewriters, and any other function of the
product are the behavior. A test that passes because a mock returned the
answer the assertion wanted does not lock that behavior and is a defect.

The only stand-in allowed is an **external** system, and only when the test
is **not** end to end:

- A git remote may be a local repository the real `git` talks to.
- An HTTP API may be a file or a local server the real client reads.
- The production code that builds the request still runs. The test asserts
  on that request and on the files the product writes.

An end-to-end test calls the real external system. `make test-health`,
`make test-engine`, `make test-engine-bump-live`,
and the native and published-image serve tests do not mock that call.
Pointing `SKILLS_DIR` or `REPO_ROOT` at fixture files is not a mock: the
real loader and the real git still run.

### Tests address engines by id, never by index (mandatory, durable)

A test that drives `model_engine_pick.offer()` / `rank_engines()` or the
interactive picker MUST address an engine by its **id** (or derive its position
from the same call), and MUST NOT hardcode an index. The engine **order is
vendored upstream data** (`data/models.json` from trending-local-llms):
`rank_engines` sorts same-backend engines by measured t/s, so a new or updated
upstream measurement reorders a model's engines with **no llgenie code change**.

Pinning a *named* engine to a *fixed* slot — `row["engines"][1] == "llama.cpp"`,
or a literal interactive choice `engine="2"` — is a defect. When upstream shifts
the order the `registry-sync` gate goes red, so the sync PR never opens and
llgenie's data silently ages. `row["engines"][0]` meaning "the top-ranked engine"
is fine; a named engine at a fixed index is not. Use
`by_id = {e["id"]: e for e in row["engines"]}` and read `by_id["<engine>"]`, and
derive an interactive engine's 1-based position from the same `offer()` the PTY
is driven with.

Measured (2026-10-13): upstream added a TensorFold measurement on a **DGX Spark**
(an NVIDIA/CUDA box, 67 t/s) that sorted above llama.cpp (33.7 t/s) for
`qwen3.8-flash-next-125b`; two tests in `tests/test_strata_download.py` went red
(`2 failed, 4220 passed`) and the sync PR never opened.

Prove a fix is real, not a loosened test: run it against a freshly synced
registry (`make sync-registry`, `make sync-quant-catalog`,
`make render-trend-list-matrix`) in `llgenie/test:latest` and show the test fails
on the old (index-based) code and passes on BOTH the old and the new registry.

### The vendored registry is additive only (mandatory, durable)

`data/models.json` is a **verbatim copy** of trending-local-llms'
`data/models.json`, replaced wholesale by the weekly `make sync-registry` PR.
`make check-registry` re-validates the NEW file's shape, which cannot see what
the sync **lost**, so a sync that dropped a key, a model, a measurement, a t/s
or an engagement counter used to land silently and only show up later as a
thin trend list (`llgenie` then ranks engines from data that no longer exists).

- **A key is never removed, renamed or narrowed, and a value is never shrunk.**
  Additions are always fine. `scripts/registry_keys.py` compares the working
  copy against the previously committed one (`HEAD:data/models.json`) and fails
  on: a removed model, a key gone from a model row (list-of-objects compared as
  a key union, so an upstream collapse/reorder is not a loss), a lost
  `(engine, hardware)` measurement group, a lowered t/s, a lowered engagement
  counter, a lost `backends` / `supported_engines` entry, a lost format, or a
  removed engine-registry entry.
- **`make check-registry-keys`** drives it and is part of `make check-registry`,
  which `make ci-unit` (`.github/workflows/pipeline.yml`) and the weekly
  `.github/workflows/registry-sync.yml` job both run — a guard no CI job executes
  is a defect, never a spare part (bundle it into an existing target or add its
  own target following the internal-`_name` + public-wrapper pattern; the upstream
  twin of this rule is trending-local-llms rule 6d). Test:
  `tests/test_registry_keys.py`, wired into `make test-unit`.
- The same rule is enforced where the store is WRITTEN — trending-local-llms
  `check_no_value_loss` (its issue #114). llgenie never patches upstream data to
  make a sync pass: a loss is reported upstream and fixed there.

### Agent-implemented issues always end in a monitored, green PR (mandatory, durable)

When an agent implements an issue — its own or a filed analysis issue — the work
is not done at "code written":

1. **Implement on a feature branch** cut from the tip of `main` (worktree rule
   above), with the OpenSpec change + tests in the same branch.
2. **Open the PR** (upstream base, fork head, `closes #<issue>`, one
   Conventional Commit message per logical step). Never leave the work as an
   unpushed branch or a local-only change.
3. **Monitor the pipeline the PR triggered** (`gh pr checks`), read the failing
   job's real output, and **fix the PR until the checks are green** — the agent
   owns its own PR's CI, including flaky-looking stages it can reproduce.
4. **Merge is a squash merge with a proper Conventional Commit message** (the
   PR title/body carry the issue reference), so history stays one commit per
   change. Where the repo's CI owns the merge (e.g. trending-local-llms'
   `auto-merge` job), the agent drives the PR to green and lets that job land it
   — it never merges a red PR, a draft, or one with unresolved review threads,
   and it never merges a PR a human reviewer is still working on.

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
      result = llgenie_serve._probe_file_downloadable(...)

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
every stage (lint, unit, install, health, top-tier, openspec) is invoked
via `make <target>` both on the host loop and in the GitHub Actions jobs, so the
command executed is byte-identical in CI and locally. A Python test that exists
with no corresponding `make` target to drive it is a defect; a CI job that calls
`pytest` (or any tool) directly instead of `make <target>` is a defect.

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
- `make test-install` — host install tests (verify installed launcher runs a model).
- `make test-health` — **end-to-end**: launch the tiny model from `~/bin`, answer
  `"hi"` on `/v1/chat/completions`, assert a healthy reply.
- `make ci-engines BACKEND=<b>` — the ONE engine stage (issue #120, `scripts/ci_engines.py`):
  `cpu|cuda|rocm|vulkan` -> `make test-install-published`; `metal` -> `make test-native-engines`
  (each native-Metal engine: install at the pin, version, tiny model on Metal + "hi") + the
  TensorFold targets. CI calls it on Linux only (`published.yml`); `metal` runs on an Apple-Silicon host.
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
- `make test-image` / `make openspec-image` — pull the CI image published for the current
  Dockerfile + lockfile hash (`ghcr.io/<owner>/llgenie/{test,openspec}:<hash>`); build it
  locally only when that hash is not published yet (issue #117).
- `make test-image-pull` / `make openspec-image-pull` — CI: pull that hash, never build
  (fails when missing). `make publish-ci-images` — CI job `ci-images`: build + push
  (amd64 + arm64) only the hashes not on GHCR. `make ci-image-refs` prints the refs.
- `make ci-<job>` — one target per CI pipeline job (`ci-lint`, `ci-unit`,
  `ci-agents-read`, `ci-openspec`, `ci-cpu-health`,
  `ci-top-tier`, `ci-install`). Linux and macOS both call `pipeline.yml`: one job each,
  the same on both OSes, no combined jobs (issue #120). `make ci-free-disk` and `make test-engine-stage
  TEST=serve|detect` keep OS / matrix decisions in make, so no CI job or step is skipped.

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
