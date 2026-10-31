---
name: llgenie-architecture-issue-pass
description: "Audit llgenie architecture and file refactor issues."
version: 1.2.0
metadata:
  hermes:
    tags: [llgenie, architecture, github, issues, refactor]
    category: software-development
    related_skills: [github, codebase-inspection]
---

# Architecture pass

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`, `web`.

Skills that stay enabled: `github`, `llgenie-architecture-issue-pass`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

A structural audit of this repository that ends in issues another bot implements. This is the contract a
host agent runs when the owner says "go over the architecture and file the refactoring work". It is the
HOST half of the fleet: no CI leg preloads it, and it is admitted by name in `HOST_SKILLS`
(`scripts/check_agent_skills.py`) so every admission is a reviewed diff.

> **Provenance:** this file is the host-profile mirror of
> `.hermes/skills/llgenie-architecture-pass/SKILL.md`, which is the canonical copy — it is admitted by
> name in `HOST_SKILLS` (`scripts/check_agent_skills.py`) so the repo copy is gated like any other
> skill. Exactly three things may differ: `name:` (Hermes requires the directory's name),
> `description:` (Hermes caps it at 60 characters) and this paragraph. **A change here is mirrored
> there in the same pass**, and the two are diffed after normalising those three — checked, not hoped.

## Inputs

- **`origin/main`**, and its sha taken from the API, never from the checkout's `HEAD`:
  `gh api repos/asimov-agent/llgenie/commits/main --jq .sha`.
- A read-only tree of that commit — the working checkout is routinely parked on a PR branch:

  ```bash
  cd /home/asimov/repository/git/llgenie && git fetch origin
  git worktree add --detach ../llgenie-wt/<name> origin/main
  # 0 modified files, real main; `git worktree remove` it when the pass is done
  ```

- `docs/ARCHITECTURE.md` §Scripts (the grouping the tree is supposed to have) and `AGENTS.md` (the house
  rules a finding must not contradict).
- The open + closed issue list: `gh issue list --state all --limit 900`. A finding already filed is a
  comment on that issue, never a second issue.

## Output

- One issue per finding, labelled `agent:implement`, rendered through `scripts/issue_body.render`
  (`Problem`, `Why it matters`, `How we fix it`, `Benefit`, `Acceptance criteria`, optional
  `Not covered`, `Technical` last) — the marker is the body's first line and is what dedupe reads back.
- The baseline sha in each body's `## Technical`, plus the method that produced every count.
- One cross-reference comment per issue naming the dependency order, and a hand-off to the planner to
  triage rather than an assumption about capacity.

## Rules

- **Report at the end of EVERY pass — working on, finished, blocked on — even when the answer is "nothing assigned".** Silence is indistinguishable from a dead lane on the inbox's board, and a lane it cannot see gets force-delegated work it already completed (or cannot be delegated to at all). A pass that ends with only an internal "standing by" and no message to the inbox has NOT reported. The report names a measured blocker, not a mood: "blocked on <PR> merge — `agents/` is 0 files on `main`, so the versioning PR cannot open without becoming the second stack the issue forbids", then names what you are doing instead of sitting idle. Verifying that a directive's object exists is the same discipline as verifying an instruction's sha. **And a pending-list in your own report is a claim about PR state — re-read each PR's `state` before calling it "stacked, unarmed, waiting on <parent>".** A PR that has already merged is not stacked: it rides the parent into `main` and must be dropped from the pending list, or the inbox corrects a lane that is reporting done work as outstanding. The check is one command per PR (`gh pr view <n> --json state,mergedAt,mergeCommit`), and `MERGED` is the value that removes it — not "it was open last time I looked".
- **"Refine the nearest unrefined issue" is only work if an unrefined issue exists — scan before you refine.** Every open `agent:implement` issue may already carry full acceptance criteria (measured: all 30 unassigned ones did, and the flagship one the planner named was already Problem/Proposal/Requirements/Acceptance). Reading them is not the task; confirming none needs refinement, then falling back to the standing mandate (file a measured refactor issue), is. Refining an already-refined issue, or sitting idle because "nothing needed refining", both fail the lane's purpose.
- **Measure `origin/main`, never the working checkout.** `/home/asimov/repository/git/llgenie` is often
  parked on a feature branch; six issues were once filed against a PR tip while claiming `main@<sha>`.
  Take the sha from `gh api`, cut a detached worktree, and write that sha into the issue.
  **The rule applies to a REF, not just a sha: a failing CI run is evidence about the branch it ran on.**
  `gh api .../runs/<id> --jq .head_branch` names it, and a defect read from a PR's run is that PR's to fix,
  not rot on `main`. Read the branch before writing "this gate is red on `main`" — filing it as repo-wide
  turns a one-PR bug into a phantom repo bug that the wrong lane then owns. Cheap disproof: run the named
  tests at a detached `origin/main` worktree. Green there and red on the branch means the branch introduced
  it (often a PR that *adds* the file the test rejects, which reds every PR after it merges — so it is a
  merge-blocker on that PR, not a follow-up issue).
- State the counting method next to every count a reviewer could reproduce differently: targets come
  from `make -qp`, not a line regex; "files containing the call" and "test modules containing the call"
  are different denominators and must be named.
- **Cite the invariant, not one number.** Two correct measurements can look like a disagreement: `stat`
  bytes vs `len()` characters (multibyte dashes), or a merged-tree sha that changes with merge order.
  Write "byte-identical, 55 lines" and "three conflicted files, no more, no fewer" — each survives the
  unit or ordering ambiguity that a lone figure does not.
- Name the population a count is drawn from when two counts share a number. "Eleven wrappers" meant
  three different elevens in one pass (the names, all helpers, and the bodies that never read an exit
  code); the implementer greps the narrowest one and under-scopes the fix.
- A file path or line number in an issue is a claim: read it at the measured commit, not from memory or
  from the branch you happened to be in. **And a finding whose `where:` cannot be opened from the repo root
  is a defect in the REPORTER, not in the tree.** Probe it by running the gate against a differently-named
  root (`--root /tmp/<odd-name>`): if the printed path starts with `<odd-name>/agents/...`, the path is
  computed one parent too high (`agents.parents[1]` sits above the repository). Two path conventions in one
  output is how a reviewer stops trusting paths and starts grepping. Recipe:
  `references/verification-and-rebuild.md` §6.
- Read the label back after filing (`gh issue view <n> --json labels`) — a create-flag label can be
  silently dropped on a CI token path.
- Reference linked issues by NUMBER in the body. "the issue linked below" breaks the moment bodies are
  regenerated and edited out of order.
- A finding about someone else's code is an issue, and the change is another leg's PR — never implement
  it from a pass. **A finding about your own behaviour artifact is the exception**: when the rule that
  failed lives in a skill, a SOUL or a procedure doc, carry it into the tree yourself as an issue **and**
  a reviewable PR. Filing the issue and stopping leaves the rule outside version control, which is the
  defect you just filed. Never merge, never push to `main`, never edit `AGENTS.md` (owner approval).
- Copy the mechanism from the tree, not from imagination: `git diff origin/main...<branch>` of the closest
  precedent and match its shape, so the second instance is a one-line neighbour rather than a second
  design. Check whether that precedent is merged; if it is not, say in the issue which of the two lands
  first, so the conflict is one line either way.
- Verify a gate you touch by **negative control**: break the thing, run the gate, confirm the exact
  finding key, restore. Restore from a copy taken before the sabotage — `git checkout -- <file>` restores
  HEAD and silently discards your own uncommitted work in that file.
  **Then verify the sabotage LANDED before you trust the green.** A control that patched the wrong
  occurrence, or the wrong function's body, leaves the suite exactly as it was — and an unchanged suite
  looks identical to a passing control. `grep -c '<the exact phrase you deleted>' <file>` must read `0`, or
  call the function and see the wrong value, *before* you run the suite. Two silent no-ops in one session
  (`s.index(...)` matching an earlier occurrence, then a sabotage inserted into the neighbouring function)
  each produced a confident "controls fire" claim that was false. Recipes:
  `references/verification-and-rebuild.md` §1.
- **An allowlist or exclusion is proven by trying to WIDEN it, not by reading it.** A skip-list is only
  safe if it is scoped to the exact thing it excuses, so attack it: copy the excused file to another
  name, invoke it by absolute path, by `./`-prefixed path, from a different cwd, with an absolute
  `--root`, and add a fresh offender in another directory — every one of those must still be REFUSED.
  An exclusion implemented by directory or by content pattern fails open on exactly those cases; one
  exact path does not. Pair it with a `--include-self`-style flag that judges the excused file on
  demand, so a reader can see what the exclusion buys instead of trusting a constant.
