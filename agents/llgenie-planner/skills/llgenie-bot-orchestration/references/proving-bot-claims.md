# Proving a claim another bot handed you

Three checks that turn "a bot said so" into evidence. All are read-only: no worktree, no branch, nothing to clean up
afterwards.

## Verify the citation, and verify it in the right place

A correction can itself be wrong. Tonight a comment quoted an id that had not been read back, so a second comment corrected it — and the check of the correction searched the wrong issue's comments and reported `present: 0` for an id that was correct, on a different issue. The correction was right; the verification of it was a neighbouring question.

- **Read the id back from the object you posted it to**, with `--paginate`; a bare `?per_page=100` answers "is it on the first page".
- **Search the issue the comment is on**, not the issue that references it — a cross-reference points across numbers, and the comment always lives on its own.
- **A `present: 0` is a claim about your query before it is a claim about the world.** Print what you searched beside what you found.

## A closing link is eventually consistent, so "none" is not absence

Two instruments answer "will this issue close": the **body keyword** (author-controlled, immediate) and
`closingIssuesReferences` (indexed, **lagging by minutes**). Reading the indexed field seconds after a PR is created or
its body edited returns an empty list on a PR that is correctly linked — and reporting that as "no link" sends a lane to
edit a body that was already right. Measured: two PRs read `closes=none` for several minutes and both then reported
their issue with no body change at all, and one of them was the second PR in a row that drew the same wrong demand.

- **The positive is proof; the negative is not.** `closes=<n>` settles it. An empty list means "not indexed yet, **or**
genuinely absent", and the two are indistinguishable in the moment.
- **Check the author-controlled fact first**, because it has no index and no lag:
  `gh api repos/<o>/<r>/pulls/<n> --jq .body | grep -ciE '^\s*(close[sd]?|fix(es|ed)?|resolve[sd]?)\s+#[0-9]+'`.
  A match means the author did their part — the body's rendering (a list, a blockquote, a bolded keyword) may not be
  line-anchored, which is itself proof the field, not the grep, is the authority once it has indexed.
- **Re-read before you report, and write `pending` rather than `none`** when the PR is minutes old or its body was just
  edited. `none` is a claim about the moment; a link gap is a claim about the artifact.
- **Fix it on the body, never the branch**: a link is PR metadata, so the vehicle and its CI are untouched.

Same family as every other one-directional check here: two things answer adjacent questions, one of them lags, and the
fast one is the one that reads as done.

## A compound command is classified by its first matching segment

The completion gate counts a `terminal` call as exactly one kind, and `tool_kind` returns on the **first** segment that matches (`progress_integrity.py:77-91`):

```
"cmd_a && cmd_b ; pytest …"   -> the first segment decides; `git …` or `cp …` matches a
                                 mutation prefix, so the whole call counts as a mutation and the
                                 pytest segment is never seen
"/venv/bin/python -m pytest"  -> does NOT match the test prefix "python -m pytest" (absolute path)
"pytest …"                    -> matches
```

So two habits that look right both fail: **chaining the verification onto the edit**, and **invoking the interpreter by absolute path**. Both leave `verified_test_passes` at zero while the work is genuinely verified, which reads exactly like not verifying at all.

- **Run the test as its own call, starting with `pytest`.** Put the venv on `PATH` once (`export PATH=/…/.venv/bin:$PATH`) — the export persists between calls — instead of prefixing each invocation.
- **Never bundle a mutation and its verification into one command.** They are two facts and the tooling can only record one per call.
- **General rule, beyond this gate:** any classifier that inspects a command line reads the *first* thing it recognises. If a command contains two intended actions, assume only one is visible to whatever is watching.

Related shape from the same evening: `--log-failed` returning empty meant the query never reached the logs, and a `| tail` swallowed an exit status. **Every one of these is a tool answering about the surface of a command rather than its content.**

## A versioning PR is a checkpoint, not a state

The reviewer lane reported **"0 of 10 files differ from live"** at 23:54Z against its branch — true when measured. Its PR merged at 00:09:32Z. At 00:37Z, against `origin/main`, **four files differed and ~8,197 bytes existed only in the profile** (`gate-auditing.md` alone +3,874 b).

- **Compare against `origin/main`, never against a branch.** A branch comparison is valid only until the merge — which is precisely when it stops being useful.
- **Run the drift check post-merge.** The tree only becomes the baseline *after* it lands.
- **A clean result is a timestamped measurement, not a property.** "0 of 10 differ at `<sha>` on `<date>`" is a claim; "we are in sync" is not one and expires silently.
- **Prefer the gate to the habit:** `CHECK=1 make sync-agent-profile PROFILE=<lane>` already fails with `DIFFERS` / `TRUNCATED?` and names the remedy, so wrap that command instead of reimplementing it.

The dangerous half is not the drift — it is that **a successful versioning PR looks like the end of the work.** Nothing prompts a re-check, so the drift that follows the fix is the least likely to be noticed. Same lesson as `enabledAt`, `closingIssuesReferences` and `updated_at`: **a value describes the moment it was read.**

## How the completion gate decides, read from its source

The "Nerve completion integrity check" that keeps returning `no task-relevant mutation was attempted` is not a judgement about the work — it is three boolean clauses, and knowing them tells you which one you are failing (`plugins/nerve/hermes_nerve/nervous.py:1362-1374`):

```
coding_change        = change_required and (coding or changed_paths_present)
no_relevant_attempt  = relevant_mutation_attempts == 0
missing_verification = coding_change and verification_required and verified_test_passes == 0
fires if any of the three
```

- **`requested_paths` comes from the triggering message** (`nervous.py:374` → `progress_requested_paths(user_message)`). When that message names files — as a lane's report does — only a mutation to those files counts. **When it names none, `mutation_is_relevant` returns true for any non-scratch path** (`progress_integrity.py:162`).
- **`verified_test_passes` only increments on a `test`-kind tool that SUCCEEDED** (`nervous.py:839-840`). A failing suite counts for nothing, which is correct and also why a red local run looks identical to no run at all.
- **The practical consequence:** a turn that changes files without a passing test in the same turn trips `missing_verification` even when the change is real and relevant. The honest response is to run the tests that cover the change — not to make a cosmetic edit.

**And the trap this exposes in my own habit:** `pytest tests/test_agent_profiles.py` fails 9 tests on this host because it reads the live profile, and passes in CI with a clean `HOME`. **A local red that CI cannot see is not evidence of a broken tree, and running it that way neither verifies nor falsifies anything** — use `HOME=/tmp/cleanhome`, as `references/local-verification.md` already says.

## `created_at` is not a start time

A CI run created at 21:11 and still open at 00:32 was reported by me as "over three hours — this one deserves to be called stuck". Reading the **job** rather than the run destroyed that claim: `linux / unit` had started at **00:16:38Z**, sixteen minutes earlier. The run spent 21:11–22:34 **queued**, then ran fast jobs, then waited again for its unit leg.

- **Queue latency and execution time are different numbers.** `created_at → first job started_at` is the wait; `started_at → completed_at` is the work. A single "duration" conflates them, and reporting it produced a false outlier **one comment after I had written that a frozen timestamp is not a hang signal**.
- **"Stuck" invites a cancel or a re-run, and both are wrong on a job that is progressing.** Report the run's age, the job's start, and the queue depth separately, then say which one is abnormal.
- **A band is only meaningful per measurement.** "40–60 minutes" was execution time and still holds; "3h20m" was queue + execution and described nothing.

