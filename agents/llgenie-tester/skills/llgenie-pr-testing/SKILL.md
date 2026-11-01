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

## Role artifact (2026-11-01)

The artifact is the test evidence: failing test name or pass count, job id, sha, and run id. Do not take another lane's fix. `message_agent` to `llgenie-planner` with the PR number, the sha, and the run id.

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
- **The SAME artifact reds a WHOLE unit-suite run on a detached worktree — dozens of "failures", all
  artifacts, none of them the branch.** `scripts/unit_tests.py run` in the container on a worktree
  mounted without the parent repo reds every git-dependent test at once (tracked-file scans,
  secret-scan's committable set, registry prev-revision, engine-bump): a wall of `FAILED` whose one
  cause is `git ls-files → fatal: not a git repository …/worktrees/<id>`. Never report that count as a
  branch red — judge unit from CI (a full checkout) or a full clone, and prove it is the artifact
  before dismissing it: `git ls-files | wc -l` non-zero on the HOST at the same worktree, or one
  failing node green under a non-git assertion.
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
- **`make test-unit` runs the test IMAGE itself — run it on the HOST from the worktree, never nested
  inside a `docker run`.** The Makefile derives its container mounts from `override ROOT := $(shell
  pwd)`, so a nested invocation computes `$(pwd)` = the container's own mount (`/repo`), which does not
  exist on the host, and the inner docker call has no `/var/run/docker.sock` to reach: the run dies with
  a docker-socket `Error 125` in seconds. Split the roles by what each needs — per-file `python -m
  pytest` in the image is the inner loop (needs deps, no docker); the full gate is a host `make` run
  from the worktree (needs docker + the real host path). If you see `Error 125`/`Cannot connect to the
  Docker daemon` from a gate, you nested it — that is your invocation, not a repo failure, and it must
  be disclosed as an operator artifact, never reported as a red.
- **A pushed branch schedules no CI — the PR is what triggers it.** Every workflow here gates
  `pull_request`, so a green local run plus a branch with no open PR has zero `gh pr checks` output; a
  verdict at the head needs the PR opened first, and the run at that head is the one you cite.
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
completed — read the job by id instead. **`gh api …/jq` does NOT accept jq's own flags** —
`gh api <path> --jq '…' --arg R "$R"` fails with `accepts 1 arg(s), received 4`, because `--arg` is
handed to `gh`, not to the jq filter it runs. Interpolate in the shell instead (build the filter with
the value already substituted, or loop in bash and echo the run id beside the output). A silent `[]`
from a `--jq` that swallowed the value reads exactly like "no job matched". **`gh pr view --json
mergeCommit` is an OBJECT, not a string** — `--jq '{mc:(.mergeCommit//"-")[0:8]}'` dies with
`expected an array but got: object`; use `.mergeCommit.oid` or
`--template '{{if .mergeCommit}}{{.mergeCommit.oid}}{{end}}'`, and expect it null while the PR is open. **A `completed/success` run is not the stage verdict if it
is the WRONG workflow** — this repo has `guard`/`scope`/`holds` and `CI` workflows, and a green
`holds` run (jobs `guard`,`holds`) says nothing about `linux / unit`. Enumerate the jobs and match
the stage name (`linux / unit`), and check the run's `workflowName`, before citing a run id as
"unit green"; a success run of `guard`+`scope` has no unit job at all. Also worth knowing: `gh run view <id>` can report
`cancelled` for a run whose job genuinely FAILED (a later push cancels the run); judge red/green with
`gh api .../actions/jobs/<job-id>` (status+conclusion+steps), not the run conclusion, and never from
`gh pr checks`'s fail column.

- **A `pull_request` job's git HEAD is the MERGE ref, not the PR head — a gate log naming a different
  sha is not evidence of a wrong tree.** `actions/checkout` on `pull_request` fetches
  `+refs/pull/<n>/merge` and checks it out, so the job log reads `HEAD is now at <merge> Merge
  <head> into <base>` and a gate inside it reports e.g. `referent <ptr> is an ancestor of HEAD
  (<merge>)`. Before calling a run "measured the wrong commit", grep the log for the checkout line:
  `gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'
  | grep -iE 'checkout|HEAD is now at'`. A `Merge <pr-head> into <main-side>` HEAD means the gate ran
  on the post-merge tree — which for a "must be green on a clean merge-tree" criterion is the RIGHT
  tree, and the strongest evidence available. Do not fetch that merge sha as a branch; it exists only
  as the synthetic ref.
- **For a docs-only diff, ci-scope's `scope` job IS the gate — a missing `linux / unit` run is correct,
  not "unverified".** The `WRONG workflow` rule above bites a CODE PR cited off a green `guard`+`scope`
  run. The mirror holds for a docs/doc-pointer re-point: `ci_scope` classifies the diff `docs`, and its
  `scope` job runs the gates a docs-only PR still needs (`make check-docs` → `check_architecture_census.py
  check`, `check-docs-fragment-only-agrees`, `openspec-tasks`) with NO unit matrix scheduled at all.
  So state the verdict as "PASS on the dispatch's gate (scope/check-docs green at <head>) with the unit
  matrix not run because the diff is docs-only" — explicitly naming the absent stage as an EXPECTED
  selection beats both calling it unverified and silently implying a full suite ran. Confirm the gate
  actually executed by grepping the scope job log for `make check-docs` and the gate's own OK line
  (§2b), never from the job's `conclusion=success` alone.

## 3. Audit coverage against the diff, not against the PR body

For every changed path ask "which gate fails if this is wrong", then check a test proves it. The PR
body's "Measured:" block is a claim, not evidence — reproduce the counts.

- **A guard's exemption is CODE, not the docstring that describes it.** Before calling a carve-out a
  live hole, read the resolver's entry set and its transitive reach set: if the exempted call is
  reachable through an entry that IS already in the set (`helper → entry → … → the I/O primitive`,
  sliced through helpers), the exemption is correct by construction and the prose merely describes it.
  A docstring sentence saying "X is not flagged" is DERIVED text; the names the guard actually matches
  on are the fact. Judging the prose manufactures false "gap" findings against a sound guard.
- **Probe a reach/scan helper by calling it on a STRING, not by dropping a synthetic test file in.**
  These helpers are usually driven by a loop over the suite roster (`ut.select(repo)`); an in-memory
  synthetic module is not in that roster, so the loop never visits it and the probe returns 0 findings
  — which reads exactly like "the guard does not bite" and sends you to "fix" a working guard. Call
  the scan function directly (`_hub_opens(<source string>)`) for the mechanism question, and answer the
  roster question by listing the real files that carry the call
  (`grep -l '<symbol>(' tests/*.py`) and checking each one's marks and `unit-suite.json` membership.
  "The file I touched has no offenders" and "the guard sees nothing" are two different claims; only
  the roster tells you which one you measured.
- **An exemption restored by the newest commit touching the same file is a DECISION, not a
  regression.** `git log --oneline -1 -- <guard file> origin/main` names that commit; if its message
  says seal/carve-out/exempt, the current state is intentional. Before filing residue on it, check
  whether the exempted callers are hermetic (planning-only paths that never open the live host) — an
  exemption that keeps a set of hermetic callers from false-redding is doing its job, and "the docs
  still mention the carve-out" is not a defect.

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
- **Never message a partner lane with "armed / watcher running / reviewer can go" without reading
  `.state`/`.mergedAt` in the same breath — the merge may already have landed.** Arm-time, watcher
  start and "checks green" are REACH-state: they describe the instant before the merge, and auto-merge
  can fire minutes later while a background watcher is still running. A report built from those is
  stale-on-arrival and draws a correction from the planner. The cheap guard: open every status message
  about a PR with `gh pr view <n> --json state,mergedAt,mergeCommit` and lead with the measured word.
- **A state you already told another lane is a CLAIM — re-read it before repeating it, and correct it
  on-record when it moved.** Issue/PR state quoted from memory or from your own earlier comment goes
  stale silently: `#N stays open for the other lanes` was false while the issue read
  `state=CLOSED`, `stateReason=COMPLETED`. Before putting an id's state in a message or a comment, read
  it in that moment — `gh issue view <n> --repo <r> --json state,stateReason,closedAt` (or `gh pr view
  <n> --json state,mergedAt`) — and when a state-driven instruction arrives, treat the live field, not
  the dispatch, as the fact. To learn WHO/WHAT closed it before you credit anyone, read the timeline:
  `gh api repos/<o>/<r>/issues/<n>/timeline --paginate --jq '.[]|select(.event=="closed" or
  .commit_id!=null)|{event,by:.actor.login,commit:(.commit_id[0:8]//"-")}'`. A correction that exists
  only in your head is not a correction: post it where the wrong claim lives, with the measured field
  and the sha, in the same shape as the original.
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
  **A scratch clone whose `origin` is a LOCAL clone (not the network remote) has no
  `refs/pull/<n>/head`** — fetch it in the CANONICAL clone first
  (`git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>`), then fetch that ref into the scratch
  (`git fetch origin refs/remotes/pr/<n>:refs/remotes/pr<n>`). A `couldn't find remote ref` in the
  scratch clone is the local-origin tell, not a missing PR — fetching there alone silently leaves you
  measuring a stale HEAD you never moved. **Once fetched, never pass `refs/pull/<n>/head` to a local
  git command.** `git merge-tree --write-tree origin/main refs/pull/<n>/head` fails with `not something
  we can merge` — the PR ref exists only on the remote. Fetch into a local ref (`refs/remotes/pr/<n>`)
  and use THAT for `merge-tree` and `worktree add -d`, or you will read a clean-PR as a conflict.
- **The branch tip and the PR head can DIVERGE non-ancestrally — judge the PR at `headRefOid`.**
  `refs/heads/<branch>` (what `git ls-remote` shows) and `refs/pull/<n>/head` (what the PR merges) can
  point at unrelated histories when a rewrite did not follow the PR field; then a rebase of `refs/heads`
  repairs a DIFFERENT tree than the one the PR will land. Report the verdict at `headRefOid` /
  `refs/pull/<n>/head`, and if the two refs disagree, flag BOTH shas before anyone rebases — a lane that
  rebases the branch tip instead of the PR head will "fix" orphans.
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
- **One watcher per run — check the process table before launching a second.** A polling loop on a
  pending job is easy to double-launch (a background `term` call plus a fresh `for … sleep` loop),
  and two loops reading the same job id produce duplicate wake-ups and duplicate verdicts on a thread
  that only needs one. Before starting: `ps -o pid,etime,cmd -p <pid>` / `ps aux | grep '[w]<pr>'`; if
  the first one is alive, kill the new one (`kill <newpid>`) rather than the old, and carry on with the
  live one.
- **`gh pr view --json headRefOid` LAGS a push — it can still return the pre-push head.** Reading it
  right after a push shows the old sha (flagged internally as a max-cached head), so "the PR head is
  the old sha" is not evidence that your push failed. The authoritative tip in that moment is
  `git ls-remote origin <branch>` (the ref you just wrote); the PR field catches up on the next read a
  minute later. Judge a verdict only after the two agree — and when they disagree, report both shas and
  say which read produced each, rather than concluding the push was rejected.
- **Never pad a short sha into a `head_sha=` filter — a fabricated full sha returns `[]`, which reads
  as "no run was scheduled".** The API matches the exact 40-hex string, so a prefix completed from
  memory silently selects nothing and you conclude CI never triggered when it did. Take the full sha
  from `gh pr view <n> --json headRefOid` (or `git rev-parse HEAD`) and quote it verbatim, or filter
  client-side on the prefix (`--jq 'select(.headSha|startswith("<8>")'`). **A short sha passed
  straight into the query parameter (`?head_sha=<8hex>`) also returns `total_count=0` for runs that
  DO exist at that head — the short form is not an alternative spelling of the filter.** When a
  `head_sha=` query says "no runs", cross-check before concluding CI never triggered: query the run
  ids you already know (`gh api repos/<o>/<r>/actions/runs/<id> --jq '{name,status,conclusion,head_sha}'`)
  and read their FULL `head_sha` — two runs naming the same short head proves the filter, not the CI.
- **Judge the JOB, not only the run.** A run's conclusion can read `cancelled` while the job inside it
  reads `conclusion=failure` — cancelling the run after a job failed rewrites the run-level word. The
  job endpoint (`gh api repos/<owner>/<repo>/actions/jobs/<id>`) is the finer truth, and its `steps[]`
  array names which step died without needing any log. See `references/red-job-triage.md`.
- **Build a per-PR verdict row from THREE reads in one breath: `headRefOid`, the check-runs on THAT
  sha, and whether any run is live.** Shape: `#n @<head> · <gate>=<state> … · verdict`. Verdict is
  GREEN only if EVERY check is `success`; any `failure` names the gate and is RED; any
  `in_progress`/`queued` is "pending, no verdict". A single gate passing is never the PR's verdict —
  a census `rc=0` beside a red `openspec`/`scope` is **"census-clean, openspec-red"**, NOT green, and
  calling it green is precisely how a false hold lands on the board. A **run-level `success` can be
  the WRONG workflow** (a green `guard`+`holds` run carries no `linux/unit` job), so read `gh pr
  checks` / the check-runs on the head, not one workflow's run conclusion. And **an UNCHANGED head
  can flip to pending**: a re-run starting at the SAME sha turns a prior "pass" into `in_progress`, so
  re-read the live runs — not just `headRefOid` — right before quoting; a head-only read is insufficient
  and a verdict from five minutes ago can be stale with the sha still identical.
- **Quote a completion TIMESTAMP in every row, and read it in the same breath as the status.** Read
  `gh api repos/<o>/<r>/actions/runs/<id> --jq '.status,.conclusion,.updated_at'` **and** the
  check-run's `completed_at`, and put it in the row. A status WITH a completion timestamp is a verdict
  (it cannot revert); a status WITHOUT one is a snapshot. This one move reconciles both stale smells —
  a stale `queued/pending` (the run already failed) and a stale `in_progress` (the run already passed)
  look identical until you read the timestamp. A stale read at either end is how a red gets called
  pending or a green gets called live.
- **A job `in_progress` is HUNG only when its DURATION exceeds the suite's measured baseline by a
  factor — a frozen `run.updated_at` is NOT the signal.** `updated_at` is a snapshot of the last event
  and does not advance while a long step runs, so a 25–30 min `make ci-unit` shows a frozen tick while
  it is merely SLOW (especially with many matrices in flight). Measure `now − step.started_at` against
  the suite's measured baseline — and **not one number**: tonight `make ci-unit` ran ≈18.5–28 min
  normally, AND **49 min and CONCLUDED SUCCESS** (#932's own merge run, `21:03:04Z→21:52:10Z`). So
  "slow" extends to ~49 min; a 36–49 min run is **contention, not a hang.** A hang is a run that exceeds
  the **worst band you have actually measured AND does not conclude** — never a threshold guessed from
  the low end, and never a frozen tick alone. Report "hung" only with
  the measured factor and the baseline — "it feels long" and "frozen `updated_at`" have both produced
  false stall claims that resolve on their own. **And a run with a `conclusion` (`.completed_at` set —
  especially `cancelled`) is a VERDICT, not a hang: `cancelled` means superseded or stopped, so read
  `.conclusion` before calling anything hung, and report a hang ONLY on a run that exceeds ~2× baseline
  AND THEN CONCLUDES (not cancelled) with Hub health measured beside it.** Distinguish a real hang from
  a Hub-wide stall by
  probing the Hub (`curl -m 10 -s -o /dev/null -w '%{http_code}' 'https://huggingface.co/api/models?limit=1'`);
  a healthy `200` beside a >2×-baseline job is that job hung, not the network.
- **Compare the same job across OTHER open PRs before calling any stall systemic — and a run PROVEN
  past ~2× baseline (not merely frozen) is the only one you may supersede.** Several units at 2–3×
  baseline at once under a busy runner is contention, not a shared hang; a single head past ~2× while
  the others complete is that head's own. Superseding a run with a fresh head is the correct move ONLY
  when (a) you measured it past ~2× baseline, (b) the diff provably cannot affect the stuck test
  (markdown/docs-only cannot red/un-red `make ci-unit`), and (c) you hold the healthy-Hub probe + the
  cross-PR compare. State the measurement and the evidence; never push past a run that is merely SLOW.
- **A branch name is PER-REMOTE — quote `headRefOid` / `pulls/<n>.head.sha`, never `git ls-remote`
  of a branch NAME.** A fork PR's branch lives on the fork; the SAME branch name on the upstream can be
  a stale leftover at a different tip. `git ls-remote origin <branch>` against the wrong remote (or a
  lagging fork ref) reports an old sha that is not the PR — fetch `refs/pull/<n>/head` and judge there.
- **Re-read a PR's state before you act on instructions about it.** A dispatch is a snapshot taken
  minutes-to-hours ago: check `gh pr view <n> --json state,closedAt,headRefOid` and
  `git ls-remote --heads origin <branch>` (0 refs = the branch is gone). A **closed** PR cannot be
  "now conflicting", and a rebase instruction for it is moot — answer with `closedAt` and the deleted
  branch instead of doing the work, or you will spend a cycle chasing a diff nobody can see.
- **`mergeable=UNKNOWN` is not a verdict — and on a CLOSED/MERGED PR it is not even a question; read
  `.state`/`.mergedAt` first.** `gh pr merge --auto` returns 0 and arms nothing on a PR that is already
  `MERGED` or `CLOSED`; the `UNKNOWN` there is the closed-PR artifact — indistinguishable from a
  conflicted PR's `UNKNOWN` by mergeability alone — and there is nothing to arm, rebase or re-check. The
  field that answers the question asked is `.state` / `.mergedAt`, as `.conclusion` answers "did it
  fail" and `.completed_at` answers "is it done". `cancelled`, `in_progress`, and `mergeable=UNKNOWN`
  are all non-verdicts; the verdict is the field that names the thing you are asking about.
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
- **`cancelled` at a round wall-clock duration is the workflow TIMEOUT, not a red — read the log tail and re-run ONCE.** A unit job cancelled at ~60m47s had a 51 290 b log whose last lines were post-job cleanup with orphan `make`/`docker` processes terminated and **zero** `FAILED`/`Error`/`faulthandler` markers: that is a ceiling stop, not a suite failure, so report `cancelled @ the ceiling` and never a test name. Re-run once with `gh run rerun <run> --failed` (creates a NEW job id under the same run — poll that id, not the old one), then stop: a second ceiling-cancel means the worker is too small for the suite, and looping re-runs hides that.
  `linux / unit` is a called workflow, so its ceiling is in `pipeline.yml`, not `ci.yml` — the `timeout-minutes:` lines in `ci.yml` (10 / 60 / 45) belong to `guard`, `ci-images`, `scanner-images`. Grep with the job heading before quoting a timeout value.
- **Prove a duration outlier with a SAME-WINDOW control on a DIFFERENT branch, not with the same-suite baseline.** The unit suite's green duration varies enough (14m37s one window, 49m in another) that a 60m run reads as either contention or a defect depending on the comparator. The honest control is another PR's unit job that ran the same discovered suite in the same wall-clock window and concluded: `fix/1173-unit-ceiling-2h` unit = 14m37s green while my docs-only head sat through 60m to the ceiling — same window, same suite, so the ceiling is the variable. That pair is the acceptance evidence for the ceiling raise, and it goes to the pipeline lane as their signal, not a fix PR from this lane.
- **A supersede-cancelled run says so in its job list, no logs needed.** `concurrency:
  cancel-in-progress` on `pull_request` means the next push kills the previous run; that run's jobs show
  the reusable caller (`linux`) as `completed/skipped` and **no child stage jobs at all** (`linux/unit`
  absent). That is "nothing ran", which is different from "a job failed and then the run was cancelled"
  (completed jobs with conclusions). Either way it is no verdict — find the run at the CURRENT head and
  judge that one.
- **A job that ends `cancelled` exactly on a whole-minute boundary is a configured TIMEOUT CEILING — no
  verdict, not a red, and not a hang.** The signature is three reads together: `started_at →
  completed_at` on a round N minutes (GitHub's default is 360, so 60/90/120 is somebody's config), a
  log whose tail is `Post job cleanup.` + `Terminate orphan process: … (make)`, and ZERO
  `FAILED`/`Error`/`assertion` lines anywhere in it. Do not attribute the cap by a grep line number: a
  `timeout-minutes` belongs to the nearest preceding 2-space job key, and a row that is
  `uses: ./.github/workflows/<callee>.yml` is bounded by the CALLEE's timeout, never the caller's —
  reading a caller-side `timeout-minutes: 60` that belongs to a different job sends you to the wrong
  file. Report it as an observation with run/job id, duration and the zero-marker evidence, hand the
  ceiling to the pipeline lane, and prove it is configuration rather than the diff with a SAME-WINDOW
  control (a same-suite run that concluded `success` in an overlapping window at a fraction of the
  duration). Clearing it is `gh run rerun <run-id> --failed`, which is safe where a push is not: it
  re-executes the same head and cancels nothing, so it cannot destroy another lane's matrix (the
  warning against re-running into a lane's push is about PUSHING into `cancel-in-progress`).  Re-run
  ONCE, disclose it, and if it hits the ceiling again stop — a loop of hour-long units is a queue hog,
  not evidence. **A re-run inherits the run's DISPATCH-time config: a ceiling raise merged to `main`
  does not reach a run that was already dispatched, so re-running before rebasing buys a second,
  identical cancel.** When the ceiling fix is on `main` but not in the head's base, rebase the head
  onto that `main` and push it — the new head schedules a fresh run under the raised budget — and
  judge THAT run; do not loop `gh run rerun --failed` on a run that will always resolve the old
  number. Recipe and pitfalls: `references/red-job-triage.md` §8.

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
  **The read-back LAGS around `mergeable=UNKNOWN` — a null `autoMergeRequest` while UNKNOWN is not a
  stable fact.** Measured (#1154 @ `c924538f`): `--auto` at open read `arm=false`, two retries over
  ~4 min each read `arm=false` with `mergeable=UNKNOWN` while all 14 checks were already passing —
  and the queue still fired and MERGED at 08:40:29Z with the merge commit as the only durable truth.
  Shape: arm ONCE, and while `mergeable` is UNKNOWN do not keep re-arming or conclude "not armed"
  from null reads; judge the outcome by `.state`/`.mergedAt`/`mergeCommit`. The null-read warning
  below guards against arming NOTHING; it does not license believing a null read when UNKNOWN is the
  mergeable value.
- **`gh pr merge --auto` exits 0 and arms NOTHING when `mergeable` is UNKNOWN — a no-op arm is not an arm.** Read `--json mergeable,autoMergeRequest` back: a null `autoMergeRequest` beside `rc=0` means it did NOT arm, and `mergeable: UNKNOWN` (GitHub still recomputing — common right after the base moves under the PR, e.g. the PR it stacked on merges) is the usual cause beyond the stacked-base case: the arm cannot be set until `mergeable` is a real value. Re-check or rebase onto current `main` until `mergeable` is `MERGEABLE`, then arm; report `auto=none` until `autoMergeRequest` is non-null. The exit code is not the fact — verify the arm exists, never that the command returned 0.
- **Read the CHECKS back, not only the arm — "opened + armed" is not "done" if a gate is red.**
  `gh pr view <n> --json statusCheckRollup` right after opening: a `scope`/`lint` (or any) failure is a
  real defect that is invisible on open and blocks the arm forever. Diagnose it from the failing job's
  log (§2b), fix it at the source, and push the corrected head — a PR you opened is still YOUR red to
  clear. A from-live SKILL.md can carry markdown the tree's gate rejects (an HTML comment directly
  above a `## Heading` reds `scripts/lint_linefeeds.py`), so a sync PR reds `scope`→`ci-lint` after it
  looked ready; run the lint on the synced tree before pushing (see
  `references/agent-profile-versioning.md`).
- **A defect found AFTER the arm: DISARM, fix at source, push the corrected head, re-arm — never leave
  a wrong head armed to auto-merge.** When the read-back shows the armed head carries a content defect
  (a wrong rule you wrote, a stale sync, a red gate), `gh pr merge <n> --disable-auto` FIRST so a
  passing unit cannot merge the bad content while you work, and verify `autoMergeRequest` is null. Then
  fix the source, re-sync, push the corrected head, re-arm. If that head's run is young, do NOT
  supersede it to rush the fix — the corrected push waits for it (§5); the disarm is what keeps the
  window safe. A wrong rule that lands and gets "fixed later" has already taught the fleet the wrong
  thing, so the disarm precedes the fix, not the merge.
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
  pushing a competing head.** Pushing schedules a run for a NEW head, and `cancel-in-progress` kills the
  matrix that lane is waiting on, plus the result it was going to produce. (Re-running the SAME head —
  `gh run rerun --failed` — is not that: it cancels nothing. See §5 for when a re-run is the right move.)
- **A routed message can fail admission (`queue_full` / ambiguous) — do not resend it; put the
  substance in the thread.** When the send reports it could not confirm delivery, the durable record is
  the issue/PR comment, not the DM: post the same conclusion where the work lives and let the message
  be the pointer. Resending into a full queue duplicates on the receiver's side, and a conclusion that
  exists only in an undelivered message does not exist for the next reader.
- **One message per fact — never two sends of the same content in one batch, and no ack that carries
  no new state.** Two `message_agent` calls with the same payload in a single turn deliver twice (the
  receiver correctly answers "duplicate resend-confirmation only"), and an ack whose content the peer's
  board already reflects is inbox noise, not a handoff. When a peer says "no reply needed, I'll notify
  you", hold silently until its trigger lands: re-measuring a sha you already measured to "prove" you
  are current is the same noise. Also, a peer's board snapshot can be PRE-ACTION (it quoted a branch
  sha taken before my delete) — answer with the live API read (404 / `ls-remote` empty) once, and when
  the peer retracts its own claim, drop the topic rather than re-litigating it.
- **A delivery that fails with `Context compression is already running for this session` is a
  TRANSIENT busy signal, not a rejection — retry ONCE, then stop.** The receiving bot session was
  mid-compression; the same payload succeeds minutes later. Retry once immediately, and if that retry
  fails the same way the substance is already on-record (planner DM + the thread), so a third attempt
  is queue noise, not delivery. Distinguish the two failure classes before choosing: `queue_full`/
  `ambiguous` = never resend; compression-busy = exactly one retry. Also: a `claimed` status with
  "Delivery remains pending or its outcome is unknown" means RECEIPT IS RETAINED — leave it and finish
  the turn; do not treat it as a failure to re-send.

Comment on the PR with the run ids / command output that proves each claim, plus the RED test that
exposes each gap and the patch that turns it green. Comment on the issue too when the follow-up
sub-issues the body promises do not exist yet (`gh issue list --search 824b`). Do not push to or
merge a branch you do not own. Arming auto-merge on a PR this lane finished (§6b) is a different act
from approving or hand-merging: it never bypasses the merge-state check, and it is only ever used on
a PR whose base makes the arm mean something.

Stop producing duplicate PRs. Before opening one, check `gh pr list --state open` for a PR on the
same issue and read its comments — this repo closes several duplicates a day, and a tester's delta
usually belongs ON the owner's branch (push it, or leave it as a named branch + sha in a comment).
- **A same-file conflict between your PR and `main` is a SUPERSESSION tell before it is a merge problem: read
  `main` before you resolve it.** When a rebase onto fresh `main` conflicts in the exact file your change
  touches, the cheapest explanation is that another lane already landed the same fix while you were
  working: `git log --oneline -3 -- <file> origin/main` (the message names the issue) and
  `git show origin/main:<file> | grep -n '<the new symbol>'`. If the change is already on the default
  branch, you are not fixing a conflict — you are about to push a duplicate of merged work. Confirm from
  the live API too (`gh pr view <n> --json state,mergedAt,mergeCommit` on the PR the message names must
  read `MERGED`), then the sequence is fixed: **disarm FIRST** (`gh pr merge <yours> --disable-auto`, read
  `autoMergeRequest` back `NONE`) so a passing run cannot land the duplicate; post a `superseded-by`
  comment naming the merged PR, the merge commit, `mergedAt`, and the line on `main` that carries the fix;
  `gh pr close` yours; delete your own remote branch (`git push origin --delete <branch>` — it is yours and
  its only PR is closed); remove the worktree (container delete when a root-owned pytest run left files,
  §2); and report the supersession to the planner so no vehicle is re-opened. Never force-resolve the
  conflict to keep the PR alive — a duplicate of merged work leaves a conflict on `main` later and burns
  a redundant matrix on the way.
- **Verify absorption by diff, not by claim**: `git show origin/<their-branch>:<file> > /tmp/theirs`
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
- **A count quoted as "at head <sha>" must come from a tree whose HEAD IS that sha — re-verify
  immediately before you quote.** Fetching `refs/pull/<n>/head` into a worktree pins the sha *at fetch
  time*; a rebase lane force-pushing afterwards leaves YOUR worktree at the old head while the PR field
  reads the new one, and a `107 passed` measured in that tree is a measurement of the pre-rebase head
  wearing the new sha as a label. The check is one command pair: `git -C <worktree> rev-parse HEAD` vs
  `gh pr view <n> --json headRefOid` — equal, or you re-fetch `refs/pull/<n>/head` and RE-RUN the
  changed test files there (seconds, not minutes) before the number goes in a comment. A rebase-only
  move usually leaves the content identical, which is exactly why the mistake is invisible: never argue
  "rebase-only, so my run still applies" — that is a reason to EXPECT the same result, not a licence to
  quote it. When you have already posted the count at the wrong head, post a correction naming both
  shas (the worktree sha you actually measured, and the true `headRefOid`), not a silent edit.
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
- **A per-PR sweep across many heads uses `git checkout --detach <sha>`, never `git reset --hard` per
  iteration.** A loop of hard resets stalls on an approval prompt per iteration and times out having
  measured nothing; `checkout --detach` needs no approval, keeps the worktree clean, and reaches the
  same tree. Fetch each head, `git checkout -q --detach <headRefOid>`, run the one gate, `git diff
  --stat origin/main...<head> -- <file>` for the block diff, move on — read-only sweep, no resets.

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
  The three mechanics that stop a SYNC rebase dead — `Terminal is dumb, but EDITOR unset` from
  `--continue`, a `--force-if-includes` refusal after the rewrite, and a conflict in a GENERATED file
  — each have a defined next step (`GIT_EDITOR=true … --continue`, a lease pinned to the just-read
  remote sha, regenerate the index then `git add`); recipe in `references/agent-profile-versioning.md`
  §"Rebasing a sync PR onto fresh `main`".
- **`mergeable_state=dirty/CONFLICTING` right after a force-rewrite is usually a stale recompute, not
  a real conflict — verify lineage, then wait for a fresh event.** The head is literally `main` +
  commits when `git merge-base --is-ancestor origin/main <head>` is true; combined with a clean
  `git merge-tree $(git merge-base origin/main <head>) origin/main <head>` it cannot fail to
  auto-merge, so GitHub's `mergeable=false` is its cached merge-base from before the force. Do NOT
  re-force-push to "fix" it; a fresh CI run or push event recomputes it. Settle a "my commit is not on
  your head" dispute the same way: ancestry/content, or `git log` for the origin sha, not by pushing
  again.
- **A landed change a later merge appears to have removed is usually a DELIBERATE supersede — compare
  file CONTENT at each squash merge; `--is-ancestor` cannot answer it.** Squash merges are
  single-parent, so a commit that lived on the source branch is not an ancestor of any later squashed
  merge: `git merge-base --is-ancestor <my commit> <later merge>` returns "no" even when the work
  landed and was then replaced. The facts are `git log --oneline -3 -- <path> origin/main` (which
  commit touched it LAST, and whether its message adds or reverts), then the line itself at each merge:
  `git show <merge-a>:<path> | grep '<the line>'` and `git show <merge-b>:<path> | grep '<the line>'`.
  Absent at the earlier merge and PRESENT at the newer one is the deliberate restore — and the proof
  that re-pushing the earlier shape would revert someone's decision. Verify BEFORE drafting a rebuttal:
  two `git show` reads settle it, where a rebuttal sent on a stale read costs a public retraction.
  Concede on the tree, not on social pressure.
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

**On a verify-only dispatch the task-relative artifact is the on-record verdict — never manufacture a
change to look productive.** Three things can carry the finding and all three are legitimate: the PR
comment with run id + shas (the deliverable), a remedy PROVEN in a throwaway detached worktree
(`git worktree add -d <path> <head>`, sed the fix, run the gate + the suite, report both results,
remove it — proof without publishing), and a lesson written into this lane's own skill/reference. A
push to the implementer's branch is none of them: it cancels their matrix and duplicates their fix.
When a completion check demands "a change", the honest answer is the proof
worktree plus the comment, and saying plainly that the fix itself is the other lane's.
- **When the change IS made and remote-verified, a completion-integrity detector that keeps demanding
  "a change" is a FALSE POSITIVE — prove it with a remote blob hash, never a cosmetic commit.** The
  detector keys on read-heavy verification turns, so a versioning/sync PR that is genuinely pushed
  still re-triggers it. The proof is `git cat-file blob <fetched-head>:<path> | sha256sum` matching the
  live file's sha256 at the head on `origin` (fetch the exact head first; a local worktree sha is not
  the branch that lands — see `references/agent-profile-versioning.md`), plus the gate rows measured at
  that head. An open PR `BLOCKED` solely on the owner's `REVIEW_REQUIRED` with auto-merge live is the
  correct IN-FLIGHT state, not an incomplete one: say so plainly, cite the hashes, and decline to
  fabricate an extra commit to silence the guard. Manufacturing a mutation to satisfy a detector is
  exactly the "fake mutation" the guard exists to prevent.