- A gate that matches a **substring** proves nothing: `if section not in body` still passes a body whose
  heading was renamed to `## Rules for reviewers`. Read the matcher before citing a gate as evidence, then
  measure every committed instance before tightening it — when they all already comply, tightening is free
  and it is what makes an acceptance criterion real rather than rhetorical.
- Keep the profile mirror and the repo copy in step: normalise `name`/`description`/provenance and diff
  them. Drift between the two is a finding, not a chore for later.
- A criterion that names TWO docs hides a second owner: `grep -rln '<subject>' docs/ AGENTS.md README.md`
  before saying the documentation is done. The queued alarm was described in `docs/BOTS.md` *and* in a row
  of `docs/ARCHITECTURE.md`'s cron table, and only the first got the fix until the criterion was re-read.
- **Measure the discriminator you are about to publish**, not the one you were handed. A proposed test
  that reads "empty `runner_name`" was null on an `in_progress` job too, and "`startedAt` is null" was
  false because it is stamped at enqueue — the check would have shipped as guidance that answers nothing.
  Run each proposed field against one positively-known and one negatively-known case before it reaches an
  issue, a doc or an acceptance criterion. **And check that a second cause cannot produce the same
  value:** `mergeStateStatus` is `BLOCKED` both on a PR with a failing check AND on every PR here that
  merely has `REVIEW_REQUIRED`, so it cannot answer "are non-required checks advisory?". `UNSTABLE` is no
  better: measured on a PR whose 27 checks were 18 success, 1 skipped and 8 with **no conclusion** and
  zero failures, the field still read `UNSTABLE` — "a check failed" and "checks still running" collapse
  onto one value too. When causes collapse onto one value the field is undiscriminating: record the
  co-factors (`reviewDecision`, `isDraft`, and the `statusCheckRollup` conclusion buckets including the
  no-conclusion count) beside it, and isolate the variable with a **before/after pair on the same object**.
- A test that fails on the host for a missing dev dependency is **host-only**, not a regression: check
  `tests/fixtures/unit-suite.json` for its recorded alternative target, and confirm the same failure on a
  clean `origin/main` worktree before attributing it to your diff. Fixing a green-in-CI test on the host
  is work nobody asked for; reporting it as your own red is worse.
- `make openspec-new NAME=<name>` creates the change directory **root-owned** (the CLI runs `docker run -u
  root` against a `rw` mount), so the first write fails with EACCES — `sudo chown -R $(id -u):$(id -g)` the
  directory, then write. `sudo` needs the terminal tool's tty; a `sudo` inside a non-interactive tool call
  fails with "a terminal is required".
- A corrected number means correcting the BODY, not just adding a comment — the implementer reads the
  body.
- **A diff-based gate cannot see an uncommitted artifact, so "I added the note and it still says I didn't"
  usually means you have not committed yet.** A change→note rule reads the PR's diff (`base...HEAD`), not
  the working tree, so a note file sitting untracked is invisible and the gate reports exactly what it would
  report if the file did not exist. Commit the artifact, then re-run the gate, before concluding the rule is
  broken. The corollary for verification: when you test such a gate locally, the artifact must be in a
  COMMIT, and the gate needs the base ref in the environment it reads (`CHECK_DOCS_BASE=origin/main` and
  similar) — an unset base makes the rule skip silently with a "skipped" note that still exits 0.
- **Anchor a body edit on line-exact headings, never on a substring.** Section names appear in prose
  ("see `## Not covered`"), so `body.index("## Not covered")` slices at the mention and duplicates half
  the issue. Match `lines.index("## Not covered")` for the heading itself, and re-read the body
  immediately before writing: another agent's append to the same issue is silently replaced by your
  `--body-file`, so verify their content survived instead of assuming it did.
- **Judge a run by one completed run at the PR's head sha, and read `conclusion` literally.** `gh pr checks`
  prints `cancelled` as `fail`, and any jq that buckets "not success" into `bad` reports cancelled jobs as
  failures — filter on the explicit values (`failure`, `timed_out`, `startup_failure`) and report cancelled
  and pending as their own counts. State "N success, M pending, 0 failures", never "green".
- **When a run was cancelled, rerun it; never push to restart it.** `gh run rerun <id>` re-executes at the
  same sha with no new commit; a push cancels the requeue and costs the whole matrix again. Confirm the
  rerun took by `run_attempt` incrementing and `status` returning to `queued` — the attempt number, not the
  moment, is the evidence.
- **Before attributing a cancellation to your diff, check whether the head moved.** `cancel-in-progress`
  kills the previous run whenever the branch is re-pushed. `git diff <old-sha> <new-sha>` returning empty
  proves the tree never changed, so the run was superseded rather than broken — say that instead of
  investigating a failure that does not exist.
- **A path filter must match the change CLASS, never a file extension.** `**/*.md` also matches vendored
  data tables, skill contracts and test fixtures, each read by a gate the filter would skip. List the docs
  paths explicitly and pin it with a test; the path-to-gate table and the negative controls are in
  `references/path-selective-ci.md`.
- **A safety property must hold at EVERY entry point, not just the one the workflow calls.** A classifier
  whose empty/unknown-diff widening lives in `main()` returns the narrow 3-job selection when called as a
  library function — so tests, ad-hoc probes and any future caller get the unsafe answer while the CLI
  looks correct. Test the invariant through each surface (library call, CLI, `make` target) and diff the
  verdicts; where they disagree, the invariant is a property of the wrapper and belongs one level down. **Check EVERY public function in the module you touch, not only the one the issue names.** Fixing the widen-on-unknown in `classify()` left the sibling `select()` silently failing CLOSED on a mistyped class: `select(['tests_typo'])` returned 2 of 10 jobs with no raise, no stderr and exit 0 — the same quiet-empty-set defect one function across, reachable by the exact library caller the module's own docstring advertises. A safety property added to one function is a claim about that function, not about the module.
- **An assertion that rejects a CORRECT implementation is worse than no assertion** — it teaches the next
  person to edit working code to match the test. Assert the behaviour, not one spelling of it: accept
  `${{ github.base_ref || 'main' }}` OR a shell default `${X:-main}`, and use `>=` / `issubset` for
  "at least these events", never `==` on a set the implementation may legitimately grow. Prove the guard
  still reds by restoring the defect, then restore the file and confirm green.
- **Run a test with the real runner before calling it red.** A hand-rolled stand-in for `capsys` /
  `monkeypatch` reproduces the wrong shape and fails tests that pass; two "failures" survived exactly as
  long as the fake fixture did. If the stand-in is needed, make it **live**: `redirect_stdout` into a
  `StringIO` that `readouterr()` reads *during* the run, and call the function inside that context — a
  fake that returns an empty buffer after the call fails every test that prints. `scripts/run_test_functions.py`
  does exactly this. A missing dev dependency is host-only — check the CI image's requirements file for
  the pin (`pyyaml`, `pytest` live in `containers/ci-variant/requirements.txt`) before filing it as a defect.
- **A test name you cite, or a count you state, is a claim.** `grep -c '^def test_'` the file before
  writing "N cases" in a PR body, and grep the name before citing it in a workflow comment; a comment
  naming a nonexistent test and a body claiming one case more than the file held were both real, and both
  are caught by that one check. **The same check governs "nothing tests this":** a missing
  `tests/test_<script>.py` is not absent coverage, because a module is often exercised from a suite named
  after its consumer (`grep -rl '<script name>' tests/` before writing "no test file"). Declaring a script
  untested when it is covered elsewhere misprices the risk of changing it.
- **An empty or unclassifiable diff must WIDEN, never narrow** — empty widens and passes, unknown widens
  and stays red. `github.base_ref` is empty on `merge_group`/`workflow_dispatch`, so the classifier needs a
  `main` fallback or it diffs against `origin/`. Exit table and both controls:
  `references/path-selective-ci.md`.
- **`needs:`-gated job rows are created PROGRESSIVELY, as their dependencies resolve — a mid-flight count
  is a lower bound.** Watch one run and the total grows under you (19 rows while `engine-matrix` was still
  queued, then 25 once `engine-image` finished and `linux-published/*` materialised). So: quote a
  **completed** run's total, never a snapshot, and when a snapshot and a total disagree, the total wins.
  Do not "correct" a mid-flight reading upwards into a rule — say the count was taken mid-flight and
  re-measure at completion.
