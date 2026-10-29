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
   - **A PR that implements an issue MUST close it — `closes #<issue id>`**
     (the deliberate closing keyword GitHub uses to link a PR to its issue, so
     merging the PR closes the issue). Three cases, no fourth:
     - **The PR implements the issue:** the body MUST end with `closes #<n>`.
       Measured on `main` (`4d999e3`), 13 of the last 38 merged PRs carried no
       closing reference — an issue whose implementation merged was left open, or
       was closed by hand with no implementing PR (#321: closed manually at
       02:47:40Z, and the defect it names still reproduces — run `38841759439`,
       `failure`, 0 jobs).
     - **The PR implements only PART of the issue:** the body MUST NOT close it.
       The issue stays open and the body names what remains as its own linked work
       item in `Not covered` — never prose the next reader has to find (#290 left
       #279 open with its remaining half described only in the PR text).
     - **The PR implements no issue** (a pure chore): say so in `Issue:`, name the
       change instead, and open a tracking issue if the change needs one.
   - **NEVER close an issue by hand while a PR implements it.** The PR closes it on
     merge; a hand-closed issue whose PR is still open (or never existed) makes the
     issue's state stop being evidence about the code.
6. Keep each PR to one change/OpenSpec change. Rebase or merge `main` in when the
   PR goes stale; never force-push shared branches.
7. **CI merges a green, conflict-free PR; the agent never merges it by hand
   (MANDATORY, durable).**
   - The `auto-merge` job in `.github/workflows/ci.yml` squash-merges a pull
     request that is **green and conflict-free**, with the branch deleted, no
     human click required. Green means every PR-relevant job of that run passed;
     conflict-free means `mergeStateStatus == CLEAN` — so a `DIRTY` (conflicting),
     `BEHIND` (stale), `BLOCKED` (required check or review pending) or draft PR is
     left alone, as is any PR whose head moved after the run started
     (`--match-head-commit`).
   - **The scope is narrow on purpose:** `pull_request` events only, a non-draft
     PR, a head that is **this repository or the owner's fork**
     (`andyholst/llgenie` — the branch every agent PR is pushed to), and a head
     branch that is not `main`. Any other fork stays manual. A fork head is merged
     **without** `--delete-branch`: the base token cannot delete a branch in the
     fork, so its branch is kept (and printed in the log), which is not an error.
   - **`do-not-merge` is the human hold.** A reviewer who is mid-read labels the
     PR and CI defers to them; the job prints the hold and exits 0, it is never a
     red run. An unbound `closes #n` is the other failure mode and it is loud:
     after the merge `make verify-closure PR=<n> REPO=<repo>` reads the PR's own
     closing references and fails, naming the issue, when one is still open.
   - The agent still never runs `gh pr merge` itself (no squash, no rebase, no
     merge commit, no `--admin`, no `--auto`) and never pushes to `main`. When the
     work is done it pushes the branch, updates the PR body, drives the PR green,
     and **stops**, reporting the PR URL: the CI job lands it, or a human does.
   - "Push to mainstream" means: the PR targets `asimov-agent/llgenie:main` and is
     green and mergeable. Landing it is CI's action (or the reviewer's, when the
     job defers).
   - Images reach GHCR only through that path: after the merge, the CI run on
     `main` builds, tests and then pushes each engine image. The merge is made with
     the owner PAT for exactly that reason — a merge made with the job token starts
     no workflows, so that run would never happen.

## Every issue carries the problem, why, the fix and the benefit — then the technical solution (MANDATORY, durable)

An issue is the root of the pipeline — issue → feature branch → OpenSpec change → code → PR →
`closes #n` — and it is the text an implementer starts from. A body that lists machine fields is
readable only by the run that filed it, so **every issue carries these six sections, in this order**:

```markdown
## Problem              what is wrong, observed — the measured symptom, never the ticket title
## Why it matters       the consequence of leaving it: what breaks, what it costs, what it blocks
## How we fix it        numbered, plain language — what changes, and why that addresses the cause
## Benefit              what the reader gets once it is fixed; what stops happening
## Acceptance criteria  one `- [ ]` item per provable outcome — what "done" looks like, tickable
## Technical            LAST, and the only technical section: files, targets, tests, gates, measured numbers
```

`## Not covered` is optional and, when present, sits between `## Acceptance criteria` and
`## Technical`. Each item in it names the issue it was filed as — out-of-scope work is its own linked
issue, never prose.