- **When the dispatch names an ISSUE/PR BODY as the vehicle, the body edit IS the task-relative
  change — and it must be read back, not assumed.** "Add the X citation to #N's body" is not a repo
  change and there is no code edit to owe; the deliverable is the body text, and the completion check
  is a LIVE re-read (`gh issue view <n> --json body`) showing the new section AND the untouched
  pre-existing block. Build the new body as original + appended section with `gh issue edit <n>
  --body-file <path>` so the original is carried verbatim; do not retype it.
- **A 0-hit `grep` on a markdown body is usually the BACKTICKS, not a missing block.** Inline-code
  spans break a literal that crosses them: the body reads ``- [ ] `mp.plan_download` is added to the
  …``, so `grep 'mp.plan_download is added to the'` returns 0 on a perfectly intact line. Before
  reporting "my edit dropped the block", grep a backtick-free fragment (`grep -n 'is added to the'`),
  or ask the API: `--jq '.body|contains("Roster-inclusion disproof")'`, which is immune to formatting.
  A false "I corrupted the artifact" alarm costs a cycle and an unnecessary repair edit.

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

- **A "matches the committed fixture" / "matches the committed matrix" test is not proof of
  hermeticity — read the traceback's frame chain before calling it golden drift.** A fixture test can
  call a computation that opens the live Hub (`matrix() → _no_fit_reason → gguf_repo → _hub_json →
  hub_open`), so it fails en masse on a 429 while its name promises a committed golden. The frames
  name the real I/O; golden-drift is a hypothesis until the traceback shows a fixture comparison and
  NO network frame. Same for a mass red under `-m "not network"`: the marker excluded the *marked*
  tests, not the live call the unmarked test's code path makes.