- **A new `workflow_dispatch:` is gated twice over.** `make check-dispatch-forms` rejects a bare
  `workflow_dispatch:` unless a COLUMN-0 line reads `# dispatch: no inputs — <reason>` (an indented one
  does not match the regex), and it also fails when the generated table inside `docs/BOTS.md`'s
  `dispatch-forms` markers is stale — regenerate with `make dispatch-forms-report` and paste it back.
  Run that target's `check` after adding any trigger, before claiming the workflows pass.
- **A probe whose arms ALL fail proves nothing — put a positive control in the same run.** Three labels
  starving at once is equally consistent with "this label cannot be provisioned" and with "nothing was
  ever scheduled", and a dispatch that returned 404 (`not found on the default branch`) or 422
  (`Cannot trigger a 'workflow_dispatch' on a disabled workflow`) never scheduled anything yet reads as
  evidence. Name the arm that must succeed, show that it succeeded in the identical run, then report the
  negative. Recipe, dispatch traps and the history-scan interpretation table:
  `references/runner-supply-probes.md`.
- **Verify a branch head's tests in the repo's test image, with the parent `.git` mounted too.**
  Bare-host pytest can exit 2 printing nothing because `tests/conftest.py` imports a module that hangs —
  a blocking import, not a missing dependency — so the silent exit is the harness, not the diff. Run
  `docker run --rm -v "$PWD:/w" -v "<main-repo>/.git:<main-repo>/.git:ro" -w /w <test-image> python -m
  pytest <files>`; from inside a linked worktree that second mount is REQUIRED, or every git-backed test
  fails with `fatal: not a git repository: .../.git/worktrees/<name>` and looks like a real red.
  **When a gate needs GIT HISTORY (not just files), a worktree mount is the wrong tool entirely — use
  `git clone --local <repo> /tmp/x && git checkout <sha>` and mount the clone.** A worktree's `.git` is a
  FILE pointing at `<repo>/.git/worktrees/<name>`, so no mount of the worktree directory alone can make git
  work, and a gate whose diagnosis is about a commit (a census pointer, a merge-base, `block in SOUL`
  against a historical sha) will fail in a way that reads as a repo defect. Measured cost: a
  `check_architecture_census` run from a worktree mount printed "the doc's pointer `564e938` is not a real
  commit (dangling from an amend?)", which was believed, reported upward and written into a PR body — while
  the same gate in a full clone printed `OK — referent 564e938 is an ancestor of HEAD`.  A gate that says
  "not a git repository" has measured YOUR MOUNT, never the tree: treat every failure whose text names a
  missing/bad/absent commit as unverified until re-run where `git rev-parse --git-dir` resolves.
  **A `git clone --local` of your own checkout inherits the source repo's STALE remote-tracking refs, so a
  just-pushed commit is absent from the clone and `git checkout <sha>` fails "did not match any file(s)"** —
  then `git fetch origin <branch>` inside the clone resolves against the stale local ref and cheerfully
  reports the OLD head, and `git log FETCH_HEAD` agrees with it. The clone then verifies the previous commit
  and returns a green that says nothing about your push. Repair in the SOURCE repo first, then re-clone:
  `git -C <main-repo> fetch origin '+refs/heads/<branch>:refs/remotes/origin/<branch>'`, confirm
  `git rev-parse --short refs/remotes/origin/<branch>` equals the sha you pushed, and only then clone. This
  is the "measure the apparatus, not the subject" trap in its most expensive form: a green suite on the
  wrong commit looks exactly like a green suite on the right one. **The API is the authority on which sha is
  the head** (`gh pr view <n> --json headRefOid`): when the API and your clone disagree, the clone is stale,
  never the API — do not report the clone's green as verification of that head until the clone's
  `git rev-parse HEAD` prints the API's sha.
- **A base retarget is the push-free fix for a misleading stacked diff — but a retarget you must undo
  later is worse than a body note.** `gh pr edit <n> --base <branch>` is metadata only, so the diff
  re-renders at once with no commit and no cancelled matrix. Use it when the new base is where the PR will
  land; when the base moves back after the parent merges, state the arithmetic in the body instead ("N
  files here, M are this PR's; the parent is not on `main` yet, so its files render here — self-correcting
  when it merges") and leave the base alone.
- **The "Nerve progress guard / no task-relevant mutation" message can be unsatisfiable — do not feed it.**
  It has fired mid-session after a commit, a push, a PR and a posted review, and kept firing across a dozen
  further mutations. Treat a repeat after real, verifiable progress as an environment mismatch, say so with
  the evidence, and stop: pushing code purely to make a checker move is the behaviour the repo's own #817 doc
  forbids. Keep doing the real work and verify each step against the remote (file read back, PR state, run id)
  rather than against the checker. **When a run is live at the head, this guard and the never-push-during-a-run
  rule resolve the same way: WAIT.** The only remaining "mutation" a starved `ci-unit` leaves available is a
  push, and that push cancels the matrix — so satisfying the checker would destroy exactly the evidence you are
  waiting on. The correct posture is: state the run's live step read (`gh api .../jobs/<id> --jq '.steps[]'`
  showing one step `in_progress`), say the work is done and the last gate is externally blocked, and hold a
  poller for the verdict — never push to make the guard stop firing.
- **A PR stacked on a non-`main` base gets NO CI, silently.** Every workflow here gates on
  `on.pull_request.branches: ["main"]`, so a PR whose base is another feature branch produces an empty
  checks tab — `gh run list --branch <head>` returns nothing, which reads like "still starting" and never
  starts. Check `gh pr view <n> --json baseRefName` before promising a run id, and if it is stacked either
  cherry-pick onto the real base branch or retarget to `main` (which makes it supersede, not stack).
  **A CI-blind branch can still be exercised on demand:** `gh workflow run <file> --ref <branch>` executes
  that workflow at that ref, with no commit and no matrix-wide cost — the cheapest way to prove an
  event-only code path (a `workflow_dispatch` fallback, a merge-queue branch of a shell script) that no
  that `pull_request` run will ever reach. The run's log is the evidence; cite its id.
    **A fork-head (cross-repo) PR is a different blocker class, not a queue**: `gh pr view <n> --json
    isCrossRepository` — a `pull_request` run from a fork receives **no repository secrets**, so any
    secret-dependent leg reports success while doing nothing, and the base repo's bot-approval trick does not
    apply on a fork head, so a fork PR that needs review can sit at `reviewDecision=REVIEW_REQUIRED` with
    `reviews=0` until a human approves. Read the shape before blaming supply: cancelled publish jobs plus
    `linux: skipped`, or a green-looking run that merged nothing. The remedy is not to wait — re-push the same
    commits into the base repo (`git push origin <sha>:refs/heads/<branch>`), open a same-repo PR with
    `--head <owner>:<branch>`, and close the fork PR with a comment naming the same head sha. Check whether the
    branch YOU open is same-repo too; that is the cheap half of the same rule.
