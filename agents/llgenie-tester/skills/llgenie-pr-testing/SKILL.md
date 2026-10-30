---
name: llgenie-pr-testing
description: Test a llgenie PR against its issue's acceptance criteria.
---

# Testing an LLGenie PR against its issue

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `code_execution`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `containerized-repo-verification`, `github`, `llgenie-pr-testing`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

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
  the tree,  so without that mount `git ls-files` returns nothing and per-path assertions pass
  vacuously.
- **A git-dependent GATE run inside the container on an unmounted worktree fails with a MISLEADING
  message, not a vacuous pass.** `scripts/check_architecture_census.py` and any gate that shells out
  to `git cat-file`/`git ls-files` inside a `-v "$worktree":/repo` mount (no main-repo mount) cannot
  resolve the worktree's gitfile: it reports `the doc's pointer \`<sha>\` is not a real commit` and
  `tracked=0, testspp=0, changes=0` — which reads EXACTLY like a real dangling-pointer defect but is
  the container artifact. Distinguish it before believing it: a dangling pointer from the actual
  gate-defect class (§11) is ONE sha and the counts are non-zero; an unmounted-worktree run blames
  EVERYTHING (`tracked=0`). Git-dependent gates need no pytest — run them on the HOST in the worktree
  (`python3 scripts/check_architecture_census.py check`), where git resolves; keep pytest in the
  container (it needs no git).
- **A test that does `import scripts.<x>` dies at COLLECTION on a sibling import.** If the module under
  test itself imports a sibling on `scripts/` (`import base_ref`), `python -m pytest` inside the image
  exits 2 with `ModuleNotFoundError: No module named '<sibling>'` and an empty summary — which reads
  like a hang, not a collection error.  `scripts/` is not on the image's path by default; run the
  container with `-e PYTHONPATH=/repo/scripts`. The repo's `make test-unit` already sets this up;
  your ad-hoc run has to do it by hand.
- **Captured output goes through a host-absolute path, never `/repo/...` from the host shell.**
  `docker run … python -m pytest … > /repo/x.txt` is redirected by YOUR shell, not the container, so
  the file lands at the host's `/repo` root (root-owned, invisible to `ls /repo`) or the redirect
  fails before docker even starts. Write to the worktree by full path —
  `> /home/asimov/repository/git/llgenie-wt/<name>/x.txt` — and read it from the host that already
  owns the tree. Same for a `PULSE_DONE` marker: `echo … >> "$OUT"` on the same absolute path, and
  wake on the marker line.