The same mistake in a different field: `updated_at` does not advance during a long step, `enabledAt` records a time and never a head, and `closingIssuesReferences` populates asynchronously. **Every one of these is a timestamp being read as a state.**

## A queued board is a defect in one shared thing, not many PRs

Four PRs sat blocked tonight at once — `#1065`, `#1126`, `#1115`, `#1129` — every one with the same single job in progress, `linux / unit`, at 37–59 minutes. Each looked individually "blocked"; the board was **queued by one shared bottleneck**, and naming it per-PR hid the actual defect.

- **Group before you report.** If the blocker has the same name on every row, it is one item, and it gets an issue (this one became #1139) rather than four status lines.
- **Distinguish slow from stuck by the band, not by feeling.** Record the observed minimum and maximum; a leg that always runs an hour is indistinguishable from a hung one, so "still running" is not information unless the band is stated.
- **A cancel produces no verdict, which is worse than a red.** `cancel-in-progress` means any push during the window destroys the work rather than delaying it, and a lane reading "0 failures" from a cancelled run will report success.
- **Never let the queue push you into the wrong recovery** — re-running a live job or pushing to "kick" it are both destructive; the only safe recovery is `gh run rerun` on a *completed* run at the same sha.

## When two tools answer one question, run both

One lane shipped two audit tools that answer the same question — what is safe to delete — and ran them back to back on the same repo at the same moment. They disagreed:

```
shell   SAFE 162 branches / 125 worktrees      python  SAFE 45 branches / 132 worktrees
```

Both had bugs, and **the direction of each mattered more than its size**: the python tool computed worktree safety as `total − dirty`, so **six clean worktrees sitting on unique branches were listed as safe to delete** — the destructive direction, work that exists nowhere else; and it counted branches as `merged-and-clean + unmerged-with-a-PR`, silently dropping **117** lossless orphans that were perfectly deletable — merely wasteful. A single tool cannot be wrong out loud.

- **Run the second implementation before trusting the first**, especially where the answer authorises deletion.
- **Check the error's direction, not just its magnitude.** Too-optimistic on a delete list destroys work; too-pessimistic merely annoys. Only the first is an incident, and the same "16 off" means opposite things either side of the boundary.
- **When both agree, quote both.** "Two tools produced this" is a stronger claim than a bigger number.
- **Guard the rule, not the count**: the test here asserts that reintroducing `total − dirty` fails and that a bucket-enum deletable set fails, because an exact-count assertion reds on the next unrelated push and teaches the next person to update the number instead of the rule.

Related, and the same night: a generator that emitted lint-red output while every committed block was lint-clean, an audit script whose four-bucket tool existed only in a live profile, and a "0 commits ahead" worktree that a prune would have called merged. **Every one was an answer that looked authoritative and had never been contradicted.**

## Acceptance criteria are the deliverable of a refine, not a courtesy

Two issues were dispatched tonight with a diagnosis and a suggested fix but **no acceptance criteria** — `## What`, measurements, `## Suggested fix`, `## Scope`, and nothing a reviewer could check. That is the shape that produces a PR nobody can judge: the lane guesses what "done" means, the reviewer guesses back, and the disagreement surfaces after CI is green.

- **Every refine ends with `## Acceptance`**, and every criterion is a command, a quoted output, or a printed pair — never "works correctly".
- **Demand the negative.** "The gate fails when the rule is removed, and passes when it is restored" is acceptance; "the gate passes" is a wish. The fleet's whole night was one long lesson that a check which cannot go red proves nothing.
- **Name the trap the fix invites.** Both refined issues had one: declaring plausible rules the `SOUL.md` never states swaps a silent pass for an enforced falsehood; and a split that concatenates rather than moving sections strips blank lines and fences. A criterion that forbids the cheap fix is worth more than one that rewards the expensive one.
- **Verify the paths you cite in the criteria.** A criterion named `agents/llgenie-pr-engine-improver/SOUL.md`, which does not exist; `git ls-tree --name-only origin/main agents/` named the real one. Cite what the tree has, not what the sentence needs.

## To judge a branch, measure the base

A PR body claimed its regeneration **would introduce** a defect. Measuring `origin/main`'s own fixture showed the defect was
already there — 33 of 162 rows — and that the regeneration would instead **regress 48 correct rows**. Two different
failures, only one of them the PR's, and the difference was visible only in the base.

- **Count the thing in `main` before you count it in the branch.** "This adds N bad rows" and "this adds rows to a tree
  that already has M bad rows" are different sentences with different owners.
- **A body sentence is a claim like any other**, and it survives review by being unchallenged rather than by being true.
  Quote the base measurement beside it.
- The same move settled three corrections in one evening: the ternary fixture, the empty-server placeholder rows, and a
  "no such engine in the matrix" claim that was true of the branch and false of main.

## A progress detector keyed to the files named in a message will demand the wrong edit

An automated "did you make progress" check can derive its notion of relevance from the files mentioned in the message that triggered the turn. When that message describes **another lane's PR**, the check scores the turn as idle unless those files change — and the correct response for this lane is to change none of them. Measured: a stall control whose `requested_paths` were another lane's scripts, with `relevant_mutation_attempts: 0` after a turn that landed a verified skill split, a tested diagnostic and a fleet audit.

The wrong resolutions are the tempting ones: edit the other lane's files on a branch of your own (a phantom conflict in a green PR), or repeat the work in a place the check reads. **Both trade a real green for a counter.**

The right resolution is the one this lane is allowed: **verify on those paths without mutating them** — extract the PR head with `git archive <sha> | tar -x -C /tmp/<dir>` (an extraction, not a worktree, nothing to prune), run the shipped tests and the shipped script there, and report what they did. Measured that way on one lane's head: its script suite passed 9 tests and its audit tool refused with `refs/remotes/origin/main missing` rather than inventing a report — the behaviour its author had demanded of everyone else.

Then say plainly what the check is asking for and why it is refused. **A planner that edits a peer's branch to clear a metric has converted a detector into a source of the drift it was built to catch.**

## A negative control that silently no-ops is not a control

Before trusting a control, prove the control itself ran. Tonight `git stash push <path>` was used to revert a fix and
measure the old behaviour; the file had already been committed, so nothing was stashed, `git stash pop` printed
`No stash entries found`, and the "reverted" run was actually the fixed tree. A control that no-ops is
indistinguishable from one that passes — and from one that would have caught the defect.

- **Put the control's input into an unmistakable state and read it back** (copy the file, write a sentinel line)
rather than relying on a stash/checkout whose failure is silent.
- **Assert the control's premise beside its result**: `OLD_MESSAGE_PRESENT=True` printed next to `test FAILED`, never
a bare `FAILED`.
- **A pair of runs is the evidence, never one**: fixed → pass, reverted → fail, restored → pass.

Same shape as the empty-log trap: `--log-failed` returning empty was read as "no cause found" when it meant "the query
never reached the logs". Both are questions answered by absence, and absence must never be accepted without a positive
control.

## 0. State what you verified: head + minute, or `pending at <hh:mmZ>`

A board line or verdict is a claim about a **head**. Quote the head sha and the minute it was measured in the same
line, or — when you cannot re-read the head in the turn that writes the line — write `pending at <hh:mmZ>` instead of
a state word.

- **A report is accurate at composition and stale on arrival; that is not a lane error.** Relay lag runs minutes, so
  `13/0/1` describes a head that may already have merged. The sha beside the line is what lets a reader see it rotted;
  a state word without one is unfalsifiable and gets quoted onward as current.
- **Count the check buckets, never only failures.** A row reading `0 failed` can carry five `cancelled`/`skipped`
  checks and a deciding gate that never executed. Report `success / failure / cancelled+skipped / pending` as four
  numbers, or say `N conclusions, 0 absences` when every check completed.
- **A fact with an expiry beats a state.** `pending at 22:03Z` is falsifiable by the next reader; "in progress" is
  not. Same for a file size or a copied profile: quote the value measured in the command that used it, never a
  snapshot from an earlier turn.
- **A source that keeps growing is not an unanswerable gate.** When live or derived content grows between turns (a
  profile, a generated file), the growth is bounded by how fast its owner writes — so re-measuring at use time answers
  the gate correctly, which a fresh `CHECK=1` pass at push proves. Do not escalate to a "structural" issue because a
  figure moved; the defect is quoting a stale snapshot, and the fix is the habit, not a redesign.
- **Backticks in a `--body` string are commands, and the failure is silent.** Inside double quotes the shell runs
  each backticked phrase as command substitution before `gh` ever sees it. Measured: a comment quoting a test path
  and a config line *posted successfully* — exit 0, URL returned — with both phrases replaced by the empty output of
  a failed command, so the published text read `can merge with  never having a verdict` and no exit code flagged it.
  The weaker version of this rule ("it exits 1 and posts nothing") is the lucky case; the dangerous one is a
  zero-exit, mangled comment that the next reader treats as the record. **Use `--body-file` for anything containing
  backticks, `$`, or quotes**, and after posting with `--body`, read the comment back and compare it to the intent.

## 1. Is the sha it measured really `main`?

```bash
gh api repos/<owner>/<repo>/commits/main --jq '.sha'
git -C <repo> fetch origin main --quiet && git -C <repo> rev-list --left-right --count HEAD...origin/main
git -C <repo> branch -r --contains <sha-they-cited>
```

- `branch -r --contains` naming only `fork/<branch>` means the numbers describe an unmerged PR branch.
- A local checkout `2 0` ahead of `origin/main` is the usual cause: an agent measuring "the working tree" measures
  whatever branch the owner left checked out, and a feature branch is not main.
- Consequence: the batch's counts are unverified, and any acceptance criterion quoting them cannot be ticked
  honestly. Correct in public, ask the filer to re-measure and cite the sha.

## 2. Does the claimed count name the right population?

Grep against a tree-ish instead of checking out:

```bash
# files matching a pattern
git -C <repo> grep -l '<pattern>' origin/main -- <path>
# definitions by name
git -C <repo> grep -c '^\s*def <name>(' origin/main -- scripts
# a file's size / a specific line
git -C <repo> show origin/main:<file> | wc -l
git -C <repo> grep -n '<symbol>' origin/main -- <file>
```

Populations that look like the same number and are not: *definitions named X*, *definitions whose body lacks Y*,
*all helpers under any spelling*. Name the population, state the enumerating command, and eyeball two or three known
members before ticking.

- **A coverage figure is a set difference, not a subtraction of sizes.** "documented − invoked" and
  "documented ∖ invoked" are different numbers whenever anything is invoked but undocumented: measured 267 documented,
  127 invoked, `267 − 127 = 140` arithmetically, while the true uncovered count was 154. Compute the intersection
  (`len(set(doc) & set(invoked))`) and report `covered`/`uncovered` as set sizes; never subtract two populations.
- **A count that cannot be reproduced is a property of your grep, not of the tree.** Before defending a number, re-run
  it with a broader pattern (option forms, `$(MAKE)`, unindented calls) and see whether the figure moves: a difference
  between `make X` at line start and `make -s X` anywhere produced 31 versus 127 distinct targets on the same tree.
  Adopt the reproducible method, say which method you adopted, and withdraw the old figures explicitly rather than
  leaving two sets of numbers in the issue.
- **A branch is unique only if it ADDS A PATH trunk never had — never by diffing its sha against trunk.** A squash
  merge rewrites commits, so `git diff --stat main...<tip>` reports every file of a fully-merged replay as changed:
  that method counted 133 "unique" branches out of 160, and the same tree yields 6 when the question is asked
  properly. The sound test is `git diff --name-status main...<tip>` filtered to `A` entries, each confirmed with
  `git cat-file -e main:<path>`; two branches adding the same path are one piece of work however different their
  shas. Control the method on a branch you KNOW merged before publishing: an implausible number is a reason to build
  a control, not a caveat.
- **An audit's arithmetic is part of its result.** Buckets must sum to the population — `safe + preserve == total`,
  per branch AND per worktree — or the audit has not finished measuring. Keep the preserve set as an explicit list
  and re-read it each run: a worktree that goes dirty mid-session joins it, and a byte-identical branch is a
  duplicate rather than a sixth item.

## 3. Do two PRs actually conflict, and what is the resolution?

```bash
git -C <repo> fetch origin \
  'refs/pull/<a>/head:refs/remotes/origin/pr-a' \
  'refs/pull/<b>/head:refs/remotes/origin/pr-b' --force
git -C <repo> merge-tree --write-tree origin/pr-a origin/pr-b
```

`merge-tree --write-tree` prints the merged tree sha, then one line per conflicted path in the form
`<mode> <sha-1> 1|2|3  <path>` (base, ours, theirs). Three entries for one path = a real conflict; no entries = it
would merge clean.

What to send back, per conflicted path:

1. the union line (both sides' data preserved, one entry per side),
2. both sides' tests kept, not one replaced,
3. any prose sentence whose subject count changed ("the one X" -> "the X and Y", and the duplicated paragraph
   deleted rather than kept twice).

Ask for the gate output on the **merged** tree (skill/wiring/docs/test targets), then post the recipe as a comment on
both PRs. A recipe that lives only in a DM is lost to whoever merges second.

- **Render any generated index AFTER resolving, never before.** For a file rendered from fragments/notes (a changelog
  aggregate, a manifest), rendering on the old base reproduces the very conflict the rebase existed to escape, because
  the aggregate is a shared append. Order is: land on the new base → regenerate → gate → push.
- **Two independent resolutions of one conflict is a collision, not redundancy.** When a rebase lane and the PR author
  both resolve the same conflict, pick the author's (it holds the semantic knowledge) and park the other explicitly on
  the PR — "superseded by `<sha>`, do not push" — or the next reader sees two parked resolutions and pushes the wrong
  one. Name which resolution was preserved; never let a rebase re-derive a semantic merge that was already made.
- **A rebase lane's own "superset" claim expires with the base it measured.** A branch file that was a superset of
  `main` can become older than `main` once trunk moves, and a wholesale take then silently reverts trunk's fix.
  Compare helper SIGNATURES (params added/removed), not function-name sets.
- **Rebase a branch only after its head has been QUIET; stop rather than race a live author.** Each attempt against a
  branch being pushed finishes on a sha that no longer exists, and every push costs the matrix the PR needs as
  evidence. Measure the head twice a few minutes apart before starting. When a head is replaced under you repeatedly,
  abort cleanly, leave the worktree clean, and hand back with the one-hunk recipe and the traps in a PR comment — the
  right outcome is that the branch lands later with its deviation documented, not that a rebase wins a race.
- **When trunk merges faster than a branch can rebase, stop re-cutting.** A re-cut cancels the run that would have
  evidenced the PR, so the branch pays for being current with the only evidence it had. A head one commit behind that
  still reads `MERGEABLE` owes no action: the diff-vs-trunk check is the fact, ancestry is not.

**Complementary, not contradictory — test before ordering a "pick one".** When a rebase lane stops-and-reports two
implementations that "contradict" (or you sent a lane to "pick which implementation wins"), first check whether they are
actually two *complementary* policies git simply failed to auto-merge because both landed in the same file region:
different time-bases (one reads at check-time, one names the after-commit edit), different severities, different
call-sites. Ordering a "pick one" on complementary code deletes a legitimate behavior. The correct reconcile is
keep-both (union the two behaviors + both tests) and dedupe only the genuinely-redundant shared helper (e.g. two
byte-identical UTC-stamp formatters) onto one canonical name. Only a *genuine* same-timebase trade-off — two versions
of the same decision, one must replace the other — is a "pick one" situation.

## 4. Who approved that merge?

```bash
gh pr view <n> --repo <owner>/<repo> --json mergedAt,mergedBy,reviewDecision,author
gh api repos/<owner>/<repo>/pulls/<n>/reviews --jq '.[]|"\(.submitted_at) \(.user.login) \(.state)"'
```

An `APPROVED` review submitted by the same identity that then merges, seconds later, is an automated merge gate doing
what it was configured to do — not the owner's approval. Report it as an incident with both timestamps, and never
describe it to the owner as "you approved this".

## 5. Read the artefact before characterising the lane

A lane's DM is a summary; the PR thread is the record. Never conclude "that lane reports nothing" or "the verdict only
lives in chat" from the message you received — open the PR and count the comments:

```bash
gh pr view <n> --repo <owner>/<repo> --json comments --jq '.comments[] | "\(.createdAt) \(.author.login) \(.body|length)"'
```

A wrong characterisation costs the lane a defensive reply and costs you the trust needed for the next correction. Say
"I inferred that from the summary instead of reading the thread", in public, once.

**Relaying a lane's finding makes you its author.** Telling the owner "this analysis is what I am adopting" moves the
claim from the lane's account into your report, and if it is later falsified you are the one withdrawing it. Reproduce
the claim with one command before it leaves your turn — the same measurement the lane ran, on the tree you can see —
because a plausible finding with a sha on it is still a claim, and "it sounded right and had numbers" is how a wrong
premise ends up in a PR body that another lane then builds on. A retraction is cheap; a retraction that a third lane
already acted on is not.

## 6. Your own dispatch quotes a stale sha

The sha in a dispatch is stale by the time the lane reads it — the board moves in minutes. Write "fetch and branch from
the sha you get **now**, and name it in your start comment" rather than "branch from `<sha>`", and when you re-check
someone's head, re-check it in the same turn you quote it: `git ls-remote <remote> <branch>` decides the branch tip, and
a cached sha is history, not state.

## 7. "Pushed" means on the remote ref, not committed in the clone

A lane reporting "committed `abc123`" only claims local history; the deliverable is the branch tip. Verify presence on
the remote, and read the ref that decides it:

```bash
git ls-remote --heads https://github.com/<owner>/<fork>.git <branch>   # the FIX, not the PR-object
gh api repos/<owner>/<repo>/pulls/<n> --jq '.head.sha, .commits_url, .changed_files'   # lagging snapshot
```

- The PR-object `head.sha`/`changed_files` is cached and lags a force-push by minutes; the fork ref read via
  `git ls-remote` is the fact. When they disagree, trust the ref and say the PR-object has not caught up.
- **"The ref" means the ref on the PR's OWN head repo — `git ls-remote` of a same-named branch on another remote is
  not the PR head and is usually a stale leftover.** When the head repo is a fork, the branch can exist on both the
  fork and the base repo with different tips; the base repo's copy is the old one. Read
  `pulls/<n>.head.repo.full_name` first and `ls-remote` THAT repo; `ls-remote` of the base repo's same-named branch
  manufactures a fake "the branch and the PR head diverged / two unrelated histories" alarm.
- A claim that the remote head is a new commit when `ls-remote` still shows the old one means the work is
  local-only, not shipped. Correct the lane by naming the exact command that still shows the old head, and require a
  push (not a re-stated commit) before the change is real.
- **"My check passed" is scoped to the tree it ran in — prove that tree IS the PR head.** A lane reporting
  `make sync-agent-profile CHECK=1 → OK 6/6` (or any gate green) has verified whatever checkout it ran the command in;
  if its fix commits are not ancestors of the PR head (`git merge-base --is-ancestor <fix-commit> <pr-head>` = NO)
  and appear on no origin branch (`git branch -r --contains <fix-commit>` empty), the green describes a tree nobody
  will merge. The test being green and the fix being shipped are two facts: verify both — the fix commit is an
  ancestor of the PR head AND the gate re-run against the *fetched* head object (`git show <pr-head>:<file>`), never
  the lane's worktree — before accepting the reload as done. This is the self-report trap one level deeper than
  "pushed": the lane did run the test and it did pass; it just wasn't the deliverable's tree.
- **Mid-operation stream loss is a stop, verified remotely — never a blind `--continue`/`--abort`/push.** When a lane
  reports it opened a rebase/merge and its tool-output stream stopped surfacing (the last N calls ran but returned
  nothing), treat that as a legitimate pause: the lane must NOT fire `--continue`, `--abort`, or any push while it
  cannot re-read its own branch. Verify the remote independently instead — `ls-remote` / PR `head.sha` / "is the new
  main an ancestor of the remote head" — the answer tells you the op never reached the remote (last-good head intact,
  safe hold, nothing half-landed) vs. something pushed. Confirm the pause to the lane, name its last-good remote sha
  as the safe restore, and say resume-on-stream (determine state → resolve conflict → `--continue` → re-gate → push
  with-lease) or `--abort` to the good head if the stream never returns. A mid-rebase that stayed local costs nothing
  and never leaves a stray push; penalizing the lane for pausing teaches it to push blind.
- A stack of unresolved commits accumulating under one PR (`ls-remote` tip advancing every retry while the PR commit
  list grows) is record-churn — verify the content is unchanged since the last independent verdict before trusting it.
- **The push has to land on the ref the PR head actually resolves, not any same-named branch.** A PR opened from a
  FORK (`head.repo.full_name` ≠ the base repo) reads the fork's branch, `refs/heads/<name>` on the fork — a push of
  the same branch name to the *origin* (base) repo is inert: the fix is complete and verified but invisible to the PR,
  which keeps showing the old red head. Before accepting a lane's "pushed," read where the head lives:
  `gh api repos/<owner>/<repo>/pulls/<n> --jq '"\(.head.repo.full_name) \(.head.ref) \(.head.sha)"'`, then push the
  commit to THAT ref (`git push --force-with-lease <fork-url> <branch>` for a fork-head PR). A verified-but-inert fix
  that "is ready for review" while the PR shows the pre-fix head is exactly the report-vs-ref mismatch the whole class
  exists to catch.
- **The two-state trap: a CLOSED PR still reports `mergeable_state=blocked`.** GitHub's pull record has `state`
  (open/closed, authoritative) and `mergeable_state` (computed, reported even on a closed PR because its branch still
  resolves a head) as separate keys. A lane reading `mergeable_state` as the PR state will assert an OPEN/swept/MERGEABLE
  PR that is actually closed, repeatedly, because `ls-remote refs/pull/<n>/head` keeps resolving the branch sha. Ref →
  sha truth is not PR state; read `pull.state` (or the issue `state` + `closed_at`), give the lane the exact key names
  once, and never re-arbitrate a settled `state` fact — the server record wins regardless of a client's field-name
  misread.
- **A closed PR's live successor is a NEW PR number, and the lane usually has not noticed.** When a branch is closed
  (by the owner, or as a duplicate) and then re-pushed, GitHub opens a *different* PR number on the same
  `headRefName`; the old number keeps resolving a head and `mergeable_state`, so a lane polling "my PR" by number
  reports `armed`/`awaiting CI` for hours against a vehicle that is dead. Correct the lane to the successor by
  number, not with a bare "that's closed": `gh pr list --repo <o>/<r> --head <branch> --state all` maps branch → every
  PR it has ever had. The board line is the successor's `state`+`headRefOid`, and the closed one's own
  `closed`/`closedAt`/`mergedAt` is the proof it is not the live vehicle.
- **"I withheld the push" beside a sha that IS the pushed head is a self-contradiction — measure which is true.**
  When a lane's report couples a no-push claim with a sha, resolve it against both the remote and the PR object:
  `git ls-remote <remote> | grep <sha>` (did it land, and on which `refs/pull/<n>/head`?) and
  `gh pr view <n> --json state,headRefOid` (does an OPEN PR carry that head?). One of the two claims is false and the
  trail should say which; a lane that describes a state it did not create is relaying a phantom, not reporting.
- **A sha that "is not in the repository" may only be UNREACHABLE.** `git log --all` and
  `git for-each-ref --points-at` enumerate REFS, so a force-pushed-away head is reachable from none and both
  commands return nothing — while the object still exists on the server. Confirm existence with
  `git cat-file -t <sha>` and `gh api repos/<o>/<r>/commits/<sha>`, then say "unreachable from any ref", never
  "does not exist". Repeated history replacement is what produces this: every superseded head survives as an
  object and vanishes from the ref graph, so a reader who measured it an hour earlier was not fabricating it.
- **A commit on the branch is not the fix if a later command discarded it.** Two silent erasers, both seen in
  one evening: `git checkout HEAD -- <path>` reverts a file's edits made this session (a lane's classifier fix
  disappeared and the PR shipped a body describing code it no longer contained), and re-seating onto a moved
  trunk can DROP whole commits (a generator fix plus its test vanished from a head whose summary still
  reported both). Read the deliverable at the pushed head — `git show <head>:<path>`, and
  `gh pr diff <n> --name-only` to see the file list — never the lane's account of its own commit list. When
  asking a rebase lane for a pre-push check, include commit preservation: capture
  `git log <base>..HEAD --oneline` before the rebase and diff it after; a commit that disappears is a red.

