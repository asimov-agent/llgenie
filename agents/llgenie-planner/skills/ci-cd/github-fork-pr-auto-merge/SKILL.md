---
name: github-fork-pr-auto-merge
description: Use when fork-head PRs do not auto-merge despite green CI.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [github-actions, pull-requests, forks, auto-merge, rebase, ci]
---

# Fork PR auto-merge and the rebase gate

## When to Use

Use when PRs from a fork head (`owner/repo:<branch>`) targeting the upstream repo
are not being merged even though CI is green, or when the rebase bot skips a PR
that is behind `main`.

For llgenie specifically, the work-item mechanics around this gate (bot claim on
the issue, worktree off `origin/main`, OpenSpec through the container, which
remote is the fork, polling a 45–60 minute CI) live in the `llgenie-engine-image-ci` skill
(its `references/` directory). That skill's `ci-contract-tests` reference file is the map of the contract
suites a workflow/bot-prompt/make-target edit reds — read it before changing a gate workflow, because a
functionally correct change still fails `linux / unit` on guard, dispatch-form, cron-minute, unattended-prompt
and time-budget tests.

## The merge job must not live in the `pull_request` workflow

A `pull_request` run from a fork gets **no repository secrets**. `secrets.X`
expands empty, so the job's `GH_TOKEN`/`BUMP_TOKEN` is blank and the first `gh`
call 404s or 401s. Under `set -e` the step dies before any merge and the run
reports "failed" while CI itself was green. Moving the job into the same
`pull_request` file does not help — the trigger is the problem.

Seam: keep the merge in its own workflow started by `workflow_run` on the CI
workflow completing with `conclusion == success`, then resolve the PR from the
run's `head_branch`/`head_repository`. Also accept `workflow_dispatch` so a
queue that predates the fix can be drained by hand.

Bootstrap note, and the mechanism behind it: a `workflow_run` workflow executes the copy of the file on
the **default branch**, never the PR's — both the workflow YAML and the checkout it makes. A green PR that
fixes the gate is therefore gated by the broken version and dies with the identical error, however correct
its patch is. Expect exactly one manual (or admin) merge to land the fix; the queue flows from the next
green run. Diagnose that state rather than a regression with `gh run list --workflow <auto-merge>.yml`: a
`failure` immediately after a green CI run, with `skipped` runs before it (their CI was red, so the job's
`if:` never fired), is this. State the bootstrap in the PR body so the reviewer knows the manual merge is
by design, and prove the fix on the run *after* it lands.

## A fork `pull_request` run cannot PUBLISH, and a failed run keeps that sha red

A separate mechanism from missing secrets: the fork run's `GITHUB_TOKEN` is read-only against the base
repository, so a step that writes to a registry dies there while everything above it passed.

- Symptom: `denied: installation not allowed to Write organization package` (GHCR) or the registry's
equivalent, thrown AFTER build + tests succeeded — the job name then reads like an engine/test failure and the
real cause is two steps above. Grep the job log for `denied:` before touching the code under test.
- Fix the HEAD, not the step: ship anything that publishes from a branch **in the base repo** (same-repo
head). A publish step gated on a same-repo head / `push` event is the alternative when verification alone is
wanted on PRs — but say which one you chose in the PR body, because "skipped" and "failed" both hide.
- **Classify the change before the first push: an edit to a container image's INPUTS makes the fork PR
permanently red.** A build context hashes the files it installs (`Dockerfile*`, `requirements*.in`/
`.txt`, lockfiles), so touching one moves the image tag; CI must then PUSH that tag, the fork token
cannot, and every job that pulls the tag (`install-published-*`, anything running `<image>:<hash>`)
fails behind it. Two red job families, one cause, and no commit pushed from the fork can clear it — so
cut the branch in the BASE repo from the start when you have push rights
(`gh api repos/<base> --jq .permissions` → `push: true`), and only fall back to moving the head later
when you do not.
- **Check runs attach to the SHA, not to the run.** A fork-headed run that failed leaves that sha red forever,
so re-opening the identical commit from a same-repo head still shows the old failure. Push a fresh commit
(`git commit --allow-empty -m …`) when moving a PR to a same-repo head, and re-read `gh pr checks` against the
new `headRefOid` — the old run's rows are the ones that keep appearing otherwise.
- A same-repo head is also what lets the PR's own pull_request run exercise write-scoped steps at all; the
`push` event may be limited to `main`, so do not expect the branch push to produce a run.

