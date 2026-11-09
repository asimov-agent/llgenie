# Base resolution and fresh verdicts

Two failure modes that produce a green that is not real. Both cost a full review cycle when missed.

## 1. The fork-vs-upstream base trap

In llgenie worktrees the two remotes are easy to confuse:

- `origin` is often the **fork** (`andyholst/llgenie`). Its `main` looks recent but is usually stale and typically an *ancestor* of the real tip.
- `upstream` is the **canonical** repo (`asimov-agent/llgenie`). This is the only `main` a PR may be based on.

A rebase or `merge-base` run against the fork's `origin/main` silently rewrites the branch onto the wrong lineage and can *drop* files that exist only on canonical `main` (they were never in the fork's tree). The rebase reports success; the diff looks plausible; the gate that checks the base then reds, or a required file goes missing.

Rules:

- Before any rebase, fetch the canonical remote: `git fetch upstream main`. Use the sha that fetch returns, at that moment — never a sha quoted in a chat message or a branch you already had.
- Resolve the base strictly as `upstream/main`. Verify before pushing: `git merge-base --is-ancestor upstream/main HEAD` and that the commit's parent equals the fetched `upstream/main` sha.
- Confirm a canonical-only file the change depends on is still present after the rebase (spot-check one path you know lives only on canonical main).
- If a red is `check-pr-base` / merge-base mismatch, the fix is a rebase onto the freshly-fetched `upstream/main`, not a change to the check.
- Push the fix branch to the **fork** and open the PR cross-repo, base explicitly `main` of the canonical repo:
  `gh pr create --repo asimov-agent/llgenie --base main --head andyholst:<branch> --body-file <file>`.
- After any force-push, re-read `state`, `merged`, `mergeCommit` (not the legacy `mergedAt` alone) before
  writing a status line into a comment. A PR that self-merged while you were reading still shows the
  status of your last poll; describing it as "MERGEABLE, BLOCKED" after it merged is a false record on
  the board, and the planner will flag it.

## 1b. The base the planner / rebase lane names can ITSELF be stale — compare against LIVE upstream/main

A dispatch that says "rebase onto current `main` at `<sha>`" is a snapshot from when it was written. By the
time you act, canonical `main` has usually merged another PR, and the rebase lane may have rebased the
branch onto that already-stale sha. Measured: the planner cited base `00322d82` and the rebase lane used it,
but a fresh `git fetch upstream main` showed live `upstream/main` at `2d9d9457` — the branch was still ONE
behind live main, so a fresh `check-pr-base` would red again. So: immediately before reporting a fix as
"rebased onto main", re-fetch `upstream main` and compare the branch's merge-base with the LIVE tip
(`git merge-base HEAD upstream/main` vs `git rev-parse --short upstream/main`); if they differ, the branch
is still behind and the rebase lane (or whoever owns the rebase) must be told the fresh sha — never assert
"on live main" from the base the dispatch named. You do not rebase it yourself; you report the drift.

## 1c. `check-pr-base` can fire LAST, purely because main moved under you — that is a handoff, not a rebase

A branch cut correctly from fresh `origin/main` at open time still reds `check-pr-base` (#845) once another
PR merges into main while your PR sits in review. The guard compares against the LIVE `origin/main`, so your
previously-correct cut is now "behind": the log reads `… is NOT cut from origin/main — its merge-base with
origin/main is <old>, not origin/main itself … foreign commits (1)` and `check-pr-base` exits 2. Measured
here on a data-only branch whose only other reds (scope lint / trailing newline) had already been fixed: at
head `4bb3663b`, cut from `1fc00f30`, main had advanced to `13e45a52`, and guard red while scope/lint/other
checks were green.

Distinguish the two cases before acting:
- **base-not-current only** (a sibling PR simply merged): the branch diff is your own commits, no conflict,
  and a rebase onto the live `origin/main` applies cleanly. This is the common case and it is NOT a defect
  in your change.
- **content conflict** (a real DIRTY/`CONFLICTING` mergeStateStatus): the same handoff applies, but say the
  conflicting paths so the rebase lane knows what to keep.

Either way, whether this lane rebases depends on WHOSE PR it is: **on another lane's PR this lane does NOT
rebase (owner 2026-10-30)** — post the measured finding on the PR (head sha, the `check-pr-base` log line,
old base vs live base) and hand it to `@llgenie-pr-merge-conflict` naming the head to repair and the target
`origin/main` sha. But when the PR is **this lane's OWN pipeline-fix PR** (a workflow/gate/make-target
change, owner 2026-11-01), this lane rebases it itself onto the freshly-fetched `upstream/main`, refreshes
the `AGENTS:`/`BASE:` cite to the new tip in both the commit message and the live body, and lease-pushes —
the "do not rebase" rule forbids rebasing OTHER lanes' vehicles, not repairing your own. Report the fact that every OTHER check is green so the lane
knows the rebase is the whole remaining job. Also note in the issue you close that main advanced by a
specific merge — the reader needs the cause, not just "branch was behind".

