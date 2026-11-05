---
name: llgenie-issue-to-pr
description: "Use when implementing a llgenie issue as a reviewable PR."
version: 1.0.0
author: llgenie-issse-implementer
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [llgenie, pr, ci, gates, worktree, docker]
    category: software-development
    related_skills: [github, bulk-mechanical-migration]
---

# LLGenie issue → reviewable PR

## When to Use

Load this whenever you are dispatched to implement, fix, or version something in
`asimov-agent/llgenie` and the deliverable is a reviewable PR — a code fix, a skill
live→tree sync, a docs/CHANGES row, a gate repair. Layer over `github` for gh/PR mechanics. Delivery loop: one issue, one branch, one PR, body
`closes #<n>`; never push `main`, never merge by hand.
PR body + squash-commit close line must be the PLAIN literal
`closes #N` (no bold, no colon/hyphen before `#N`):
`references/plain-close-line.md`.
Terminal/guard pitfalls, persisted cwd + REPLAN + observe verify: `references/terminal-and-guard-pitfalls.md`. OpenSpec change-first: `references/openspec-change-first.md`.
A PR that reds on close-mismatch + stale AGENTS line + non-live base
(`check-pr-closing`/`check-pr-agents-line`/`check-pr-base` together):
`references/pr-close-mismatch-recovery.md`.
Index red → `references/mechanical-index-regeneration.md`.
Fork PR head pinned to the old sha after a force-push, or CI's unit leg skipped
for your head → `references/stale-pr-head-and-self-proof.md`.
Queue re-dispatches a **closed/merged** issue by number (residual `agent:implement`
label keeps it "open" in a stale snapshot) → verify `gh issue view <n>` state, refuse
the phantom, set a no-reply boundary: `references/closed-issue-redispatch.md`.
Skills-surface change needing a change→note→fragment trio (committed-diff gate):
`references/change-note-fragment-trio.md`.
Whole batch of sibling PRs red on the same gates:
`references/multi-pr-batch-repair.md`.
CI false greens: `references/open-pr-measurement.md`, `references/post-merge-verification.md`.
Shared red: `references/shared-vs-task-ci-red.md`.
Container image non-root/build: `references/container-runtime-fixes.md`.
Head disagreement / peer rebase ask (rule #994) → `references/reconciling-disagreeing-heads.md`.
Premise may already be met (store landed / gate green) → `references/measure-scope.md`.
Engine decisions for a new store (`check-engine-skill-gap` staleness) → `references/engine-skill-gap-decisions.md`.
Shared-checkout hazards (a stash popping another lane's files; the mutation guard reading a git
subprocess as "no mutation") and generated-artefact drift: `references/local-worktree-hygiene.md`.
Container won't start / pre-existing host failure: `references/local-unit-run.md`.

Folding a lane's LIVE profile into `agents/`: `references/live-profile-fold.md` (read before the
first edit).

## Acceptance-criteria form contract (#1796 #1, owner 2026-11-05)