## Read three lines of the job log before blaming the merge policy

The order separates the three failure classes, which all present as "green CI, no merge":

1. `GH_TOKEN:` **empty** → the job runs where repository secrets do not exist (fork `pull_request` run, or
a workflow that forgot to forward the PAT). Fix the trigger, not the decision.
2. `GH_TOKEN: ***` (a real PAT) and the run still dies → the **call** is broken, not the decision: an
unsupported `--json` field (below), a PR that never resolved, a `gh` subcommand shape the installed CLI
does not have. The decision logic is never reached, so no deferral comment appears either.
3. A resolved PR plus `[auto-merge] PR #N deferred to a human: …` → now it really is merge state
(`BLOCKED`/`BEHIND`/`DIRTY`/draft/hold label), and the printed reason is the work item.
4. A resolved PR plus `gh pr merge … failed (1): GraphQL: At least 1 approving review is required by
reviewers with write access` → the DECISION was right and GitHub's protection refused the merge
(see the admin-bypass caveat below). Nothing in the script is broken; a repository setting is.

A run that cannot merge must exit non-zero; a `success` that merged nothing is the worst shape of a gate.

## `gh pr view --json` refuses the whole call on a field that does not exist

`gh pr view --json state,…,authorAssociation,…` answers `Unknown JSON field: "authorAssociation"` and
exits 1 — it does not ignore the name, and it does not return the other fields. One invented name therefore
kills every run of the gate before any decision is reached, in production only: the field names look
plausible because the GraphQL-ish ones exist in other tools. Rules:

- Keep the requested names in ONE constant and join it into the single call, so there is one place to audit.
- Lock that constant against the CLI's own allowlist. Capture the `Available fields:` block of
  `gh <sub> --json __probe__` into a fixture, and assert every requested name appears in it. Do it per
  subcommand (`pr view`, `pr list`, `issue view`, `issue list`, `pr checks`, `run view`).
- Make the test fake `gh` **reject an unknown `--json` name** exactly as the real CLI does. A fake that
  answers `pr view` with whatever JSON blob the test handed it makes this entire bug class invisible, which
  is how a green suite ships a gate that has never once run.
- Derive anything you wanted an extra field for from a field that exists: bot authors are `…[bot]` or
  `app/…` in the LOGIN (there is no author-association field), ownership from `headRepository` /
  `headRepositoryOwner`, closure from `closingIssuesReferences` on `pr view` only.
- A fake `gh` generated as Python source inside a string literal must emit newlines as `chr(10)`, not as an
  escaped `\n`: the outer literal interprets the escape once, so the generated file ends with a real newline
  inside a string and every case that touches the fake dies with `SyntaxError: unterminated string
  literal` — not just the case you were writing.

## Long PR and issue bodies: write a file, do not inline them

A body passed as `--body "…"` is shell-expanded: backticked command names, `$(…)`, and unmatched quotes
turn a `gh pr create` into a `gh` usage error or a truncated body. Write the text to a file and pass
`--body-file` / `-F <file>` (for `gh pr comment` too). When the body must be edited later, edit the same
file and re-post, rather than re-typing a heredoc.

## Gate on WHO opened the PR, not on where the head lives

The condition the user wants: the PR author is the repository owner, a write
collaborator, or the bot — **regardless of whether the head is a fork**. A
"head must be same-repo" check is the wrong gate and silently excludes the
fork PRs that should merge.

- Author: `pull_request.user.login`.
- Collaborator: `gh api repos/{repo}/collaborators/{login}/permission --jq .permission`
  in `{admin, maintain, write}`.
- Bot: compare against the bot's own login and the actor login the run carries,
  not against a hardcoded human name.

## Resolving the run to a PR: only digits are a number

`workflow_run` hands the gate a **run id**, not a PR number, so one step maps the run back to its PR:
the run object's `pull_requests` array first, then a head-branch search. Two traps, both measured:

- **`gh api` prints a failed response's body to stdout.** A fork `pull_request` run 404s on
  `repos/{repo}/actions/runs/{id}/pull_requests`, and `name=$(gh api … || true)` therefore yields the
  JSON body (`{"message": "Not Found", "status": "404"}`) — `|| true` discards the exit status,
  **not** the output. A `[ -z "$name" ]` guard never fires, the fork fallback never runs, and the blob
  then breaks the output file (next bullet). A value is a PR number **only when it is digits**;
  anything else is "no answer" and falls through to the search.
- **`$GITHUB_OUTPUT` takes one `key=value` per line.** A multi-line value is refused
  (`::error::Invalid format '<line>'`, `Unable to process file command 'output' successfully`) and the
  step fails, so the merge never runs — and no deferral comment is posted either, because the decision
  script was never reached. Write `number=<n>` only after validating, or let a script own the write.

Put the resolution in a script with a test, called from a make target, not inline in the step: the
404/fallback/validation logic is exactly what an inline shell snippet hides, and the make target is the
one path that also runs on the host.

`gh pr list --head owner:branch` matches a **same-repo** branch only and finds nothing for a fork head.
Search instead, and filter on the owner so a same-named branch in another fork cannot be picked up:

```bash
gh pr list --repo "$REPO" --search "head:$BRANCH" --state open \
  --json number,headRepositoryOwner \
  --jq '.[] | select(.headRepositoryOwner.login=="'"$HEAD_OWNER"'") | .number'
```

`gh api repos/{repo}/branches/{branch}` returns 404 for a fork branch too: guard each lookup, and verify
the resolved PR's `headRepositoryOwner.login` before merging.

## `mergeable: UNKNOWN` means GitHub has not computed it yet — wait, do not defer

GitHub computes `mergeable` **asynchronously**, so a read taken right after a CI run finishes can answer
`UNKNOWN` — neither "conflicts" nor "mergeable". A decision that reads it once and treats it as a verdict
parks a green PR with a deferral nobody retries (measured: `mergeable: UNKNOWN`, PR stayed OPEN while the
API answered `MERGEABLE` seconds later, and the only reason it ever merged was a later run reading a
settled state).

- Poll `mergeable` itself, bounded like the approval wait (6 × 5 s), before deciding: roll the poll into the
  same helper that waits for `mergeStateStatus == CLEAN`, and return as soon as `mergeable` is any settled
  value. A state that never settles still defers — with the last observed value in the comment.
- Check the APPROVAL gate too: a `review_blocked()` predicate that requires `mergeable == MERGEABLE` returns
  False on `UNKNOWN`, so the approve-then-merge path is skipped entirely and the run defers on a state it
  never tried to clear. Order the decision so the settle happens BEFORE that predicate.
- Test it with a fake `gh` whose first N `pr view` answers have `mergeable: UNKNOWN` and then settle: assert
  the merge happened, that it did not fall back to `--admin`, and that at least N+1 reads were spent.
  Reuse the fake's per-PR/read counter instead of adding a second fixture shape.
- Do NOT treat `UNKNOWN` as "conflicts" and rebase: `DIRTY` is the conflict signal, `UNKNOWN` is a timing
  signal, and a rebase on `UNKNOWN` churns a branch for nothing.

## Clear the review first, then merge — in that order

A review-blocked green PR has three candidate answers, and only one of them normally works. Take them in
this order, and make the order explicit in one function rather than inlined in the job:

1. **Approve as the identity that is NOT the author, then merge normally.**

   ```bash
   gh pr review "$PR" --repo "$REPO" --approve --body '<why the non-author identity approves>'
   gh pr view "$PR" --repo "$REPO" --json reviewDecision,mergeStateStatus   # require APPROVED + CLEAN
   gh pr merge "$PR" --repo "$REPO" --squash --delete-branch --match-head-commit "$HEAD_SHA"
   ```

   This is the path a repo WITHOUT a review rule gets for free, and it is the one that satisfies the rule
   instead of fighting it. Re-read the PR after approving — **but POLL, do not read once**: GitHub computes
   `mergeStateStatus` asynchronously, so the read taken the same instant as the `--approve` still says
   `BLOCKED` (measured: approval landed, state was `CLEAN` seconds later, and the job had already abandoned
   the legitimate path for `--admin`). Loop a bounded number of times (e.g. 6 × 5 s) until
   `mergeStateStatus == CLEAN`, then merge; if it never settles, defer naming the last observed state.
   Build that deferral text from the state you just read — never from the approval helper's reason
   variable: on the success path it is unset, and the f-string renders `None; the admin merge was refused
   too: …` as the comment a reviewer has to read.
   Test it with a fake `gh` that keeps answering `BLOCKED` for the first N `pr view` calls after an
   approval — a fake that flips to `CLEAN` immediately cannot catch this.