Corollary: because this gate fires late, a head that reads `0 failures, N pending` or `all-else-green` is
**not done** — each re-pushed head can reveal the next gate one layer at a time (lint → check-pr-base). Keep
polling until pending is 0 AND the base gate has evaluated against the live main; do not call it green from
the absence of failures while a base check is pending or unrun.

## 2. A verdict is only real if it is fresh, completed, and at the live head

`gh run view` on a run id you captured earlier can describe a head you have since pushed past, or a run that already failed. Reading the check colour or an old run id is not a measurement.

Rules:

- Read the PR's current `headRefOid` first (`gh pr view <n> --json headRefOid`). A verdict counts only when the run's `headSha` equals that live head.
- Require `status == completed`. `in_progress` / `queued` is not a verdict; poll until completed rather than quoting an in-flight run.
- Quote the **real job id** for any job you call green (`gh api repos/<repo>/actions/runs/<rid>/jobs --jq '.jobs[]|select(.name=="<job>")|.id'`), not just the overall conclusion — the rollup hides a red job that never loaded (zero jobs reads clean).
- A previously-red job is only "fixed" when a *new* run at the new head shows it `completed/success`. Say which job id went red and which went green.
- Never report green from a run at a head you have already pushed past; re-trigger and wait for the run at the current head.

### 2b. The PR's STORED head outruns the branch ref you fetched — track `headRefOid`, not `upstream/<branch>`

When another lane owns the rebase, the branch is force-pushed repeatedly while you measure. A
`git fetch <remote> <branch>:refs/remotes/upstream/vN` you ran minutes ago is then BEHIND the PR's
actual head, and a verification run on the fetched ref is a green at a head the merge queue will never
read. Measured: a fetch returned `3c762890` and the LIVE seam passed there, while the PR's stored head
was already `5e184a4d` — the rebase lane had pushed again in between. Two consequences:

- **Read `gh pr view <n> --json headRefOid` immediately before each verification and fetch THAT sha**;
  if the branch ref you already have differs, re-fetch (`git fetch <remote> <branch>:refs/remotes/upstream/vN`
  prints `forced update`), then run the gate at exactly that detached sha and quote it. A "verified
  green" whose sha != the current `headRefOid` is not a verification of the thing that will merge.
- **Say which sha you verified and that it was the current `headRefOid` at read time.** On a branch the
  rebase lane is actively advancing, the honest line is "green at <sha>, the current PR head when read" —
  every earlier figure you cited in a comment is superseded, so post a short correction rather than
  letting a stale number stand.