- **Every issue this lane files AND every PR body it opens carries a `## Acceptance criteria` section with each criterion a `- [ ]` markdown checkbox, one per provable outcome; a criterion a reviewer cannot tick is not one (#745).** A work item that defines "done" without a tickable checklist is not a work item this lane files — name the command/field each box proves so a reviewer (or #1792 at merge) can check it. The section MUST use the canonical `## ` heading, never a bare `**Acceptance criteria:**` bold line (that defeats `issue_body.missing()` and the verdict-gated ticking in `acceptance_writeback`, #1644). This contract is versioned here via #791 and re-synced with `make sync-agent-profile PROFILE=llgenie-issse-implementer` (SYNC per #1724). *cite #791 / #1796 / #1812*

## Procedure

1. **Fresh base.** `git fetch origin +refs/heads/main:refs/remotes/origin/main` (explicit
   refspec — a bare `git fetch` leaves a stale `refs/remotes/origin/main`). Cut the
   worktree/branch from the sha you just fetched, and write that sha into your start
   comment. One worktree per issue under a scratch path (e.g. `/tmp/w<n>-<slug>`).
2. **Verify on a STANDALONE CLONE, never a linked worktree.** See the first pitfall —
   a linked worktree mounted into the `llgenie/test` container false-reds every
   git-dependent test. Clone the pushed branch fresh (`git clone --branch <ref>
   --single-branch`, then `git fetch origin main:refs/remotes/origin/main` so gates that
   need `origin/main` resolve) and run the gate there.
3. **Run the gates the way CI does**, inside `llgenie/test:latest`:
   `docker run --rm -u root -e PYTHONPYCACHEPREFIX=/tmp/pyc -v "$PWD":/repo -w /repo -e HOME=/root llgenie/test:latest <cmd>`.
   - `scope` → its failing component names the fix; usually `check-docs`.
   - `check-docs` / `ci-scope` need `origin/main` present in the clone (see above).
   - `check_agent_profiles.py` for absent-from-tree rows.
   - **Run the UNDERLYING command for any docker-shelling make target — `make ci-unit` /
     `make test-unit` FAIL inside the container with `Cannot connect to the Docker daemon`.**
     The Makefile's `test-unit` target itself shells out to another `docker run`, and the
     `llgenie/test` image has no docker-in-docker, so the nested call cannot reach a daemon — the
     outer container is fine, the inner one dies. Invoke the inner command directly instead:
     `docker run … llgenie/test:<tag> python scripts/unit_tests.py run` (that IS what `test-unit`
     runs). `ci-unit` = test-unit + skills-validate + check-registry + check-strata-models, so also
     run `make skills-validate check-registry check-strata-models` — those targets do NOT shell to
     docker and run fine inside the container. The full unit leg is ~6-7 min; run it in background
     per the cell-cap rule, never a foreground `execute_code`. Do not read the nested-docker error
     as a broken image — pull/daemon are fine, the recursion is the whole problem.
4. **Rebase only when `mergeable == CONFLICTING`.** Re-measure with
   `gh pr view <n> --json mergeable,mergeStateStatus` (UNKNOWN is a transient recompute —
   re-poll before acting). A MERGEABLE-but-behind PR is not broken; do not chase main.
   **The no-chase rule governs a PUSHED branch under review. A local branch you have never
   pushed and never opened a PR for may be rebuilt onto the freshly fetched main at will** — no
   lease, no reviewer, no shas anyone holds. A gate red on a file you never touched (lint on a
   fixture, a docs-exceptions shape error) is usually the tell that main moved past your base, not
   that you dirtied it: compare that file at `origin/main` against your base before assuming the
   diff is yours, then `git rebase origin/main` and re-render any shared-append file (CHANGES.md)
   from its fragments rather than hand-merging the markers.
   Confirm a true conflict with `git merge-tree --write-tree origin/main HEAD`.
   **An engine-build gate red on `Cache export is not supported for the docker driver.`
   (or `manifest unknown`, `make: *** [Makefile:1306: build-engine] Error 1`) is NOT a stale-base
   rebase problem — it is a pipeline docker-driver defect.** root-cause it: engine_image.py
   `_buildx()` forces `--builder default` (legacy `docker` driver, `type=inline`-only cache) while
   engine-build.yml's `docker/setup-buildx-action` creates a `docker-container` builder that supports
   `type=registry` cache export; the `--builder default` override defeats it. Do NOT rebase a
   mergeable PR for this (#1015) — quote the error, route to the pipeline/infra lane
   (ci-pipelines-maintainer), which opens the fix PR.
   **`mergeable_state` vocabulary — do not conflate these:** `conflicting`/`dirty` = a REAL
   conflict (rebase owed); `unstable` = MERGEABLE but a check is failing/pending (NOT a conflict —
   no rebase, chase the failing check's ownership instead); `blocked` = required review/check gate;
   `behind` = base moved, still mergeable. `gh api repos/<o>/<r>/pulls/<n> --jq .mergeable_state`
   reads `unstable` on a PR whose only red is an ambient test in a file outside your diff — that is
   the same "report measurement, do not chase" case, never a rebase trigger.
   **A runtime guard or watcher demanding "a mutation" is NEVER grounds to rebase a
   MERGEABLE-but-behind branch — issue #1015 forbids chasing every main move, and a rebase that
   only satisfies a guard rewrites shas under the owner's review for zero merge benefit.** When the
   guard fires on already-pushed, already-verified work, the legitimate actions are: re-verify the
   pushed artifact from an independent source (fresh `git clone --branch <b> --single-branch`, HEAD
   == pushed sha, target file hashes byte-identical), post the FINISH bookend, or clean up your OWN
   scratch clones/refs (`rm -rf /tmp/<verify-clone>`, `git update-ref -d` the refs you made). Do
   NOT rebase, do NOT fabricate a file edit — state the measured truth and hold.
5. **Open the PR ready-for-review** (`gh pr create --base main`), body `closes #<n>`.
   Write the body to a FILE and pass `--body-file`, then read it back (see the body-mangling
   pitfall). Bookend: a start comment (issue id, branch, fetched main sha, what "done" means)
   and a finish comment (head sha, what changed, the command/run that proves it, what's open).
6. **Arm auto-merge when done** — after all checks read `success` AND `mergeable==MERGEABLE`:
   `gh pr merge <n> --squash --auto`, then read back `.autoMergeRequest` whole (a null
   subfield with `// "none"` lies). If the owner merged a peer PR directly, do not re-arm.
   **After arming, poll `state` (or `mergedAt`), NOT `mergeable`/`mergeStateStatus`.** A
   `mergeable` that reads `UNKNOWN` for minutes after the arm is not always the transient
   recompute that resolves on re-poll — it can be the squash actually IN FLIGHT, and once the
   merge lands `mergeable`/`mergeStateStatus` stay `UNKNOWN` forever while `state` flips to
   `MERGED` (`gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy`). A loop that waits
   for `mergeable==MERGEABLE` before checking `state` polls a settled PR that already merged
   and never terminates; read `state` first each iteration, and when it is `MERGED` stop — the
   deliverable landed (verify content at the merge commit, per the pitfall below).
   **The REST `state` field uses a DIFFERENT vocabulary from `gh pr view --json state`:
   `gh api repos/<o>/<r>/pulls/<n> --jq .state` returns `open`/`closed` and reads `closed` on a
   MERGED PR — only the `merged` boolean (or `merged_at`) distinguishes shipped from abandoned.**
   **`gh pr view --json` (GraphQL) has NO `merged` field — asking for it fails hard with
   `Unknown JSON field: "merged"` and the whole query returns nothing, so a script that tries to
   read it looks like an empty/garbled result, not a schema error.** `merged` is a REST-only scalar
   (`gh api repos/<o>/<r>/pulls/<n>`); the `gh pr view` equivalent is `mergedAt` (non-null = merged)
   plus `mergeCommit`/`mergedBy`. Ask `gh pr view <n> --json state,mergedAt,mergeCommit` and treat
   `state:MERGED` / non-null `mergedAt` as the merge fact — never re-issue the query guessing field
   names.
   A `gh api pulls/<n> --jq '{state,merged,merged_at,merge_commit_sha}'` showing `state:closed` is
   NOT evidence of a withdrawal; read `merged==true`, then confirm the merge commit is contained
   in main (`git branch -r --contains <merge_sha>` names `origin/main`) and that the issue is
   `state:closed, state_reason:completed`. `gh pr view --json state` normalizes a merged PR to
   `MERGED`, so the two channels disagree by design — never read the REST `closed` as
   "closed, not merged". A branch ref that vanished (`git ls-remote ... refs/heads/<b>` empty)
   alongside REST `state:closed` is the merge-deleted-branch signature, not a failed push.
   **When the dispatch forbids merging ("never merge", "stop at the reviewable PR") or the
   repo's merge gate is owner-gated, do NOT arm — report `nothing armed (owner-gated)` in the
   finish comment and let the owner / gate bot merge.** The org's automerge gate runs as the
   `asimov-agent` bot: when it merges your green PR it reads `mergedBy: asimov-agent` with
   `autoMergeRequest` and `auto_merge.enabled_at` BOTH null, and posts a
   `<!-- auto-merge: merged <sha> -->` PR comment. That is owner-side automation, not your arm —
   state it as such and never claim credit for arming a merge you did not request.

## Gates that reds are easy to misread

- **`check-docs` requires THREE surfaces for any change under `agents/<profile>/`:**
  (a) an `agent-wiki/<stem>.md` change note that names an issue/PR AND has its own index
  row;  (b) a `docs/changes.d/<stem>.md` fragment — its CONTENT is the CHANGES.md table row
  itself (`| <date> | <summary> | [<stem>.md](agent-wiki/<stem>.md) | #<n> |`), NOT prose,
  and it must END WITH A NEWLINE. The file-writing tool does NOT append one, so a generated trio
  passes `check-docs` locally yet reds `make lint` (part of `scope`) on the push — check `tail -c1`
  on every note/fragment and append `\n` where missing, and run `make lint` alongside `check-docs` (lint sees only TRACKED files — `git add` first); (c) the same
  row rendered into `CHANGES.md` linking the note. A prose fragment (a plain sentence instead
  of a `| … |` row) makes `make changes-index` refuse with `is not indexed — add
  docs/changes.d/<stem>.md with its row` and `CHANGES.md not written`; copy the shape from any
  existing `docs/changes.d/*.md`, do not hand-invent it. Since the row carries `#<n>`, do not
  finalise the docs surfaces until the real tracker-issue number exists — a `#ISSUE`
  placeholder row will not satisfy the gate. Missing any surface reds `scope`. The gate message
  names the missing piece — run it, don't guess.
  **The change→note check diffs COMMITTED git state, so an uncommitted note/fragment is
  invisible to it** — a freshly written note that never reds is not a pass, it is a diff that
  cannot see it. Stage + commit the note, fragment and rendered `CHANGES.md` first, then run
  the gate, and pass an EXPLICIT base (`BASE=<sha>`) — a bare run with no base can skip the
  diff entirely and report green while proving nothing. Verify by running it a second time
  with the base against the committed head.
- **Adding a new USER-FACING make target reds TWO gates over the same surface with DIFFERENT
  acceptance criteria — clearing the CI gate with `docs-exceptions.json` does NOT clear the unit
  test.** `check-docs` accepts an entry in `tests/fixtures/docs-exceptions.json` (shape: `targets`
  is a map, each value an OBJECT with `reason`/`decided`/`issue` keys, never a bare string — a
  string value makes the gate reject the file). But `tests/test_check_docs.py::
  test_the_real_tree_documents_every_user_facing_target` asserts `documented == targets` and does
  NOT honour the exceptions map, so the two targets count 291 vs 289 and the test reds while the
  CI gate is green. The real fix is to NAME the targets in a README-linked docs page (the
  `docs/ARCHITECTURE.md` `make ci-unit` gate-bundle list is where sibling gate names already
  live) — documentation, not exception-record. Revert any exception entry you added once the
  targets are documented, or the gate flags the records STALE. **Separately, wiring a new target
  into `ci-unit` reds `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired` unless you
  classify it in `scripts/issue_bot_gates.py` (`FAST_GATES`/`DEFERRED`)** — a gate nothing
  classifies is a wiring hole. Both reds reproduce on clean `origin/main` ONLY when the target
  already exists; they are YOURS the moment your branch introduces the target.
- **A green-wait watcher can false-fire `ALL_GREEN` before all checks are even created — and
  the completed-only-filter variant is the same bug.** A loop that polls `success == total`
  with a floor like `total >= 13` fires the moment 13 checks exist and all passed — the long
  `linux / unit` leg may not have been created yet, so it is absent from `total` and the
  compare is trivially true. The identical false-fire comes from deriving the count from
  `select(.status=="completed")`: then an in-progress leg (`linux / install`, `linux / unit`)
  is absent from BOTH numerator and denominator, so "12 completed of 14 total, all success"
  reads as green when two legs are still running. Green requires
  `len(runs) == expected_job_count AND all(status=="completed") AND every conclusion=="success"`
  — query the FULL run list (no completed-only filter), take the expected count from
  `ci-scope`, and never compare a completed-count against itself. When any watcher fires, do
  NOT trust it: re-query `commits/<sha>/check-runs` yourself and read every row; `unit` can
  then show `failure` or `in_progress` while the watcher already claimed green. The watcher's
  exit is not the verdict.
- **Your recorded PR head goes STALE when a prior window rebuilt the branch onto newer main —
  re-measure `headRefOid` before trusting any prior evidence, and when it moved, reconcile by
  CONTENT-DIFF, not by re-running everything.** A compaction handoff or a long-lived worktree
  can leave you holding a sha that is no longer the live PR head: a later window (or you, before
  a context reset) rebased the branch onto a newer `main`, giving a NEW fix commit and a NEW
  census commit. Two tells that this happened: `git merge-base --is-ancestor <your-old-sha>
  <live-head>` returns NO, and `git -C <worktree> rev-parse HEAD` still reads the old sha while
  `gh pr view <n> --json headRefOid` reads a different one. Do NOT force-push your old head back
  or re-run the whole gate suite blind. Instead confirm the rebuilt fix is content-identical to
  the one you verified: `git diff <old-fix-sha> <new-fix-sha> -- <every evidence-bearing file>`
  — an empty diff on those files means your prior per-module green evidence still certifies the
  new head (only census figures / CHANGES rows legitimately differ on the newer base). Then arm
  on the LIVE head's checks. **A watcher you left polling the old head will eventually fire
  `RED`/`ALL_GREEN` about a head that is moot** — kill it and start a fresh watcher pinned to the
  live `headRefOid`; do not read the old head's red as a defect in the branch. **A watcher RED whose process is ALREADY GONE (`ps aux | grep -iE 'watch<pr>'` shows it exited) is
definitively stale — do not investigate the red at all, just confirm the live head's check-runs are
clean.** A long-lived watcher chain leaves one dead watcher per superseded sha, and each still
fires its `RED`/`ALL_GREEN` completion notification into your turn after the process has exited;
that notification is a goodbye from a head nobody is on. Verify the LIVE head's check-runs
(`commits/<live-sha>/check-runs`) show no failure, note the stale watcher was already reaped, and
move on — a red nobody's process is measuring is not a defect. **A watcher's FIRST
  job on any notification is a head check — `gh pr view <n> --json headRefOid` — because a
  long-lived chain (rebase → census re-point → rerun) accumulates one dead watcher per superseded
  sha and each replays a RED about a head nobody is on. Keep EXACTLY ONE watcher per PR:
  `pkill -f <watcher-name>.sh`, confirm none remain (`ps aux | grep -iE 'watch<pr>' | grep -v
  grep`), then start the new one pinned to the live sha.**
- **`gh api .../actions/jobs/<id>/logs` REFUSES with `the response contains terminal escape
  sequences; pass --allow-escape-sequences to output it anyway` — that is not an empty log, it is
  the API guarding ANSI codes.** Retry with `--allow-escape-sequences` and strip the codes before
  grepping: `gh api repos/<o>/<r>/actions/jobs/<jid>/logs --allow-escape-sequences | sed -e
  's/\x1b\[[0-9;]*m//g' | grep -iE 'FAILED tests|short test summary|passed'`. That yields the exact
  `FAILED tests/test_<x>.py::<test>` lines the annotation only hinted at, so you can name the failing
  file and prove it is (or is not) in your diff. (Note `gh run view --log-failed` and `gh api .../logs`
  behave differently — the former may exit non-zero empty; the latter refuses on escapes.)
- **When the CI log-fetch returns nothing usable (`gh run view <run> --job <id> --log-failed`
  exits non-zero with empty stdout), reproduce the failing gate LOCALLY instead of fighting the
  log API.** The job's step names tell you which `make` target failed (`make ci-unit`, etc.); run
  that target in your worktree/standalone clone with output to a log file (background if slow) and
  read the `FAILED …` / `short test summary` lines. A deterministic local run names the exact
  test the annotation only hinted at (annotations often carry only infra noise like a Node
  deprecation warning). **For an IN-PROGRESS job the log API is unusable altogether —
  `gh api repos/<o>/<r>/actions/jobs/<id>/logs` returns a ~213-byte `BlobNotFound` XML with rc 1.**
  That is neither a failure nor a stall signal; it just means the log is not archived until the job
  finishes. Read per-step progress without the log instead:
  `gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|select(.name=="<leg>")|.steps[]|{number,name,status,conclusion,started_at}'`.
  A composite `make ci-unit` step (test-unit + skills-validate + check-registry + check-strata)
  sitting `in_progress` for 15–20 min on a fresh run is normal — the ~13 min figure is the
  `test-unit` leg ALONE, and the composite adds the extra targets plus image pull. Judge a stall
  only by a step whose `started_at` has frozen for ~1.5 h, never by the missing log blob.
- **`gh pr checks` exits 8 while ANY check is still pending.** Exit code is not a verdict;
  parse the rows (`pass`/`fail`/`pending`) or query `commits/<sha>/check-runs`. `linux / unit`
  is the long leg (~13 min) and often the last to conclude — a red nothing else can be read
  as a defect until it finishes.
- **`conclusion: cancelled` is a NON-SUCCESS verdict — the leg is not green, and the fix is a
  same-head re-run, never a push.** A `linux / unit` that runs ~12 min and ends `completed /
  cancelled` with zero code reds is a superseded/cancelled run (a `cancel-in-progress` from a
  rerun or a duplicate dispatch), not a defect in the branch: `gh api
  repos/<o>/<r>/commits/<sha>/check-runs` will show every OTHER leg `success` and only that one
  `cancelled`. Re-queue it at the SAME sha with `gh run rerun <run-id> --failed` — the head, the
  base and every passing leg stay put, so it cannot drift the PR the way a push would. Two traps:
  (a) the rerun call landing twice races itself — the second returns `cannot be rerun; This
  workflow is already running` while the FIRST one already re-queued it, so read the run back
  (`gh api repos/<o>/<r>/actions/runs/<id> --jq '{status,conclusion}'`) and expect
  `pending→in_progress`, not a second command; (b) a `--failed` rerun can also re-run legs that
  were already green — watch the job list until the cancelled leg alone flips to `success`. Treat
  the re-run's exit code as a request, not a verdict; the green still has to come from
  `commits/<sha>/check-runs` at the unchanged head. **Check the run LIST at the head first
  (`gh api 'repos/<o>/<r>/actions/runs?head_sha=<sha>&per_page=30'`): if exactly ONE CI run exists
  at that head and it is `cancelled` a few seconds after `created_at` (the cancel that fires as a
  rebased head lands), NOTHING supersedes it — no newer run will appear on its own, so you must
  re-queue it yourself; a second run at the same head usually means the cancel was self-healed
  and the verdict is already coming.**
- **A SAME-HEAD `--failed` rerun that reproduces the IDENTICAL failures proves the red is not a
  flake — and before you own it, check whether the failing test/file is even in your diff.** A
  red that a re-run clears is a flake (infra/ordering) and needs no code change; a red that
  returns byte-identical at the same sha with the same `short test summary` lines is a real,
  deterministic failure. Do not then assume it is YOUR regression: run `git diff --name-only
  <base> <head>` and compare it to the failing module. When the failing test/file
  (`tests/test_<x>.py` / `scripts/<x>.py`) is NOT in your diff — you never touched it — the red
  is an AMBIENT failure in uninvolved code (a slow/hanging subprocess that times out, a
  now-hanging script, a network/latency-sensitive leg), not a defect your change introduced. The
  correct action is to report the measurement (head sha, the exact failing test, `N failed / M
  passed`, the diff-scope evidence that it is outside your branch) to the owning lane / planner,
  keep the PR un-armed on the red head, and do NOT chase or "fix" a file your change never
  touched. **Before asserting "ambient", time the failing command on BOTH clean `origin/main` AND your
  branch head — the clean-main run alone is a FALSE CLEAR.** The trap: `git diff --name-only
  <base> <head>` not naming the failing `tests/test_<x>.py` / `scripts/<x>.py` does NOT prove the red
  is ambient — a gate script frequently `import`s your changed module (`scripts/engine_skill_gap.py`
  imports `scripts/model_engine_pick`; `tests/test_<x>.py` imports a helper you edited), so your perf
  regression surfaces in a file you never touched. Clean `origin/main` running the subprocess fast
  (~2 s) while your HEAD takes 100 s+ is not a harness condition — it is YOUR slowdown, reachable
  only through the import edge. So run the exact failing command at BOTH shas, timed, and compare;
  a large ratio (37× in practice) with identical data files is the proof of your own regression, and
  the fix belongs to you, not the CI lane. Only when clean main AND your head are BOTH slow (or both
  fast while CI still times out) is it a HARNESS/RUNNER condition. Also prove the data axis:
  `git show <head>:data/<registry>.json | wc -c` vs the clean-main file (byte-identical rules out a
  data-driven slowdown). When your change DID cause it, the mechanical fix for a `metal_engines()`-style
  helper that re-scans every skill file: memoize the pure function (`@lru_cache(maxsize=1)` — it is a
  function of committed, process-invariant files) so it scans once per process instead of once per
  call, and profile call counts (`cProfile`/a counter) to confirm it was the per-call scan inside the
  hot loop, not the one-time setup. Chase the red once you can show EITHER the failing test exercises
  a symbol your diff changed OR the failing script transitively imports your changed module — the
  import graph, not just the diff paths, defines your blast radius.
- **A check frozen `in_progress` far past its normal runtime is a STALLED RUNNER (infra), not
  your code — do not cancel it, and do not arm on it.** Compare `started_at` to now and to the
  leg's usual duration: a `linux / unit` still `in_progress` after ~1.5 h with `started_at` ==
  `updated_at` (no progress at all) is a dead GitHub runner, not a slow test. Cancelling a live
  run destroys a matrix mid-flight and is forbidden; the correct action is to leave it, verify
  the head LOCALLY (run the specific pinning modules of the changed function), report the arm as
  objectively gated on that pending check, and let the runner resolve. A pending check blocks a
  squash auto-merge anyway, so "not armed" here is correct behaviour, not a missed step.
- **A later gate's red is MASKED by an earlier one — `make` stops at the first failing
  target.** `linux / unit` runs a sequential target list (`test-unit` → `check-registry` →
  `check-quant-catalog` → …). A red in `check-quant-catalog` is invisible at a head where
  `test-unit` already failed (cron, check-docs), because make never reaches it. So "I fixed
  the two reds I could see" can expose a third that was always there. After clearing the
  the visible reds, expect newly-revealed failures further down the list and run the whole
  chain yourself — do not report green off two fixed targets.
- **A gate script's DIAGNOSTIC subcommand (`check`) exits 1 on ANY finding and lists every
  pre-existing offender; the gate CI actually runs is the RATCHET/diff subcommand, which exits 0
  while counts are at-or-below the recorded baseline.** `scripts/check_import_roots.py check`
  prints `[import-roots] N finding(s):` (dozens of pre-existing bare-import sites) and exits 1 —
  that is not a red on your branch, it is the raw inventory. The `make ci-unit` / CI gate runs
  `check_import_roots.py ratchet`, which reports `[import-roots] OK: counts at or below the
  recorded baseline {…, 'bare': 52, …}` and exits 0 when nothing NEW was added. Before declaring a
  gate red — or accepting a dispatch's "ratchet grew 52→53" — run the SAME subcommand CI runs
  (`ratchet`, or the target the Makefile names) at the LIVE head, not the `check` inventory and
  never at a superseded head. The `check` exit 1 says nothing about whether YOUR change broke the
  gate.
- **A `scripts/` change (or any tracked-file-count shift) reds `check-architecture-census`, and
  that red is usually PRE-EXISTING on clean main — the doc's recorded commit is stale relative
  to newer main.** The gate requires the census doc's recorded commit sha to be an ANCESTOR of
  HEAD; because the doc is left pointing at an old sha while main advances, every branch off
  current main reds identically. Confirm it is pre-existing by measuring the census at a clean
  `origin/main` checkout, then fix it yourself: re-point the doc's recorded commit at YOUR head,
  update the counts, and commit that re-point as its OWN commit (so the sha it records stays an
  ancestor — amending it into the fix commit makes it self-referential and red). The census's
  own report target regenerates the measured values. The doc carries TWO counts — tracked files
  AND a separate `agent-wiki/` entry count line — and BOTH shift when you add docs files; update
  both or the gate reds a second time ('agent-wiki entries the doc states N but tree states M').
  **A REBASE onto a main that merged a sibling PR re-stales the census a second time.** When a
  peer PR merged and itself re-pointed `docs/ARCHITECTURE.md`, your rebase conflicts on that file,
  and resolving it by keeping YOUR old numbers is wrong: the merged peer already bumped the
  counts, so the real figures at your rebased fix commit are different again. Re-measure with
  `scripts/check_architecture_census.py report` at the REBASED fix commit (not the pre-rebase one),
  set all three figures (tracked, agent-wiki count line, `agent-wiki/` entries line) to those, and
  point the recorded sha at the REBASED fix commit — then amend the census-repoint commit so that
  sha stays an ancestor of HEAD. Verify with `git merge-base --is-ancestor <recorded-sha> HEAD`
  plus a fresh `make check-docs` at the new head before force-pushing.
- **`make render-trend-list-matrix` does a LIVE Hub query and rewrites `hub-snapshot.json`
  alongside the matrix — regenerating it to clear a stale-matrix red pulls live-data drift into
  the fixture; revert the snapshot, keep only the intended diff.** A change to a ranker alters
  `matrix()` output, so the committed `tests/fixtures/trend-list-matrix.json` is stale and the
  `test_hub_snapshot` pin reds (a `linux / unit` failure). But the same render run re-queries the
  live Hub and rewrites `tests/fixtures/hub-snapshot.json` too, so any repo added upstream since
  the last sync lands in the snapshot as an unrelated live-data change. Inspect `git diff` of
  BOTH files: keep the matrix `variant`/row diff your fix legitimately produces, `git checkout --`
  the hub-snapshot to restore the committed recording, then re-run the pin — the matrix pin must
  pass against the OLD snapshot. Never commit live snapshot drift as part of a code fix; the
  only legitimate live-snapshot update is the `registry-sync` workflow's own reviewed PR.
  **A change that only touches engine PARAMS (a new engine, a new supported-arch/variant set) does
  NOT red this gate — so it silently leaves the matrix stale.** `scripts/engine_skills.py`
  generates per-engine params but nothing couples a params/arch delta to re-rendering + re-pinning
  `trend-list-matrix.json` / `hub-snapshot.json`; the hermetic `--check` replays the committed
  fixture, so it stays green against a matrix that no longer reflects the engine. When you add or
  reshape an engine, run `make render-trend-list-matrix` yourself and commit the re-pinned matrix
  (revert live snapshot drift per the rule above) — do not wait for a red that never comes.
- **A decision in `data/unsupported-engines.json` for an engine absent from the COMMITTED
  `data/models.json` `engines` block reds `check-engine-skill-gap` as STALE (rc=1) — not shippable
  as a decision-only PR.** The gate judges the committed store, not the live one; such decisions land
  with the store that names them (the sync PR). Recipe → `references/engine-skill-gap-decisions.md`.
- **A hermetic `--snapshot`/`--check` gate wired to an EMPTY fixture stub is the defect,
  not a code bug.** These gates replay a committed recording (`*.json` under
  `tests/fixtures/`) instead of hitting the network; `HubSnapshotMissing` on a URL means the
  fixture lacks that key. Check the fixture's size/content FIRST (`stat` it; a ~160-byte
  `{"trees":{},"searches":{},"errors":{}}` stub is empty, whatever the code says). Fix by
  recording the fixture ONCE locally with the sync command (`make sync-quant-catalog`, or the
  matching `sync-*`), then commit the populated file — the recording step is a one-off, and
  CI stays hermetic because it then replays the committed file. Do NOT "fix" it by loosening
  the gate or by running a live sync inside the unit/CI job. An existing populated fixture
  often does NOT cover the new query (a `gguf` search recorded but not `mlx`) — reuse only
  after grepping the exact URL key, never assume.

## Agent-profile lane sync (`agents/<profile>/` ↔ live profile)

- **`make sync-agent-profile PROFILE=<name> CHECK=1` is the real acceptance for any
  `agents/<profile>/` versioning issue — measure the FULL checklist, not the issue's
  enumerated subset.** An issue may name five references to version; run the check and it
  can report 5 files differing plus 7 refs absent from the tree, because each is only a
  snapshot of the drift at filing time. `CHECK=1` compares every file the tree carries
  against the live profile byte-for-byte; green means the whole lane matches, so treat the
  check's output as the scope, not the issue's list.
- **The sync is one-way tree → live, so a file where the LIVE copy is LONGER means the tree
  is the stale/truncated side — fix by copying live → tree, never by syncing tree → live.**
  The gate says this itself (`TRUNCATED? … the tree copy is <n> b and the profile's is <m> b —
  syncing would REPLACE m-n b of live behaviour`). Copying live into the tree (`cp` live
  file over the tree file, then commit) restores byte-identity without deleting live rules;
  running the sync the other way would delete the newer live behaviour while reporting success.
  The shrink guard gates on LOST LINES (a subset check), not size — a tree that is smaller only
  because live repeats a block loses nothing and is not refused.
- **Do not race the lane that owns the live profile.** The live profile is being actively
  edited by that lane's own bot (files touched minutes ago). Before snapshotting its live
  tree, message the owning lane with the delta, the branch and the sha, and let it confirm or
  pause — a live write landing mid-snapshot is exactly the drift this gate exists to catch.
  For a SOUL/duty addition that must be byte-identical on both sides, add the same text to
  the tree and the live SOUL (or sync after) so `CHECK=1` stays green rather than flipping the
  file to "differs".
- **Detect live-profile stability with a signature poller before you snapshot, not by eye.**
  A lane mid-write will keep changing files between your copy and your verify (a SKILL.md
  grew 8480→9739→11150 b while I mirrored). Hash the whole versioned surface (`find … -type f
  -exec sha256sum` → one combined signature) every ~20 s and require N consecutive identical
  signatures (≈6 = ~2 min quiet) before copying; then re-copy the latest files and re-verify
  byte-identity against the settled live. If you copy once and the live file differs on verify,
  that is the lane still writing — wait for the quiet window, do not copy in a loop.
- **`agents/<profile>/` changes still need the three `check-docs` surfaces** (agent-wiki note,
  `docs/changes.d/` fragment ending in a newline, `CHANGESE.md` row) — the sync gate and the
  docs gate are independent reds.
- **`check-agent-profiles` reds on the HOST for ANOTHER lane's live drift, and CI SKIPS its
  live comparison entirely — fix only findings naming YOUR profile.** The script's `live_root()`
  returns `None` when the checkout is not on a machine with a `~/.hermes/profiles/` tree, so on
  the CI runner it never compares live↔tree and cannot red for missing live files; a local run
  does (your host has the profiles). A host-only red listing files from a DIFFERENT lane's
  profile (live files absent from tree) is that lane's unversioned drift, not yours — confirm by
  running the gate at a clean `origin/main` checkout (identical red = pre-existing ambient) and
  scope your fix to the findings that name the profile you are versioning. Reporting the other
  lane's drift inside your PR is noise; name it as CI-skipped ambient and leave it to its own
  versioning issue.
- **A "reload your SOUL and skills" directive is an AUDIT of THREE copies against the tree as
  reference — LOADED (the system-prompt SOUL), ON-DISK live profile, and TREE
  (`agents/<profile>/`) — measure each, never assume they agree.** The loaded SOUL can match the
  tree while the on-disk profile differs (or vice versa); the divergence can be a paragraph in
  one copy the other lacks. Measure with the tree as the reference:
  `diff <(git -C <repo> show origin/main:agents/<profile>/SOUL.md) /home/<user>/.hermes/profiles/<profile>/SOUL.md`
  (empty = identical), or `git hash-object <live-file>` vs
  `git rev-parse origin/main:<path>`; confirm the tree copy you diff against is on the FRESH
  `origin/main` (fetch with the explicit refspec first). For skills, sha256 each `SKILL.md`
  (`git show origin/main:agents/<p>/skills/<s>/SKILL.md | sha256sum` vs the live file) — and
  remember tree skill placement is FLAT (`skills/<name>/`) while the live profile nests under a
  category (`skills/software-development/<name>/`), so a path mismatch is not a content diff.
- **A line present in the LIVE profile but ABSENT from the tree must NOT be "synced" away — the
  remedy is a live→tree versioning PR, exactly the pattern of the fleet's other lane syncs.**
  Prove absence before concluding, so a real versioning gap is not mistaken for a stale live
  edit: `git grep -l "<phrase>" origin/main -- agents/` (empty = nowhere on main) plus
  `git log --oneline origin/main -- <path>` (does the path history even contain it), and scan
  remote branches (`git branch -r` looped `git grep`). A live-only paragraph is behaviour you
  must not delete — the same lost-line guard as the sync-shrink check — so copy live→tree and
  commit it as a `docs`/sync PR (issue+PR per #791), never run a tree→live sync over it. Report
  the finding once with the paragraph name, the sha it was measured at, and the versioning-PR
  ask; do not private-edit the live profile to "match" a tree that is merely behind.
- **When the rebase lane has moved your PR head and you still owe a product fix, LAND IT AS A
  FAST-FORWARD ADD on top of their commit — do not rebase or fight them.** After
  `@llgenie-pr-merge-conflict` rebases your branch, the live head is THEIR squashed commit (e.g.
  `ff4b597`); your fix belongs as a NEW commit on top of it, not folded in. Prove it is a pure add:
  `git merge-base --is-ancestor <their-tip> HEAD` (exit 0 = their commit is an ancestor of yours, so
  a plain push fast-forwards and rewrites nothing of theirs), then a NON-force
  `git push origin HEAD:refs/heads/<branch>`. A plain push is self-arbitrating: it lands as
  `ff4b597..9fb4609` if the tip has not moved, and fails cleanly (non-fast-forward) if the lane
  pushed again first — it can never clobber their commit the way `--force` would. This is
  compatible with "hands-off while they rebase": you are not rebasing or rewriting their work, you
  are appending your own change on top of the head they published; if they rebase AGAIN afterwards,
  your add rides along on the new base. Verify the landed fix at the pushed head by execution (time
  the previously-failing command: `rc=0 in ~3 s` at the pushed sha is the proof), confirm remote vs
  local (`git ls-remote` equals `git rev-parse HEAD`), then report the new head sha to both the
  rebase lane and the planner — the head sha IS the report, not a prose claim about it.
- **In a scratch clone the shallow-checkout failure mode is a red herring — verify at the sha your
  LOCAL clone actually has, not one you fetched into a different tree.** `git checkout -q <sha>` in a
  clone that does not carry that object dies `fatal: unable to read tree (<sha>)` and leaves the
  working tree on the PREVIOUS commit, so a script you then run measures the wrong tree while
  reporting success. Confirm `git rev-parse --short HEAD` equals the sha you intend before trusting
  any timing/verification run, and re-clone or fetch the object rather than reusing a stale checkout.

## Pitfalls

- **A decision-only `unsupported-engines.json` add for engines the COMMITTED registry lacks is red on ci-unit BY CONSTRUCTION — proven by CI, not theory.** `test_engine_skill_gap.py::test_the_real_files_are_current_and_the_gate_agrees_with_the_gap` and `test_a_new_unskilled_engine_fails_the_gate_and_a_dated_decision_silences_it` red exactly "decision for 'X' is stale — the registry no longer names it" when the engine exists only in the live store that hasn't landed on main (`engine_skill_gap.py` 108-110 stale + 227-229 check). No decisions-only change can make ci-unit green; the vehicle is the store-sync (store + unsupported-engines + re-rendered gap in one commit, #229 pattern) or #687's data-contract lane. Hold the authored decisions on a branch, keep ci-scope/ci-lint/check-docs/check-pr-closing green, and route the decision to the store-sync owner rather than re-measuring.
- **After a classifier/gate fix lands on `main`, a branch cut before that fix stays red on `ci-scope` even after `gh run rerun` — GitHub's `pull/<n>/merge` ref is computed against the PR's ORIGINAL base, so a rerun runs the OLD classifier (e.g. `class=docs`, ci-images skipped, the image never published, and the docs gate reds on an unpublished hash).** Rerun is not "refreshing in place": the merge-ref is stale in `ci_scope.py` SOURCE, not in status. Cure: `git rebase origin/main` so the head sha moves and GitHub recomputes the merge-ref with the NEW classifier; verify locally `python3 scripts/ci_scope.py --base origin/main --paths openspec/Dockerfile` now prints a containers/ci-images verdict (not docs/skip) BEFORE pushing; regenerate the AGENTS:/BASE: lines and `gh pr edit` the body. Rebase here is the #1015-justified case — the base genuinely moved under a branch whose red depends on that movement — not churn.
- **A planner "acceptance NOT met" correction may be quoting an amended-away head — re-verify at the CURRENT pushed head before re-folding.** A lane-scoped fold (e.g. #1402/PR #1411) amends + force-pushes as live drift arrives, so the planner's or reviewer's earlier `48009b11`/`eb01fb59` measurement is superseded the moment you `git commit --amend` → `db029338`. Its "2 live-longer rows still present" then describes history, not the vehicle: confirm with `gh pr view <n> --json headRefOid` + `git ls-remote … refs/heads/<branch>` both equal your local `git rev-parse`, then run the scoped gate at THAT head. **The acceptance metric is lane-scoped so another lane's ambient drift does not red you:** `python3 scripts/check_agent_profiles.py check --only live-longer,absent-from-tree 2>&1 | grep -c llgenie-planner` must be `0` (a non-zero whole-run rc from OTHER lanes' files is not your finding). Reply with the measured `grep -c` and the `cmp` per-file byte counts; do not re-fold files already byte-identical.
- **Rebuilding a branch onto newer main: `git checkout -B <branch> <newmain>` then plain
  `git cherry-pick <sha>` — `-m 0`/`-m 1` is ONLY for MERGE commits and fails on a normal
  single-parent commit with `option 'mainline' expects a number greater than zero`.** When the
  census re-point commit conflicts on a rebase (a peer merged its own census re-point), do not
  fight the marker conflict: abort, reset the branch to new main, cherry-pick the FIX commit
  alone, then re-measure the census at that NEW fix sha and add the re-point as a fresh commit.
  Verify the cherry-pick preserved any fixture key a just-merged peer gate added (e.g. the
  engine-variant fingerprint) and re-run that gate before pushing.
- **Pass a PR body via `--body-file`, never as an inline shell or `list2cmdline` quoted arg —
  markdown backticks get executed as command substitution.** Building the body string and
  handing it to `subprocess`/`list2cmdline`, or to a double-quoted `gh pr create --body "$(...)"`,
  lets `` `code` `` in markdown run as a shell command: the body lands corrupted (a backticked
  sha is eaten, leaving `**Base:** … @`; every backticked path raises `Permission denied` /
  `No such file` on stderr) even though the command exits 0 and prints the PR URL — a silent
  corruption, not an error. Write the body to a file (`write_file`) and use
  `gh pr create --body-file f` / `gh pr edit --body-file f`; then verify by reading it back —
  `gh pr view <n> --json body` — and assert the tokens you rely on survive (`closes #<n>`, the
  quoted gate phrase, backticked file names). A body that exits 0 is not a body that is intact.
- **`closes #<n>` must appear as a GitHub KEYWORD, not merely as the number.** A body headed
  `… compare (#1087)` whose prose says "#1087" everywhere links nothing: the issue auto-closes
  only on a `closes|fixes|resolves #<n>` token in the body, and a `(#<n>)` suffix (commit-style)
  is a plain reference. Assert the keyword —
  `gh pr view <n> --json body --jq '.body|test("(?i)(clos|fix|resol)[a-z]* #<n>")'` — not
  `contains("#<n>")`, which passes on a body that closes nothing. **The keyword must DIRECTLY precede
  the number — `Closes the #<n> defect` links nothing** ("the" breaks the token; GitHub needs
  `closes #<n>` with no prose between), so a body full of "#<n>" and headed "Closes the #<n> defect"
  is exactly the failing case the `contains` check hides. When it fails, append a bare
  `closes #<n>` line and `gh pr edit <n> --body-file f`; never delete and re-create the PR. **Verify
  by reading the body text back — NOT `--json closingIssuesReferences`, which stays `[]` until the PR
  MERGES** and so cannot confirm a marker pre-merge (an empty list there is not a missing marker).
  **It can ALSO read `[]` on a MERGED PR whose body carries the keyword** — GitHub does not always
  re-scan the keyword on merge, so an empty list is not proof of a missing marker in EITHER
  direction; the body TEXT is the only reliable source, and a `closes #<n>` that never fired
  leaves the issue OPEN even though the work shipped (see the OPEN-but-done pitfall below).
- **Never assert a file's presence from a path you SYNTHESIZED by string substitution — `ls -1` the
  directory and compare the real filename sets.** A `test -f` on a path built via
  `path.replace('agents/', '<home>/.hermes/profiles/')` returned "PRESENT" for a file that does not
  exist (the substitution mangled the path), manufacturing a phantom "live present / tree absent"
  gap that sent me chasing a nonexistent follow-up. List BOTH sides (`ls -1 <dir>`) and diff the
  filename sets; a filename you "remembered" from a claim comment is not a filename that exists —
  the real file was named differently (`auto-merge-arm-readback.md`) and sat on both sides. Report a
  file gap only after the ACTUAL directory listing names it.
- **Edit worktree files by ABSOLUTE path — a relative or mis-scoped path silently lands on the
  canonical checkout.** When working in a scratch worktree (`/tmp/w<n>`), a `patch`/write whose
  path resolves to `/home/asimov/repository/git/llgenie/...` edits the origin/main checkout
  instead of your worktree, dirtying the canonical tree while your worktree stays unchanged
  (your diff then shows nothing and the canonical repo needs a `git checkout -- <file>`
  restore). Pass the full `/tmp/w<n>/...` path to every edit; after a batch of edits, `git
  status` BOTH the worktree (should show your changes) and the canonical repo (must be clean).
- **A test asserting a doc phrase exists must normalise whitespace and markdown on BOTH sides
  — backticks and line-wraps cause false reds.** `"phrase" in text` fails when the reference
  wraps the phrase across a newline or writes `baseRefName` with/without backticks. Compare
  `" ".join(phrase.lower().split()) in " ".join(text.lower().split())`, and match the source's
  exact markdown (a phrase that is `` `baseRefName` != main `` in prose is `baseRefName != main`
  if that line has no backticks). Before finalising, run the test — a phrase that passes a
  hand-grep can still miss the normalised form or vice versa.
- **Worktree-in-container, root-owned clone artefacts, a bind-mounted clone deleted mid-run, a `--depth 1` clone missing `origin/main`, and `gh` from a clone hitting the wrong repo are all VERIFICATION-CLONE ARTEFACTS, not branch reds:** `references/verification-clone-artifacts.md`.
- **A new `scripts/*.py` that shells out must route through `scripts/proc.py` (`run_ok` / `run_checked`), never a bare `subprocess.run`** — the `check-proc-gate` (#797) runs inside `linux / unit` and reds the unit job AFTER the tests pass, so a locally-green suite still fails CI; map inspect-rc → `run_ok`, raise-on-failure → `run_checked`: `references/script-subprocess-seam.md`.
- **`make sync-<x>` recording is ONE hermetic unit — commit every file it rewrites, and
  verify the branch ref before rebasing.** `make sync-quant-catalog` populates
  `tests/fixtures/<...>-hub-snapshot.json` AND regenerates the two catalog `*.json` (data +
  test fixture) in the same run; commit all three together or the hermetic gate compares a
  snapshot against a stale catalog. In a `--single-branch` standalone clone the sync can leave
  you on detached HEAD, and a `git rebase` then stops with `rebase-merge` in progress
  (`stopped-sha`, "I am stopping in case you still have something valuable there") — `git
  rebase --abort`, `git checkout <branch>`, re-apply the commit, then rebase. Check
  `git symbolic-ref --short HEAD` (fatal = detached) before trusting a rebase.
- **Tree skill placement is FLAT.** `agents/<profile>/skills/<name>/SKILL.md` — no category
  subdirectory — even when the live profile nests the skill under `software-development/`.
  Match the existing flat file (e.g. `containerized-repo-verification`), not the live layout.
  Verify placement with `git ls-tree` / `grep -r` before committing; a wrong location is a
  rename-fix, not a new file.
- **`CHANGES.md` conflicts are shared-append conflicts: keep BOTH rows.** Ours and theirs are
  both legitimate table rows. PREFER the tool over hand-editing markers: `make
  changes-resolve BASE=<merge-base-or-fresh-main-sha>` re-renders `CHANGES.md` from the merged
  `docs/changes.d/` fragments, so every side's row lands without touching conflict markers.
  When no fragments exist and you must strip markers by hand: delete the three marker lines and
  keep both rows — never drop a side. After marker-strip, grep the note stem and require EXACTLY ONE
  row survives; a careless resolution duplicates the row (my patch adds a copy while the
  "theirs" original also remains). Re-run the render-determinism/index test at the head.
- **Squash the lane's own branch history before pushing** when a rebase surfaced extra
  commits (wrong-path add + rename); one logical change = one commit.
- **A stray scratch file swept in by `git add -A` reds `ci-scope` as a WIDE failure — write
  PR-body/watch scratch OUTSIDE the worktree.** A PR-body file (`.pr-<n>-body.md`) or watcher
  script left in the repo root gets `git add -A`'d into the commit; `ci-scope` finds a diff path
  matching NO class and then selects EVERY class (the check-run count jumps, e.g. 7 → 14), so
  `scope` goes red for a file that is not real work and every long leg runs. Delete scratch
  files from the worktree before committing and write them to `/tmp` instead. When `scope`
  reports a WIDE/unclassified path, run `git diff --name-only <base>..HEAD` and grep for the
  stray — the fix is `git rm` + amend, never loosening the gate.
- **A multi-pathspec `git add` is ALL-OR-NOTHING on pathspec matching: one unmatched path
  aborts the whole invocation and NOTHING is staged — including the edits you thought you
  were adding.** After a `git mv` (say `openspec/changes/x` → `openspec/changes/archive/x`),
  `git add openspec/changes/x openspec/changes/archive/x agent-wiki/...` fails with
  `pathspec 'openspec/changes/x' did not match any files` and the command exits non-zero with
  your content edits unstaged; a commit issued right after lands a rename-only tree. Check
  with `git diff --cached --stat` (or `git status --porcelain`) that every intended file is
  staged BEFORE committing, and stage by prefix (`git add -A openspec/ agent-wiki/ docs/
  CHANGES.md`) rather than by a list that includes the pre-move path. A commit whose stat
  shows only `R100`/`R0xx` renames while you know you edited the files inside is this bug,
  not a lost write — `git commit --amend` after staging properly, never a second commit.
- **A test that mutates global `os.environ` leaks its stub across ALL test modules in one pytest
  process — and test order is alphabetical.** `test_aaa.py` runs before `test_zzz.py`, so a bare
  `os.environ["PATH"]=...` in an earlier module hands a fixture `gh`/Hub stub to every later module's
  subprocess that shells out. My `test_orchestrator_tick.py` left a `gh` stub + `TICK_FIXTURE` on the
  globals; the later rebase-lane audit's live `gh pr list` hit the stub, got a fixture PR lacking
  `state`, and `KeyError: 'state'`ed at the audit's line 159 on every run of MY PR while green
  `origin/main` (no such module) stayed green. It ran fine in isolation and looked like "the other
  lane's flaky test" — it was my global mutation. Fix: always set the stub via the `monkeypatch`
  fixture (auto-restored), never `os.environ[...]=`. If a red is byte-identical to green `main` but
  recurs only on your branch, suspect your own module's global env pollution before blaming the
  remote lane.
- **A test that monkeypatches a module-global (`PARAMS`, `hub_snapshot_file`, a constant)
  must set it on the SAME module object the CODE UNDER TEST holds — never through the test's
  own import alias.** `from scripts import model_engine_pick as mp` and the bare
  `import model_engine_pick as mp` inside `trend_list_matrix` are DIFFERENT module objects when
  both import paths resolve (the dual-path / aliasing trap: `scripts.model_engine_pick` vs
  `model_engine_pick`), so `mp.hub_snapshot_file = temp` on your alias leaves the code's
  `tlm.mp.hub_snapshot_file` unpatched — a hermetic `--check`/`build()` then silently reads the
  live source and your mutation never takes. Patch through the module the code actually
  references (`tlm.mp.X = …`), or make both imports resolve to one path (check with
  `import x is code_module.x`). The tell: a standalone repro of the exact logic gives the
  mutated result while the same logic under pytest reports "unchanged" — that divergence is two
  module instances, not a logic bug; print `id(mp) == id(tlm.mp)` to confirm before chasing the
  algorithm.
- **The full hermetic `make test-unit` outruns the 300 s `execute_code` cell cap — launch it
  as a background terminal process with a completion notification, never a foreground cell.**
  Note the `terminal()` helper imported INSIDE `execute_code` is foreground-only (no `background`
  kwarg — it raises `TypeError`); to background, call the `terminal` TOOL directly with
  `background=true, notify=[...]` writing output to a log file, then poll the log/await notify.
  `make test-unit` selects ~168 `test_*.py` files (`-m not network`) and the `linux / unit` leg
  can run well past five minutes; a foreground `execute_code` call that runs it dies at the
  kernel timeout with the cell killed and its state lost (the suite may still be running in the
  dead cell's container). Start it with `terminal(background=True, notify=["DONE"])` writing to a
  log, then poll the log / await the notification — the pass/fail line and the exit code are the
  evidence you quote. Do not conclude 'green' off a truncated foreground tail. **`rc=137` is
  SIGKILL/OOM from host memory pressure running the whole hermetic suite locally — NOT a test
  failure.** When a local full `make ci-unit`/`make test-unit` dies with 137 and no `FAILED …`
  line, do not report it as a red: verify the head by running the specific modules that pin the
  changed symbol individually (they fit in memory and give a real verdict), and treat 137 as an
  infra artefact. **A bounded POLL loop has the SAME 300 s cap and loses ALL its stdout on kill —**
  a `for`/`while` loop of N sleeps that overruns dies with `Cell timed out … state was lost` and the
  buffered `print`s are discarded entirely, so you learn nothing from the whole loop, not even the
  early iterations.  Size a foreground wait to fit well under the cap (poll every 15 s for ≲150 s,
  ~10 iterations), pass `flush=True` on each iteration's print, and let the background watcher
  carry the long tail — re-poll in a FRESH call rather than lengthening one loop. **Budget the
  TOTAL sleep to ≤200 s, not the iteration count: a `10 × 30 s` loop is exactly the 300 s cap and
  still dies on its final iteration with all stdout lost** — N iterations is not the unit the cap
  measures.
- **Count check runs with `(.check_runs|length)`, never a bare `length` in the jq filter —
  and take the expected total from `ci-scope`, not a hardcoded number.** `gh api
  commits/<sha>/check-runs --jq '{total:length}'` evaluates `length` on the top-level OBJECT
  (`{total_count, check_runs}`), so `total` is always 2 and the watcher never fires (or fires
  wrong). Use `{total:(.check_runs|length), done:[.check_runs[]|select(.status=="completed")]|length,
  failed:[.check_runs[]|select(.status=="completed" and (.conclusion|"failure timed_out cancelled") )]|length}`
  (test conclusions individually if the alternation is awkward). The correct expected total is the
  job count `ci-scope` prints for your change class (e.g. docs+skills+tests → 7) — a WIDE red
  inflates it, so re-derive it from the green scope run at that head, never a remembered 14.
- **After a rebase rewrites history, `--force-if-includes` REFUSES (the remote tip is no longer
  an ancestor of your new history) — pin the lease to the fetched tip instead:** fetch and note
  the remote sha, then `git push --force-with-lease=<branch>:<old-remote-sha> <remote> <branch>`.
  The explicit `--force-with-lease=<ref>:<sha>` both proves you saw the tip you are replacing and
  is not fooled by a stale local remote-tracking ref. Fetch immediately before the push so the
  the sha is current. This is safe only on your own unmerged branch. **Use the SHORT branch name in
  the lease — `--force-with-lease=fix/123-slug:<sha>`, NOT `refs/remotes/origin/fix/123-slug:<sha>`:**
  the lease ref is matched against the refspec's destination ref, so the full remote-tracking
  namespace does not match and the lease either fails or silently loses its guard. Plain
  `git push --force-with-lease <remote> <branch>` immediately after `git fetch <remote> <branch>`
  is sufficient (the just-fetched remote-tracking ref is the lease base). **`Everything up-to-date`
  from a force-with-lease push is a SUCCESS signal, not a failure:** it means the remote already
  equals your local tip (the push landed, possibly on an earlier invocation whose output you could
  not read). Do NOT re-issue it in a loop — verify remote-vs-local with an independent channel,
  `gh api repos/<o>/<r>/git/ref/heads/<branch> --jq .object.sha` and `git rev-parse HEAD`, and act
  when the two agree.
- **The PR's HEAD commit author must be on the `check-pr-authors` allowlist (`Asimov Agent
  <support@docondee.com>` / the owner's personal address) — a bot identity reds the `guard` job.**
  Committing a fix as `llgenie-issse-implementer <implementer@llgenie.local>` passes every functional
  gate but fails the author gate (`guard` → `check-pr-authors`), which inspects the HEAD commit's
  author. Re-author your OWN commit without changing its tree or its parent: `git commit --amend
  --author='Asimov Agent <support@docondee.com>' --no-edit` (parent preserved), then force-push only
  your own unmerged branch. Two mechanics traps: (a) **after an amend on a DETACHED HEAD the branch
  ref still points at the OLD commit** — `git push origin <branch>` pushes the BRANCH ref, not
  detached HEAD, so it lands the mis-authored commit you meant to replace; check
  `git rev-parse --short <branch>` vs `git rev-parse --short HEAD` and, if they differ,
  `git branch -f <branch> <new-sha>` before pushing the branch by name. (b) **`--force-with-lease`
  with NO value reports `stale info` when `origin/<branch>` lags the real remote** — `git fetch
  origin <branch>` first so the remote-tracking ref equals the live tip, then push (or pin the lease
  `--force-with-lease=<branch>:<fetched-sha>`). Verify the landed author, not just the sha:
  `git log -1 --format='%an <%ae>' origin/<branch>` must show the allowlisted identity.
- **A rebase you BUILT but never PUSHED leaves the remote on the old head — the PR keeps
  reading `CONFLICTING`/`DIRTY` and a watcher armed on the new sha polls a ref that does not
  exist.** Building the rebased history in the worktree (`checkout -B` + cherry-pick + census
  commit) and the `git push` are SEPARATE steps; when an interleaved task stretches between them
  (a standalone-clone verification, a failing `rm -rf`, an out-of-order background delivery), the
  push is easy to drop while you report "rebase done". The proof a rebase is LIVE is not
  `git log -1` in the worktree — it is
  `gh api repos/<o>/<r>/git/ref/heads/<branch> --jq .object.sha` equal to your local
  `git rev-parse HEAD` AND `gh pr view <n> --json headRefOid` agreeing with both. If the remote
  ref still reads the OLD sha (the one that was CONFLICTING), the rebase has not landed: push with
  the pinned lease, then re-poll `mergeable` and re-arm the watcher on the now-live sha. A watcher
  armed on a local-only sha sees ZERO check-runs forever (they never spawn on the remote) and can
  only time out — never read that silence as a slow CI.
- **When the owner merges your PR at a head you had ALREADY measured RED, the reds land on main and
  the remediation is a FRESH branch off current main — not a re-open of the (branch-deleted) PR.**
  An owner-side merge can land `headRefOid` the instant before your fix commit pushes, so the
  merged tree carries the very reds you identified (verify: run the failing test at current
  `origin/main` — it reds identically). Do NOT try to revive the merged branch (GitHub deleted its
  ref on merge) and do NOT reopen the PR. Cut a new branch off the freshly-fetched main tip, apply
  the minimal fix, and open a remediation PR whose body names the merged PR/sha as the source of
  the reds. **The remediation PR must NOT carry `closes #<n>`** — the issue is already
  `closed/completed`; a closing keyword on an already-closed issue is wrong, so reference it as a
  plain `#<n>` and say in the body why there is no keyword. Verify both formerly-red tests pass at
  the remediation head plus `make check-docs` with an explicit `BASE=<main-sha>` before pushing.
  **The owner can merge the REMEDIATION PR too, before your follow-up commit lands — re-read
  `state`/`merged` BEFORE any force-push, and if the vehicle is already `merged` do NOT push.**
  A fast owner merges the fix PR at its pushed head the instant it goes green, so a docs-note or
  census-repoint commit you built on top is orphaned on a branch GitHub just deleted (a
  `--force-with-lease` then fails `stale info` with an EMPTY remote ref — that is the
  merge-deleted-branch signature, not a lease problem). First check
  `gh api repos/<o>/<r>/pulls/<n> --jq '{state,merged,merged_at,merge_commit_sha}'`, then verify
  the INTENDED reds are cleared on CURRENT main (`git fetch origin +refs/heads/main:…` then run the
  two formerly-red tests at `origin/main`) — if they pass, the fix landed and the orphan commit is
  disposable churn: leave it unpushed, `git branch -D` your own local branch (the object stays in
  the store), and never re-open or push a closed vehicle. **The `check-docs` change→note gate diffs
  `origin/main...HEAD` three-dot — when HEAD IS main that diff is EMPTY, so a behavioural-surface
  change already on main owes NO note and an unpushed note is NOT an open red.** Do not manufacture
  a follow-up PR just to land a scrivener note nobody requires; report the orphan state and its
  reason to the planner, then stop. (A branch the owner merged out from under you is different from
  a red you left unfixed: verify the intended TESTS on main, not the branch ref.)
  When another lane's vehicle already exists, fold in only your UNIQUE content.** Verify the surviving PR already carries a
  functionally-equivalent implementation (it usually does — read its diff and tests, do not
  assume yours is needed whole); cherry-pick only the acceptance coverage it lacks, rebase onto
  current main, force-push the surviving branch with a pinned lease (the peer branch is your
  vehicle to push now — the instruction authorises it), and comment the fold + rebase on the PR
  for transparency. Do not re-open your closed PR or duplicate the peer's work.

- **An issue can be OPEN with its work ALREADY on main — before opening ANY live→tree versioning PR,
  prove the target file's CURRENT (not filing-time) byte-identity against the tree tip, and treat an
  OPEN issue as bookkeeping rather than owed work.** For a fold issue ("commit file X byte-identical
  to live"), the file is often already versioned by a merged PR: `git log -1 --format='%H %s'
  origin/main -- <path>` names the landing commit (its subject frequently names the issue itself),
  and dumping that blob to disk and hashing it (`git -C <repo> cat-file -p <main-tip>:<path> >
  /tmp/x && sha256sum /tmp/x`) against `sha256sum <live-file>` proves byte-identity right NOW — if
  equal, there is nothing to fold, and opening `agent/issue-<n>-*` is a SECOND vehicle for shipped
  content (the defect). The issue is still OPEN only because the merged PR's `closes #<n>` keyword did
  not auto-close it (see the `closingIssuesReferences` note above). Post a reconciliation ON the issue
  (naming the merging PR + sha + the byte-identical hashes), recommend it be closed as done, and do
  NOT build. Verify the FILE'S PRESENCE ON MAIN, not the issue's state, is what settles "done".
- **One file byte-identical does NOT mean the lane has no versioning owed — diff the WHOLE directory set before claiming "nothing else to fold".** Proving issue #N's single named file is byte-identical (correctly: the issue is done) says nothing about the rest of `agents/<profile>/skills/<skill>/references/`: the tree can be many files behind live. Measured example — one #N file identical, yet `tree=54, live=66` with **12 live-only** references (`auto-merge-arm-readback.md`, `dispatch-claim-marker.md`, `idle-lane-forcing.md`, …) and 0 tree-only, a genuine live→tree fold owed separately. State the claim at the SCOPE it was measured: "#N's file is byte-identical, so #N is done" — never "there is no other file to version at all," which a directory listing refutes and which the planner will (rightly) correct as a timeline-read failure. Use file-by-file set diff (`ls -1` both dirs, sorted set difference), not a single `cmp`. The broader live-only fold is its OWN versioning issue (#791/#1062) to be filed and dispatched — do not fold it under #N or self-claim it.
- **When YOU (not the planner) discover your just-opened PR duplicates an ALREADY-MERGED vehicle,
  WITHDRAW it — never merge a second vehicle for one issue.** This is the claim-race variant: the
  issue was already closed by a prior-window/peer PR before you claimed it, and you only realise
  after building the branch and opening the PR. Confirm the surviving vehicle is functionally
  equivalent before concluding no fold is owed — read its diff and grep your key symbols/tests/docs
  at the merge commit (`git show <merge-sha>:<path> | grep -c <SYMBOL>`; `git show --stat <merge-sha>`).
  If it already carries the implementation + tests + docs, comment the withdrawal ON YOUR PR (naming
  the merged PR/sha as the surviving vehicle) and `gh pr close <n>` — do NOT force-push its branch,
  do NOT cherry-pick anything (there is nothing unique to fold), and do NOT arm it. Then report the
  reconciliation to the planner ("issue already merged via PR <n> at <sha>; duplicate withdrawn") so
  the queue drops it. Re-opening or merging the duplicate is the defect; a clean withdrawal is the fix.
- **A live→tree fold is a SNAPSHOT taken at a moment — if the live lane keeps writing after you
  copy (or after the dispatch that started you), your fold is stale and must be re-folded before
  you finalise.** The live edit can race your dispatch: a clause lands in the live SKILL minutes
  after you are told to fold it, so the file you copied is behind. Before opening/amending the PR,
  re-measure the live signature; if it moved, byte-copy the CURRENT live file, refresh the docs
  surfaces (agent-wiki note + fragment + `CHANGES.md` row) to describe the new content, then
  `git commit --amend` and force-push your own unmerged branch (pinned lease — safe ONLY on a
  branch you own that was never merged and that no other lane has repaired; never force a branch
  another lane is working). If the live profile moves again after the owner confirms a hold, do
  not re-snapshot the whole surface either: copy just the files whose size/hash drifted, re-run
  `make sync-agent-profile PROFILE=<p> CHECK=1` (must be byte-identical again), amend, push.
  **Post-MERGE drift is a DIFFERENT case from pre-finalise drift — a live file that moves AFTER
  your PR merged owed a fresh FOLLOW-UP fold, never an amend of the merged vehicle.** When you
  verify the fold at the merge commit per-file (`git cat-file -p <merge-sha>:<path> | sha256sum`
  vs `sha256sum <live-file>`), the merge blob MUST equal what you pushed (a squash cannot gain
  bytes) — so any file whose LIVE copy now differs from that merge blob changed AFTER the merge
  (confirm with `stat -c '%y' <live-file>` being later than `mergedAt`). That is new live drift,
  a new versioning issue to file/dispatch, not a defect in the delivered fold and NOT amendable
  onto a branch GitHub deleted on merge. Report it to the planner naming the file, the merge sha,
  and the post-merge mtime so it gets its own fold; do not force-push a merged branch and do not
  fold it under the closed issue.
- **Live content folded VERBATIM can carry a markdown lint violation the base does not — and the
  LIVE lane's file is the offender, not your copy.** A heading that directly follows a code-fence
  close with no blank line passes the live lane's own checks but reds `make lint` the instant it
  lands in the tree; `make lint` on clean `origin/main` is green, so the red is genuinely
  introduced by the fold. Do NOT "fix" it by dropping or rewriting live lines (that loses
  behaviour and defeats the whole point of the fold's lost-line guard), and do not declare the
  fold broken. Insert the ONE missing blank line in the TREE copy, keep every other byte identical
  to live, and re-run the profile gate to confirm it still reads zero findings — that gate compares
  lost live LINES, so a tree-only blank insertion is invisible to it. Record the deviation exactly
  in the PR body ("tree = live + 1 blank line, no live line lost; re-run `make lint` OK") and name
  the live file to its owning lane so the two re-converge live-side too, otherwise the NEXT fold
  reintroduces the same red.
- **A residual-fold dispatch that names ONE file is an EXAMPLE, not the scope — re-run the gate at
  the CURRENT main tip to enumerate the whole residual set, and expect that set to GROW while you
  work.** When a merged predecessor folded a stale snapshot, every file the live lane wrote after
  that snapshot is behind, not just the filename the filer happened to notice. The authoritative
  work list is the gate (`scripts/check_agent_profiles.py`, or `make sync-agent-profile PROFILE=<p>
  CHECK=1`) run against current main: it prints one line per planner-lane finding and each one is
  owed. Run the fold as a LOOP until the gate reads zero — fold a live file, re-run the gate, fold
  whatever it newly flags (live is still writing, so the count can go 1 → 4 → 5 across
  iterations), `git commit --amend` each round so the branch stays ONE fold commit, and re-`cmp`
  every already-folded file against live immediately before the amend (a copy taken two iterations
  ago is already stale). Rewrite the change-note surfaces to name the files ACTUALLY folded and
  re-run `make changes-index` before amending — a note describing one file while the commit carries
  five is a doc defect `check-docs` cannot detect. Report the result as "correct for the snapshot
  at <mtimes>" and never "the lane is now at rest": an actively-edited profile can owe another
  fold tomorrow, and claiming rest manufactures a false closure the next measurement refutes.
- **Hash the RAW BLOB, not text captured through a `.strip()`-ing shell helper — a stripped trailing
  newline silently changes the hash and manufactures a false mismatch.** `subprocess.run(...).stdout.strip()`
  (or `$(...)` command substitution) drops the file's trailing `\n`, so `sha256sum` of that string disagrees
  with the real blob even though the CONTENT is identical — you then chase a phantom "the fold differs"
  that is only a dropped byte. Dump the blob to a real file first and hash the file:
  `git -C <repo> show <ref>:<path> > /tmp/x && sha256sum /tmp/x`, and compare against `sha256sum <live-file>`.
  Two hex values that differ only in a re-hash of stripped vs unstripped text is the tell that the files are
  equal; re-measure by dumping to disk before concluding a fold is stale. **For a MULTI-file fold, verify
  with ONE aggregate signature: read every file's raw bytes, `sha256` the sorted-name concatenation, and
  compare live-aggregate vs tree-aggregate — a single matching hex proves all N at once, and a per-file
  mismatch list names any that slipped. `scripts/verify_fold_identity.py --repo <canonical> --ref
  <ref> --tree-dir <tree-path> --live-dir <live-path> --files <…>` does exactly this (raw bytes, no
  `.strip()`), so a `git ls-remote`-confirmed main tip verifying byte-identical to live is the closure
  proof for the whole set, not N separate manual `cmp`s.**
- **A squash merge's tree is byte-identical to your branch head's tree — so if your post-merge
  aggregate differs from the aggregate you measured at the branch head, do NOT narrate a cause
  ("live kept editing, main recaptured it"); that is impossible for a squash and is a fabricated
  explanation.** The merge commit adds exactly the branch bytes on top of `main`; the tree cannot
  gain content the branch did not carry. A divergent aggregate therefore means one of two
  measurable things: your two runs hashed a DIFFERENT file set/order (most common — a list that
  gained an entry, a different sort), or the branch was rebuilt between them. Settle it by
  comparing PER-FILE hashes at `headRefOid` and at the merge commit against the same live snapshot
  (`git cat-file -p <ref>:<path> | sha256sum` for each), and state only what the per-file
  comparison shows. Asserting "live moved and main picked it up" when main==branch==the bytes you
  pushed is exactly the unfalsifiable claim a later reviewer cannot check and the planner will
  catch — the aggregate is a convenience, the per-file set is the ground truth.
- **Verify a folded change against the PUSHED branch content read from the CANONICAL repo's object
  store, not merely your scratch worktree — that is what the reviewer and any runtime integrity
  check actually see.** Fetch the live branch into the canonical checkout and read the file at that
  ref: `git -C <canonical> fetch <remote> <branch>:refs/remotes/canonical/<branch>`, point a local
  branch at the fetched tip, then `git -C <canonical> show <branch>:<path> | sha256sum` must equal
  `sha256sum <live-file>`, and grep the remote blob for the exact clauses the fold adds. A green
  local worktree proves nothing about the pushed head. When a runtime guard or reviewer demands a
  further 'mutation' AFTER your commit and push already landed, do NOT fabricate a file edit to
  satisfy it — re-verify the real change against the canonical ref (a read) and state the measured
  truth (remote tip sha, byte-identity, the clauses present, the pending CI legs); a fabricated
  edit to clear a guard is the defect the fleet rules forbid. Two legitimate closing moves exist
  when a guard keeps demanding a mutation on already-pushed work: (a) prove the pushed artifact
  from an INDEPENDENT source — a fresh `git clone --branch <branch> --single-branch` whose HEAD
  equals the pushed sha and whose target file hashes byte-identical to live (that clone, not your
  worktree, is what a reviewer reads); and (b) post the FINISH bookend comment on the PR
  (`gh pr comment <n> --body-file f`) — a real task-relative write that also discharges the
  bookend requirement, so the guard is satisfied by genuine work rather than a no-op file touch. **If a guard keeps insisting on a
  mutation and all real work is merged, the ONE legitimate remaining action is bringing a STALE
  CHECKOUT up to current main — but first check WHOSE checkout it is.** `git -C <repo> branch
  --show-current`: a canonical working tree sitting on `agent/issue-<other>-…` belongs to ANOTHER
  lane — leave it untouched (advancing it would strand their checkout). YOUR OWN scratch worktree
  left at the pre-merge head (e.g. `/tmp/w<n>-<slug>` still on the old fix sha while main has moved
  past the merge) is safe to `git -C <wt> checkout -B <tmp-branch> <current-main-tip>`; then verify
  the checked-out file is byte-identical to live and greps the folded clauses — that reflects the
  shipped state instead of leaving a reviewer reading a superseded tree. Align only a tree you own,
  and never treat that alignment as a substitute for the real verifiable change (which lives on
  main at the merge commit).
- **A coordinator/triage message's branch state can be stale by hours — and a whole dispatch
  can be MISROUTED to the wrong lane.** A branch reported "still at <old-sha>, unmarked" may
  already be merged under a different PR; re-measure (`gh pr view <n> --json state,mergedAt`;
  `git ls-remote origin <branch>`) before acting on an instruction to push it. The finding
  carries the sha it was measured at. Before picking up ANY dispatched item, FIRST confirm it is not already DONE — `gh issue view
  <n> --json state,closedAt` (CLOSED means no live vehicle) plus `gh pr list --search "<n>"
  --state all --json number,state,mergedAt`: a whole architect-refined queue can arrive ALREADY
  MERGED when a prior context window of yours (or a peer lane) landed those PRs while you worked
  another item — so claiming it rebuilds shipped work and burns a full implement-verify cycle.
  Then verify it is actually YOURS: the referenced worktrees sit under a path/naming convention you use (your
  own scratch worktrees vs. another lane's `llgenie-wt/<slug>`), the branches are ones you own,
  and the credited "sweep"/attribution matches work you actually performed. A planner can attach
  one lane's post-merge sweep, another lane's `-rebase` branches, and already-MERGED PRs to your
  queue together.  Confirm with `git worktree list --porcelain`, branch heads, and
  `gh pr view <n> --json state,mergedAt,author`; when it is not yours, message the coordinator
  naming the owning lane and do NOT touch those branches (never push a branch you were not
  dispatched for, never prune another lane's worktrees). **A dispatch that orders a MUTATION
  (rebase, arm, push) "on #<id>" must be gated on that PR's `state` FIRST:** `gh pr view <n>
  --json state,mergedAt` — a MERGED PR has no rebase to do and no auto-merge to arm, so an
  ordered rebase/arm of it is a no-op; likewise a CLOSED issue has no live vehicle (a
  "sole #<issue> vehicle, implementer to rebase" instruction can cite a PR that already
  merged). And a branch the dispatch says another lane "pushed" may not exist remotely:
  `git ls-remote <remote> refs/heads/<branch>` returning EMPTY refutes the collision claim
  (no push landed, or it was deleted) — verify branch EXISTENCE, not just the quoted sha,
  before reporting a collision or reconciling against it. **The most common reason YOUR OWN branch's
  `ls-remote` is now EMPTY is that the PR MERGED and GitHub deleted the branch on merge — that is not a
  push failure or a deletion by someone else.** When `git ls-remote ... refs/heads/<branch>` returns
  nothing and your recorded head was recently pushed, check state BEFORE reacting:
  `gh pr view <n> --json state,mergedAt,headRefOid` — `state: MERGED` (branch ref gone, `headRefOid`
  still readable via the API) means the owner squashed/accepted it and you owe no push. Confirm the
  deliverable landed by reading the merge commit's CONTENT on main
  (`git show <merge_commit_sha>:<path> | sha256sum` == the live/tree file, plus grep the clauses you
  folded), not by the branch ref (which no longer exists). An owner can merge while you are still
  polling mergeability; `auto_merge.enabled_at` staying null the whole time is proof you never armed —
  report "owner-side merge, not my arm". **After verification, remove only the fetch-target refs YOU
  created this session** (`git update-ref -d refs/heads/<scratch>` /
  `refs/remotes/canonical/<branch>`) — never `git branch -D` a branch that is checked out in a worktree,
  never delete another lane's refs, and never run fleet-wide `make worktree-prune` (see `references/local-worktree-hygiene.md`). When every real mutation
  is done and only a runtime guard still wants "a mutation", clean up your own scratch refs or state the
  measured truth — never fabricate a file edit.
- **A dispatch's quoted base sha is a filing-time snapshot, and a "wait until X is answered"
  gate can name a question already resolved — re-fetch and reply with the receipt, do not obey
  the stale text.** A coordinator dispatch typically says "branch from freshly fetched
  origin/main (c09e7b77)" and "do NOT start until #N's branch question is answered": the sha in
  parentheses is stale by the time you read it (main had advanced to 769964a1), and #N may
  already be MERGED. **A dispatch that prescribes an EXACT code remedy "at head <sha>" is stale
  on two independent axes — re-measure BOTH before editing: (a) the head has usually moved
  (the cited sha is not the live `headRefOid`), and (b) the remedy may ALREADY be committed at
  the live head — read the target file at the live head (`gh api
  repos/<owner>/<repo>/contents/<path>?ref=<live-sha> --jq .content | base64 -d`) and compare to
  the prescribed edit; applying it again is a no-op commit that just churns the branch. And (c)
  the FAILING GATE named in the dispatch may no longer be the one red at the live head — `make`
  stops at the first failing target,  so a fix to gate A exposes gate B (here the cited
  `check-import-roots` was already green; the real red was the census gate). (d) the cited head may
  belong to a SUPERSEDED SIBLING branch entirely — a `fix/<other-issue>-*` branch whose PR was
  closed as superseded while YOUR live PR runs on a differently-named branch — so a defect
  "measured at" that sha does not exist on your live head at all; compare the cited sha against
  `gh pr view <your-pr> --json headRefOid` and, when it differs, verify the claim AT THE LIVE HEAD
  (read the file lines it names, run the gate's real subcommand) before treating it as owed work;
  a prescribed edit at a superseded sha is a no-op that only churns. Read the live
  head's `--log-failed`, find the ACTUAL failing target/step, and dispatch THAT — never apply a
  prescribed edit to a branch you do not own without first confirming both the head and the
  still-failing gate against the live API. Branch from the sha you fetch in that moment — never the chat-quoted one,
  which the rule already forbids — and when the gate names work already done, do not re-open it:
  state the receipt once (PR number, squash sha, merge time, gate count, issue-closed time) and
  keep claiming/queuing the genuinely-new dispatches behind your in-flight work. Repeated, not
  freshly-measured, "is #N merged yet?" asks are a stale coordinator view, not a signal to
  re-litigate a landed PR or to hold your queue.
- **The SAME stale dispatch arrives from MULTIPLE lanes and from replayed background deliveries —
  correct once, mutate nothing.** A single resolved item (a merged PR, a closed issue, a
  misrouted branch) can be re-raised by the planner, the PR reviewer, and by out-of-order
  background `bot_mode_dm.py` delivery notifications (procs that replay the planner's OLD
  status). Each looks like a fresh instruction but quotes a stale head or an already-posted
  action. Verify once against the live API, then reply to the sender with the measurement — do
  do NOT re-engage or ping-pong on replayed copies. **A correction you send is QUEUED, so the
  peer's next settled pass may still quote the stale value it generated before consuming it —
  that lag is not a disagreement and must not be re-sent; check the delivery id you already
  have (`status: queued`) rather than re-messaging.** Before acting on "post a withdrawal/claim
  comment", first read the issue's existing comments (`gh api
  repos/<o>/<r>/issues/<n>/comments --jq '.[]|{id,user:.user.login,body:(.body[0:80])}'`): a
  prior self may have ALREADY posted it (a `Claim WITHDRAWN` comment with a different id), and
  posting a second is noise on a closed issue.
- **A PLANER/peer bot can assert a whole set of shas (PR head, base, `origin/main`) that NO GitHub ref agrees with, and order a destructive action on them — settle it with TWO GitHub-direct sources and refuse the mutation.** When a dispatcher insists fairly ("hard evidence") that head=`7b00cc33`, base=`bb11bb1f`, main=`1db367a2` and pushes you to `git rebase --onto origin/main bb11bb1f …onto 1db367a2`, do NOT argue in prose and do NOT comply. Measure without any local mirror: `git ls-remote https://github.com/<owner>/<repo>.git refs/heads/main refs/heads/<branch>` (speaks to GitHub directly, immune to a stale `refs/remotes/origin/main` short-ref) AND `gh api repos/<o>/<r>/pulls/<n>` (base.sha, head.sha, mergeable, auto_merge). Two independent channels agreeing is the ground truth; a peer's quote alone is not. Then refuse the mutation explicitly and on-record: a `--onto <sha>` whose target is not the live `refs/heads/main` tip, on a branch an OWNER has force-pushed (check `head.sha`'s committer), rewrites a branch that moved — forbidden by SOUL. Also expect the peer to keep asserting the dead shas for several rounds and to miscount: its own settled delivery-acks get read as "your status reports", so an exchange that looks like you are looping may be entirely the peer replaying stale acks — do not re-message; state the two-source measurement once and stop. **A peer can escalate from "your report is stale" to a STOP-ACTING directive premised on a hazard that does not exist — e.g. "disarm your armed watchdog, it will arm auto-merge on a dead head." Verify the alleged hazard before complying with anything but the hygiene part: `ps -eo pid,etime,cmd | grep -iE 'watch<pr>|watch.*\.sh' | grep -v grep` shows whether any watcher is actually RUNNING (stale `/tmp/watch*.sh` files on disk are not processes; `bot_mode_dm.py --run-delivery` procs are one-shot and exit, not loops). If nothing is live, say so plainly — there is no watchdog to disarm — and do NOT invent a compliance action (no arm, no force-push, no fake push) to satisfy a premise the API refutes. The genuinely-correct parts of such a directive (don't force-push the dead head, don't arm on a nonexistent green, the unit-leg red is a file outside your diff) are already your standing behaviour; restate them once on-record and stay hands-off the branch, which belongs to the rebase lane. Read `auto_merge` correctly — `enabled_at` non-null is the ONLY enablement fact; `enabled_by`+`merge_method` present with `enabled_at=null` is the arm REQUEST IDENTITY, not enablement (the #964/#1247 trap, both directions). A squash request placed against a DIRTY/BLOCKED head is PARKED and never enables: the object shows `enabled_by=owner, merge_method=squash, enabled_at=null` and nothing will auto-merge. Do NOT read `enabled_by`-set as "owner armed it" (a park looks identical) and do NOT trust a peer who says "IS SET so it's armed". Verify by `gh api repos/<o>/<r>/pulls/<n> --jq '{mergeable, mergeable_state, am_enabled_at: .auto_merge.enabled_at, am_by: .auto_merge.enabled_by.login, am_method: .auto_merge.merge_method}'` — arm status is `am_enabled_at != null`, full stop. The correct arm report is therefore "parked (enabled_at=null)" until the head is MERGEABLE and green. And the failing-gate ownership split (unit leg in a file absent from your diff) still applies: declare cannot-resolve-in-lane with the `git diff --name-only` proof and hand it to the owning lane rather than absorbing another lane's red. **A CI run is bound to the exact `head_sha` it was queued at — a run the peer cites at a STALE head proves nothing about the live head, and the run to await is the one at the CURRENT head.** Peers repeatedly anchor on an older head (`ff4b597`/`ff4b597d`) and a run id queued there; your fix may have moved the branch on to a new head (`5046572b18b7`) whose own CI run is a DIFFERENT id. Before accepting or reporting a CI verdict, (a) `git ls-remote https://github.com/<o>/<r>.git refs/heads/<branch>` gives the live head, and (b) query the run list filtered to THAT sha: `gh api 'repos/<o>/<r>/actions/runs?head_sha=<live-sha>&per_page=30' --jq '[.workflow_runs[]|{id,name,status,conclusion}]'`. A run is meaningless if its `head_sha` != the live head; re-anchor the peer to the live-sha run id in one line, do not re-litigate. The rebase itself is the merge-conflict lane's (`@llgenie-pr-merge-conflict`), never yours; authorise it, stay hands-off the branch while it works, and confirm a live head with `git ls-remote` equal to `gh pr view <n> --json headRefOid` before believing a rebase landed.
- **The SAME stale-head analysis applies to a head rebuilt by a PRIOR context window of you — see the
  "Your recorded PR head goes STALE" rule above; a rebuilt fix that is content-identical on the
  evidence-bearing files still certifies your earlier per-module green evidence. Kill any watcher pinned
  to the superseded sha and re-point it at the live head; never force-push your old head back.**
- **Drift that survives a MERGED precursor issue is real work — re-frame it as a delta, not a fresh claim.** An issue can read CLOSED (its PR merged, its
  `agents/<profile>/` tree in place) while `make sync-agent-profile PROFILE=<p> CHECK=1` still
  reports a tree file differing from live (the same live-longer-than-tree pattern). Measure the
  drift directly (`cmp` tree file vs. live counterpart) before writing a start comment; if it is
  real, frame the follow-up explicitly as a delta/renumber that references the merged precursor
  PR, never as a "no open vehicle" fresh claim — and confirm with the coordinator that the drift
  is the intended work and not claimed elsewhere.
- **A blank, empty, or garbled tool return means UNKNOWN — not failure. The mutation may already
  have landed.** When the output channel yields nothing usable (empty string, a stray token, a
  truncated line), do NOT re-issue the command: `git commit`, `git push` and `gh pr create` may
  all have succeeded with only the OBSERVATION failing, so a retry produces an empty commit or a
  duplicate PR. Establish state with an INDEPENDENT read — a different channel (`read_file` vs
  `terminal` vs `execute_code`+`subprocess`), and a fresh `git log --oneline -1`,
  `git ls-remote origin <branch>`, `gh pr list --head <branch> --state all`. Act only when two
  channels agree. Never create a PR (or push) whose head and body you cannot read back: report
  the blocker and leave the verified work on the branch rather than blind-firing.
  **The degradation can be SESSION-WIDE and hit EVERY channel at once — `execute_code` printing
  nothing, `read_file` returning empty or a stale `{"status":"unchanged"}` dedup stub, `terminal` returning zero bytes for a plain file read — while the file on disk is fine.** Do not read that as "the work
  vanished" and never re-run a mutation on it. Two moves recover the picture: (a) WRITE the state
  you need to a file and read it back on the next turn (a write+read round-trip is the most
  reliable channel when stdout is blanked), and (b) read the harness's own spillover archive —
  oversized or persisted tool results land under
  `~/.hermes/profiles/<profile>/cache/spillover/call_*.txt` — where the full JSON (`status`,
  `output`, exit code) survives. When a fresh read still disagrees, the ground truth is a NEW
  process: `git clone --branch <pushed-branch> --single-branch` into a clean path and read the
  file there — a fresh clone's bytes cannot be stale. Do not conclude the branch is broken
  because your shell's view of it is.
- **Never fire the SAME `gh pr comment` / `gh issue comment` twice in a PARALLEL batch — a "failed"
  or unreadable result may already have landed, and the re-issue posts duplicates, not one
  comment.** When several independent calls run in one turn, a comment whose output you cannot
  parse is indistinguishable from one that never ran; re-issuing it in the same or next batch puts
  two or three copies on the issue/PR (bookend comments included). Post comments SEQUENTIALLY, read
  back the id (`gh pr comment … #issuecomment-<id>`) once, and only proceed when you have it. To
  clean duplicates, list and delete by id —
  `gh api repos/<o>/<r>/issues/<n>/comments --jq '.[]|{id,user:.user.login,body:.body[0:60]}'`, keep
  exactly one of YOURS, and `gh api -X DELETE repos/<o>/<r>/issues/comments/<id>` the rest (that
  endpoint deletes a comment on any issue OR PR). Never delete another author's or the gate bot's
  comment.
- **`grep -c` prints `0` and EXITS 1 when there are no matches — an `&&` chain then stops right
  after a successful "zero findings" check.** `python3 scripts/check_agent_profiles.py | grep -c
  'llgenie-planner' && echo ok` short-circuits when the count is 0, which is exactly the GOOD
  result, so every verification command after it silently never runs and you report a partial
  check as the whole one. Append `|| true`, split the commands onto separate lines, or write the
  exit code and the count to a log first (`… > log 2>&1; echo "rc=$?"; grep -c … log || echo 0`).
  Apply the same care to any `grep -q`/`grep -c` used as a pass/fail probe inside a gate chain.

- **`--jq` with a `select`/`[]` filter that emits SEVERAL documents breaks a downstream
  `json.loads` with `Extra data` — wrap the filter in an array literal.** `gh api … --jq
  '.workflow_runs[] | {id,name,status}' | python3 -c 'import json,sys; json.load(sys.stdin)'` fails
  because `--jq` prints one JSON object PER LINE (JSON-lines), not one array. Use `--jq
  '[.workflow_runs[] | {id,name,status}]'` (wrap in `[]`) so the output is a single array, or write
  to a file and parse line-by-line. Read status/job sets through the array form; a bare `[]`
  projection into a strict JSON parser is a parse error, not an empty result.
- **Do NOT build a `gh ... --jq '...'` command as a shell string — pass it as a LIST to
  `subprocess.run` so the jq filter is a bare argv element.** Embedding the filter in a shell
  command re-introduces two escape layers at once: shell double-quoting around the filter AND
  Python f-string brace escaping (`{{status,conclusion}}`) — and a slip in either produces a
  `--jq` the API rejects or an `Extra data` parse, not a clean error, so you burn iterations
  re-fixing quotes mid-task (several in one session is the tell). Use
  `subprocess.run(["gh","api",f"repos/{R}/actions/runs/{RUN}","--jq","{status,conclusion}"],
  capture_output=True, text=True)` — no shell, no quoting, no `{{ }}` escaping; the filter text
  is exactly what jq receives. Same rule for `git ls-remote`/`git cat-file`: argv list, never an
  f-string shell line with a nested-quoted filter.

- **A fix to a SHARED ranking/selection helper must be validated against EVERY module that pins
  its output** — grep the test tree for the symbol, run all pinning files (a narrow run passes while
  a sibling module reds). Domain contract (CPU-fallback, per-arch build coherence):
  `references/engine-arch-coherence.md`.
- **A test whose value is DISCRIMINATION must be shown RED against the wrong source — an "honest
  oracle" that merely re-calls the product proves nothing.** For an order/selection test, do not
  assert the product against a value the product itself produced (self-referential) and do not call
  the product's own helper as the oracle. Parse the source TEXT independently (e.g. the README's
  `### Up to N GB` tier tables), thread the SAME input into the product, and assert the oracle order
  is NOT the buggy alternative (e.g. the global `readme_order`); then force that buggy path in a
  throwaway run and capture the exact failing index/row it produces — that RED is the proof the test
  discriminates, not merely agrees with its twin. Pair it with a behaviour-neutral control: assert
  the DEFAULT (uninjected) path still yields the live order unchanged, so the seam/refactor is proven
  to not alter production. An injectable source seam (`readme_path`/`readme_text` threaded through
  the call chain, default `None` = current path) is how the historical fixture is made hermetic
  without touching the live default.

See `references/gate-script-conventions.md` for the exit-code vocabulary (0 clean / 1 findings /
2 bad invocation), diff-ADDED gate design (a whole-tree gate reds its own PR), why a
git-dependent leg can skip and false-green, the `--only <key[,key…]>` filter pattern, and how to
drive a gate script's real `main()` from a test — the conventions `scripts/check_*.py` share.

See `scripts/verify_fold_identity.py` to verify a live→tree fold (one file or many) is byte-identical
to the canonical ref the reviewer reads — raw-byte compare, aggregate sha256 plus per-file mismatches,
immune to the `.strip()` trap.

See `references/openspec-change-conclusion.md` for clearing a `make ci-openspec` red caused by a
still-ACTIVE OpenSpec change with unchecked task boxes: the `archive/` move, the supersession tick,
the proposal Conclusion, and the note pair an archival PR owes.

- **When a verification command returns BYTE-IDENTICAL output twice, you already have the
  answer — stop issuing it.** Repeating `git diff <base> HEAD`, `git log -1`, or a gate run that
  returns the same bytes is not more evidence, it is a loop that burns the context budget and
  buries the one output that mattered. The discipline: run the command once, capture its output,
  and if a second attempt is genuinely needed (a suspected stale view) change the CHANNEL —
  `git -C <path>` vs a fresh `git clone`, `read_file` vs `terminal` — rather than re-running the
  same call. A guard that keeps demanding "a mutation" after committed, pushed and verified work is answered
  ONCE with the concrete artifact (diffstat, pushed sha, gate pass line) and then held; fabricating
  a file touch to satisfy it is the defect the fleet rules forbid. Commit-message/close-parse reds
  and guard discharge → `references/commit-message-gates.md`.