- **One renderer, never a hand-built body.** `scripts/issue_body.py::render` is the ONLY place those
  headings are spelled. Every producer that files an issue renders through it:
  `security_issues.body_for`, `code_review.issue_body`, `run_failure_reactor.issue_body`,
  `engine_skill_gap.issue_body`, `registry_change_issue.render`, `architecture_bot.render_issue`,
  `queued_run_alarm.file_label_issue`. A change that adds a producer adds it to
  `issue_body.PRODUCERS` in the same change.
- **The dedupe marker is the body's first line, unchanged.** Every producer's idempotence reads its
  marker back (`security_issues.MARKER_RE`, `filed()` in `code_review`/`run_failure_reactor`,
  `registry_change_issue`'s marker search, `queued_run_alarm.label_marker`). Restructuring a body
  must never cost a producer its memory of what it filed.
- **The mapping to a PR body is fixed**, so the two cannot drift: issue `Problem` ↔ PR `Issue:`,
  `How we fix it` ↔ `Fix:`, `Benefit` ↔ `Benefit:`, `Technical` ↔ `Technical:`. The PR body has its
  own gate (below); the issue body has `make check-issue-bodies`.
- **The agent legs enforce it on issues no script wrote.** `issue-triage`'s `REFINED:` block and
  `issue-refiner`'s `RESTATED:` block carry the same six sections — those two legs are the only
  mechanism that reaches a human-written issue.
- **`make check-issue-bodies` is the gate** (`scripts/check_issue_body.py`, inside `ci-unit`, and
  classified in `scripts/issue_bot_gates.py`): it fails on a producer that hand-builds a body, a rendered body
  missing a section / out of order / with `## Technical` anywhere but last, `## Acceptance criteria`
  with no `- [ ]` item, an `AGENTS.md` that has lost this section, and an issue skill that no longer
  states the shape. `make issue-bodies-report` prints what it reads.

## An issue's numbers name the commit they were measured on (MANDATORY, durable)

An issue that asserts a count, a file path or a line number is making a claim about **one commit**. Name
it in `## Technical`, and take `main` from the API — never from the checkout you happen to be standing in,
which is routinely parked on a feature branch:

```bash
gh api repos/asimov-agent/llgenie/commits/main --jq .sha      # the sha the issue will cite
git worktree add --detach ../llgenie-wt/<name> origin/main    # a read-only tree of that sha
```

State the counting method beside every number a reader could reproduce differently: targets come from
`make -qp`, not a line regex; "files containing the call" and "test modules containing the call" are
different denominators and both must be named. When two populations share a number, name the population —
a count that is right but answers a different question is worse than no count.

A number that is challenged is **re-measured, and the body is corrected** — not just a comment, because the
implementer reads the body. The comment carries the delta: the claim, what was filed, what it measures, and
whether the correction rescopes an acceptance criterion. Six issues were once filed against a PR tip while
claiming `main`; three needed rescoping after an independent re-measure.

## Every PR body and commit message carries the issue, the fix and the benefit (MANDATORY, durable)

A commit and a PR are read on their own. A reviewer, a `git log`, a `git bisect` must learn from
them what the **issue** was, how the change **solves** it and what the **benefit** is, without
opening the issue. An empty, placeholder or subject-only message is a defect, never a shortcut.

- **NEVER an empty or placeholder message.** Not a commit `-m "update"` / `-m "fix"` / `-m ""` /
  `-m "wip"`, and never a PR opened with no `--body`, `--body ""` or `--body "-"`. A body that says
  nothing is the same defect as no body at all.
- **The subject is a typed Conventional Commit:** `type(scope): imperative summary`. It is the index
  entry, not the explanation — it does not replace the body.
- **The body carries three labelled parts, in this order:**
  - `Issue:` — the problem or goal, naming its number (`#313`). State the measured symptom, not the
    ticket title.
  - `Fix:` — the mechanism that solves it: what changed, and why that change addresses the cause
    rather than the symptom.
  - `Benefit:` — what the change buys, and what it prevents from now on.
- **Then the technical extension** as a `Technical:` part: the files, functions, make targets, tests
  and gates the change touches, plus any measured number that proves the claim — the detail a
  reviewer needs to verify the work without re-deriving it.
- **A PR that implements an issue closes it — `closes #<issue id>` in the body** (required above); a
  partial implementation does not close it and names what remains as a linked work item. The commit
  references the issue, the PR closes it. Both exist for every change, both carry the three parts.
- **The in-repo producers follow the same rule.** `engine-bump.yml`, `issue-bot.yml` and
  `registry-sync.yml` build their commit message and PR body this way — a bot's commit is read by the
  same reviewer as a human's.

`make check-pr-hygiene` (`scripts/check_pr_hygiene.py`, run by `ci-unit`) is the gate: it reads every
producer the repository owns and fails on a commit with no message, a placeholder message, a subject
that is not a typed Conventional Commit or no body, on a PR opened with an empty or placeholder body,
and on an `AGENTS.md` that no longer carries this section. `make pr-hygiene-report` prints what it
reads.

## A PR's commits are authored by Andy Holst or Asimov Agent — no one else

A commit's author is the attribution every reader trusts: `git log`, `git blame` and `git bisect` all
answer "who wrote this" from it. Two identities may author a PR's commits, and no others:

```
Andy Holst <andy.holst@protonmail.com>
Asimov Agent <support@docondee.com>
```

- **The name matches EXACTLY and the email must be the one that belongs to it.** `Andy`, `andyholst`
  and `Mr. Asimov` are the same two people under other spellings, and they FAIL — a reader of
  `git log` cannot tell whether `Andy`, `Andy Holst` and `andyholst` are one person or three.
  `Andy Holst <someone@else.example>` fails too: the name must carry its own address.
- **Every bot identity fails.** `github-actions[bot]`, `llgenie fix-bot`, `Hermes Agent`,
  `asimov-agent` and `llama-ai-agent` are outside the allowlist; the repo's own workflows therefore
  commit as `Asimov Agent` (`fix-bot.yml`, `issue-bot.yml`, `rebase-bot.yml`, `engine-bump.yml`,
  `engine-bump-rebase.yml`, `registry-sync.yml`). An automation that stamps the token owner's LOGIN
  (`gh api user --jq .login` → `asimov-agent`) is a violation, which is why those workflows pin the
  identity even though the PUSH and the PR still use `BUMP_TOKEN` (issue #136).
- **The scope is the commits a PR ADDS** (`git rev-list --no-merges <base>..<head>`). A merge commit
  is skipped — its author is the merge machinery, not the PR's — and a commit already reachable from
  the base branch is someone else's landed work. So the merge commit GitHub writes on `main` (authored
  `GitHub <noreply@github.com>`) never trips the gate, and neither does history on `main`.
- **A `Co-authored-by:` trailer is attribution too.** A commit whose author is allowed but whose
  trailer names anyone else fails, under its own finding key.
- **Remediation for a branch that is already off the allowlist:** set the identity
  (`git config user.name "Andy Holst"` / `git config user.email andy.holst@protonmail.com`), then
  `git rebase --reset-author` (or `git commit --amend --reset-author`) and
  `git push --force-with-lease` on your OWN PR branch (AGENTS.md allows the force-push there).

`make check-pr-authors` (`scripts/check_pr_authors.py`, run by `ci-unit`) is the gate: it reads the
PR's commit range, every `Co-authored-by:` trailer, the repository's producers, and the presence of
this section (so the rule cannot be deleted silently). `make pr-authors-report` prints every commit in
the range with its verdict. `PR_BASE` / `PR_HEAD` bound the range (defaults `origin/main` / `HEAD`);
`ci-unit` runs it with no range on a push to `main`, where the static half still applies.

## Every workflow file is validated before it can merge (MANDATORY, durable)

GitHub REFUSES a whole workflow file whose `${{ ... }}` expression it cannot parse, and the refusal is
silent: the run arrives `status=completed`, `conclusion=failure`, with **zero jobs**, a `name` equal to
the file PATH, and no log at all (`gh run view <id> --log-failed` → `log not found`). Measured on `main`
(issue #330): `.github/workflows/engine-bump-rebase.yml` was refused on every workflow-touching push
because of one comment inside the `rebase` job's `run: |` block —

```yaml
        run: |
          # folded into one `${{ ... }}` so the mode this run took is readable in the log.
```

Rules that follow:

- **A `#` line inside a `run:` block scalar is SCRIPT TEXT, not a YAML comment.** GitHub evaluates every
  `${{ ... }}` in the file's raw text, so an expression written in such a comment IS parsed, and an
  unparseable one refuses the whole file. Never write expression syntax there — describe it in words.
- **`yaml.safe_load` does not save you.** PyYAML has no notion of `${{ }}`, so it accepts a file GitHub
  rejects. A YAML parse is not a workflow validation; PyYAML also accepts a duplicate key that GitHub
  refuses.
- **A 0-job red run whose `name` is the file PATH is a startup failure, not a failed job.**
  `gh run view <id> --json name,jobs` → `name` = the path and 0 jobs = GitHub refused the file. Do not
  chase it as a regression in the code the run would have tested.
- **`make check-workflows`** (`scripts/check_workflows.py check`, run by `ci-unit`) is the gate: every
  YAML file in the repository must end with a newline, every `${{ ... }}` in it must parse, and every
  `.github/workflows/*.yml` must declare a top-level `name:` (a missing name is what makes a run present
  itself as a path). `make workflows-report` prints what it reads. Its tests are
  `tests/test_workflows_valid.py` in `make test-unit`, where a strict YAML parse with no duplicate keys
  also runs — the make gate is stdlib only, so `ci-unit` can run it on the host on Linux and macOS.

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

6. **The PR lands without the agent merging it.** Merging is CI's action now
   (rule 7 under "Git workflow"): the `auto-merge` job in `.github/workflows/ci.yml`
   squash-merges the PR the moment the run is green **and** the PR is conflict-free
   (`mergeStateStatus == CLEAN`), non-draft, a head in this repository or in the
   owner's fork (`andyholst/llgenie`), and carries no `do-not-merge`
   label. So there is nothing to wait for at a keyboard — and nothing for you to run:

   - **Never run `gh pr merge`** (no `--squash`, `--merge`, `--rebase`, `--auto`,
     `--admin`). A hand merge bypasses the one place that checks the merge state and
     pins the head commit, and a merge made with the job token starts no workflows —
     the post-merge run on `main` (which publishes the engine images) would never run.
   - What you DO own: drive the PR green (`make loop`, then `gh pr checks <N>`), reply
     to review threads, and keep the branch current (`rebase-bot` does this every six
     hours). If the job defers the merge, it printed why — `DIRTY` (conflicts),
     `BEHIND` (stale), `BLOCKED` (a required check or review), a draft, a fork, or
     `do-not-merge` — and that reason is the work item, not a reason to merge by hand.
   - A reviewer who wants to hold the PR labels it `do-not-merge`; remove the label
     when the review is done and the next green run merges it. An approval is no
     longer a precondition for landing, and it is no longer a licence to merge.
   - After it lands, prune the branch **and** the worktree with `make worktree-prune`
     (issue #431), never a hand-typed `git branch -D`: it removes them only for a
     branch whose PR is MERGED **and** whose merge commit is on `origin/main` (this
     repo squash-merges, so a squashed branch tip is never an ancestor of `main`).
     `make worktree-prune DRY=1` prints the plan and mutates nothing.
   - Verify what landed (`git fetch origin && git log origin/main -1`) and report the
     merge commit sha, exactly as before. `make verify-closure PR=<N> REPO=<repo>`
     proves the body's `closes #<n>` actually closed; CI runs it right after the
     merge, and you can run it yourself on any merged PR.

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
     build + tests passed. It is a step of every `engine-image-*` job, so a same-repo
     `pull_request` run publishes what it built and tested (measured: run 38121659510
     pushed `llama-cpp:23b0202a-021e11d2-cuda`). A FORK head cannot: GitHub scopes its
     `pull_request` token to the base repo's packages read-only and refuses the write
     (`denied: installation not allowed to Write organization package`, measured on PR
     #651). That refusal is a permission no fork PR can be given, so `push` turns THAT
     message, inside a `pull_request` run only, into a loud skip — a `::warning::`
     annotation plus a `SKIP publish <ref>: pull_request token cannot write … (issue
     #155)` line — and the image is still built and post-build tested; the run that
     lands the change on `main` publishes it. The policy lives in the script, never in a
     scenario-scoped workflow `if:` (`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`
     forbids those). A push run's denial, or any other failure (network, bad tag, an
     image that fails its own version test), still fails loudly — never a silent pass.
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
- **The CI `install` job waits for the images it pulls (issue #169).** `make ci-install`
  runs `make ci-wait-engine-images ARCH=cpu` BEFORE `make ci-install-run`: the gate resolves
  exactly the tags `install` pulls (`install_engine_launchers.install_plan` is the one place
  that list is built) and polls the registry manifest until each is published, naming and
  failing on a tag that never appears. It never builds an image, never pulls a different tag,
  and never skips an engine. The gate is a make prerequisite, not a workflow step, so the job
  keeps running exactly one `make ci-<job>` target, and the OS branch lives in the gate
  target itself (`ci-install` stays OS-neutral — macOS pulls no engine image, #120). Without
  it, the first run of a new pin fails `[install] FAIL llama.cpp/cpu: not published` while
  its own `engine-image-*` job is still pushing that tag.
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

`data/models.json` is a **copy, normalised on the way in,** of trending-local-llms'
`data/models.json`, replaced wholesale by the weekly `make sync-registry` PR.

- **What "normalised on the way in" means (issue #687), and what it does NOT.** Upstream's
  store started writing model names into `formats[].name` (`"Qwen3.8-27B"`, `"LLM (MoE)"`),
  which no consumer can act on: llgenie could not map those rows to a download, so the
  pick/matrix tests saw `use_format: safetensors` and the planner raised `StopIteration`.
  `scripts/sync_registry.normalise()` therefore restricts `formats` to the vocabulary
  (`GGUF | MLX | safetensors | mlx-safetensors | litertlm`), and a row left with none states
  the format its own repo/id names (`-GGUF`, `mlx`, `litertlm`), else GGUF — the picker's
  documented `<name>-GGUF` fallback, applied once at vendor time. A duplicated row id is
  dropped. Every departure is printed by the sync.
- **Rows are NOT folded into "one row per model".** Upstream's `models[]` holds distinct
  entities (a base model, a merged finetune, an MLX conversion, a run on one box) and its own
  README lists each as its own row; a name heuristic cannot tell `Qwen3.8-27B Defiance
  Uncensored` (a finetune) from `Qwen3.8-27B (iPad Pro + eGPU R9700)` (a run), and folding
  dropped real models. The vendored README stays upstream's list, verbatim.
`make check-registry` re-validates the NEW file's shape, which cannot see what
the sync **lost**, so a sync that dropped a key, a model, a measurement, a t/s
or an engagement counter used to land silently and only show up later as a
thin trend list (`llgenie` then ranks engines from data that no longer exists).

- **A model, a key, an engine, a list entry or a stated footprint is never removed,
  and a stated footprint is never shrunk.** Additions are always fine.
  `scripts/registry_keys.py` compares the working copy against the previously
  committed one (`HEAD:data/models.json`) and fails on: a removed model, a key gone
  from a model row (list-of-objects compared as a key union, so an upstream
  collapse/reorder is not a loss), **an engine that had a measurement for the model
  and has none** (that is the unit `rank_engines` groups by, so losing it thins the
  trend list), a lost `backends` / `supported_engines` entry, a lost format, a
  removed engine-registry entry, a lowered `weight_gb` / `context_tokens` /
  `system_ram_min` (on the model or on a measurement), and a **tracked post** (the
  `/status/<id>` of a `source_post`) that is nowhere in the new store.
- **A measurement is identified by its post, store-wide — never by its
  `(engine, hardware)` label (issue #668).** Upstream refines a hardware string
  (`RTX 6000` → `RTX 6000 24GB`), re-attributes a post to a split model row and
  upgrades a profile link to the real status URL; none of that loses a
  measurement, and keying on the label made all of it read as one and froze the
  weekly sync for 13 days (#534). `engagement.seen_posts` is a DERIVED placeholder
  (rebuilt on every upstream sort), so its element keys are not data and an emptied
  one is not ten lost keys.
- **What the store RE-READS is reported, not failed.** A surviving post's lowered
  t/s (upstream correcting a figure) and a decreased engagement counter (a live X
  re-scrape — likes genuinely fall) are printed as `NOTE:` with both numbers, and
  do not fail the gate: they remove nothing from the ranked set. Do not "fix" a note
  by widening `data/models.json`; a note is a report.
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
- **A data-carrying bot job carries a NEW engine; ci-unit refuses it (issue #683).** The
  weekly sync must be able to land a store that first names an engine llgenie does not
  ship: `make skills-validate … ALLOW_NEW_ENGINES=1` names that engine and continues, the
  sync's next step opens one tracking issue per new engine (`make spawn-engine-skill-issues`),
  and `make check-engine-skill-gap` in `ci-unit` is what keeps the resulting PR red until
  each engine ships a skill or gets a dated decision in `data/unsupported-engines.json`.
  Without that split the job deadlocks: measured 2026-10-26, `skills-validate` exited 1 on
  16 engines upstream had just started listing, so no sync PR landed after 2026-10-13 and
  the issues that would have decided them were never opened. `ALLOW_NEW_ENGINES=1` is never
  passed from `ci-unit`, and it never tolerates a skill whose engine left the registry.

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
   change. The repo's `auto-merge` job owns the merge (rule 7 above, the shape
   `trending-local-llms` uses in `qa-validate.yml`): the agent drives the PR to
   green and lets that job land it. It never merges a red PR, a draft, or one with
   unresolved review threads, and it never merges a PR a human reviewer is still
   working on — `do-not-merge` is how a human says so.

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

### Documentation is part of the change: a dated note, indexed — never a README append (MANDATORY, durable)

Every change — a pipeline/job/workflow edit, a feature, a behaviour, a make target, a
stage — MUST be **recorded as its own dated note in `agent-wiki/` and indexed in
`CHANGES.md` in the SAME commit**, before the PR is ready for review. The README is the
**user guide**, not the change log (issue #678): it says what llgenie is, how to install
it, how to use it, and one page on how it works, and it points at the references. Change
history appended to it was why it grew to 2,600 lines of work record while a new user
could not find "Download a model". A "done" report that makes a code change without its
note and index line is incomplete, however green the pipeline is.

1. **`agent-wiki/` — the note, one per change.** Track the implementation as a dated
   `agent-wiki/YYYY-MM-DD-<kebab>.md` entry, unique to that change: what was verified
   against the spec, the decisions taken, the current status. **Reference the issue and
   the PR it implements** (`#<issue>`, `#<PR>`), plus any related issue/PR it
   complements or supersedes. Zettelkasten rules: one idea per note, a stable dated
   filename, links — never a copy of another note. Amend the existing entry for the
   change instead of writing a second one for the same work.
2. **`CHANGES.md` — the index.** Add one row per change (date, the change in one line,
   a link to its note, the issue/PR). Newest first. `CHANGES.md` is what a reader
   follows to find the history, and it is linked from `README.md`.
3. **The user guide still describes use.** A change that adds, renames or alters a
   **user-facing** feature, `make` command, target or behaviour MUST also be mirrored in
   `README.md`'s matching section in the same commit — how to run it, what it does, how
   it fits the workflow. Automation detail (bot legs, cron slots, CI wiring, secret
   plumbing) belongs in `docs/BOTS.md`; engine build/serve detail in `docs/ENGINES.md`;
   the code map in `docs/ARCHITECTURE.md`. **Never document a change by appending a
   section to `README.md`**, and a bot never writes `README.md` at all.
4. **The gate is real.** `make check-docs` (`scripts/check_docs.py`, run by `ci-unit`
   next to `check-wiring`) fails when a user-facing make target (a `##` help line, i.e.
   one `make help` prints) is named in neither `README.md` nor a `docs/` page the README
   links, when a recorded exception in `tests/fixtures/docs-exceptions.json` goes STALE,
   when an `agent-wiki/` entry references no issue or PR, when a note is missing from
   `CHANGES.md` or an index row points at a note that does not exist, and when
   `README.md` carries an issue-numbered change heading, a change-log heading or the
   generated dispatch-table marker. A target documented in no doc needs a dated entry in
   the exceptions file (reason + date + issue) — an omission has to be a decision, not an
   accident. `make docs-report` shows the whole picture (documented / missing / recorded
   exceptions / each record's references and index state). Run it in the same commit as
   the change; a red `ci-unit` here is the gate working, not noise.
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

**Every target that produces no file of its own name MUST be in the `.PHONY:` block
(issue #392).** `make` runs a recipe when no file carries the target's name, so a target
that is not `.PHONY` and is shadowed by a file of that name (a left-over scratch file, a
checkout on a case-insensitive filesystem) prints `make: '<target>' is up to date.` and
runs nothing — a green run that verified nothing. `make check-wiring` (inside `ci-unit`)
fails on any parsed target that is neither declared in `Makefile`/`tools/Makefile`'s
`.PHONY:` block nor recorded under `not_phony` in `tests/fixtures/host-only-wiring.json`
(for a target that genuinely writes a file of its own name; the entry needs a reason and
is stale once the target is declared or gone). `make wiring-report` prints the counts.

### The unit suite is aggregated, never enumerated (mandatory, durable)

`make test-unit` does NOT name its test files. It runs `scripts/unit_tests.py`,
which **discovers** every `tests/test_*.py` minus the deliberate exclusions in
`tests/fixtures/unit-suite.json` (each with a reason, an issue, a date and the
target that runs it instead). A new test file is in the gate the moment it
exists — there is no shared line to edit and no conflict to resolve. Keeping a
file OUT of the gate is a dated decision, not an omission. De-selection inside a
selected file is by exact `--deselect file::test` node id, never a `-k`
expression (`-k` matches substrings, so a new test whose name CONTAINS a
deselected test's name would be silently dropped). `make check-wiring` asks the
aggregator what it selects, so a discovered file is wired through the target
that runs it. `scripts/unit_tests.py excluded` lists what is kept out of the
suite and by which target, and `make test-unit` prints the selection before
pytest runs. This
mirrors the sibling repo `trending-local-llms`, whose unit entry is one
aggregating call with the network/hardware checks in their own targets.

A target that runs a SUBSET of the suite — the loop's fast stage, `make test` —
does NOT name its files either. The subset is a **named group** in the same
roster (`groups.fast`, issue #403) and the target runs
`scripts/unit_tests.py run --group <name>`. So a new test that belongs to the
subset is added in the roster alone; there is no second shared line. A group
names a file the roster excludes, names a file that is gone, names no file, or
carries no reason/issue/date is a finding, and a group a recipe asks for that
the roster does not record is fatal — a target cannot silently run nothing.
`make check-wiring` attributes only the group's files to that target, so
`make test` never claims to run the whole ~20-minute suite.

- `make install` — build gguf venv, pull/build every engine image for this host,
  write `~/bin/llgenie`, `~/bin/llgenie-engine-<id>` start scripts and the
  `~/bin/llama-server` container shim, then `make test-built-engine` (each start
  script prints its engine version through its image).
- `make test-built-engine` — run every installed `llgenie-engine-*` start script with
  `--version` (docker run of its image); fails unless each prints a version.
- `make ci-wait-engine-images ARCH=<backend>` — CI gate (issue #169): wait until every
  image `make install` pulls for that backend is published; names and fails on a tag that
  never appears (no build, no pull, no fallback).
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
  (amd64 + arm64) only the hashes not on GHCR. `make ci-image-refs` prints the content-hash
  refs, including the agent's.
- `make agent-image` / `make agent-image-pull` — pull `ghcr.io/<registry>/llgenie/agent:latest`
  (issue #989). `publish agent` points that tag at the current content hash, and moves it
  again when the hash is already published. `make agent-image-ref` prints the `:latest` ref
  the bots pass to `docker run`.
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

## A bot's behaviour lives in its project skill, not in a Makefile recipe (MANDATORY, durable)

Every Hermes leg — the issue-bot's triage and implement steps, the refiner, the dedup, the
architecture bot, the masked fetch, the rebase agent and the fix bot — runs under ONE **Hermes
project skill**: `.hermes/skills/<name>/SKILL.md`, the layout Hermes discovers from a trusted
checkout, preloaded with `hermes -s <name>` (issue #577). Measured before this rule: the same
`UNATTENDED: …` paragraph inlined seven times, prompts of 1005-1629 characters, and every leg
starting with "Load AGENTS.md" to learn what its own bot may do.

- **A leg's inline prompt is a pointer plus the run's parameters** — the input file, the output
  file, the values only that run knows. It never restates the contract: `make check-agent-skills`
  fails a prompt over 400 characters, a leg with no `-s`, a name with no skill, a frontmatter name
  that disagrees with its directory, a skill missing `## Inputs` / `## Output` / `## Rules`, and an
  inlined unattended contract.
- **`## Output` names the ONE file the leg may write.** The deterministic step after the agent does
  every GitHub write (comment, label, issue, PR); an agent that writes elsewhere hands its edits to
  the job as if a human had made them.
- **`bot-unattended` carries the shared unattended contract once**, and every leg preloads it beside
  its own skill. Never paste that paragraph into a recipe again.
- **The agent image registers the checkout's skill dir** (`scripts/hermes_skills_register.py` from
  `scripts/install_hermes_ci.sh`, `skills.external_dirs` → `/repo/.hermes/skills`): Hermes reads
  skills only from its own home and from `external_dirs`, so an unregistered checkout makes
  `-s <name>` resolve to nothing and the leg runs with NO contract while reporting success. The
  build reads the value back, and `tests/test_agent_skills_live.py` proves the load through
  Hermes's own preload path.
- **A new bot leg means a new skill**, and its own `make` target names both. `skills/engines/` is a
  different thing: those describe inference servers, are read by `generate-engine-params`, and are
  never loaded by an agent.

## A bot's credential must reach the AGENT's shell, never a log (MANDATORY, durable)

A bot leg that forwards a key the agent's own shell cannot read gives you a run that
**does nothing and reports green**: the container has the key, the step log shows the
name (GitHub masks a registered value to `***`), and the agent's shell reads it EMPTY.
Measured on this host against the real Hermes (issue #358) — plain names read
`agent-shell=EMPTY` (exit 1), the forced twin reads `agent-shell=set` (exit 0).

- **Hermes strips provider credentials from its terminal tool on purpose**
  (`tools/environments/local_env_policy.py::_STATIC_PROVIDER_ENV_BLOCKLIST`: `NOUS_API_KEY`,
  `GH_TOKEN`, `FIRECRAWL_API_KEY`, `HF_TOKEN` …), and `env_passthrough` can never re-allow a
  blocklisted name. The one sanctioned way through is `_HERMES_FORCE_<NAME>`, which its
  terminal env builder unwraps back to `<NAME>`.
- **ONE list, one seam, in the Makefile.** `AGENT_SHELL_KEYS` names every credential a
  container receives; on the host `make` exports `_HERMES_FORCE_<NAME>` from `<NAME>` by
  reference (the value is never on a command line, in a recipe or in a log — `ps` cannot see
  it) and only when `<NAME>` is set; every agent leg carries `$(AGENT_SHELL_FORWARD)`. A leg
  that spells out `-e <NAME>` without the forced twin is the defect, not a shortcut.
- **Prove it, do not assume it.** `make agent-shell-keys-check` drives Hermes's REAL terminal
  environment (`LocalEnvironment`) inside the agent image and fails — naming the variable, never
  printing a value — when a container credential reads empty in the agent's shell. Every bot job
  that starts the agent image runs it, with `AGENT_SHELL_CHECK_KEYS=` narrowed to the keys that
  job actually sets (a key the job legitimately lacks must not fail the check).
- **A web reach is one leg, keyed by name.** `make agent-fetch` is the ONLY place a bot fetches a
  URL: `FIRECRAWL_API_KEY` is in `AGENT_SHELL_KEYS` (so the agent's shell is proven to see it), the
  prompt reads the value from the environment and never prints, echoes or writes it, and the fetched
  text — nothing else — lands in `OUT`. A second hand-rolled fetch is a defect; `make search-smoke`
  is the loud proof that the key works (401/402/403 and an empty 200 both fail).
- **Before the image, not inside it.** Every leg runs `python3 scripts/require_env.py <KEYS>` as its
  first recipe line, ahead of `scripts/ci_images.py ensure agent`, with the keys that leg forwards —
  so a missing secret costs seconds instead of a 120-180 minute run. The suite derives the roster
  from the Makefile; a leg added without the guard reds `make test-unit`.
- **A missing credential is LOUD, never a skip.** An unset key, or a Hermes that cannot be found
  where the check runs, exits 2; `--allow-unconfigured` is the only opt-out, it says so, and no
  workflow may use it.

## A bot's transcript is redacted before it prints (MANDATORY, durable)

A bot's agent stream IS the job's console output, and GitHub's masking is a filter over the stream,
not a property of the content: a transformed value (URL-encoded, base64, a slice) sails past it, and
nothing is masked in a log a job uploads itself. So no leg prints its stream raw.

- **Every public agent leg runs through ONE seam**, `$(call scrubbed_run,…)`: the command's stream is
  captured to `$(HERMES_LOG)` (gitignored — never printed, never uploaded), the console gets only the
  redactor's bounded tail (`$(HERMES_LOG_TAIL)`), and `$(HERMES_LOG_SCRUBBED)` is what a workflow
  uploads. The command runs in a subshell and its own exit status survives, so a red leg stays red.
- **`scripts/scrub_log.py` is the only thing that prints.** It reads the secret VALUES **by name**
  from its environment (the list lives once, in `scripts/check_secret_output.py::SECRET_VARS`), masks
  every raw / URL-encoded / base64 spelling, plus credential SHAPES (`ghp_…`, `hf_…`, `sk-…`,
  `Bearer …`) that never entered its environment, and prints a COUNT — never a value, never a prefix.
  A missing input is exit 2: a stream that cannot be read must never look like a clean run.
- **That one list carries every credential the agent RECEIVES.** A name in the Makefile's
  `AGENT_SHELL_KEYS` must be in `SECRET_VARS`; `tests/test_secret_output.py` compares the two (and the
  workflow `secrets.<NAME>` roster) and reds `make test-unit` when one is missing, because a forwarded
  key that is absent there is neither scanned when printed nor masked in the transcript (#379).
- **A leg that calls `hermes` outside the macro is a defect**, and so is a workflow that uploads the
  raw `$(HERMES_LOG)` — the raw file holds the unredacted stream by construction.

## Record of work

Track progress in `agent-wiki/` as dated `YYYY-MM-DD-<name>.md` entries (what was
verified against the spec, key decisions, current status). Keep entries concise;
don't over-engineer. Every entry **references the issue and the PR it implements**
(`#<issue>`, `#<PR>`) — `make check-docs` fails an entry that names neither — and it is
updated in the SAME commit as the change it records, never in a later follow-up
("Documentation is part of the change", above).