2. **`--admin` only when the author IS the merge token's account** (self-approval is refused by GitHub, so
   step 1 cannot run). `--admin` fails wherever the review rule is enforced for admins — see below.
3. **If both are refused, defer with the reason ON the PR and exit 0.** A policy refusal is not a broken
   gate: post the deferral comment (one per head SHA) and return success, exactly as for `BLOCKED`/`BEHIND`.
   Never let "could not merge" share an exit code with "chose not to" — but never turn a setting into a per-
   PR red run either, because the next reader of the PR cannot act on a run log.

Keep a stranger's PR deferred — none of this applies to an author outside the repo's identities. A fork
head's branch cannot be deleted by the base token: merge without `--delete-branch` and print the kept branch
rather than failing.

**Before writing step 1, grep the decision script for an approval helper that nobody calls.** The classic
shape is a bypass that replaced the legitimate path: an `approve()`/`try_approve()` function is written and
tested, then a later fix routes the review block straight to `--admin` and leaves the helper as dead code —
so the run "tries everything" while the one call that would work is never executed. `grep -n 'def .*approve\|
try_approve(' <script>` and check each definition has a caller; wiring an existing helper is a two-line
change, while re-implementing the path is how the second, divergent implementation appears.

**The author gate and the approval gate must agree on the same set.** A job that admits an opener as "the
repo's own bot" for the merge decision but only accepts two human logins for the approval leaves every
workflow-created PR (`app/github-actions`, `dependabot[bot]`) permanently blocked, with the two halves of the
same job disagreeing. Keep one predicate (login in the allowed humans OR a bot login `…[bot]` / `app/…`) and
use it in both places.

**A PR authored by the merge token's own account needs a SECOND identity's token.** Every bot PR pushed or
opened with the owner PAT is authored by that PAT's account, so the job can never approve it. Add an optional
secret (e.g. `APPROVER_TOKEN`) holding the other allowed identity's PAT, use it for the approval only, pass
it through the child's environment (`GH_TOKEN` in the subprocess env) — never on a command line — and
register its name in whatever secret-scanner list the repo keeps, or the guard test will refuse the change.
Set that secret without minting a PAT first: the CLI's own credential for the OTHER identity is already a
user token, so `gh auth token | gh secret set APPROVER_TOKEN --repo <repo>` (piped, never echoed) works and the
approval lands — but a `gho_…` OAuth token dies the next time that account re-authenticates, so replace it with
a dedicated classic PAT (`repo` scope) when convenient and say so rather than leaving a silent time bomb.
Unset must degrade to step 3, not to a crash. Confirm whether the optional secret actually exists before
diagnosing the code: `gh api repos/{repo}/actions/secrets --jq '.secrets[].name'` lists the NAMES (a missing
name is the whole answer, and it is a one-line answer to give the owner), while a deferral comment that says
"set APPROVER_TOKEN" and a run log that shows the approval was skipped are the two symptoms that look like a
logic bug and are not.

**`--admin` does NOT bypass a required review that is enforced for admins.** When the branch demands N
approving reviews from reviewers with write access AND administrators are not exempt, GitHub answers
`GraphQL: At least 1 approving review is required by reviewers with write access. (mergePullRequest)` no
matter that the token's account is the repo owner. If the PR is also authored by that same account,
self-approval is refused too, so **no CI identity can land it** — the honest answer is "a repository
setting is blocking the gate", not another code change.

Diagnosing which setting, which fixes exist, and how to set the approver secret are in
`references/approval-and-branch-protection.md`. Two facts from it that change the diagnosis and are easy to
get wrong: a non-admin token sees branch protection as **404** (not "no protection"), and a ruleset listing
only `deletion` + `non_fast_forward` does NOT mean no review rule exists. Never paper over the refusal by
dropping `--admin` or by having the job token approve.

