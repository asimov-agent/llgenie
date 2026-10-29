---
name: llgenie-pr-testing
description: Test a llgenie PR against its issue's acceptance criteria.
---

# Testing an LLGenie PR against its issue

Issue and PR numbers differ: `#824` is an issue; the PR implementing it is found with
`gh pr list --repo asimov-agent/llgenie --search 824` (PR title carries `(#824)`).

## Standing order (every reply)

Open every reply with one status line, then the detail — the planner's rule and the owner's:

```
BOT <profile> · working on #<id> · branch <ref> @ <sha> · since <hh:mmZ> · blocked on <x|none> · next <y>
```

- A report without an issue id, a branch (ref + sha) or a run id is not a report. "Verified" with no
  `gh run view <id> --json status,conclusion,headSha` behind it is not a verification.
- If you are working on something nobody dispatched, say so first, in that line.
- End with the one decision you need from the human, never a recap of what you just did.

## 1. Read the design before running anything

```
gh issue view <n> --repo asimov-agent/llgenie --json body,comments > issue.json
gh pr view <pr> --repo asimov-agent/llgenie --json body,files,headRefOid,mergeStateStatus
```

`## Acceptance criteria` and `## Technical` are the contract. **Comments can authorise a design that
contradicts the body** (a planner comment pivoting from matrix placeholders to trigger-level
`paths-ignore`); the newest authorised design wins — quote the comment when the body is stale.

## 2. Run the changed files' gates, not the whole pipeline

- Worktrees live under `/home/asimov/repository/git/llgenie-wt/<name>`; if the branch is already
  checked out there, reuse it and **leave it clean** (`git diff > patch`, `git checkout -- .`).
- **Run pytest inside the CI image, not with `--noconftest`.**
  `docker run --rm -u root -v "$PWD":/repo -v /home/asimov/repository/git/llgenie:/home/asimov/repository/git/llgenie -w /repo -e HOME=/root llgenie/test:latest python -m pytest <node ids> -q --no-header`
  is the unit stage's own environment: conftest loaded, no-skip rule enforced. `--noconftest` is how a
  `pytest.skip` fallback looks green locally and red in CI — conftest is what rejects skips, and it
  also pulls `scripts.llgenie_serve` (gguf+numpy), which is why people reach for `--noconftest` in the
  first place. Mount the MAIN repo as well as the worktree: a worktree's `.git` is a pointer outside
  the tree, so without that mount `git ls-files` returns nothing and per-path assertions pass
  vacuously.
- Make gates call plain `python3 scripts/*.py check`: put a scratch venv's `bin` first on `PATH` so
  `pyyaml` resolves (system `/usr/bin/python3 -m venv`, not the Hermes venv), then run each gate and
  print its exit code.
- **Kill long runs without killing yourself.** `pkill -f "<pattern>"` matches your own shell when the
  pattern appears in the command string you are typing — write it `pkill -f "[u]nit_tests\.py"` or
  kill by pid/session id. A killed `make test-unit` leaves the container running: clean up with
  `docker ps -q --filter ancestor=llgenie/test:latest | xargs -r docker kill`.
- **A worktree that smells of root cannot be removed, and `sudo` is not available to you.** A run
  with `docker run -u root` (the standard pytest recipe above) leaves root-owned files in the tree,
  so `git worktree remove` fails with `Permission denied` while `sudo` refuses for lack of a TTY. Do
  what the repo's own `CI_HOME_CLEAN` does — delete from a container, then prune:
  `docker run --rm --entrypoint sh -v <worktree-parent>:/r llgenie/test:latest -c 'rm -rf /r/<name>'`,
  `git worktree prune`, and `docker rm -f` any leftover `llgenie/test` containers before reporting.
- **Never report your own timeout as a repo failure.** `timeout N make <gate>` exits **124**, a
  SIGKILLed background job exits **137**: both mean *you* stopped it, not that the gate failed. The
  report must not carry an exit you caused — re-run with a larger cap or in the background first.
  Same for a cap that a network-bound gate cannot meet locally: say "exceeded my N-minute cap", never
  "the gate is red".

## 2b. CI job logs ARE readable — the 0-byte result is a gh guard

`gh run view <run> --log-failed`, `gh api .../jobs/<id>/logs` returning 0 bytes or nothing is NOT an
API limit. The job log carries ANSI escapes and `gh` refuses to print it:

```
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'
```