## 7.5 "Green" names one gate; a PR needs all of them

A lane's "GREEN" is almost always **the gate it was asked to run**, and it arrives in tables that invite you to read
it as the PR's verdict. A census/schema/doc gate returning rc=0 on six PRs says the gate is fixed — not that six PRs
are landable. When a lane reports a batch verdict, re-derive the full required set yourself at each head and label the
rows honestly:

```
gh api repos/<o>/<r>/commits/<head>/check-runs \
  --jq '[.check_runs[]|{n:.name,c:(.conclusion//.status)}]|sort_by(.n)|.[]|"\(.n): \(.c)"'
```

- Row vocabulary: **GREEN** only when every check is `success`; **pending** when any is `in_progress`/`queued`;
  otherwise `<gate>-clean, <othergate>-RED` naming the red one. "census-clean, openspec-red" is the honest label for a
  PR that passes one gate and cannot merge.
- Accepting a batch "5/6 GREEN" built from one gate creates false holds in one direction and false confidence in the
  other; correcting it costs one API call per row and is the planner's job, not the lane's to remember.
- Same rule for a lane that quotes a head from its own earlier measurement: the verdict is only valid at the head read
  in the same breath, so re-read `pulls/<n>.head.sha` and quote it in the row.
- **A cancelled fan-out forges the row of a legitimate skip.** When the job that computes the matrix is cancelled,
  every downstream job reports `skipped` — byte-identical to a job deliberately not required for that diff. Measured:
  the same PR, same class of change, ran its deciding gate and red-ed on one head; after a push cancelled the fan-out,
  the next head reported that gate `skipped` with `0 failures`, and it was armed. `skipped` already means "this diff
  needs no such job", so the cancelled case does not merely look ambiguous — it borrows that meaning's credibility.
  Acceptance for the fix: a cancelled fan-out must fail the pipeline or mark its dependents `cancelled`, never
  `skipped`, so the two states stay distinguishable in check-runs output.