When the setting is unreachable (the token's repo permission has `admin: false`, so protection reads as
404 and cannot be edited), unblock the ONE PR without touching settings — supply the review as the other
identity, then re-run the failed gate:

```bash
gh pr review <PR> --repo <repo> --approve --body '<why this is the non-author identity approving>'
gh pr view <PR> --repo <repo> --json reviewDecision,mergeStateStatus   # require APPROVED + CLEAN
gh run rerun <auto-merge-run-id> --repo <repo>                          # the gate re-reads the PR
```

A re-run of the `workflow_run` job re-evaluates the CURRENT PR state (the `event == 'pull_request'` /
`conclusion == 'success'` conditions are still satisfied by the original run), so the merge lands with no
new CI cycle. Confirm afterwards with `gh pr view --json state,mergedAt,mergedBy` and the run's
`conclusion: success` — and check the merge identity, since the gate merges as its own PAT account rather
than as the human who clicked approve.

## A deferral is not a retry — sweep the deferred PRs on a schedule

The gate fires on a completed CI run, and a deferral exits 0 by design with one marker-deduped comment per head
SHA. So a blocker that clears **without a push** — a secret added, a review posted later, `do-not-merge`
removed, a pending check that finished — leaves a green PR unmerged until a human re-runs the job by hand.
Measured: deferred at 06:05, the approving secret added at 06:37, merged at 06:40 only because the run was
re-executed.

Close it with a second trigger over the SAME decision — never a second merge path:

- Keep the deferral marker addressable (`<!-- auto-merge: deferred <head> -->`, already written one per head
  SHA) and add a `recheck` that lists the open PRs and, for each whose marker names its **current**
  `headRefOid`, runs the ordinary `run(pr, head)` — approve as the other identity, merge, verify closure.
- Skip a marker for an older head (that verdict described another tree) and skip a PR with no marker: the
  sweep retries its OWN deferrals, not every open PR. `do-not-merge` still wins.
- Bound it (`--max-prs`, 5) and print one line per PR (`retrying`, `not a retry`, `cap reached`), so a sweep
  log answers "why is #N still open" without a second tool.
- Full design, the scheduling shape, the dispatch-trigger trap and the fake-`gh` test traps are in
  `references/deferral-and-recheck.md` — read it before adding a trigger to the gate's workflow file.
* Schedule it (`schedule: "*/30 * * * *"`) with the owner PAT and the approver token, and guard the existing
  `merge` job with `github.event_name == 'workflow_run'` so the schedule does not try to resolve a run that
  does not exist. The sweep stays runnable by hand through the make target or a re-run of the last sweep, so
  it needs no dispatch surface of its own.
* **Never rely on that cron alone — also run the sweep on the CI completion that triggers the gate.** A
  `schedule:` block on a workflow that already has `workflow_run` can silently never fire in a given repo:
  the workflow reports `active`, the file on the default branch carries the cron, and the workflow still
  produces ZERO `schedule` runs (measured 30 of 30 `workflow_run`), while another workflow's hourly cron in
  the same repository runs fine. Wire the sweep as a second job with `needs: [merge]` + `if: always()` so
  every CI completion retries the deferrals, keep the cron as a backstop, and prove the trigger with
  `gh api repos/{repo}/actions/workflows/<id>/runs?per_page=30 --jq '[.workflow_runs[].event]|group_by(.)|map({(.[0]):length})'`
  rather than reading the YAML. A sweep that has never executed looks exactly like a sweep with nothing to do.
- **Do NOT also add `workflow_dispatch` (or any second trigger) to that file.** A dispatchable workflow is a
  different contract in most hardened repos: the type-checked test suite requires it to carry the repo's
  byte-identical owner/collaborator guard job (checked for `github.actor` AND `github.triggering_actor`,
  accepting only `admin|maintain|write`, before any secret is read) and to state its contract in the README.
  A workflow that never had a dispatch trigger has none of that, so adding `workflow_dispatch:` to make the
  sweep hand-runnable reds the whole unit suite on the workflow-guard and dispatch-form tests while the
  feature itself is correct. Before adding a trigger, grep the test tree for the workflow's filename
  (`grep -rl "<file>.yml" tests/`) and read what those tests demand of it; prefer the schedule plus the make
  target as the manual path.