`gh run view --log-failed` additionally refuses while the RUN is in flight even when the JOB has
completed — read the job by id instead. Also worth knowing: `gh run view <id>` can report
`cancelled` for a run whose job genuinely FAILED (a later push cancels the run); judge red/green with
`gh api .../actions/jobs/<job-id>` (status+conclusion+steps), not the run conclusion, and never from
`gh pr checks`'s fail column.

## 3. Audit coverage against the diff, not against the PR body

For every changed path ask "which gate fails if this is wrong", then check a test proves it. The PR
body's "Measured:" block is a claim, not evidence — reproduce the counts.

## 4. Path-selection / CI-scope PRs: test the trigger against the repository

A `paths-ignore` filter and a classifier are two halves of one decision. Compare them over
`git ls-files`, applying GitHub semantics (`*` stops at `/`, bare pattern = root only, `**/` matches
zero dirs). Deriving a sample string from the pattern itself (`"**/*.md"` → `"*.md"`) is a tautology
that always passes — that shape hid a filter 43 tracked paths too wide.

Prefer invariants that can fail: every ignored path is docs-only; `ci.yml`'s ignore set equals the
replacement workflow's `paths`; every `ci.yml` job and every `pipeline.yml` stage is named by the
classifier (`engine-published-test` is the job id, `test-published-*` is the check family — compare
against `name:` prefixes, not ids).

## 5. Evidence discipline — a stale head is not evidence