- **Arm only on a base of `main`; a stacked PR is not armable** (amended rule 16, #873). A non-`main` base
  produces no workflows (#950) and the ruleset requires no status checks (#880), so `gh pr merge --auto` there
   is an **instant merge**, not a queue. Measured twice on this lane: `#978` merged at 09:26:51Z and `#972` at
  09:28:51Z, both `MERGEABLE/CLEAN` with `reviewDecision` none, both landing unreviewed on the shared feature
  branch — the fingerprint is `state=MERGED` with `autoMergeRequest=NULL`, which leaves no armed intent to
  inspect afterwards. So: arm on `main` only; a finished stacked PR states\n  `auto=none (stacked base: no required checks, #950)` and is armed **on retarget** when its base lands, with\n  the arm time commented on the PR. **Merging a stacked PR by hand is a bypass, not a handoff.**\n\n**A PR fixing an issue stays UNLINKED if its body says `Refs #N` instead of `Closes #N` — and an unlinked
fixed issue keeps being force-delegated.** `closingIssuesReferences` is only populated by the closing keywords
(`Closes`/`Fixes`/`Resolves`); `Refs` links the conversation but never registers the auto-close, so the issue
remains OPEN with no assignee and the inbox re-assigns it as "yours, go do it". When your PR is the landing
vehicle for the fix, write `Closes #N` in the body — then verify it actually registered (`gh pr view <n> --json
closingIssuesReferences` returns the issue, or GitHub's `linkedPullRequests` shows it), because on a non-`main`
base the cross-ref can lag. Do not report "fixed, in #<pr>" and move on if the issue still reads OPEN — that is
the exact report that keeps the delegation firing.

**A `CONFLICTING` ms on a PR whose PARENT was rebased is a history-divergence artifact, not a content
collision — prove it before re-resolving.** When the base branch is rebased (a parent PR re-cut onto a fresh
`main`), the 3-way merge-base moves below the whole `agents/` tree, so EVERY stacked PR renders `add/add` on
dozens of files that already exist identically on both sides. The discriminator is the base's own content delta:
`git diff --stat <old-base> <new-base>` (should touch only the couple of files the rebase actually changed) plus
`git diff <new-base> <your-head> -- <path>` for each file you own (empty = the tree kept your content). Only a
file that genuinely diverges in content is yours to resolve; the add/add flags themselves are noise. Never
re-push a spotless-against-a-moved-base result to "un-conflict" it — that is re-aligning to a base about to move
again, which is the rebase lane's job.

**`--force-if-includes` REJECTS a force whose remote tip is not an ancestor of your new head — use plain
`--force-with-lease` after a fresh fetch instead.** `--force-with-lease=<branch>:<old-sha>` can still return
"stale info" when its tracking ref was deleted by the fetch, and `--force-if-includes` is *correctly* refusing
history replacement (your rebased head does not contain the current remote tip). The working incantation after a
rebase onto a moved base: `git fetch origin <branch>` (to refresh the ref), then `git push origin HEAD:<branch>
--force-with-lease` — plain, no explicit sha, so git reads the just-fetched expected value. The `+ remote…local`
forced-update line in the output is the proof it replaced the old head.

**A hand-spliced conflict region keeps its `=======` even when the text blocks are right — compile after every
manual resolution.** Cutting both sides out of a merge marker and joining them leaves the divider line behind,
and it is invisible to `grep '<<<<<<<'` (which misses `=======`); only `python3 -m py_compile <file>` or a suite
run catches it. After any `sed`/`python` splice of a conflicted file, compile once and grep BOTH marker shapes
before continuing.

**A skill and the SOUL are two carriers of the same protocol — "version-here" means BOTH agree.** A rule that
exists only in the SOUL is read at session start; the skill is what loads when the pass runs, so a pass can
follow a different protocol than the session start that invoked it. When a SOUL edit is consent-blocked, the
writable skill carrier is the place to carry it (see the protected-file rule below); when both are writable,
assert the agreement with a test that reads BOTH files and demands each lesson appears in each — not just a
count of how many the SOUL has, which hides a carrier that never gained the rule at all.
- **Never push while a run at the head is in progress — even with an explicit licence.** `cancel-in-progress`
  on `pull_request` means the push itself kills the running matrix: measured, a 30-minute run at 19/28 green
  with zero failures had its remaining 8 jobs cancelled **one second after** a push that was authorised and
  correctly scoped. The authorisation covers *what* to push, never *when*; the destructive part is entirely
  the timing. Wait for the run's verdict (or "verdict first, assertion second"), then push once.
  **The combination that breaks this rule is an explicit instruction plus a stalled run** — first nothing
  moves, so waiting feels costless to abandon, then someone authorises, and the push lands on a matrix that
  was merely queue-bound. Two standing consequences: a run frozen with `0 in_progress` for tens of minutes
  is starved, not finished, so its queued rows will still be killed; and **for a body-, doc- or SOUL-only
  change there is no deadline at all** — a one-line text edit can wait for a verdict, and a rule about not
  destroying matrices must never be delivered by destroying one.
- **`gh run rerun` is REFUSED while a run is in flight, so "cancel then rerun" is the only lever and it
  costs the matrix.** `gh run rerun <id>` returns `cannot be rerun; This workflow is already running` and
  the API returns `403 {"message":"This workflow is already running"}`; both only succeed on a `completed`
  run. Never offer a rerun as the remedy for a hung job without saying that the run must first conclude or
  be cancelled — and do not cancel a live matrix to obtain that right.
- **A job with no `timeout-minutes` has no deadline, so "hung" and "slow" are indistinguishable and a
  runner stays held.** Parse the workflow for the key before calling a stall a hang (13 of 57 jobs in one
  audit declared none, inheriting GitHub's 360-minute default), and measure the stall as a step-transition
  table rather than `updated_at`: four steps in 27 seconds then one step with no transition for 50+ minutes
  is the evidence. File the missing budget as its own issue — **worded as "the pipeline cannot bound this",
  never "the job is slow"**. The cause is usually available: see the log-recipe rule below before writing
  "unknowable" into an issue.
- **CI job logs ARE readable — `gh api .../jobs/<id>/logs` returning 0 bytes is the CLI refusing to print
  ANSI, not an empty log.** Read them with:

  ```bash
  gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences \
    | sed 's/\x1b\[[0-9;]*m//g'
  ```

  Measured on one job: `0` bytes without the flag, `86848` with it. `gh run view --log-failed` fails the
  same way for the same reason. **Never write "logs are unavailable" into an issue or a report without
  trying the flag** — that sentence stops the next lane from diagnosing, and it is copied into playbooks.
  If the flagged call is genuinely empty, that is log *retention* on an old run, which is a different
  statement from a permissions or tooling limit.
- **Before cancelling a run "to free a runner", check the POOL it holds against the pool the blocked run
  needs.** Hosted Linux and macOS runners are separate queues: a run holding `linux/unit` frees nothing for
  a run whose only pending rows are macOS, and the successes you destroy buy an idle slot nobody wanted.
  Read `runner_name` per job (`gh api .../runs/<id>/jobs`) on both runs, then decide; "stage-heavy" is not
  the discriminator, "holds the resource the other run is waiting for" is.
- **A negative control that does NOT fire is a filed finding, not a discarded control.** When the sabotage
  you injected leaves the gate green, the guard is missing that assertion — write it up with the observed
  output and the exact command (`make <gate>` → `OK`, `exit 0`), because a control that cannot fail teaches
  nothing and the gap is invisible until it bites. Revert the sabotage either way, and confirm the clean
  tree is green again.
- **`gh pr edit` has no `--head` flag — an existing PR cannot be pointed at a different branch; close it and open a new one.** `gh pr edit <n> --head <branch>` errors `unknown flag: --head` (verified against this account), so a PR left pinned to a tangled branch cannot be retargeted in place: comment the resolution on the tangled PR, close it, and `gh pr create` from the clean branch. Do not cycle flag spellings — the CLI exposes `--base` mutation but not head mutation. `--force-with-lease` per branch and plain (below) still do the branch-side work; only the PR object needs the close-and-reopen.
- **A closed PR does not follow its branch.** Pushing to the branch of a closed PR moves the ref and
  leaves the PR pinned at its pre-close sha (`pulls?head=<repo>:<branch>&state=all` is how you find the
  successor). Verify `pr.head.sha` against `git ls-remote` before claiming a push is visible to reviewers.
  **Before acting on "rebase onto `<sha>`", prove the sha is on a live ref:**
  `git branch -r --contains <sha>` returning empty means it exists only in history — rebasing onto it
  bases a live PR on a commit nothing can merge. Check `gh pr view <n> --json state` on the PR that sha
  Treat any instruction that quotes a closed PR's head as stale until re-measured.
  - **A worktree that is "ahead" of its remote is not carrying unique work until you prove it per file.**
    `git rev-list --left-right --count <remote>...HEAD` showing `N ahead` counts commits the *remote branch*
    lacks, which includes every commit already merged into `main` and every commit of a superseded stacked
    base — so a tree diff against an older base is **always** non-empty and proves nothing. The test that
    decides is per-file blob equality: for each differing path, compare `git rev-parse HEAD:<path>` against
    the same path in (a) `origin/main`, (b) the target PR's ref, (c) the branch's own remote. A path matching
    one of those carries nothing new; only a path matching **none** is a candidate. Then close it out: a
    "unique" file that is byte-identical to an older `main` commit, or whose every line is a strict subset of
    the remote's version, is **older, not unique**. `git reset --hard <remote>` is safe only after that proof
    — and the pre-reset sha stays in reflog, so say where it is rather than implying it is gone.
  - **After a rebase resolves itself, verify the OUTCOME, not the success message.** A recorded `rerere`
    resolution applies silently during `git rebase` ("Staged '<file>' using previous resolution … Successfully
    rebased"), so the conflict is gone before you ever see it. Read the resolved file for the union case it was
    recorded for — both added rows present, both keys in `.PHONY` — because rerere replays whatever resolution
    was recorded however many commits ago, including one that dropped a side.
- **A consolidation PR can silently drop a property its predecessors had — test the property, not the
  body.** When work is folded into one branch, the merge is written by someone else and the parts that
  were prose in the old PR bodies (a trigger event, a fallback, an `on:` key) are exactly what falls out:
  `grep -c 'merge_group:\|workflow_dispatch:' <file>` and `grep -c "base_ref || 'main'" <file>` on the
  NEW head, per property. A green CI run on the consolidation is **consistent with** a dropped property
  when the property only matters on an event CI never runs — say that explicitly instead of reading the
  green as proof.
**Ruling a large conflicted vehicle's scope: measure it against its OWN base, never against `main`, and
subtract the absorbed before quoting delta.** A stacked PR whose purpose landed upstream reads as "N-commits
of unique work" against `main` while being net-destructive against the feature base it actually stacks on —
measured once: 110 commits / 75 files / `+9355/−9` vs `main`, but `+30/−1343` vs its own base, including a
deleted lane SOUL and zero added skill bullets, because its whole `agents/` tree was already absorbed and its
reason-to-exist (an amended rule) had since landed via the base's orchestration block. So the scope question
"which commits are still-needed vs already-on-main" is answered in two steps: `git diff --stat <base> <head>`
for the genuine delta, then for each candidate added line test it has not already arrived through the base
(grep the base's file for a phrase unique to the change). A net-negative candidate and a census whose counts
already match the current tree are NOT splittable content — report "nothing genuine survives" and close the
vehicle rather than shipping a hollow narrow PR to satisfy the letter of a split instruction. **Never fabricate
a split or narrow-rebase vehicle when measurement shows every candidate is already absorbed, retired, or
destructive — the honest resolution is close-with-note, and the warning sign is a diff that is mostly
deletions on a vehicle named for a rule the base already has.**

- **A stacked PR's base moving silently changes what its diff measures.** When the parent branch gains
  commits, GitHub recomputes against the new merge base, so the file count and `+/-` jump (a 3-file,
  `+44/−2` PR reappeared as 10 files, `+1190/−1` — it looked like it duplicated the whole parent).
  `git fetch` the base, `git reset --hard origin/<base>`, cherry-pick your own commits, re-run the gates,
  and only then quote numbers. **Never cite a file count from a stacked PR without a fresh base.**
- **Rebase a stacked PR only when it is actually `CONFLICTING` — never onto every move of `main`.** An
  owner rule and the arithmetic behind it: a stacked branch resting against a moving `main` has no CI, so
  re-rebasing "to keep it fresh" produces a new push with no run behind it and, once the parent lands, a
  second rebase for the retarget anyway — work done to make the board look current, not to change the
  object. The discriminator is the merge, not the date: `git merge-tree --write-tree --messages <base>
  <branch> | grep -cE "^CONFLICT"` (and `mergeStateStatus == CONFLICTING`) is the only trigger; a
  base-lag that merges clean stays stacked and arms **on retarget** when the parent lands. Restate the
  trigger in the PR body when you do rebase, so no reviewer reads the divergence as rule drift.
  **A stale local `origin/main` ref shadows the real remote** — `git fetch origin main` printing
  `warning: refname 'origin/main' is ambiguous` is the tell — so for a sha that matters read
  `gh api repos/<owner>/<repo>/commits/main --jq .sha` or an explicit `refs/remotes/origin/main` refspec
  in the same turn, and cite that fresh value rather than the local ref. (This names the ambiguous-ref
  tell that the older fetch-the-sha rule did not.)
  **When the stack's commits carry a tree-wide re-seed (six lane SOULs, a moved manifest), rebasing replays
  every one of them and you get `AA` conflicts across dozens of files you never edited — rebuild instead:**
  detached worktree on the base tip, `git show <old-branch>:<path> > <path>` for the files you own
  wholesale, and patch the one shared file (the test module) by inserting **after** the neighbour's block
  rather than replacing the file, so the lane that landed first keeps its tests. Then commit once and
  `git push --force-with-lease=<branch>:<old-remote-sha>`. **Enforce the rebuild with
  `git diff --stat origin/<base> HEAD` before the push:** any deletion outside the lines you wrote means a
  file was copied from an older tip, and the PR then reads as deleting the tests and SOULs the base gained —
  the same defect class as a truncated seed, one directory over. Wholesale `git show <ref>:<path> > <path>`
  is only safe for a file this lane alone owns; a shared file (test module, manifest, exemption list) is
  patched by insertion, never replaced. Correcting a body or a rule is not a reason to
  cancel a matrix: check `gh run list --branch <head> --status in_progress --json databaseId --jq length`
  → `0` before the push, and after it re-read `mergeStateStatus` (it can read `CONFLICTING` for the first
  seconds while GitHub recomputes — and the `gh pr view` field for draft state is `isDraft`, not `draft`,
  which errors out rather than defaulting).
- **Verify the object an instruction names before executing it — instructions arrive with stale state.** A
  dispatch written against an earlier reading can name a closed PR, a finished run, a superseded sha or a
  run that is already `completed`: act on the *intent* only after confirming the *object*. Two habits make
  this cheap: re-read the state in the same turn you act (`gh pr view <n> --json state,headRefOid`,
  `gh api .../runs/<id> --jq .status`), and when the named object no longer exists, find the one the
  instruction was reaching for — "cancel the run to free a runner" pointed at a concluded run while a live
  run on the same closed PR still held one — then say which you acted on. **Quote a sha from a fresh API
  call in the same message, never from an earlier turn**; a head that is one commit behind is still wrong,
  and a report that cites it describes a branch that no longer exists.
- **A fix that changes a SHAPE breaks assertions outside its diff — run the wider affected suite, not just
  the named tests.** A PR that corrects N stale assertions (a deleted CI caller, a replaced inline command)
  can leave an N+1th asserting the old shape in a file it never opened, because those assertions describe
  the shape rather than the behaviour: `assert '--event "${{ github.event_name }}"' in step["run"]` still
  passes on the base and fails the moment the step delegates to a `make` target. So: for every named test
  list, also run **every test file that reads the files the PR edits** (`grep -rl '<workflow or script
  name>' tests/`), and confirm a green base — a test that fails only on the branch is the diff, not
  staleness. The repair is to pin the new wiring plus a separate assertion on the `make` recipe, keeping the
  behaviour tests where the behaviour lives; loosening the assertion to whatever the YAML now says is not.
- **When your PR is blocked on someone else's fix, pre-build the unblock and prove it locally instead of
  waiting idle.** Rebase onto the current `main` in a throwaway worktree, resolve the conflict, run the
  gates, save the result as a named local branch (`rebase/<pr>-onto-<sha>`), and do **not** push it — the base
  is about to move again, so pushing now buys a second rebase and a cancelled run. Then say plainly what the
  unblock will cost ("one push, then it collapses to N files") and which sha it is based on
  (`git merge-base <branch> origin/main` — a preparatory branch's parent is the previous commit in the chain,
  not `main`, so check the merge-base before claiming the base). A blocker you can name, with the fix already
  gated, is a better state than a push that races someone else's merge.
- **Re-measure the premise of a criterion before enforcing it.** An acceptance rule you wrote from
  someone's reasoning ("a `paths` filter is disqualified, branch protection would wait forever") can rest
  on a fact that is false here — check the fact (does this repo require any status checks?) before making
  an implementer satisfy the rule, and if the premise is gone, recommend amending the criterion rather
  than the code.
- **A merge strategy that removes a conflict can manufacture silent corruption — check what the gate
  READS before trusting the merge.** `merge=union` on an append-only rendered file merges two branches'
  whole re-renders by concatenation: measured in throwaway repos, two branches adding different rows
  merge clean (but leave the rows unsorted), while two branches rewriting the SAME existing row produce a
  **duplicated** row with one header and no conflict marker. So union converts a loud `DIRTY` into a quiet
  duplicate. Whether that is caught depends entirely on the check: a `check()` that parses the FRAGMENT
  files and never opens the rendered aggregate (measured: it read only the per-change files, and the
  committed aggregate was compared to `render()` solely in an advisory `report()` with no exit code) lets
  a half-merged or duplicated aggregate pass every gate. Before recommending any conflict-removal measure,
  `grep` the check function for the artifact it opens — a check that never opens the merged file cannot
  see what the merge did to it, and "merged cleanly" is not "merged correctly".
- **Refining an issue that proposes N independent measures: measure each one's FAILURE MODE and name the
  one that is load-bearing if only one can land first.** A conflict fix has several plausible levers (a
  merge strategy, a gate, a tooling-scope change) and they are not equal: the merge strategy removes the
  visible symptom but, if no gate reads the merged artifact, trades a loud failure for a silent one, so it
  is a mitigation, not the invariant. The load-bearing measure is the one that makes the design's own
  stated sentence true — the doctrine is often already written (a module docstring saying "the gate never
  requires it current, so a change PR never has to touch it" — so quote it and make enforcement match it).
  Sharpen the acceptance to **one stated mechanism per negative control**: assert the gate fails on the
  forbidden edit and passes on the allowed one with the merge strategy explicitly NOT in play, then test
  the merge strategy separately on `git merge` exit status. An "either (a) or (b)" acceptance lets a
  passing test claim one mechanism while the other silently never ran, and it hides the case where the
  chosen measure cannot fail at all.
- **Convert the accepted measure into a spec that names file, function and line — and EXTEND an existing
  gate rather than adding a target.** A refinement that stops at "add a gate" makes the implementer write
  three attempts; the spec is the deliverable and it has four answers, each read from the tree: (1) **where**
  — the exact file + function + line, choosing the module that ALREADY has a base/head-scoped sibling
  subcommand (grep the argparse setup for an existing `--base/--head` parser and copy its shape) instead of
  bolting the rule onto a repo-only `findings()` that has no PR context; (2) **is the changed-file list
  already available** — reuse the tree's single diff reader (`ci_scope.changed_paths`) rather than adding a
  `gh pr view --json files` call, which needs a token and a network round-trip a static gate must not; note
  that the base sha is usually already exported (`PR_BASE: ${{ github.event.pull_request.base.sha || 'origin/main' }}`)
  so no workflow-env change is needed and the rule also works on a push; (3) **the exact failure message**,
  naming both the forbidden file and the replacement (directory + the command that renders it), so a reader
  knows what to do instead of only what not to do; (4) **two named negative controls the implementer writes
  verbatim** — the ALLOWED case must pass (the one a naive "any mention fails" implementation wrongly reds)
  and the forbidden case must fail naming both paths. **Extend, do not add:** `check-pr-hygiene` is already
  in `FAST_GATES` (`issue_bot_gates.py`), so a new SUBCOMMAND of it inherits pre-push execution for free,
  whereas a NEW make target lands unclassified in `ci-unit` and reds `make test-unit` until someone decides
  FAST vs DEFERRED (the #475 validator). Stating that choice keeps a one-line gate from becoming a
  classification argument.
- **Do not describe an unimplemented feature's benefit as already true — mark it prospective.** "Extending
  the gate means `make lane-preflight` picks it up for free" is a claim about a target that may not exist
  yet: `grep -n '<target>' Makefile` returning nothing means the benefit is CONDITIONAL on that target's PR
  merging. Write "once <PR> merges, <target> will additionally run it" — describing the intended state as
  the current one is the same error as citing a stale sha, and it is the error a corrective pass most needs
  to watch for in its own prose.

## The audit checks that have produced real issues

Run these over `scripts/*.py` with `ast`; hashes of normalised `ast.unparse` bodies find copies that
`grep` misses.

| check | how | why it lands |
|---|---|---|
| import graph vs the doc's own grouping | resolve local imports, map onto the §Scripts groups, DFS for cycles | a prose-only layering plus a real cycle is a gate waiting to exist |
| duplicate function bodies across modules | sha1 of normalised `ast.dump` per `FunctionDef` | byte-identical readers per leg = drift in a coordination protocol |
| subprocess wrappers | defs named `_run`/`_sh`/`_gh`/`run_gh`/`_cmd`, and whether the body reads `returncode` | "never reads the exit code" is the actionable count, not "N wrappers" |
| import roots | count `sys.path.insert` and both spellings (`import <m>` vs `import scripts.<m>`) per test file | two module objects in one session |
| Makefile size | `make -qp` for the TARGET count; line regexes only for recipes and inline snippets | a line regex double-counts targets declared twice |
| workflow duplication | identical `- name:` steps across `.github/workflows/*.yml`; `workflow_call` users | scaffold copies that must be fixed N times |
| a documented invariant with no gate | for each claim in `docs/ARCHITECTURE.md` ("X is refused/guarded/checked"), find the make target that runs it — `grep -c <script> Makefile` | a guard wired to no target enforces nothing, and is usually red when you finally run it |

## Audit: which generated artifacts does no gate read?

A recurring class in this tree is *a check whose result nothing gates on*. It is NOT "generated files are
unguarded" — most are gated — so do not assume the hole exists; measure it, because the honest answer is
often "eight of nine are covered, here is the one". Method (gate-free, no PR):

1. Enumerate writers: `grep -rlnE "write_text\(|open\([^)]*['\"][wa]" scripts/*.py` → the scripts that write.
2. Extract only the **committed** targets they write (`git ls-files --error-unmatch <path>`), not runtime
   scratch files — a scratch artifact needs no gate.
3. For each, find the generator's own `check`/`--check` and confirm it is **CI-reachable**: directly a
   `make` target in a workflow, OR nested under `check-docs` (which CI runs), OR a pytest the discovered
   unit suite collects. "Not a `make` target in ci.yml" is NOT the test — see the discovery note below.
4. Prove coverage by **semantic** corruption in a throwaway copy (`cp -r . /tmp/x`), run the check, assert
   `rc=1`, restore. **Append-only corruption is a false positive** — appending a line to JSON/MD passes
   harmlessly; corrupt a real value (a per-directory count, a model display name, a whole dropped case).
5. Report a table: file · generator · gate · CI-reachable · corrupt⇒nonzero. Only a row with `none` is a hole.

Two facts that make this cheap and that stop a false "untested" claim:
- **The hermetic unit suite is DISCOVERED, not enumerated** — `scripts/unit_tests.py` globs every
  `tests/test_*.py` minus `tests/fixtures/unit-suite.json` exclusions. So `grep <name> Makefile` finding
  nothing, or a check target absent from CI, does **not** mean untested: a `tests/test_<subject>.py` that
  loads the committed fixture and asserts it equals the live render IS the gate. Check `tests/` before
  filing "no gate".
- **A gate can live inside another gate's recipe** — `check-docs` runs `changes_index check`,
  `check_docs check` AND `check_architecture_census check`, so the census is CI-covered even though no
  workflow names it. Grep the *Makefile recipe*, not just the workflow file.

The generalisable lesson to write into any follow-up issue: the defect is **"a validator exists but its
verdict gates nothing"** (it lives in an advisory `report()` with no exit code, or a check the CLI never
calls), not "a file is generated". `CHANGES.md` qualified because `check()` parsed only the fragments and
compared the rendered file solely in advisory `report()` (#1063). Every other generated file was safe
because its validator *fails* a target CI runs. Do not file hollow issues for the correctly-gated files —
that is the same defect as a hollow PR.

## A gate whose MESSAGE names the wrong cause is its own class of defect

Distinct from "nothing gates on it": here the gate fails correctly-shaped but **diagnoses the wrong
subject**, which sends the next reader to edit the innocent party. The discriminator to look for is a
message that *speculates about the author's mistake* ("dangling from an amend?") when the actual failure
was *the environment could not look*. Reproduce it by running the gate where the tool it depends on cannot
work — a directory with no `.git`, a partial container mount, no network — and check that the message still
puts the blame on the file. The fix is always the same shape: **distinguish "could not check" from "check
failed" with a separate exit code** (e.g. 2 = unreadable input vs 1 = a real finding vs 0 = OK), name the
tool that failed, and drop the speculation. Acceptance for such an issue needs three controls, not one:
the unreadable case must change to the new code, the clean case must stay 0, and a genuinely bad input in a
READABLE environment must still exit 1 — the third is what proves the guard did not simply soften. File it
in this lane's own voice even when the trigger was your own false finding: the mistake was yours, the
diagnostic that drew you there is the tree's.

## When two PRs both add a host skill

Every host skill writes `HOST_SKILLS`, `.hermes/skills/README.md` and `tests/test_agent_skills.py`, so the
second PR to merge always conflicts. Measure it (`git merge-tree --write-tree --messages a b`), resolve in a
throwaway worktree, and prove it on the MERGED tree — the recipe, including the README trap that leaves two
host-skill paragraphs and a false "the one HOST skill" sentence, is `references/host-skill-merge.md`.

## When reviewing a path-selective CI branch

The trigger may filter only the docs class; rows inside a family stay with `CHANGED=`. The
class-vs-extension table, the enforcement answer for a repo with no required checks, the widen-on-empty
table, the dispatch-form gate and the four negative controls are in `references/path-selective-ci.md`.

**A branch you opened is not necessarily a branch you still own.** Other legs push to, rebuild and
force-push shared branches; before reviewing or reporting on "your" head, `git fetch` it and check
`git log --oneline -3` plus `git diff <your-sha> <their-sha>` — an empty diff means the tree is yours and
only the sha moved (so cancelled runs were supersedes), while a new commit list means someone else built
there and your PR body is now describing work you did not write. Report the state you measured, and say
which sha it was measured on. **When the rebase lane has replayed your commits onto a new base, your next
commit will NOT fast-forward — cherry-pick only the new commit onto THEIR head; never force your older
lineage over it.** Measured: a note commit built on a head of mine that the lane had already replayed
rejected with "stale info", and the correct repair was `git cherry-pick <my-new-commit>` onto
`origin/<branch>` then a plain push — a force there would have reverted their replay. Re-confirm the
tree afterwards is still yours: your files present, `git status --short` empty.

**A rewrite can keep the checks and delete what they check** — the inverse of a lost test. Measured twice in
one night after another lane force-pushed a `MERGEABLE/CLEAN` branch: the test file survived intact while the
implementation (`snapshot_caveat`) and the SOUL statement it asserted were gone, so the PR proved a contract
it no longer met and only the suite could tell. After any head change you did not make, check three things,
not one: the **shape** (`git diff --stat origin/<base> origin/<branch>`), the **carriers**
(`git show origin/<branch>:<path> | grep -c 'def <symbol>'`, and the same for each test name), and the
**behaviour** (run the gate and the suite at that head). A green `mergeStateStatus` over a red suite is the
signature of a rewrite that removed the subject and kept the exam.

**A census taken in a worktree you have edited is a census of your own edits.** Before reporting the base's
state — "the canonical block is 15 of 16", "the gate is red here" — re-measure it in a **detached worktree of
the base with `git status --short` empty**. After a few hand edits the wrong conclusion ("the base drifted")
is indistinguishable from a real finding, and it was wrong exactly that way once tonight.

**Fetch the branch you are cutting from, in the same breath as cutting it.** `git fetch origin main` does
nothing for a branch cut from a feature branch that carries the tree: `git fetch origin <base> main`, record
`git rev-parse --short origin/<base>` in the start comment, and treat a base tip fetched minutes ago as stale.

## When a rule block must be copied into several profiles

A fleet-wide rule (a canonical bullet list in an issue) is copied **verbatim** into each `agents/<profile>/SOUL.md`,
so a diff across profiles shows identical text and any divergence is a review finding. Prove the copy instead of
claiming it: extract the fenced block from the issue and assert `block in soul` on the **full block including its
heading**, then print the byte count. Match the issue's **bullet ORDER** too — a bullet inserted at a plausible
yet different position breaks the cross-profile diff just as effectively as different wording, and the mismatch is
invisible to a `grep`. Keep `Refs <issue>`, not `closes`, when the PR carries one of N profiles. Gate each tree
with `make check-agent-profiles`, and prove that gate by sabotage: remove the wording its manifest declares
(`never-merge`) and confirm it reds with the standing-rule key, then restore. Clean the worktree afterwards.

**Re-diff the block against the issue before calling the PR ready — and again after any comment says
"verified".** The canonical block is a living document on the issue, so a copy that was verbatim at commit
time goes stale the moment a rule is appended, and a review that trusts "verified in #<issue>" ships the
older copy. Compare the two artefacts by value (extract the fenced block from the issue, assert `block in
soul`, print both byte counts and both bullet counts); a mismatch is a **merge blocker against the issue's
own acceptance criterion**, not a nit — it ships the file missing precisely the rule the lane earned. When
it is one bullet, catch-up is a one-line commit; do not fold it into unrelated work.

**A bullet COUNT cannot see a near-copy — assert the full fence and let punctuation be the discriminator.**
The arithmetic-safety trap is that a count of bullets (`16 == 16`) passes a block that is NOT verbatim,
because a consultant wrote "the same four rules, re-worded": a period inside the bold on three bullets, and
an arming rule that was a merged paraphrase of the canonical's single bullet. `block in soul` on the full
fence is the check that sees it; a count is the check a reviewer trusts and that fails to. The asymmetry is
the trap real copyists hit: some rules end `*\*…**` with NO period inside the bold and others end
`…\`token\`.**` WITH one — copying faithfully, never normalising, is what makes `block in soul` true.

**Extract the FENCED block, never a copy of the rule from elsewhere in the issue.** An issue body can carry
the same rules twice: once inside a `` ``` `` fence and once as numbered paragraphs elsewhere, and the two
can differ in punctuation (the numbered copy carried a period inside the bold; the fence did not). The recipe
is `blk = re.search(r"```\n(## Standing rules.*?)\n```", body, re.S).group(1).strip()` — that grabs the
fence and only the fence. Matching the duplicate instead makes `block in soul` fail on punctuation alone,
and a `block in soul == False` finding that is really "you copied the wrong source" reads as a paraphrase
defect in this lane's own work. Re-extract at commit time every time, because the canonical changed twice in
one day (a retired bullet removed, the numbered duplicate deleted).

**A profile tree is authoritative for sync, so a stale or truncated seed silently deletes live rules — test the
tree against the LIVE profile, not against another copy of the tree.** Byte counts only hint; the discriminating
test is a subset check on lines: extract the live file's non-blank lines and the tree's, and report **novel tree
lines** (added) separately from **live lines absent from the tree** (lost). Zero novel plus N lost is a
*truncation*, not a divergence, and it is what a seed copied from a partial or outdated source looks like.
Unsynced direction matters too: `live << tree` is just a stub awaiting its first sync, while `live >> tree` is a
rulebook about to shrink — only the second is a defect.

**The sync tool's own "verified … identical" claims only that it wrote what it copied.** A sync that replaces a
7,509-byte file with 5,149 bytes and prints `verified: 3 file(s) read back identical` exits 0 and is green in
every gate, because `check-agent-profiles` counts profiles and rules, not bytes. So when a sync/install tool is
in play: **run the destructive case against a COPY of the live data** (`cp -a` into a scratch dir, point the
tool's destination env at the copy), verify the copy's byte count and a couple of rule strings afterwards, and
leave the real profile untouched — then say explicitly that you only touched a copy. When reviewing such a
guard, exercise **all** paths: intact, truncated-and-refused, and `--force`. The `--force` path is the one that
usually still claims identity while shrinking, and a test asserting only `"verified" not in out` on the refusal
path never reaches it.

**A rule copied into a SOUL or a skill is pinned by NOTHING until a test asserts it, and the test that looks
like it pins it usually names a DIFFERENT lane.** A fleet-rule test in a shared `tests/test_agent_profiles.py`
hard-codes one profile path (`agents/<other-lane>/SOUL.md`), so your copy is unasserted while the suite reads
green: measured, deleting the entire rule paragraph left the suite at 46 passed, and a "verified — 79 passed"
claim was worth nothing. Before saying a rule is enforced, `grep -rn "<a phrase unique to the rule>" tests/`,
read which path each hit opens, and when no test names your carrier add one per carrier (SOUL, skill) plus the
generalisation they share — then sabotage each: delete the SOUL paragraph, delete the skill rule, drop one
cross-referenced issue number, and confirm **exactly one** test reds each time, restore, green again.
**Normalise whitespace before matching** (`" ".join(text.lower().split())`): markdown prose wraps, so a plain
substring assertion fails on your own line break between two words of the rule and passes a genuine edit
elsewhere. The first version of such a test reds on formatting rather than on the rule — that is a defect in
the test, so fix the matcher, never reflow the prose to fit it.

- **A lane owns ONE SOUL vehicle; a rule that changes the SOUL goes on the SOUL's PR, and two chairs could
  both "fix the block" and both be wrong.** When a fleet rule is versioned into a lane's SOUL, keep it in the
  one branch carrying `agents/<lane>/SOUL.md`; do not spread it across skill-only PRs and then claim the skill
  branch also failed `block in soul` — a skill branch's SOUL file is the base's and never touched, so its
  `block == False` is the tree-canonical lag, not a paraphrase on this lane's file. Before consolidating A
  into B, measure the OBJECT the directive names: a branch may be a closed PR or a merged skill PR, neither
  an open SOUL vehicle, and consolidating  phantoms re-creates the split you are trying to end. Fleet orchestration-blocks (report-back to the inbox,
  new-PR→reviewer, version-here, one-lane-one-PR) are each lane's OWN always-on protocol and belong in that
  lane's SOUL, one added block — a lane's SOUL carrying the full fleet standing-rules block but no
  orchestration protocol of its own is the asymmetry the per-lane contract exists to close.
- **A protected-file write refused on approval is reported as owed, never routed around — and a gate that
  passes over the writable carrier does not clear the protected one.** When agent-instruction writes (SOUL.md)
  are gated on owner approval and that approval cannot be delivered, carry the amendment in the writable
  carrier (the skill), leave the protected file on the old text, and **state the difference in the issue and
  the PR** rather than hiding it behind a green gate. The gate proves only the skill; a future pass that reads
  green and assumes the protected file changed has absorbed the gap. Do not retry the refused write through
  terminal/execute_code — that is the same edit via another path, and a later redelivery can be refused by the
  transport itself, so the "could not be delivered" is recorded honestly and the SOUL half named as owed.

## Declaring a standing rule in the manifest: declare what the SOUL STATES

A profile whose manifest entry says `rules: []` is not "nothing to check" — it is "nothing in this SOUL is
gated", and the gate prints `UNPROTECTED`, which is explicitly *not the same as passing*. Filling it is a
judgement call, not a mechanical one:

- **Declare the rule the SOUL actually STATES, measured against the gate's own quote-stripped view**
  (`stated_text()`), never the rule you think the lane should have. A declaration the file does not carry is
a lie the gate then enforces, and it reds the moment the unrelated sentence it matched is edited.
- **A regex match is not a statement — read the matched line before declaring.** `never\s+merge` matched a
conditional about *stacked* PRs ("is never merged into `main` on its own") in a lane whose SOUL explicitly
merges its own docs PRs ("Then merge it yourself… No approval needed"). Declaring there would gate the lane
on a rule it rejects by design. Print the matching line and judge it; do not declare from a boolean.
- **A rule stated MORE THAN ONCE survives a single deletion.** A sabotage that removes only the first copy
of a twice-stated rule leaves the gate green — the exact "control did not fire" trap one level down. `grep
-count` the phrase across the whole file before deleting, delete every occurrence, then confirm the count is
0 and the gate reds naming that profile; restore from a pre-sabotage copy.
- **Data-only gate fixes need a test, or they revert silently.** A manifest edit with no pinning test means
re-emptying an entry (back to `rules: []`) passes CI again — the defect restored by one JSON character. Add
a test that, per lane, asserts the entry declares at least one KNOWN rule (`declared <= STANDING_RULES`, a
subset check so a later addition does not red it) **and** that the rule's pattern matches that SOUL's
`stated_text()`. Negative control: revert one entry, watch it red naming the lane, restore.
  **When adding a test to an existing suite, copy the module alias that file already uses** — a new test
  spelling `cap.profiles_from_manifest` in a file that imports `guard.` fails with `NameError` and reads
  as a logic error; `grep -n 'import .*check_agent_profiles' <testfile>` first.
- **A negative control demonstrated in a PR body is not enforcement — encode it as a test that operates on a
  throwaway COPY of the real tree.** "Sabotage → gate reds → restore" typed by hand proves the gate today and
  pins nothing: reverting a declaration to `rules: []` passes CI silently. Write the control as a test:
  `shutil.copytree(agents_dir, tmp/agents)`, blank the stated sentences carrying the declared rule, call the
  gate's own `findings(tmp)`, assert a standing-rule finding **naming that profile and the rule**, restore the
  file, loop per lane. Two layout traps make the copy version silently vacuous, and both were live this
  session: **the gate reads `<root>/agents`, so copy the tree to `tmp/agents`, not onto `tmp` itself** (copying
  onto the root yields an `agents-dir` finding and no standing-rule finding, and the assertion fails for the
  wrong reason); and any helper taking the manifest or a SOUL path expects the same `root/agents` prefix, so
  both call sites, not one. Predict them by calling the gate's real functions in a REPL against a —

  **A CI-mode local clone is a tree check, never a substitute for CI at the head.** `git clone --local` + `HERMES_PROFILES_HOME=/nonexistent` + `make check-docs`/pytest verifies THAT tree; if the head was then re-authored (author-allowlist #345/#971 rebase) the clone's sha diverges (ahead=1/behind=1) and has zero runs — a report of "125 passed / check-docs OK" at a superseded sha is the mis-sha'd-work class the planner catches by measuring. Verify the tree at the CURRENT `headRefOid` from the API, quote it, and name CI's terminal verdict separately; a PR is merge-ready only with a COMPLETED unit conclusion at the quoted head. Re-authoring force-moves the branch: assume the CI matrix restarts — re-read headRefOid and the gate conclusions AFTER the re-author, never carry the old sha's numbers. A live uncompleted run whose `linux / unit` step sits in_progress for 30+ min on steps 1–4 already success is runner starvation on a single-runner host, not a diff failure — report it as in-progress-with-duration, hold, and await the verdict; do not re-push (that cancels the matrix via cancel-in-progress).
  half-built temp root before writing the test — an assertion that reds on its own scaffolding teaches the
  next reader nothing.

**Verify such a gate in the environment CI uses, not the one with a live profile attached.**
`check-agent-profiles` compares tree against the LIVE profile when one exists, so on a host with profiles
installed it returns `rc=1` on pre-existing `absent-from-tree` findings that CI never sees — which masks
whether YOUR change is green. Run it the CI way, with no live profile:

```bash
docker run --rm -v "$PWD:/w" -w /w -e HERMES_PROFILES_HOME=/nonexistent <test-image> \
  bash -lc 'python3 scripts/check_agent_profiles.py check; echo "GATE_EXIT=$?"'
```

`GATE_EXIT=0` on the clean tree, `1` on the sabotaged one, in that same environment, is the pair the issue
asks for. Also: `rc=$?` after a pipe reports the LAST command's status, not the gate's — redirect to a file
(`... >/tmp/g.out 2>&1; echo $?`) rather than piping when the exit code is the evidence.

## Triage of a CI run's state

Rerun legality, the pool-matching decision, step-transition timing, `run.status` lagging its jobs, the
`--allow-escape-sequences` log recipe and the "cancelled is never evidence" table:
`references/ci-run-state-triage.md`.

## Reviewing another lane's PR

- **Verify the claim against the tree, not the PR description.** Run the named tests **and** a control on the
  base commit: the same command on `origin/main` must fail for the same tests, or they were never the cause.
  Then run every test file that reads the files the PR edits — a fix that changes a shape leaves an assertion
  outside the diff (see the shape rule above).
- **Read the A/B table for "fixed" vs "deleted".** A stale assertion corrected to the new world
  (`macos == {"macos"}` → `macos == set()`, `assert "macos" not in callers`) is a repair; an assertion
  relaxed to whatever the YAML now says is a silent loss of the property. Say which one you found, per file.
- **`gh pr review --request-changes` is refused on this account's own PRs** (`GraphQL: Review Can not request
  changes on your own pull request`). Post the same text as a `gh pr comment` and label it "requesting
  changes (posted as a comment — `--request-changes` is refused on this account's own PR)" so the verdict is
  not mistaken for a note.

## When a number is challenged

Re-measure, then post a **delta table** (claim / as filed / measured / verdict) plus a rescope verdict,
and edit the body so the artifact is right: a comment alone leaves the wrong number where the
implementer reads it. Rescope when the corrected count changes an *acceptance criterion*, not when it
only changes prose.

**A retraction goes into EVERY artifact that carries the false claim — body first, then the comment, then
the report.** A wrong claim propagates: it is written into an issue comment, into the PR body's evidence
table, and into the message to the inbox, so fixing one leaves two copies live. Order: edit the PR body
(the artifact a reviewer reads), post the retraction comment on the issue, and state it in the report to
the inbox — then re-read each to confirm the stale sentence is gone (`grep -c '<the retracted phrase>'
<body-file>`). A retraction that names the ROOT CAUSE of the error is worth more than the correction: say
which measurement was wrong and why (a metric that could not vary, the wrong mount, a stale ref), because
that is what stops the next lane making it. Do not bury a retraction in a footnote or a "minor correction"
subject — the claim and its withdrawal belong at the same prominence.

**A metric that returns the same value for every input is not a measurement — and `len(result)` on a
fixed-shape result is the trap.** A function that returns one row per job with a boolean (`select()` in
`ci_scope.py`) has a constant `len()` by construction, so "OK, 10" measured the row count, not the job
count, and was identical for a typo, an empty list and every real class. The quantity you want is the
SELECTED subset: `sum(r[1] for r in rows)` (or any count of the flag), never `len(rows)`. Two habits catch
it: if a number is the SAME across inputs that should differ, suspect the metric before trusting the
result; and when handing a corrected figure back, quote the branch that produces it — "`select([])` → 2
(always-on only), `select(list(CLASSES))` → 10" survives, "10" does not. A verification whose assertion is
the constant would pass a wrong check (`== 10`) and red the right one (`== 2`), so the fix is the metric,
not the expectation.