- The scheduled sweep has no triggering actor: pass the token's own account (`actor=token_login(gh)`) rather
  than leaving the author gate to refuse a bot-opened PR for "not saying who triggered it".
- Test it with per-PR fake answers: the fake `gh` must answer `pr list` and `pr view <n>` for several numbers,
  or a sweep that touches the wrong PR looks identical to one that works. Assert on the recorded argv that the
  retried PR merged and a stale/absent marker produced no `pr review` and no `pr merge`.
- **Embed the fake's data so it is JSON again, and make the fixture PR trustable.** Two traps, each one a red
  test that names neither cause: (1) `DATASET = {json.dumps(rows)!r}` inside the generated fake is a Python
  *string*, so `json.dumps(DATASET)` re-encodes the string and the consumer iterates characters — embed
  `DATASET = json.loads({json.dumps(rows)!r})`; (2) a fake PR that keeps its default `headRepository` (a
  placeholder like `o/r`) is a third-party fork, so the case defers as a stranger instead of exercising the
  retry — set `headRepository.nameWithOwner` to the trusted repo in the fixture. A fake `gh` with no `pr list`
  branch exits 1 with EMPTY stderr, which reads like a crash in the code under test.

## A `workflow_run` gate can arrive after the PR is already merged

The run that triggers the gate is queued before the merge, but the gate starts only after every `needs:` job
finishes — minutes to an hour later. A human (or a second run) can merge the PR in that window, and then the
resolution step finds no open pull request and fails with "no open pull request for run <id> … a green PR
must never be silently dropped". That wording is right for a PR that vanished, wrong for a PR that landed:

- Treat `state != OPEN` as a **successful no-op** (print `PR #N is MERGED — nothing to merge`, exit 0) and
  keep the loud failure for a run whose PR cannot be found at all. Otherwise every human merge paints a red
  run over a correct merge and trains the reader to ignore the gate.
- The same applies to a re-run after the merge: `gh run rerun <id>` is safe (the original
  `event`/`conclusion` conditions still hold, and the job re-reads the current PR state), but its log will
  say the PR is MERGED — that is the expected answer, not a regression.
- **Pick the run that belongs to YOUR PR, not the newest run of the workflow.** Re-running a gate whose PR has
  already landed produces `no open pull request for run <id> … a green PR must never be silently dropped` and a
  red `merge` job — which reads exactly like the deferral bug you were chasing. Resolve it first
  (`gh run list --workflow <gate>.yml --branch <head-branch> --limit 5 --json databaseId,headSha,createdAt`),
  and if the PR is already MERGED, change nothing: the next green PR is the proof.

## A merge token without `workflow` scope cannot land a workflow change

Any PR that touches `.github/workflows/**` is merged by a token that must carry the **`workflow` scope**, and
GitHub refuses the merge outright otherwise:

```
GraphQL: refusing to allow a Personal Access Token to create or update workflow
`.github/workflows/<file>.yml` without `workflow` scope (mergePullRequest)
```

This is not the review rule and not the merge policy — a plain `gh pr merge` fails with it exactly like
`--admin` does, so no amount of retrying or bypassing helps. It is why the PR that FIXES the merge workflow
is often the one that cannot be auto-merged. Diagnose by reading the refusal text (it names the file) rather
than the PR state, then either add the scope to the PAT (`gh auth status` shows the scopes a token has) or
merge that one PR as a human. Tell the user which of the two it is; do not "fix" the gate again.

## Rebase sweep: a comment is not a claim, and BLOCKED is not a rebase state

Two rules for the sweep script:

- **Needs rebase = `BEHIND` or `DIRTY`.** `BLOCKED` means review-blocked and is
  not itself a rebase signal — but a `BLOCKED` PR can still be behind `main`, so
  decide from the compare against `main`/`mergeStateStatus`, never from the
  blocking reason alone.
- **Only a real claim marker holds a PR.** A plain human or bot status comment is
  not a claim. Match the bot's own claim string; matching "any comment exists"
  lets one comment freeze the PR forever.