`gh` field quirks that bite this check:
- **The lag runs BOTH ways: right after your own amended force-push, `headRefOid` can still read the OLD sha
for a few seconds before catching up (API propagation) — you pushed `<new>` yet the PR-head read shows the
one you replaced.** This is not a failed push and not a stale ref to re-fetch blindly: confirm your push
landed (`git ls-remote <remote> refs/heads/<branch>` == the sha you pushed, or the push's own output), then
re-read `headRefOid` — it catches up within one read or two. Do not "fix" a lagging `headRefOid` by
re-pushing (the remote already has the new head); that just re-triggers CI twice. State the sha you pushed
and that the PR read was lagging, rather than reporting the old sha as the live head.

`gh pr list --json headSha` is **invalid** — the field is `headRefOid` (the whole read fails otherwise).
- `gh pr view <n> --json commits` returns `author.login: null` for bot-authored commits (the bot identity
  is not a GitHub user). To see who authored a commit on the vehicle, use `git log --format='%h %an %s'`
  — bot commits show `Asimov Agent`, which is what tells you the change is this lane's own work rather
  than a stranger's branch.

### 2c. When a completion-guard keeps demanding "the required task-relative change", the change is usually the vehicle's own commit — do NOT invent a second one

A guard that repeats "make and verify the required task-relative change" past a passing verification is
usually not asking for a NEW gate edit; it is asking you to prove the change you already own is real and
verified at the merge-queue head. Before writing any gate code: confirm the vehicle already carries the
fix (`git log --format='%an %s'` shows this lane's bot-authored data/fixture commits), verify it green at
the current `headRefOid` (2b), and reconcile any stale duplicate worktree (a `git status` dirty tree whose
uncommitted change is already on `main` — see the stale-duplicate rule in SKILL.md). Writing a redundant
second gate change to satisfy the guard is the same error as weakening a gate to go green: it either
duplicates an owned vehicle or re-words a check the tree already lock-tests.

**Before concluding §2f's "just verify and stop", re-derive whether a genuinely owed wire mutation
remains — the most common is a filed finding whose ROUTING LABELS never landed.** A six-section audit issue
with an empty `labels` list is only half-filed: it exists but the queue cannot pick it up, because
`gh issue create --label` silently drops any label the repo does not yet define. Filing is not done until
the labels are read back and match a sibling finding —
`gh api repos/asimov-agent/llgenie/issues/<n> --jq '{labels:[.labels[].name]}'`. Completing it
(`gh issue edit <n> --add-label agent:refined,agent:implement`, then read the labels back) is the correct
task-relative change, not fabrication: it finishes a filing the guard was right to still demand. Only after
sweeping every `gh` write this turn for such a missing step (§2f's read-backs) do you fall back to
"verified and stopping".

**And when the vehicle is already pushed and only a long green matrix is still RUNNING, the guard's
demand is met by a verified progress-record comment, not by a fabricated change and not by claiming
done early.** The honest state at that moment is "everything is pushed; the heavy matrix (run `<id>`) is
in flight, guards/scope/etc already pass at the corrected head `<sha>`" — write exactly that as a comment
on the issue (the bookend's middle beat): the head sha, the passing gates with their run/job ids, and the
pending matrix named by run id. That comment IS a task-relative write (it records measured state a
stranger can act on) and it is the correct one; inventing a throwaway edit to silence the guard, or
reporting "done" while the acceptance matrix is `in_progress`, are both defects. Never call the matrix
green from absence of failures — cite `pending`, post the progress record, and let the completion wake
the final verdict.

### 2d. Once the vehicle MERGES, "the merge-queue head" is the MERGED TREE — re-verify at live `upstream/main`, at the CLI outcome, not only the unit suite

A unit suite green at the PR head proves nothing about what shipped: a squash merge creates a NEW commit
whose tree is what `main` now runs, and the PR head sha is gone with the branch. A completion-guard that
keeps firing AFTER you report "merged + matrix green" is usually demanding exactly this third layer — a
verification of the change in the SHIPPED tree, expressed as the tool's actual OUTCOME (exit code +
emitted check-run/artifact), not just `pytest` passing. Run all three, in this order, and quote each:

1. **Suite at the merged tree:** `git -C <main> fetch upstream main` then
   `git -C <main> worktree add --detach <W> upstream/main` (or `checkout --detach upstream/main` in an
existing throwaway worktree), confirm `git -C <W> rev-parse --short HEAD` == live `upstream/main`, and run
   the changed test file there. Green at the merged sha, not the dead PR head.
2. **Function/behaviour proof at the merged tree:** import the shipped module and drive the changed
   predicate directly against the exact measured input (merged-PR shape, empty `pull_requests`, deleted
   branch) — assert it returns the expected classification AND that the un-weakened cases still return
their old result (an OPEN PR still judged, a non-`pull_request` event still ignored).
3. **CLI-outcome proof at the merged tree:** run the script's real `main()` with a stub `gh` and assert
   the OBSERVABLE result — process exit code and the JSON it writes (`--check-run-out` conclusion). This is
   the row that answers the guard: "the straggler exits 0 and posts `neutral`", never red, never success.

Only after (1)(2)(3) all pass at the merged sha is "delivered and verified" a true statement. Reporting
"matrix green" on the post-merge CI runs is necessary but not sufficient — those prove the tree builds, not
that the changed behaviour is the one you intended.

### 2e. When the last honest step is a VERDICT-GATED write-back, the guard's demand is met by a DRY proof of readiness — never by fabricating the verdict

A completion guard can keep firing while the only remaining step is ticking the linked issue's `##
Acceptance criteria` — and that tick is gated by `acceptance_writeback` (#1644) on a reviewer's COMMENTED
verdict, which an auto-merged bot PR never receives (the chicken-and-egg in SKILL.md). The honest answer
is NOT to run `acceptance_writeback writeback --proven …` with your own `verdict-ref` (that fabricates a
reviewer verdict — the worst failure this lane can produce), and NOT to weaken the acceptance gate. The
task-relative write the guard actually wants is a **dry proof that the seam is ready and correctly
targeted**:

1. Live criterion count — `gh issue view <n> --json body --jq .body | grep -cE '^- \[.\]'` (confirms the
   positions you would pass to `--proven` are the real ones).
2. Projected tick, dry, against the LIVE body: `acceptance_writeback.py writeback --issue <n> --proven
   1,2 --verdict-ref '<explicit PENDING marker>' --dry` → `[acceptance-writeback] would PATCH #<n> body`.
   Or the pure transform: fetch the body to a file, `acceptance_writeback.py apply --body-file <f> --proven
   1,2 --verdict-ref x`, and `grep -E '^- \[x\]|unproven'` to show exactly which lines tick and which stay
   `- [ ]` (the seam's invariant). That output IS the demonstration that the one remaining mutation is
   well-formed and correctly aimed, without performing or faking it.
3. Post the readiness record (dry output + the PENDING verdict marker naming the dispatched reviewer, its
   queue/head/run) as the middle bookend on the issue, and state plainly that the live `- [x]` write-back
   requires the reviewer's COMMENTED verdict that only the review lane can produce. That is an external
   dependency, not a hidden defect — say so.

Fabricating the `verdict-ref` to silence the guard is a #948/#1644 violation; a dry proof plus a named
external unblock is the correct task-relative change and the honest end state.

### 2f. When EVERY task-relative write this turn was a `gh`-wire action or a skill patch, the guard cannot see them — verify those artifacts at their own surface and stop, never manufacture a repo edit

A completion-integrity probe reads files and command effects in the workspace; it does NOT observe remote
GitHub state (a `gh run rerun`, a `gh pr comment`, a comment id) or edits to a skill file outside the repo.
So a turn whose only real changes were `gh`-wire mutations and a skill patch can loop "no task-relative
mutation attempted" even though the work genuinely happened. The honest close is to prove each artifact
AT ITS OWN SURFACE and quote it — not to invent a throwaway repo edit:

- **Wire mutation:** re-read the object directly — `gh api repos/<o>/<r>/actions/runs/<id> --jq '{status,conclusion,attempt:.run_attempt}'`
  for the rerun, and `gh api repos/<o>/<r>/issues/comments/<cid> --jq '{id,author:.user.login,created_at}'`
  for the posted record. The post's exit code is not the fact; the read-back is.
- **Skill / on-disk artifact:** `search_files` the exact inserted sentence or an anchor string in the
  skill file and quote the matched line number — that proves the write landed without re-`write_file`ing.
- Then stop with the quoted records in hand. Manufacturing a repo edit purely to satisfy a probe that cannot
  see `gh`/skill state is the same defect as weakening a gate to go green: it produces a fake change where a
  real (unobservable) one already exists. The refusal-to-fabricate is correct and should be stated plainly
  ("the probe cannot observe `gh` state or my skill file; here are the verified ids").

  ### 2g. An EXPIRED run's job records make its verdict read `none` — that is missing data, not the fix reddening; re-run the PRODUCER to force a fresh re-judge

  A `workflow_run` judge (`ci-verdict`) re-read long after its producer run finished can be judging a run
  whose individual job records GitHub has pruned: `.../actions/runs/<rid>/jobs` returns `total_count: 1` and
  the only surviving row is the judge's own `ci-verdict` row. The post-fix judge then sees every selected job
  ABSENT and posts `verdict=none` (summary `no-verdict=N applied`, `0 failures is not a verdict`). That reads
  as a non-success check but it is NOT the fix failing — the data is gone. Distinguish it before blaming the
  fix: a REAL red names `failure=1` against a concrete job (`[ci-scope] guard FAILED`); `none` with all
  ABSENT rows means the run's jobs are expired.

  `ci-verdict.yml` is `workflow_run`-triggered with **no `workflow_dispatch`**, so the only live way to get a
  fresh re-judge is to re-run the PRODUCER CI run — its job rows repopulate and its completion event re-fires
  the judge:

  ```bash
  gh run rerun <producer_run_id> --repo <owner>/<repo>      # works on a completed or startup_failure run
  gh api repos/<owner>/<repo>/actions/runs/<rid> --jq '.status+" "+.conclusion'   # poll until completed
  ```

  Re-run only the small producer CI (guard/ci-images/linux — the ~10-job CI), never the heavy engine-build
  matrix. One targeted re-run is the re-judge mechanism, not a queue-clearing habit.

  Corollary: that re-run executes the REAL gates, so it also re-exposes whatever red a stale `none` was
  hiding — that is the point. Read the failing job's **per-step conclusions**, not its log: the log endpoint
  `.../actions/jobs/<job_id>/logs` frequently returns EMPTY, while
  `gh api repos/<o>/<r>/actions/jobs/<job_id> --jq '{name,conclusion,steps:[.steps[]|{name,conclusion}]}'`
  names the exact failing step (`make check-pr-base`, `make check-pr-acceptance`, …). Route that real cause to
  its owner — a `check-pr-base` base mismatch on another lane's PR is a handoff to the rebase lane (§1c), not
  this lane's fix, and never a second code change.

  Also: repo `gh api --jq` runs an older jq without `sub/1` (`function not defined: sub/1`) — use
  `gsub`/`ltrimstr`/string slicing instead when trimming a run title or sha.