## 8. A fix only closes its issue if the body carries a closing keyword

GitHub auto-closes an issue only when the PR body uses a closing keyword (`Closes #n`, `Fixes #n`, `Resolves #n`);
`Refs #n` merely links and never closes. A fix PR that is otherwise complete can leave its issue "open and unassigned"
for a full cycle because of one body word, and every re-flag reads like the work is missing when it is only the link:

```bash
gh pr view <n> --json body --jq .body | grep -iE 'closes|fixes|resolves'
gh pr view <n> --json closingIssuesReferences --jq '.[].number'   # indexed ASYNCHRONOUSLY: empty early is not absence
```

`closingIssuesReferences` does populate on an OPEN PR — it is simply indexed with a lag of minutes, so an empty read
soon after creation is inconclusive rather than corrective. Read the body keyword for the author's intent and re-read
the field before asserting a gap. When a "completed but never-closed" issue shows the fix already in a PR, the move is
to fix the body keyword (and note it), not to re-dispatch the work or force a rebase.

## 8.5 Two reports of one defect are one issue, not two findings

You and a lane can file the same defect minutes apart while both are measuring the same board. The second filing is a
duplicate, and leaving both open splits the evidence and the eventual fix across two threads.

- **Keep the one with measurement, close the one with principle.** A rate ("16 of the 40 most recently merged PRs
  carried neither artefact") outranks a restatement of the same asymmetry, because it settles the "surely there is an
  exemption" defence before anyone raises it — measured examples like a 25-file change among the offenders.
- **Close with a pointer, and move the unique contribution across as a comment.** The family table, the proposed
  acceptance test, the negative-control requirement — carry them into the surviving issue rather than letting the
  closing take them with it.
- **Say in one sentence which you closed and why.** An owner who watches one of two filings disappear cannot tell a
  consolidation from a lost report, and `not planned` alone reads as rejection to whoever wrote it.

## 9. A self-referential "verified" is a finding to fix, not a claim to accept

When a gate or a doc measures the thing it lives inside, a literal self-identity check is unsatisfiable-by-design and
every pass self-verifies. Measured shape: a census gate whose doc carries a `measured-at <sha>` pointer *inside the
tree it counts* — making `pointer == HEAD` mean "writing the doc re-heads the tree", so the gate can never fail. "Passing"
such a gate proves only that the gate ran, never that the census is true; against a moved `main` its numbers disagree by
exactly the gate's own unmerged files (a self-reference, not a confirmation).

- The review question is not "does the pointer equal HEAD" but "**would this check catch the drift it exists to catch**".
  A count-based invariant — the pointer resolves to a real commit (`git cat-file -e …^{commit}`, so a dangling sha
  reds) AND the pointer's tree carries HEAD's tracked count (so the census reds the moment `main` grows past it) —
  reds on the real defect and stays green across rebase/squash.
- When you find a gate or doc that only self-references, flag it for the fix (and require the negative control: a
  consciously-wrong pointer and a drifted count each red) rather than accepting its green. Green-through-squash is a
  property, not a defect, once the invariant is drift-catchable.

## 10. A passing local check can be a false green on a fresh clone of main

A gate that resolves a git object (a `measured at \`<sha>\`` pointer, a blob, any `cat-file`/reachability probe) can
**pass in your working clone and fail on GitHub's fresh main clone** because the working clone carries refs a fresh
clone does not — PR branches, `refs/pull/<n>/head`, worktrees. Measured shape: a squash-merged PR whose `docs/`
pointer names its own **pre-squash** commit. In the developer clone the commit is reachable (the PR branch ref still
names it, so `cat-file` succeeds); GitHub's CI clone fetches only `main`, has no PR refs, and the pointer dangles —
`[census-gate] measured-at: the doc's pointer \`abc\` is not a real commit (dangling from an amend?)` reds main's own
pipeline even though the merged change is correct.

- **The reachable-in-my-clone check is not the fresh-clone check.** A squash rewrites the commits, so `measured at`
  pointing at the pre-squash sha is dangling to anyone who reads `main` in isolation. To prove a pointer survives a
  clean clone, test reachability FROM main, not object-presence in your ref-ful checkout:
  `git merge-base --is-ancestor <ptr> refs/remotes/origin/main` must be YES. (Disconnect this from the genuine
  `merge-base --is-ancestor <old-head> main = NO` on an unmerged branch — a pointer to a live pre-merge head is fine;
  only a pointer to a commit main itself cannot reach is the bug.)
- **Squashing your own fix can strand its own pointer inside the squash.** When a fix re-derives a census/snapshot
  and records the sha it measured `at`, and then is squash-merged, the recorded sha is by definition pre-squash. Re-point
  the recorded `at` to a main-reachable commit (re-derive at the merged head, or point at an actual ancestor) so the
  gate a fresh CI run reads is green — otherwise the fix lands and immediately reds every later main run, and nobody
  sees it because every working clone still resolves the old commit.
- To verify a main-pipeline red is truly fixed, run the check in a **fresh** worktree off `refs/remotes/origin/main`
  (`git worktree add`, detached HEAD), never in the clone that has the PR refs — that is the only faithful reproduction
  of what CI will see.

## 11. Reproduce CI's tree locally — `merge-tree` between trunk and the head

A pull-request CI run checks out the **merge of the head into the base**, not the head alone. That is why a gate can
red CI while the branch passes it locally, and why an extracted tarball of the head is the wrong fixture for any gate
whose script or fixture lives on the trunk.

```bash
# the head's OWN repo first — a cross-repo PR is read from the fork
gh api repos/<o>/<r>/pulls/<n> --jq '"\(.headRepositoryOwner.login)/\(.headRefName) \(.headRefOid)"'
git -C <repo> fetch <fork-remote> '+refs/heads/<branch>:refs/remotes/fork/pr' --force
git -C <repo> rev-parse --short refs/remotes/fork/pr          # MUST equal headRefOid above
T=$(git -C <repo> merge-tree --write-tree origin/main refs/remotes/fork/pr | head -1)
rm -rf /tmp/merge && mkdir /tmp/merge && git -C <repo> archive "$T" | tar x -C /tmp/merge
cd /tmp/merge && python3 scripts/<gate>.py <the-subcommand-the-Makefile-runs>
```

- **Confirm the fetched tip equals `headRefOid` before measuring anything.** A same-named branch on the base repo is a
different sha; fetching it silently yields a false red (or a false green) about a branch nobody will merge.
- The merged tree is also the right place to answer "will this land green": a gate that reds on the merge but passes on
the head is a stale-base artifact, which is a style fix, not a rebase.
- An empty extraction of the head alone (script missing) is the tell that the gate lives on the trunk and the head
tarball was never a faithful fixture.

## 12. `cancelled` is not a verdict, and a re-run has no check-run while queued

A `completed/cancelled` check proves nothing: the job never produced an answer, so an armed PR sits "waiting" on a run
that is already dead. And once you re-run it, the commit **carries no check-run for that job until the new attempt
starts** — so a naive board read shows the PR with the check missing rather than pending, which reads as "never ran".

```bash
gh api repos/<o>/<r>/commits/<head>/check-runs --jq '[.check_runs[]|select(.name=="<job>")]|.[0]|{status,conclusion}'
gh run rerun <run-id> --repo <o>/<r>          # legitimate: re-running a dead run is not cancelling a live one
gh api repos/<o>/<r>/actions/runs/<run-id> --jq '"\(.status)/\(.conclusion) attempt=\(.run_attempt)"'
```

Quote the **run id and attempt number** while it is in flight, never the check aggregate — `null` is not `pending`,
and `cancelled` is not failure. Re-running a cancelled run is allowed; cancelling a *live* one never is.

**A frozen `updated_at` is not a hang.** `run.updated_at` records the last *event* and does not advance while a
single long step executes, so a 25–50 minute `make ci-unit` shows a frozen tick while working normally. Measured
cost: three lanes read a frozen tick as a hang in one evening; one reported a run "frozen 32 min" that had in fact
concluded `cancelled` after eight minutes, cut by its own superseding push.

- Declare a hang only on a run that **exceeds the worst duration actually measured for that job that day AND still has
  not concluded** — never on a frozen tick, and never on a low-end guess at the band.
- Calibrate the band from a run that **finished**, not an average: a 49-minute `ci-unit` that concluded `success` is
  the honest upper bound, so 36–49 minutes is contention, not a stall. Re-derive it daily; it moves with runner load.
- The fields cannot distinguish slow from stuck. Say so — "inside the measured band, no conclusion yet" — rather
  than picking the more alarming of two unsupported readings.
- **A `cancelled` leg that dies at a near-constant duration is a declared TIMEOUT, not a hang and not a supersede.**
  Measure `started_at → completed_at`; a cluster within seconds of one another across unrelated branches is a ceiling.
  Measured: five legs ended `completed/cancelled` at 60m23s–60m31s, and the workflow declared
  `timeout-minutes: 60` on exactly that job. The same status word also covers an 18-second supersede, which demands
  the opposite response — so **quote the duration with the word, always**. Read the ceiling from the workflow before
  theorising about cause: `grep -n -A6 '^  <job>:' .github/workflows/*.yml` then its `timeout-minutes`. A single
  outlier outside the cluster is a separate mechanism — report it as unexplained rather than folding it in.
- **Superseding a live run still requires: measured past the band, the diff cannot affect the failing test, and a fresh
  head known-good by another measure. Never push over, or cancel, a run that is merely slow.

## 13. Anchor a grep to the construct you mean

A substring proxy finds prose about the thing as well as the thing. Measured shape: `grep -c '<co-author address>'`
returned 2 on a range where no such trailer existed — both hits were commit messages *documenting the trailer class* —
while the anchored form returned 0.

```bash
git log --format=%b <range> | grep -i '^co-authored-by' | grep -c <name>   # the trailer
```

Before reporting a count as a defect, ask what the pattern would match if the artifact were described rather than
present. If the answer is "the description too", anchor it (line start, field name, JSON key) or parse the structure.
The gate that parses the construct is the authority; a grep is only a hint.

- **`git merge-tree --messages` prints informational notices on the same stream as errors.** `Auto-merging <path>`
  appears for every cleanly auto-merged file, so grepping that output for a PATH returns a hit whether or not the file
  conflicted. The sound test is anchored and case-sensitive: `grep -E '^CONFLICT'` (or read the tree sha it prints).
  Measured cost: a filename grep on a four-file PR manufactured a conflict claim about the one file that had
  legitimately auto-merged — the same class as any other proxy that matches the neighbouring thing.

## 14. A sha near a lane's work is not the lane's work

Before crediting a commit to a lane, read its author and committer:

```bash
gh api repos/<o>/<r>/commits/<sha> --jq '"\(.commit.author.name) | \(.commit.committer.name) | \(.commit.author.date)"'
git -C <repo> merge-base --is-ancestor <sha> <lane-head>   # does the lane's branch even contain it?
```

A squash the owner performed on their own account, sitting hours after the lane's last push on the same branch, is
the owner's commit. Crediting it to the lane is the same defect as accepting a status without its `completed_at`:
accepting an artifact because it is adjacent to work you were tracking. Lanes will correct this themselves — a lane
that refuses credit it did not earn is giving you a measurement, not modesty.

## 15. Armed auto-merge fires when the LAST check concludes — arm on done

`gh pr merge --auto` does not merge when armed; the merger sweeps when the final required check turns `success`. A
merged PR whose `mergedAt` trails its last check's `completed_at` by seconds is the mechanism working, not a bypass.
So the trigger to arm is **the work being finished**, and the confirmation is reading `autoMergeRequest` back — the
`--auto` exit code is not the fact (it exits 0 and arms nothing when the base is not the default branch).

Corollary for reporting: when a PR is green, approved and `arm=none`, it is **finished but unmerged by policy** — say
that, and name where the rule lives, rather than describing it as waiting on CI.

**An arm records a TIME, not a HEAD.** `autoMergeRequest.enabledAt` is set once and survives every later push —
measured: armed against one head, it reported the same `enabledAt` after two force-pushes, one of which carried a gate
that never executed. So "armed at <time>" cannot tell a reader which sha it referred to, or that it now applies to a
head nobody armed.

- Before reporting a PR as armed, read `headRefOid` **and** `enabledAt` in the same call; if the head has moved since,
  the arm states an intention about an ancestor.
- Dispatch consequence: "re-run the cancelled checks on that head" is valid only while that head IS the PR head. On a
  superseded sha the cancelled jobs are gone, not failed — re-read `headRefOid` first, then either re-run on it or push
  once and let a fresh matrix run.
- After a squash-merge, `mergeable`/`mergeStateStatus` describe nothing and `merge-base --is-ancestor <pre-merge-head>`
  correctly returns NO. Verify the merge by **content**: `state=MERGED` + `mergedAt`, the file present on `main`
  (`git show origin/main:<path>`), and `cmp -s` against the source matching — not by ancestry.

**A lane's own versioned charter outranks your dispatch to arm.** Before asking a lane to arm, check whether its
`agents/<lane>/SOUL.md` permits `gh pr merge` at all; a reviewer/auditor lane typically forbids merging *and* arming in
one sentence. Record `auto=none (lane charter: <path>)` and hand the arm to the owning lane or the owner — do not
re-issue the request, and do not arm it yourself on the lane's behalf to "finish the row". The lane declining is the
control working, not a gap in its cooperation.

**A disarm carries no memory — it must be written down and re-checked.** `autoMergeRequest` is one writable field with
no history, so from any later pass "not armed" reads identically whether nobody got round to it or the author stopped
it deliberately. Measured cost: an automation pass re-armed a PR whose author had disarmed it 26 seconds earlier to
keep a rule it had already falsified from landing.

- An author who disarms must post the reason and the re-arm condition as a PR comment (`disarmed: <reason> — re-arm
  when <condition>`) and name the comment id in its report; the field alone is invisible to every later pass, including
  its own.
- After any automation pass over the board, re-read `autoMergeRequest` on every PR that was deliberately disarmed. An
  arm that reappeared is a defect in the pass, not a decision — disable it again, cite the author's comment, and file
  the automation gap rather than arguing with the tick.
- Acceptance for the fix: a check that fails when a disarm reason exists on a PR and `autoMergeRequest` is set on the
  same head, plus a tick summary that reports `skipped M (author-disarmed)` with the comment id, not a bare `armed N`.

**The identity field cannot tell you who armed it.** `enabledBy` names an account every lane in a one-identity fleet
shares, so it attributes nothing. The actor is distinguishable only from the automation's own report plus the per-PR
timestamp — read `headRefOid`, `autoMergeRequest.enabledAt` and `enabledBy.login` in one call and match the time
against the pass's published arm list.

- A scheduled report-only workflow that states in its own header it never mutates a PR did not arm anything; the
  actor is the pass that publishes `#n <timestamp>` arm entries. Match those timestamps against `enabledAt` before
  accusing a lane — a repeated accusation from a shared identity is the same defect as crediting a commit by
  adjacency (§14), pointed the other way.
- A guard that can only express "should be armed" will red a PR whose author deliberately disarmed it, punishing the
  lane that did the right thing. That is a defect in the guard, not in the lane.

## 16. A checker you have never seen fail is a ritual

Before trusting a new gate, verifier or report script, exercise its failure path — otherwise its green is
indistinguishable from a checker that never ran.

- Give it negative controls that must red, one per defect class it claims to catch (a committed conflict marker; a
  regenerated aggregate whose rows no longer match a fresh render). Quote both exit codes. A checker that only ever
  prints OK is worthless, and that test is what separates a gate from a ritual.
- **A generated block must be byte-identical to the committed form, and lint-clean.** When a generator writes into a
  file a linter also reads, the two can disagree silently: a marker/capability block emitted a heading immediately
  after its marker while every committed block carried the blank line lint requires, and the mismatch stayed invisible
  because the block is written once and thereafter only copied, never re-rendered. Acceptance: render every profile's
  block and assert lint-clean AND byte-identical to the file on trunk, with the control that the test reds before the
  fix.
- Generalise it: any tool whose output is committed needs a test comparing **rendered output to the committed
  artefact**, not a test that the tool exits 0.

## 17. Prefer a canary over a tolerance marker, and guard the next fixer

A project that forbids skip/xfail leaves no marker for "known defect, tracked, must not red the build". The
usable substitute is an ordinary assertion on the defect's observable, written so it reds the moment the defect
is fixed:

```python
def test_the_known_defect_is_still_present():
    n = count_rows_matching_the_defect()
    assert n > 0, "defect fixed — delete this canary and the note referring to it"
```

- It forces removal (the property `xfail(strict=True)` is used for), it states why it exists, and it cannot be
  read as "expected to fail". Pair it with a **guard test** so the obvious future repair fails loudly: a later
  lane's reasonable instinct ("this red needs a non-red, regenerate the fixture") must red a test named for
  what it protects, instead of silently baking the defect back in.
- **Decide a regeneration by FIELD diff, not file diff.** Compare the produced artefact to trunk per field: if
  only provenance changes (`measured_on`, `variant`), the regeneration records the same data under a corrected
  label and may land; if `server`/`tps` change, it rewrites what the data asserts and must not land while the
  cause is unfixed. Quote the field totals (`{measured_on: 4, tps: 7, server: 4}`) — "N lines changed" cannot
  distinguish the two. Check the trunk value before arguing about it: one fixture legitimately carried BOTH a
  correct and a defective value for the same model, so "trunk already has the defect" and "trunk is correct"
  were each half-true, and the wrong premise changes the scope of the fix.
- **When a gate's own semantics are ambiguous, exercise BOTH outcomes before concluding what it bans.** Two
  hooks disagreeing over xfail — one red-ing every skipped report, one exempting `wasxfail` — mean a marker
  that reds when its case fails can still stay green when it unexpectedly passes. That is inconsistent between
  its own two results, not uniformly forbidden; say which outcome decided it and pick one rule deliberately.

## 18. One profile, two copies of the same skill: the readers split

A lane that reports "my skill edits are in place but the tree comparison keeps failing" may have the skill at
two profile paths. The two copies are read by different tools:

```
skills/<category>/<name>/SKILL.md   <- skill_view() LOADS this
skills/<name>/SKILL.md              <- the sync/gate COMPARES this
```

Every `skill_manage` patch lands in the loaded copy while the gate compares the other one, so the check fails
for reasons unrelated to the edit and the lessons exist nowhere in the tree. Neither tool can tell you the
other copy exists — both report success.

- Detect it in one command before accepting or rejecting the lane's story:
  `find ~/.hermes/profiles/<profile>/skills -name SKILL.md | xargs -n1 dirname | xargs -n1 basename | sort | uniq -d`
  (empty = single copy). Run it for your own lane too before quoting any drift number — a two-copy profile
  makes a measured "live is longer than the tree" figure an artefact rather than drift.
- Reconciling a split copy is a subset proof, not a copy: measure tree-only lines that would be LOST (must be
  0), copy, then verify every non-blank line of the target is present. A diff showing deletions is usually
  MOVED lines (diff counts a move as delete+add) — prove each is present rather than waving it away.
- **A script verified only in its profile copy is unverified as a shipped artefact.** Execute the tree copy at
  least once before calling it done: a pre-push verifier run only from `~/.hermes/profiles/...` printed
  `base=refs/rem` (a `${REF:0:8}` truncation) — a check that misreported what it verified, invisible until the
  committed copy ran.
- Profile scratch is pruned; anything a lane builds to last (audit script, verifier, reporter) must be
  versioned under `agents/<lane>/` by issue + PR, or it dies with the cache. The same applies to the lessons:
  a rule that exists only in a profile is lost at the next reinstall.

## 19. A reporter that advances state before delivery loses the report permanently

A delta/alarm job that writes its new baseline first and sends second cannot tell "delivered" from "lost": when
the send fails, the in-memory delta is gone and the next pass diffs against the already-advanced baseline, finds
nothing new, and emits silence. That silence is indistinguishable from "no change", so the alarm is not late —
it is unrecoverable.

- Order it: compute → append to an outbox → perform the send → only then advance the state that makes this pass
  "done". A failure after the outbox leaves a record to re-send; a failure after the state advance leaves nothing.
- Stamp every emitted line with the **measurement time of the fact it reports** (`[measured HH:MM:SSZ]`), never the
  run time — a delayed delivery then reads as delayed instead of as current.
- Prove recovery instead of asserting it: discard the send output to simulate a failed delivery, run again, and
  assert the second run re-emits the SAME items; a third run must then be empty (idempotent). Restore the real
  baseline before finishing.
- One level up, the same defect emits STALE DISPATCHES: a queue task whose subject already carries a merged PR or
  a closed issue is re-emitted because the producer never re-read `state`/`mergedAt` at emit time. The receiver then
  spends a turn disproving a task that merged hours ago, and a stale dispatch is indistinguishable from a fresh one.
  When you receive one, correct the item AND report the producer's ordering defect — it will recur every pass.

## 21. Ask what actually GATES the merge before reporting what CI says

Every green, red, cancelled or missing check is a statement about **information**, not about whether a merge can
happen. Establish the gate before drawing conclusions from a board full of checks:

```bash
gh api repos/<o>/<r>/rulesets --jq '.[]|"\(.name) \(.enforcement)"'
id=$(gh api repos/<o>/<r>/rulesets --jq '.[0].id')
gh api repos/<o>/<r>/rulesets/$id --jq '[.rules[].type]|join(", ")'      # want: required_status_checks
gh pr view <n> --json mergeStateStatus,reviewDecision --jq '"\(.mergeStateStatus) \(.reviewDecision)"'
```

Measured shape: a repository whose only ruleset listed `deletion, non_fast_forward` — **no `required_status_checks`** —
so every check could be red, cancelled or absent and the merge was unblocked by it. The only gate was
`reviewDecision: REVIEW_REQUIRED`. Six hours of analysis about whether a cancelled suite "forges a green" was, in
that repo, analysis of a forgery that would have merged nothing either way.

- **`mergeStateStatus: BLOCKED` plus `reviewDecision: REVIEW_REQUIRED` commonly means the review is the sole
  requirement.** Repo rulesets may be unreadable with a given token and an org-level ruleset may supply checks — say
  which you could read, and treat the configuration as a hypothesis until `required_status_checks` is seen.
- **Report the gate with the finding**: "cancelled, and it cannot block a merge (no required checks)" is a different
  fact from "cancelled, so we nearly merged untested work". The first is throughput; the second is an incident.
- **`--auto`/auto-merge is near-meaningless without required checks.** Arming then decides only what happens after a
  human approves, so an armed-and-untested PR is waiting on a signature, not on a matrix.
- When the answer is "nothing gates", that is an owner-level settings change. File it with the candidate check names
  and the cost, and change no settings yourself.

## 20. Prove a one-line fix without owning the branch

When a tiny fix cannot land — its lane is owner-word gated, its mailbox rejects delivery, or its PR keeps losing the
commit to a rebase — the planner can still convert "blocked" into "one edit, verified" without breaking the rule that
this lane opens no branch:

1. Apply the change in the working tree, then measure **before and after with the same command** (render the output
   and compare it to the committed artefact; run the gate that rejects it).
2. Revert immediately (`git checkout -- <path>`) and confirm `git status --porcelain -uno` is empty, so the shared
   checkout is not left dirty for the lanes that measure it.
3. Post the diff, both measurements and the one verification command that decides it as a comment on the issue, and
   say plainly that it was applied, measured and reverted — not committed, not pushed.

This is measurement, not implementation: the owning lane still makes the edit, but it no longer has to discover
whether the fix works. Do not use it to ship code, and do not leave the tree modified — a dirty tracked file in the
shared checkout reds other lanes' cleanliness checks and is indistinguishable from their own uncommitted work.