A behind-main PR must be rebased even when it carries a status comment.

## The mount trap: a repo slug exported as `REPO` becomes a docker volume source

Bot jobs export `REPO=owner/repo` (the slug) because the sweep targets read it.
Make treats an environment variable as an override of `REPO := $(shell pwd)`, so
`docker run -v $(REPO):/repo` expands to `-v owner/repo:/repo` → "includes
invalid characters for a local volume name", or a confusing
`exec scripts/…: permission denied` from the container init.

Fix: give the mount its own path variable with `override ROOT := $(shell pwd)`
and mount `$(ROOT)`; keep `$(REPO)` for the targets that need the slug. Keep the
image variable (`TEST_IMG`) in the same recipe — dropping it yields a `docker run`
with no image, which also surfaces as `exec scripts/…: permission denied`.

## Reading the failure

`exec scripts/x.py: permission denied` from a container init is almost never a
file-mode problem. Read the expanded `docker run` line first: a missing image or
a wrong `-v` source both produce that message.

Lock it with a test, but assert the mount where **both** hosts resolve it: read the variable out of
`make -p -n <target>` and require the checkout path there. A `make -n <target>` text assertion is
host-branched — on macOS the same recipe expands to a native venv command with no `-v` and no image, so
asserting the container shape reds `macos / unit` while the fix itself is correct. Assert the recipe
against the shape the host actually runs (`platform.system() != "Darwin"` → container), and keep the
slug-not-a-volume check in the recipe text on every host.

When a test splits workflow YAML text, split on a unique marker (the full `- name: …` line). Splitting
on a target name truncates at the first sibling that shares the prefix (`make auto-merge` inside
`make auto-merge-resolve`), and the assertion then reads half a step and reports a phantom failure.

Exercise the host you are not on before pushing, or the fix lands green locally and red on the other OS:
`make -e HOST_OS=Darwin -n <target>` prints the macOS expansion — plain `HOST_OS=Darwin make …` prints the
Linux one, because a makefile `:=` assignment beats the environment unless `-e` gives the environment
precedence. Pair it with a throwaway script that patches `platform.system()` to `Darwin` and re-runs the
test's own arm against that real output, and dump the base version of the test (`git show origin/<base>
:tests/<file>`) to prove the OLD assertion fails there while the new one passes — the two runs together are
the evidence the host branch is real and not a loosened test.

## A PR opened with the job token has no checks at all

`gh pr checks <n>` answering "no checks reported on the '<branch>' branch" for a PR that plainly exists means
no `pull_request` run was ever started — a pull request created with `GITHUB_TOKEN` triggers no workflows
(GitHub's anti-recursion rule). The gate is a `workflow_run` on CI completing, so it never fires either, and
the PR sits `BLOCKED`/`REVIEW_REQUIRED` forever with nothing red to look at.

Fix the CREATOR: open the PR with the owner PAT (a separate env var such as `PR_TOKEN` read by the publish
path, `GH_TOKEN` in the child environment for `gh pr create` only), while keeping the job token for
`gh issue create` where the PAT lacks Issues write. Consequence to expect: the PR's author is then the PAT's
account, which re-enters the self-approval case above — the second identity's token is what lands it.

Prove the split in the test by recording, per call, WHICH credential the fake `gh` received (write
`os.environ.get("GH_TOKEN")` to a side log) and asserting the PR create carried the PAT while the issue
create carried the job token — plus that neither value appears in the recorded argv.

When a run is still in progress, `gh run view --log-failed` refuses; use
`gh api repos/{repo}/actions/jobs/{job_id} --jq '.steps[]|{name,conclusion}'` to
name the failing step immediately. Fetching job logs needs
`gh api --allow-escape-sequences`, or the CLI rejects the ANSI output and leaves
an empty file.

`gh run view --log-failed` can also print NOTHING for a finished `workflow_run` job. Do not read that as
"no failure": fetch the job log directly and grep it —
`gh api repos/{repo}/actions/jobs/<job_id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g' | grep -E '\[auto-merge\]|At least|Error'`
— where `<job_id>` comes from `gh run view <run> --json jobs --jq '.jobs[0].databaseId'`.