- **Every verification line carries TWO shas (fleet rule 15, #873):** the PR head you tested *and* the
  `main` you compared against. Write it `run <id> · head <sha> · main <sha> · <n> passed / <n> failed ·
  <failing test names>`. A count without its baseline is a measurement of *some* tree, and the whole
  verdict on a red can turn on the pair: `4 failed on the branch` / `21 passed on main@<sha>` says the
  change is the cause, while the same 4 without the second sha reads as an unexplained red.
- **Bookend the work.** One comment when you start (issue or PR id, branch, the `main` sha you just
  fetched, what "done" means) and one when you finish (head sha, what changed, the run id or command
  that proves it, anything left open), in the thread where the work lives. A start with no finish is an
  abandoned claim; a finish with no start has no baseline to compare against.
- **Fetch immediately before you branch or force.** Branch and measure from `origin/main` as fetched in
  that moment, never from a branch you already had and never from a sha quoted in chat — a message is
  stale by the time it is read.

- **A failing test is evidence, and evidence is not a hold (fleet rule 13, issue #948).** Report the
  failing test name, the job id and the sha. If the failure is real, the issue is the remedy; if it is
  a flake, say so with the log line that proves it (the `engine-base-rocm` GHCR
  `net/http: request canceled` timeout is the precedent). Never convert a red check into a
  `do-not-merge` label — that turns a verifiable claim into an untracked absence, and a hold whose
  reason expired reads as abandonment on the board. If a hold *is* justified — a real defect, proven —
  name the resolving issue in the same comment and say what would clear it; a tag with no named remedy
  is indistinguishable from abandonment.

- Judge a run only by `gh run view <id> --json status,conclusion,headSha`, and only at the PR's
  **current** head. A force-push leaves runs at a dead head; they prove nothing about the branch now.
  `cancelled`/`queued` = **no verdict**, and `gh pr checks`'s `fail` column is never a failure count
  (it collapses cancelled runs and duplicate check names onto one word).
- **Judge the JOB, not only the run.** A run's conclusion can read `cancelled` while the job inside it
  reads `conclusion=failure` — cancelling the run after a job failed rewrites the run-level word. The
  job endpoint (`gh api repos/<owner>/<repo>/actions/jobs/<id>`) is the finer truth, and its `steps[]`
  array names which step died without needing any log. See `references/red-job-triage.md`.
- **Re-read a PR's state before you act on instructions about it.** A dispatch is a snapshot taken
  minutes-to-hours ago: check `gh pr view <n> --json state,closedAt,headRefOid` and
  `git ls-remote --heads origin <branch>` (0 refs = the branch is gone). A **closed** PR cannot be
  "now conflicting", and a rebase instruction for it is moot — answer with `closedAt` and the deleted
  branch instead of doing the work, or you will spend a cycle chasing a diff nobody can see.
- **A stacked PR that flips to `CONFLICTING` with a whole-tree diff means its BASE was rewritten, not
  that your commit broke.** The tell is the merge-base: `git merge-base <head> <base>` sitting several
  commits behind, with the diff equal to the base's own file set. Rebase onto the new base tip and the
  diff collapses back to your files; do not "fix" a conflict that is really a rewritten ancestor.
- **A stacked PR gets zero CI**: every workflow here gates `pull_request` on `branches: ["main"]`,
  so a non-`main` base schedules nothing. GitHub also retargets a stacked PR's base to `main` when
  its base PR closes — that drags the base commit into the diff, and a `.github/**` change then hits
  the wildcard and self-reports 22 of 22. Fold the commit into the canonical branch instead.
- The repo **forbids skipped tests** (AGENTS.md, enforced by `tests/conftest.py`): a test whose
  prerequisite is missing must provision it (e.g. a throwaway `git init` repo) instead of
  `pytest.skip`. Give invariants a loud failure when their input is empty too — a worktree's `.git`
  points outside the tree, so `git ls-files` is empty inside a container unless the parent repo is
  mounted, and an empty list makes per-path assertions pass vacuously.
- **A supersede-cancelled run says so in its job list, no logs needed.** `concurrency:
  cancel-in-progress` on `pull_request` means the next push kills the previous run; that run's jobs show
  the reusable caller (`linux`) as `completed/skipped` and **no child stage jobs at all** (`linux/unit`
  absent). That is "nothing ran", which is different from "a job failed and then the run was cancelled"
  (completed jobs with conclusions). Either way it is no verdict — find the run at the CURRENT head and
  judge that one.

## 6. Selection invariants to check before per-stage work (#824b)

`ci_scope.JOBS` gives `linux/openspec`/`macos/openspec` to the `docs` class only, so OpenSpec
validation is universal today **only** because `ci.yml` has no stage-level selection yet. Per-stage
selection must put openspec in `ALWAYS` (plus a test that every class selects it), or a
scripts-only PR silently stops validating specs. Likewise `docs.yml` runs `make ci-openspec` *after*
four gates that can fail first and without `if: always()` — a lint failure hides the spec validation.

## 6b. Finish the work: arm auto-merge (owner directive, 2026-10-29)

A verification that ends in a comment and no arm waits for a human instead of a merger. When the
testing work on a PR is finished — **last run**, verdict posted — arm it and report the arm time in
the same line:

```
run <id> · head <sha> · main <sha> · <n> passed / <n> failed · fails on main? <yes|no> · auto=squash @ <hh:mmZ>
```

- **"Done" triggers the arm, not "approved."** Do not wait for a human to say yes.
- **Exception: the owner explicitly refused that PR** → write `auto=none (owner instruction: <where
  the instruction lives>)` instead of arming. A silent omission is not the exception.
- **Arm only a `main`-based PR (fleet rule 16).** On a stacked PR the arm IS a merge: its base
  schedules no workflows and carries no required checks, so `gh pr merge <n> --auto --squash` has
  nothing to wait for and lands in seconds, unreviewed, in another lane's branch. An empty check list
  is not a pass and `--auto` there is not a queue position. A finished stacked PR records
  `auto=none (stacked base: no required checks, no CI scheduled)` and is armed **on retarget**;
  merging one by hand is a bypass, not a handoff.
- **After any arm, read it back** — `gh pr view <n> --json autoMergeRequest,mergedAt,mergeStateStatus`.
  An arm that reports `MERGEABLE` and then `MERGED` within seconds is the stacked-base tell, not a
  quiet queue position; report the merge commit and the arm time so the reviewer sees which of the two
  happened. `mergeStateStatus` alone cannot distinguish "waiting" from "already merged".
- **`AGENTS.md` bans `gh pr merge` for hand-merging** (`--squash/--merge/--rebase/--admin`), because a
  hand merge bypasses the merge-state check and pins no head. Arming native auto-merge
  (`gh pr merge <n> --auto --squash`) is not that: it waits for the checks and merges at the
  configured method. Never `--admin`, never a push to `main`.
- **A red is a verdict, not a hold** — the rule and its evidence shape live in §5; the only label it
  can ever justify is on a real defect **with the resolving issue named in the same comment**, never
  on a merged PR, never as "I am not confident".

Fleet rules themselves are changed through `agents/<profile>/`, not by editing the live profile: see
`references/agent-profile-versioning.md` for the sync, gate and stacked-base procedure.

## 7. Post evidence, never a merge

- **A result lives on the PR, with the run id and the sha** (fleet rule 14, #873): the shape is
  `run <id> · <sha> · <n> passed / <n> failed · <failing test names>`. A verdict delivered to one
  person is invisible to the lane that must fix it and to the next reader who must trust it — so the
  comment goes on the PR, and only the *pointer* to it goes into a message.
- **When another lane is repairing the PR, message it with the failing test and the run id instead of
  re-running into its push.** Re-running is a push into `cancel-in-progress`: it destroys the matrix
  that lane is waiting on, and the result it was going to produce.

Comment on the PR with the run ids / command output that proves each claim, plus the RED test that
exposes each gap and the patch that turns it green. Comment on the issue too when the follow-up
sub-issues the body promises do not exist yet (`gh issue list --search 824b`). Do not push to or
merge a branch you do not own. Arming auto-merge on a PR this lane finished (§6b) is a different act
from approving or hand-merging: it never bypasses the merge-state check, and it is only ever used on
a PR whose base makes the arm mean something.

Stop producing duplicate PRs. Before opening one, check `gh pr list --state open` for a PR on the
same issue and read its comments — this repo closes several duplicates a day, and a tester's delta
usually belongs ON the owner's branch (push it, or leave it as a named branch + sha in a comment).
**Verify absorption by diff, not by claim**: `git show origin/<their-branch>:<file> > /tmp/theirs`
then `diff` against yours and count lines/cases, before you believe "your work is already there".

## 8. Fix the baseline before any expectation

Expectations are a property of a BRANCH, not of the issue text. Two open PRs for the same change can
carry different class tables — one still matching markdown by extension, one matching directories —
so the same probe path yields **different counts on each**, and a row measured against the wrong one
is a red row that is not a defect. Before promising or measuring rows:

1. Name the merge candidate (the branch that will land) and its sha, out loud.
2. Re-derive the expected column at THAT head through the **CLI**, never the library: the library
   entry point can report a narrower decision than the command the workflow runs (measured: 3 of 22
   from `scope()`, 22 of 22 from `ci_scope.py jobs`), so a table built from `scope()` is a table of
   the wrong number.
3. Record the base sha in every row, and re-read `gh pr view <n> --json headRefOid` before and after
   each batch: shared branches move under you mid-session. So do shared WORKTREES — another lane can
   check out its own branch in the directory you were using, so `git rev-parse --short HEAD` before
   and after every command batch, and create a worktree named for YOUR task rather than reusing a
   branch-named one.

If two PRs claim the same change, say so and ask which is canonical instead of picking one.

## 9. Triage a batch of red PRs — reproduce locally, fix nothing

When dispatched to "find what the issue is" across several red PRs, your deliverable is the diagnosis,
not a patch. A fix from the test lane competes with the implementer's branch and gets closed.

1. **Read the job log first — it is readable (§2b), and it names the failing tests.** `--log-failed`
   being blank is a `gh` guard plus the run-in-flight rule, not an API limit; fetch the job by id with
   `--allow-escape-sequences` and grep `FAILED tests/`. Only when that is truly unavailable fall back
   to `steps[]` + `started_at`/`completed_at`: duration is a signature — a job that dies just past the
   wait cap a script declares died of that cap, not of an assertion.
2. **Reproduce in a clean worktree at the exact head** (`git worktree add --detach … <sha>`), run the
   *narrowest* command that could produce the failure first (the changed test file, then the gates in
   the job's order) — never the whole suite as the first move.
3. **Run the same command at the branch base sha** for the control. "Does not reproduce on main" is a
   claim only when you actually ran it there; that single comparison is what separates "this PR broke
   it" from "pre-existing red", and reviewers ask for it first.
4. **Report per PR**: failing node ids (or gate target), the assertion/verdict line verbatim, the exact
   command, and the base-sha result. One consolidated comment on the tracking issue plus a one-liner on
   each PR, so implementer and reviewer read the same evidence.
5. **Never invent a diagnosis when the failing piece is unreachable locally.** Name what you ruled out
   (each gate + each changed test file, with counts) and what remains, and say which environment input
   would let the next run catch it. An enumerated "ruled out" list is a finding; a guessed root cause
   is not.

**A batch of reds is usually several causes — bisect by commit before reporting**, never by the
issue title. The recipe, with the measured split, is in `references/red-job-triage.md` §7; the rule it
encodes is that a dispatch saying "one failing check each" often hides one shared cause plus one that
is genuinely the branch's own.

## 10. Verify a FIX PR — a fix that skips its way to green is worse than the red

When dispatched to verify the PR that closes the triage issue, the question is not "is it green" but
"did it delete the assertion or correct it".

1. **Re-derive the failing set at the HEAD, not from the issue text.** Run the exact node ids the red
   job named (`pytest <id> <id> … -q -rA`): every one must print `PASSED`. `-rA` is mandatory — a
   suite-wide `N passed` hides `N-1 passed, 1 skipped`, and the repo treats a skip as a broken
   prerequisite being masked.
2. **Prove nothing was deselected into green.** The suite roster lives in
   `tests/fixtures/unit-suite.json`; if the PR edits it (or a `deselect`/`excluded` entry appears for
   the time of the fix) that is the finding. Then run the four whole files, not just the ids.
3. **Read the assertion diff.** Updating an expectation to the new shape is a fix; deleting the
   assertion, relaxing it to `assertTrue(...)`, or removing a caller from a loop that still has other
   callers is a weakening. An *inverted* assertion that now proves the absence is stronger, not weaker.
4. **Check an inline call became a target, not an exemption.** If the fix moves `python3 scripts/x.py`
   out of a workflow step, run the new target's truth table directly (each branch of the decision) and
   confirm the fail-closed case too.
5. **Re-run the PR's own gates** (`check-workflows`, `check-wiring`, `check-docs`,
   `check-dispatch-forms`, `check-pr-hygiene`; add `check-pr-authors` when the branch came from a bot).
6. **State the CI leg separately.** Local green + a `queued` run is NOT a verification: report
   "local verified, run `<id>` still queued — capacity, not a verdict" and post the job conclusion
   when it lands. Never let a local pass stand in for the run id a reviewer will look for.
7. **Re-check the head before you trust your own pass.** A shared branch moves under you mid-batch
   (`gh pr view <n> --json headRefOid` before and after), and then every earlier local result AND every
   earlier run id belong to a dead head. Fetch, read the delta (`git log --oneline <old>..<new>`), redo
   the node ids and the whole files at the new head, and re-run the identity/gates — the follow-up push
   often *strengthens* what the first pass relaxed, so do not report the earlier tree's diff as the fix.
8. **The named tests passing is not the stage passing.** A `make ci-<stage>` chain stops at the FIRST
   failing target, so the red you were handed can hide a second one behind it — in the same stage an
   author-identity gate, a wiring gate, a docs gate. Re-run the chain, or at minimum every gate listed
   after the tests, before calling the stage green, and reproduce a single gate with its range pinned
   (`make check-pr-authors PR_BASE=<base sha> PR_HEAD=<head sha>`). Enumerate commit authors with
   `gh api repos/<owner>/<repo>/pulls/<n>/commits` — `gh pr view --json commits` can come back with an
   empty authors list — and treat a bot identity outside the allowlist as the usual cause; the gate's
   own message names the remedy (`git config user.email <allowed>`, `git rebase --reset-author`,
   `git push --force-with-lease`,   in the SAME push as any test change or it reds again).
9. **Re-check the other reds by patch identity, not by eyeballing the head.** Once the fix merges, a
   red PR can be "main-wide" (nothing of its own changed) or "own" (its content changed too) — and
   the only cheap proof is the patch id of the PR's own diff:

   ```
   git diff <old base> <old head> | git patch-id --stable    # before the rebase
   git diff <new base> <new head> | git patch-id --stable     # after
   ```

   Identical ⇒ pure rebase, so the red was inherited from the default branch; different ⇒ the branch
   changed content and its greenness proves nothing about the earlier red. Do this per PR instead of
   comparing file lists, and report it as a row per PR.
10. **One PR can hold two reds with different owners.** A single "./linux / install" or "./linux / unit"
   red may be the main-wide assertion set *plus* its own structural failure (a gate that waits for an
   artifact only the publish path on the default branch can create). After a main-wide fix lands, say
   per red which one it is: "this rebase clears the unit red; install stays red for its own
   wait-for-published reason". Never let "the red was main-wide" swallow the reds that are not — a
   rebase cannot publish an image, and that PR's reviewer needs to know it will still be red.
   If that structural red later turns green before its own merge, do NOT credit the branch or the
   rebase: read the job log for the line that resolves the artifact (`[install] every image install
   pulls is published` plus the tag it installs from), and report that the red cleared **by
   publication**, naming the tag. Then correct your earlier prediction out loud — the mechanism was
   right, and what changed was the artifact, not the diff.
11. **Verify the fix on the merged content, not only on the PR head.** After merge, re-run the same
   node ids at the default-branch sha and quote the merge commit + the run id whose job was green;
   "the PR was green" and "the branch is green" are two different statements a reviewer will ask for
   separately.