- **To learn where a slow stage's time really goes, run `--durations=N` over the suspect files, not
  the whole suite.** The full unit suite here is ~10× slower locally than in CI because the
  Hub-touching tests crawl unauthenticated; `pytest --durations=20 <files>` on the named suspects
  gives the slowest in minutes, while a whole-suite run is a multi-hour job. Reference-counts and
  real network-opens differ — execution (`--durations`) is the ground truth, a grep of URLs is only
  the candidate list. See `references/network-test-audit.md` for the audit-and-route recipe.
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
completed — read the job by id instead. **A `completed/success` run is not the stage verdict if it
is the WRONG workflow** — this repo has `guard`/`scope`/`holds` and `CI` workflows, and a green
`holds` run (jobs `guard`,`holds`) says nothing about `linux / unit`. Enumerate the jobs and match
the stage name (`linux / unit`), and check the run's `workflowName`, before citing a run id as
"unit green"; a success run of `guard`+`scope` has no unit job at all. Also worth knowing: `gh run view <id>` can report
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
- **A stage gate that a policy test classifies can red on classification, not on the gate's own
  correctness.** Wiring-invariant tests (`test_the_real_tree_is_wired`-style) run a policy module
  (`issue_bot_gates.check`) over the real Makefile: any `make` gate a stage runs that has no entry in
  the policy's FAST/DEFERRED sets is a finding. The fix is a DEFERRED entry WITH a reason — the FAST
  set is a frozen list (widening it is a different issue's follow-up), so "add it to FAST" is not the
  default — not removing the gate from the stage. Reproduce the finding with the policy module's own
  check before escalating; it names the exact gate and remedy.

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
- **To check out a PR's actual head, fetch `refs/pull/<n>/head` — not the bare sha.** `git fetch origin
  <head-sha>` fails with "couldn't find remote ref" (a merge-ref-only or fork head is not a fetchable
  branch name), and the PR's `headRefName` may not be fetchable either. The reliable pattern,
  independent of the head's name, is
  `git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>`, then
  `git worktree add -d /path refs/remotes/pr/<n>`. Get the layout first with
  `gh pr view <n> --json headRefName,headRefOid,headRepositoryOwner`.
- **A supersede-close is a branch-owner act, and it must land AFTER the replacement merges — never
  before.** When you close one PR as "superseded by #X", the residue (the marks/pin/delta #X exists to
  carry) must already be provably on `main`, or you strand it on an open PR whose merge is not yours to
  force. Sequence: the co-owned PR gets co-owner consent for the close (rule 14 — never close/arm/merge
  a co-owned PR unilaterally), the replacement MERGES, you read back its marks/pin on the default
  branch, THEN close. Closing a superseded PR while its carrier is OPEN is a premature close that
  silently re-opens the gap if the carrier never lands — and, because the owner can close it at any
  time regardless, re-read `--json state` before doing anything the close authorizes.

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
`references/agent-profile-versioning.md` for the sync, gate, stacked-base, **local-vs-remote
verification** (a green `--check` in your worktree is not a fix on the branch that lands — `git show
<branch-head>:<file>` matching live is) and **landing behind a live run** (a `gh run watch` watcher
that pushes on the run's conclusion, never a push that cancels it).

## 7. Post evidence, never a merge

- **A result lives on the PR, with the run id and the sha** (fleet rule 14, #873): the shape is
  `run <id> · <sha> · <n> passed / <n> failed · <failing test names>`. A verdict delivered to one
  one person is invisible to the lane that must fix it and to the next reader who must trust it — so the
    comment goes on the PR, and only the *pointer* to it goes into a message. The FINISH line (head sha +
    PR number + what stands) also goes to the inbox/triage bot in the same turn (the orchestration
    protocol): "done" is not complete until that lane has the finish line, and new reviewable PRs it
    routes go to the reviewing lane — this lane does not review its own PR.
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
- **"It's already on main" is an existence claim — check the CRITERION attribute, not the file.**
  A change that lands via another merge can carry the whole seam (workflow, marker, pin file, the
  gate check) yet still lack the coverage the acceptance criterion actually requires: the file
  `test_network_marker.py` and a working `-m "not network"` seam are on main, but if zero of the
  real-Hub tests carry `@pytest.mark.network`, ci-unit executes them for real while reading green —
  the exact directive the criterion forbids. Before declaring a branch superseded/redundant, count
  the criterion's OWN attribute per element (the marks ON the real-call tests, not the marker
  registered;  the coverage enum, not the roster file existing; the routing decorators, not the pin
  present). Artifact existence is not criterion met — file-present + green is exactly the shape that
  hides a still-open gap.
- **An exact-equality membership pin and the routing marks are ONE decision, edited in the same
  change.** A pin that asserts `marked == EXPECTED` (the network-membership census) must have its
  `EXPECTED` set widened to the new mark count in the SAME change that adds the marks — a mark that
  lands without the census update reds the pin that was protecting the set, and a census left at the
  old count while the marks grow is the pin failing closed, not a spurious red. When you widen the
  marked set, grep the pin file for the exact-equality assertion and update both sides together;
  verify afterwards by counting marks total across the changed files (mark count == census entry
  count).

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
- **Two lanes on one shared branch: push `HEAD:<branch>` with `--force-with-lease` pinned to the
  just-fetched sha, never a bare force.** When the branch is checked out in ANOTHER lane's worktree,
  `git checkout -B <branch>` fails ("already used by worktree"); set up by pushing your rebased
  detached head directly:

  ```
  git fetch origin <branch>; R=$(git ls-remote origin <branch> | cut -f1)
  git rebase origin/<branch>                      # your commit on top of THEIR latest
  ... re-run the changed tests (their push landed under you) ...
  git push origin HEAD:<branch> --force-if-includes --force-with-lease=<branch>:$R
  ```

  The lease pinned to the fetched sha makes a concurrent push between your fetch and push REJECT
  instead of clobbering — then re-fetch, re-rebase, retry. Read `$R` immediately before the push; a
  shared branch moves even while you are writing the message.

If two PRs claim the same change, say so and ask which is canonical instead of picking one.

## 8b. A shared rewrite's failure modes: the route through them, not the retreat

- **`origin/main` is not a stable onto target on this repo — name the sha.** An ambiguous ref that
  resolves to the wrong base lets a rebase absorb real commits as patch-equivalent noise and SILENTLY
  DROP them (a replay stopped ~6 commits short of the documented tip). Never
  `git rebase --onto origin/main …`; fetch then pass the explicit full sha
  (`git rebase --onto <full main sha> …`). Before trusting a re-cut, diff the net tree against the
  documented tip (`git log --oneline <dropped-candidate>..<new head>`); a content check
  (`git diff <head> <owned compose>`) that is empty is the real convergence proof, not "my pin passes".
- **`git rebase --continue` can hang in a worktree that has done a lot of this, even with
  `core.hooksPath=/dev/null`.** The hang is in `--continue`'s COMMIT step, not in the pick or the
  restart: a bare `--continue` on an unresolved conflict returns fast (\"fix conflicts\"); it only
  hangs once it actually creates the commit. When you are already mid-rebase, resolve the conflict,
  `git add`, then create the pick yourself with `git commit --no-edit` and call `--continue` again —
  it resumes cleanly. A fresh worktree does NOT dodge it, so don't restart hoping for a clean run.
  Alternatively `git cherry-pick` the commits in order is the robust substitute: it applies or STOPS
  per commit (never silently skips), so a re-cut advances with a visible stop at a real conflict —
  resolution becomes per-commit, not a mystery drop. `--skip` any pick whose content already landed
  via another merge (the old name/lineage of a renamed-and-merged file renders it empty on the
  rebased base). Prove the net tree (commits present, wiring/test invariants green) BEFORE any push.
- **`mergeable_state=dirty/CONFLICTING` right after a force-rewrite is usually a stale recompute, not
  a real conflict — verify lineage, then wait for a fresh event.** The head is literally `main` +
  commits when `git merge-base --is-ancestor origin/main <head>` is true; combined with a clean
  `git merge-tree $(git merge-base origin/main <head>) origin/main <head>` it cannot fail to
  auto-merge, so GitHub's `mergeable=false` is its cached merge-base from before the force. Do NOT
  re-force-push to "fix" it; a fresh CI run or push event recomputes it. Settle a "my commit is not on
  your head" dispute the same way: ancestry/content, or `git log` for the origin sha, not by pushing
  again.
- **The decisive clean/conflict test is `git merge-tree --write-tree <base> <head>`, exit=0 = clean.**
  The old 3-arg form prints `changed in both` for ANY same-file edit and reads as a conflict even when
  the hunks are far apart (a PR marking tests at :949/:964 and a base commit editing unrelated
  assertions at :597 of the SAME file). `--write-tree` decides on the tree, not the file list — exit 0
  means the PR merges cleanly into that base, period. When a dispatch says "rebase your assigned PR
  onto fresh main", FIRST measure `--write-tree base fresh-main`: a clean exit VETS the branch against
  the new base with no rewrite, and force-rebasing a co-owner's non-Conflicting branch is an
  unnecessary rewrite + a pointless fresh CI run. "Rebase only when actually CONFLICTING" means: prove
  the conflict with the exit code, or leave the branch alone.

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
   callers is a weakening. An *inverted* assertion that now proves the absence  is stronger, not weaker.
- **A fix that WIDENS a gate (allowlist, alias map, roster) passes its own gate trivially — the
  negative control decides it.** A green badge on a widened set proves nothing about the hole the
  widening is supposed to keep closed. Run, through the guard's own entry point over throwaway
  `git init -b main` commits, all three shapes: a valid case that must still pass, the genuine
  breakage the widening exists to stop (the real typo), and a lookalike that must still fail. Report
  the verdicts (`violations=0` / `violations=1` with the evidence string) with the command output, not
  the CI badge — a tester's one-line "passes on the positive case" is the same hole as an assertion
  that proves nothing.
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
   **But first rule out the stale-base artifact, or you will reset-author a clean branch.** When the
   CI ran with an old `PR_BASE` (a bot PR's base lagging `main`), main's newer commits sweep into the
   range through the merge ref — an ALLOWED identity with a differently-spelled name (the gate matches
   on email+name) triggers the red even though none of the PR's own commits violate it. Diagnose
   before touching history: run `check_pr_authors --base <current main sha> --head <branch head>`
   locally — RC 0 means the branch's own commits are clean and REBASING onto current main clears the
   red by itself; `--reset-author` is only for a genuinely unallowlisted commit.
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

## 11. A per-PR "measured at" census pointer is a gate-defect symptom — do not chase it per PR

`scripts/check_architecture_census.py` reads a `measured at \`<sha>\`` pointer from
`docs/ARCHITECTURE.md` and asserts the doc counts match the tree. When a PR reds because that pointer
is a now-dangling sha (a rebase/squash gc'd it) or the counts are stale, the instinct to *re-point it*
on the PR is the wrong fix: the gate takes the checked-out HEAD as ground truth, so **every
file-adding PR must rewrite the pointer, and it dangles again after the squash** — an endless
per-PR chase, and a second vehicle on a branch the rebase lane may already have moved.

Diagnose the class before touching the pointer:

1. **Is the gate's ground truth the PR head or the merge commit?** If it re-measures at HEAD (it does),
   the pointer is not a per-PR fact — it is a gate-design defect (#1053).
2. **Does the red vanish on a plain rebase onto current main?** A branch behind `main` carries a stale
   copy of `ARCHITECTURE.md`; rebasing onto current main inherits the correct pointer + counts, with no
   per-PR edit. Check with `git merge-tree --write-tree <main> <head>` (clean) and diff the two
   `ARCHITECTURE.md` pointers — if the branch does not *modify* the file, main owns it.
3. **Many PRs redding the same way is ONE gate bug, not N branch bugs.** Hold the per-PR pointer edit,
   do **not** push a second fix onto a branch the rebase lane already rebased (that cancels their live
   run and duplicates the fix), and wait for the gate-source fix (#1053) to land. Then rebase +
   re-verify (unit green + the marks/pin) after it lands and main moves.

Rule: a `measured at <dangling sha>` or stale-count red is a **gate-ownership smell first, a branch
defect second**. Re-pointing it per PR is the symptom-chase #1053 exists to end. (Learned on #1016:
the pointer `348f7b4e` was a non-object; the real fix was #1053 at the gate source plus a rebase onto
current main — my independent rebase and the rebase lane's landed on the identical tree, and no push
was needed.)