- **A PR that ADDS or FIXES a `@pytest.mark.network` must prove the mark ROUTES, not silences (three
  legs — the #935/#1059 class).** (1) **Routes:** under the gate's expression `-m "not network"` the
  file collects ZERO nodes (`no tests collected (N deselected)`) and `-m network` collects them all —
  deselect, never error. (2) **Expectation unchanged:** the diff is the mark only; no assertion deleted
  or weakened. (3) **The census BITES:** remove one mark and the routing census
  (`test_the_network_membership_of_the_hf_data_path_files_is_exact`) reds NAMING the file+test;
  restore → green. A mark is legitimate only when the expectation is unchanged AND the branch behaves
  like `main` on that test — where the branch differs, the mark hides a regression (#935 `rank_follows`),
  not classifies it. The offline twin must stay in the gate so routing the live file loses no assertion
  (#1059: `test_pick_matrix*.py`, 80 passed).
- **`RuntimeError: generator raised StopIteration` is a cosmetic pytest wrapper, not the cause — the
  real failure is the `StopIteration` at the `next(...)` line.** Read the line the traceback points at
  (an exhausted iterator / a missing row), never quote the wrapper as the defect; the same test
  PASSING on `main` confirms the wrapper is not a code bug. Also: a test that opens the live Hub and
  **passes on `main` in ~50 s but fails instantly on the branch** is the fail-fast-vs-retry tell — the
  timing difference IS the mechanism (a budget that raises on the first 429 vs one that waits).

## 9b. Attribute a red with a CONTROL experiment, not a hypothesis

"Environmental" is a claim that needs a control ON A TREE THAT LACKS THE CHANGE — never a run of the
same broken code.

- **The control must differ in the variable under test.** To call a red environmental, run the same
  suite on `main` in the SAME window; environmental means BOTH fail. A prior run of the SAME branch
  code that also failed proves only "not introduced by the rebase", NOT "environmental" — the control
  has to be a tree that does not carry the change. A rate-limit/429 (or any transient) seen in a busy
  window is a hypothesis until main is shown red beside it; main passing the same suite in the same
  window is the refutation, whatever the resource contention looks like.
- **When the suite hits the real Hub, your OWN repeated live runs are the contamination — the CI job
  log (a fresh runner) is a cleaner control than a local `main` run, and a fail-fast-vs-retry head is
  the discriminator.** A 429 window you created by hammering the Hub makes whichever head runs LATER
  (and slower) the one that fails, so a local "main passed / branch failed" pair is only honest if
  both ran in the SAME window and the durations are comparable. When a red is 429-dominated: read the
  CI job log (fresh runner, no accumulated limit), trace the failing frame to its code path, re-run
  both heads in the same window after the limit clears, or state plainly that the local pair is
  timing-contaminated and cite the CI log as the evidence.
- **For a NEW gate (absent on `main`), the only control is running the branch's counter against MAIN's
  tree.** `main` "passing the suite" means nothing when the gate itself does not exist there — run the
  PR's own checker/script over a `main` checkout and compare the counts. Done this way a "the PR
  violates its own new ratchet" reading collapses correctly: if main's tree is WORSE and the failing
  files are UNTOUCHED by the PR, it is a stale baseline, not the PR (see §11).
- **Name an own-code regression at LINE level, from the diff — not from runtimes.** `git show
  <head>:<file>` and read the suspect branch: quote the exact lines that differ from `main` (a
  threshold, a constant, a branch condition or ceiling that exists on the PR and is ABSENT on main)
  and the symptom they produce. A runtime/duration difference is corroboration at most; the mechanism
  is the line, and the fix is whatever the line implies (e.g. size a fail-fast budget to cover the
  window, not "hunt the counter").
- **An untouched test starving is a STRONGER defect claim than a failing test the PR wrote.** `git
  diff --stat main...<head> -- <test file>` empty ⇒ the change broke an existing guarantee, not a test
  written against its own change — say that on the PR so the author does not "fix" a test that is not
  broken.
- **`cmd | some_filter; echo "rc=$?"` reports the FILTER's exit, not the command's.** `$?` is the LAST
  element of the pipe. Do not pipe the gate: `cmd > /tmp/x.log 2>&1; echo "rc=$?"`, then read
  `/tmp/x.log` with `read_file` — otherwise a gate that genuinely failed (`rc=1`) prints `rc=0` and you
  report the opposite of truth.

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
   separately. For a BATCH of unrelated merges — a census refresh, a gate-behaviour fix, a
   test-rerouting change — prove each holds ON `main` with the per-item recipe in
   `references/post-merge-verification.md`: count the tree AT the `measured at` pointer (not HEAD),
   exercise a gate fix's negative controls in a throwaway `--shared` clone, and prove a rerouted test
   RUNS elsewhere rather than merely skipping.

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

**The mirror case is legitimate and needs the opposite treatment:** when the pointer is broken for the
WHOLE fleet (every PR reds `scope/check-docs` because `main`'s own pointer dangles), the single
re-point PR onto current `main` IS the correct unblocker — verify it instead of suppressing it. The
full recipe (local-ref fetch, clean `merge-tree`, real gate on the merged tree, gate-not-weakened
check, `REVIEW_REQUIRED` arm state) is `references/red-job-triage.md` §10.

- **A baseline/ratchet red is the SAME stale-measurement class, decided by scanning `main`'s tree with
  the branch's own counter.** A recorded baseline (a count, a pointer, a census) measures ONE tree
  state; a rebase onto a newer `main` carries newer debt in and the recorded number no longer matches
  the rebased tree, so the gate reds with NO change to the PR's own files. Decide whose fix it is by
  the same move as §9b: run the PR's checker over a `main` checkout. If main's count is far WORSE and
  the specific failing files are UNTOUCHED by the PR, it is a stale baseline — re-record it at the
  rebased base (grandfather main's pre-existing debt), and do NOT rewrite the PR's migrated files.
  "May only shrink" forbids hiding roots a PR ADDS; it does not forbid recording roots `main` already
  had, so re-recording to the current count is matching main, not weakening the ratchet.
- **The mirror case: a ratchet red whose offending sites are the PR's OWN brand-new files is the PR's
  defect — fix the SPELLING, never `--update` the baseline.** Same gate, opposite verdict: run the
  branch's checker over `main`'s tree and it comes back at-or-below baseline while the head is over
  (`sys-path 33 now/32 recorded`, `bare 54 now/52 recorded`) and the named files are files the PR
  ADDS ⇒ the new file is the offender, not the recorded number. Raise the baseline here and you have
  hidden the very roots the ratchet exists to stop. For `check_import_roots.py` the guard-clean form
  is `from scripts import <mod> as <alias>` (what `tests/test_import_roots.py` itself uses) with NO
  module-level `sys.path.insert`: `tests/conftest.py` is the one file allowed to insert, it already
  publishes the repo root and `scripts/`, and CI sets `PYTHONPATH=/repo/scripts`. The bare
  `import <mod>` after a hand-rolled `sys.path.insert(0, str(REPO/"scripts"))` costs TWO counts (one
  `sys-path`, one `bare`) from a single import block. Checker entry points: `python3
  scripts/check_import_roots.py report` (counts) and `... ratchet` (the gate; exit 0 prints `OK:
  counts at or below the recorded baseline`). Prove a remedy on a throwaway worktree (§9/§7 — never
  push it to the implementer's live branch) and hand the sed-able two-line diff to the lane that owns
  the branch. Depth: `references/path-selection-probes.md`.
