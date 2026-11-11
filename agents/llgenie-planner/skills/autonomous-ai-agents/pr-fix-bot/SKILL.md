---
name: pr-fix-bot
description: "Use when a bot or an agent must repair a failing PR."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [ci, github-actions, fix-bot, hermes, llm, pull-requests, auto-repair]
    related_skills: [hermes-headless-ci, github]
---

# Auto-fix bot for a failing PR

## When to Use

Building, wiring, or debugging a bot that auto-repairs a failing PR's CI with
Hermes + an LLM, then re-checks. Also the reference when a human asks you to
repair a red PR by hand: the diagnosis order, the "is it the base's fault"
check and the push shape are the same. Not for Hermes-in-CI plumbing in general
(that is `hermes-headless-ci`).

Wiring a bot that, when a PR's CI goes red, diagnoses the failure with an LLM
(Hermes CLI headless) and repairs the branch, then re-checks. Reference
implementation: `andyholst/trending-local-llms` (`fix-bot.yml` +
`scripts/fix_loop.sh` + `make _fix`). For the Hermes-in-CI plumbing (provider
alias, PATH gotcha, caching) read `hermes-headless-ci` first — this skill is the
fix-bot shape on top of it.

## Trigger: dispatch on failure, NOT workflow_run

- Put the trigger in the PR-CI workflow's own `dispatch-fixbot` job:
  `failure() && github.event_name == 'pull_request' &&
   github.event.pull_request.head.repo.full_name == github.repository`
  (same-repo PRs only). It calls `gh workflow run fix-bot.yml -f pr_number -f branch`
  with an **owner-scoped PAT** (`FIXBOT_DISPATCH_TOKEN`), not `GITHUB_TOKEN`.
- **Do NOT use a `workflow_run` trigger.** A bot-authored PR (pushed with
  `GITHUB_TOKEN`) does not re-trigger `pull_request` runs, so `workflow_run`
  never fires for the bot's own commits and can recurse/race. Explicit dispatch
  from the failing workflow avoids it.
- **Cap the bot's commits per PR** (query the PR's commits for the `fix-bot:`
  prefix, e.g. `gh api .../pulls/N/commits --jq '[.[]|select(.commit.message|
  startswith("fix-bot:"))]|length'`). At the cap, leave the PR red for a human —
  a fix that doesn't stick must not loop.
- Add a concurrency group keyed on the PR (`fix-bot-<pr>`) so two dispatches
  queue instead of racing.

## The loop: check -> fix -> re-check, capped

`scripts/fix_loop.sh` shape (exit 0 = green/safe to push, 1 = still red):

1. Run the SAME deterministic gates CI runs, **fastest first**, stop at the
   first red. Write ONLY the failing gate's output to a report file
   (`qa-report.txt`). Do NOT mix in passing suites — their negative-path
   fixtures print `FAIL:` lines that bury the one real failure and feed noise to
   the LLM. (A validator asserting it *catches* bad data prints `FAIL:` too;
   those are passes.)
2. On red, run the one-shot Hermes fix: `make fix` — the prompt tells the model
   to READ the report first and fix exactly those failures.
3. Re-check. Green -> exit 0. After `FIX_ROUNDS` (default 3) still red -> exit 1,
   leave for review.
4. The workflow commits+pushes ONLY on exit 0, as a Conventional Commit
   (`fix-bot: ...`). It never merges, never pushes to `main`, never force-pushes.

Keep the loop offline-testable: point `MAKE` at a recorder script so
`tests/test_fix_loop.py` asserts control flow (green stops; red->fix->re-check;
cap respected) without network or a real LLM.

## The loop's verdict must reach the RUN, and the leg must be able to act

Three shapes make a repair bot look healthy while it repairs nothing. All three read as
`success` in the run list:

- **A captured exit code with no consumer is a green run over a red PR.** The workflow step
  runs `scripts/fix_loop.sh`, captures `rc` into an output (`green=false`), and exits 0 so the
  PR comment can still post — and if no later step acts on that output, the job is GREEN while
  the loop printed `still RED after N round(s)` and pushed nothing. Keep the capture, then add a
  terminal step `if: steps.loop.outputs.green == 'false'` that exits 1 and names the PR. Test the
  three things separately: the step exists, its condition is exactly that output, and its body
  really exits non-zero — a comment-only "make it red" is not a guard.
- **A leg with no instruction for the failure it is handed asks a question, and asking detaches.**
  `--yolo --accept-hooks` answers shell and hook prompts, not the model's own `clarify`: a
  detached round prints `Input required; detached without cancelling`, exits **3**, and the loop
  burns every round on it (three identical `Input required` lines, then `still RED`). The fix
  prompt/skill must name the failures the repo actually produces — for an OpenSpec-gated repo
  that is an unticked `tasks.md` checkbox (tick only what is genuinely done; otherwise say so in
  the PR body), a stale generated index (`make <index>`), a spec that does not validate (fix the
  spec, not the check), and the archive gate for a change whose PR merged. State the general rule
  too: the failing check's own output IS the instruction, and a check that names nothing
  actionable is reported in the PR body rather than turned into a question.
- **The dispatch condition enumerates branch families, so a NEW producer has no repairer.**
  `startsWith(github.head_ref, 'ci/trending-refresh-')` covers the data bot and silently excludes
  every PR the implementation bot opens (`ci/data-gap-…`), which then sits red until a human looks.
  When a repo gains a second bot that opens PRs, add its prefix to the dispatch condition in the
  same change, and assert both prefixes in a test so the next producer cannot be forgotten. Keep
  the same-repo-head and `failure()` requirements, and keep one commit cap across both families.

When a repair round detaches, read the agent's OWN captured transcript (the log file the recipe
writes into the workspace, or the run artifact) before changing any prompt text — the tail printed
to the console says only that it detached, and the question it asked is what names the missing
instruction.

## Reasoning-budget trap (deepseek-v4-flash)

That SKU burns its whole output cap on hidden reasoning and writes nothing:
`No visible answer was produced ... reasoning consumed the entire budget`.
`--reasoning low` STILL thinks. Detection + retry: in the SAME round, grep the
fix log for that signature and re-run `make fix HERMES_FIX_REASONING=none`
(0 reasoning tokens) instead of wasting the round. Use `low` for a
diagnose-and-fix agent, `none` for mechanical gather steps.

## A shared gate that is red on the BASE is not this PR's diff

The gate every PR runs (`ci-unit`: lint, unit, and the registry/catalog/docs/wiring checks) fails on a
committed artifact far more often than on the branch's own change. Diagnose in this order, before
touching anything:

- **Reproduce the failing target verbatim on `origin/<base>`** (`make check-<artifact>`, `make test-unit`).
  If it reds there with the branch's files absent, the diff is innocent and the repair belongs to the
  base. Say that in the PR body/comment: a reviewer reading "unit failed" assumes the branch broke it.
- **A generated artifact has exactly ONE repair: the target the failure names** (`run make
  sync-<artifact>` in the check's own message). Regenerate and commit it. Never hand-edit the artifact
  (the check regenerates and diffs, so a hand edit stays red) and never loosen the comparison to
  accommodate it — a gate whose contract is "removals fail, additions and reorders are notes" is saying
  the sync is the sanctioned move.
- **Search the open issues for the same finding before filing yours.** A sibling bot files from the same
  red gate with the same measurements, and a duplicate splits the work. Link both ways, close the newer
  as duplicate, keep the one that carries the measured numbers.
- **Expect the base to move while you wait.** A 20-50 minute `unit` run is long enough for another PR to
  land the same regeneration. When it does, your artifact commit becomes a no-op: rebase and DROP it
  (`git rebase --skip` on that commit) instead of resolving its conflicts, so the PR returns to its one
  change and gets a fresh CI run on the new head. Re-read `mergeable` AND `mergeStateStatus` after every
  push — GitHub caches both, so a PR that was `MERGEABLE` can report `DIRTY` minutes later when the base
  advanced.
- **Release the bot claims when you finish.** A `bot-claim` comment carries a TTL; a repair that landed
  under one must post the new head sha and ask sweeps not to re-claim or force-push over it.
- **A worktree whose earlier rebase was killed keeps a `rebase-merge` directory**, and every later
  `git rebase` refuses with "there is already a rebase-merge directory". `git rebase --abort`, then
  `rm -rf "$(git rev-parse --git-dir)/rebase-merge"` — that is the WORKTREE's git dir, not the main
  clone's.

## The loop repairs in isolation — merge the base first, bound every round

A fix-bot reads ONLY the PR branch, so a failure the base already fixed costs full
LLM rounds to re-derive by hand. Four rules make the loop robust:

- **Merge the base before any LLM round.** Fetch `origin/$FIX_BASE` (unshallow
  first — `actions/checkout` clones shallow, so a bare fetch of one ref dies with
  `pathspec … did not match`) and merge it when the branch is behind, BEFORE the
  first check/fix round. A failure the base already fixed then costs ZERO rounds.
  A missing checkout or an unfetchable base is best-effort — skip it, loudly. A
  **CONFLICT is not**: leaving a conflicted merge `--abort`ed hands the one case that
  needs a model to a human. Keep the merge, put the conflicted paths and their hunks
  into the SAME report the fix round reads (plus the rule that generated artifacts are
  REGENERATED, never hand-merged), make an unmerged index RED by definition so a lenient
  check cannot call the branch green, complete the merge when the index comes back clean,
  and `--abort` only after the last round so a half-merged branch is never pushed.
- **Bound every Hermes round with a wall-clock `timeout`, not just a job
  `timeout-minutes`.** A hung round eats the whole job budget and the loop's own
  failure path (write the report, comment the PR, close the window) never runs —
  the PR gets nothing. Bound the Hermes call INSIDE the container (so the container
  is reaped with the round) AND as a host backstop around the round. Record a
  timed-out round in the report (which is what the PR comment shows), and keep loop
  notes in a channel that survives the next round's report truncation — otherwise a
  recorded timeout  is wiped by the next `run_checks`.
- **A loop scratch file must live OUTSIDE the repo tree (a `mktemp` path), or be gitignored by
  PATTERN — never by exact name.** The commit step runs `git add -A`, so any unignored file the
  loop creates in the repo root is swept into the PR. `.gitignore` entries like `qa-report.txt`
  (exact name) miss the sibling `qa-report.txt.notes` the loop truncates on every run, and the
  empty file lands in the bot's own commit. The push-guard test that plants `qa-report.txt` +
  `comment.md` in a temp clone must ALSO plant the sibling scratch file and assert it is never in
  the pushed commit — a fixture that only plants the exact names cannot catch a sibling.
- **The cause fix does NOT clean an already-committed scratch file — that is its own
  change.** The write-path fix (notes moved out of the tree) plus a `.gitignore`
  pattern only stop NEW files being staged; an ignore rule never untracks a file that
  is already tracked, so a scratch artifact that merged into `master` through another
  PR survives the fix. Check the LIVE tree (`git ls-tree --name-only origin/master`),
  and when the class is already tracked: `git rm --cached <file>` (working copy
  deleted — it is not repo content) as a SEPARATE PR, plus a tracked-tree guard
  (`git ls-files` finds nothing in the scratch class) that you prove RED with the
  file restored (`[['qa-report.txt.notes']]`) and GREEN after the removal. Without
  that guard, a future merge of a stray scratch file is silent rather than red.
- **A round that changes nothing stops the loop.** Byte-identical failure output +
  an untouched working tree = a fix that did not stick; report it and exit rather
  than spending the remaining rounds on the same failure. Ask the check only inside
  a git checkout so a control-flow fixture can never trip it.
- **Re-running a PR's CI re-validates against the stale `refs/pull/N/merge`.** After
  you fix the base, a re-run of the PR's own qa-validate still validates the OLD
  merge ref, so the already-fixed error reappears and looks like your fix did not
  land. Update the PR branch onto the fixed base (merge, not force-push) to force a
  clean revalidation against the corrected base.

## Never let the bot fake a green

Policy the fix prompt MUST encode (repo-dependent — read the target repo's
AGENTS.md):
- Fix the ROOT CAUSE; the default is a code fix, not a test edit.
- **Never make a test pass by mocking the system under test / monkeypatching
  product code / returning a canned answer** if the test claims to lock
  business logic. **Never** `pytest.skip`, delete/comment assertions, or loosen
  a bound just to go green.
- A test may be UPDATED only when it is a real, non-mocked test and its
  expectation is genuinely obsolete; add a regression test that FAILS on the
  pre-fix code.
- If the bot cannot satisfy the policy, STOP and leave the PR red with a
  comment stating the root cause and why it is leaving it — never invent a pass.
- Post per-failure: root cause, code-vs-test, and (if a test) the evidence the
  test was wrong rather than the code.

## Every command the workflow runs is a make target

A bot workflow must call `make <target>` for anything that touches repo logic —
never `python3 scripts/...` or `scripts/*.sh` directly. The make target is what
makes the command reusable locally AND by the pipeline, and the wiring guard
(`make check-wiring`) enforces every script is wired to a target CI runs. Only
`gh`/`git` orchestration (guard, PR resolution, commit/push, comment) stays
inline. Give each script a dedicated target in `.PHONY`; when the workflow
resolves a value (image ref, report path), accept it as a make variable override
(`AGENT_IMAGE=...`, `LOG=...`, `REPORT=...`) so the workflow and a local run
share one command. Codify the rule in the repo's AGENTS.md. The git commit/push
step is orchestration and is intentionally not unit-tested.

## A documented exit code does not survive `make`

`make` exits **2** for ANY failing recipe and prints the child's own code only inside its message
(`make: *** [Makefile:403: target] Error 3`). A caller that branches on a target's documented
non-zero code — "exit 3 means the rebase conflicted, keep the work and push anyway" — therefore has
a DEAD branch: `rc=$?` after `make <target>` is 2, the safe case never matches, and the step fails
on the one condition that was declared safe, discarding a finished implementation one step before
the push. Put the contract in the TARGET, not the caller:

```make
target:
	@rc=0; cmd || rc=$$?; if [ $$rc -eq 3 ]; then echo "target_conflict"; exit 0; fi; exit $$rc
```

Write it `rc=0; cmd || rc=$?` (never `cmd; rc=$?`) so it behaves the same under make's own `sh -c`
and under a `bash -e` step, and report the safe case as `exit 0` plus a machine-readable line the
caller can log. Prove it by executing the REAL recipe text (extract it from the Makefile, or call
the target) against a stub that exits the safe code, an ordinary failure and 0 — a test on the
Python function cannot see make's rewrite.

## A test that runs `make` inside `make test` sees make's directory banners

A suite started by `make test` exports `MAKEFLAGS`, so the test's own `make <target>` prints
`make[1]: Entering directory '/workspace'` / `Leaving …` on the child's stdout. An assertion that
the target prints EXACTLY one line then fails in CI while passing locally, and the failure looks
like the recipe echoed its command when it did not. Call the target with `--no-print-directory`,
and run the test once under the flags CI has (`MAKEFLAGS=w`) before pushing — otherwise the test
measures make's banner instead of the recipe's value.

## Never regenerate-and-commit in the same shell run as a merge

`git merge origin/main && make <index> && git add -A && git commit` commits the tree even when the
merge CONFLICTED: unresolved `<<<<<<<` markers go into the commit, and the branch's own gates then
fail on them (a conflict-marker guard catches it — that is the guard working, not a pass). Run the
merge as its own step, check `git diff --name-only --diff-filter=U` (or
`git status --porcelain | grep '^UU'`), resolve, and only then regenerate and commit. Generated
files (`OPENSPEC.md`, an architecture inventory block) are resolved by REGENERATING, never by
hand-merging hunks — and after EVERY base merge, regenerate and push again, because a merge that
moves the tree stales the generated index and the next validate fails on staleness alone.

## A bot's own PR needs bookkeeping before it can be repaired

Three shapes recur in a bot-authored PR, and none is a code defect:

- **Every OpenSpec task box ships unticked**, so the tasks gate refuses a complete implementation and
the fix loop burns rounds on a change whose code is finished. Verify each box against the tree (grep
the symbol, the workflow line, the test), tick the verified ones, and give the ones the run could not
do — a protected rulebook row — an explicit `— OWED, not applied` note with the intended text in
`findings.md`. A task box naming a doc row (`AGENTS.md` §8, `ARCHITECTURE.md`) is satisfied only by an
actual edit to that file: a PR whose diffstat lacks it will red the gate no matter how green its
code is, so read the change's own `tasks.md` as the checklist before touching anything else. The
full repair order is: tick the verified boxes, land the missing doc row, `make <index>` (the
`OPENSPEC.md` / inventory block is GENERATED — never hand-edited), then the local gates
(`openspec-check`, `lint`, `architecture-check`) before the push. Prove the RED half of a "verified
RED against the base" box by running the new test module inside a `git worktree add --detach
origin/<base>` checkout — the numbers in the commit message are then measured, not claimed.
- **Repair such a PR yourself when the bot's rounds detach, and follow the change's `tasks.md` as the checklist.** A repair bot that only prints `Input required; detached without cancelling` for every round (exit 3) leaves the PR exactly as it was — three identical calls and the run reports `still RED`. That is the signal to take the branch over by hand (`make worktree-resume BRANCH=…`, rules 6n), not to re-dispatch it. An implementation PR's own `tasks.md` names every step the run owed and skipped: an `AGENTS.md` §8 guard row, the `findings.md` analysis, and the generated index. Tick a box only after verifying the step against the tree, and **regenerate the index AFTER ticking** — the `OPENSPEC.md` row carries the task progress (`0/11` → `11/11`), so an index generated before the ticks is stale again and `openspec-index-check` reds on the count while every row looks right.
- **`findings.md` needs `- **Evidence:**` as a BULLET, not a bare bold label.** The parser keys on
`- **Field:**`; a paragraph starting `**Evidence:**` is silently dropped and `make findings-check`
reports every field missing for a finding that reads perfectly to a human. One bullet per field
(`Evidence`, `Why`, `Done when`), each on ONE line — a wrapped continuation line is not a field.
- **The same change is re-created under a NEW directory name** on a later attempt, so one branch can
carry two or three change directories for one issue. Keep the one whose wording matches the shipped
code and delete the rest; the unticked duplicate is what reds the gate.
- **A rewrite may DELETE the tests that lock the behaviour it "re-implements"**. Diff against the
base before landing a bot PR: a "fix" that removes a guard is a regression, and the honest move is to
close the PR as obsolete (citing the landed symbol and its test) rather than help it merge.

## Cost/faithfulness guards

- One real smoke call through the exact alias before the 20-min loop
  (`make hermes-smoke`), with every key the container gets — catches a dead key
  or a silently re-routed provider in seconds.
- Checkout + push use the owner PAT; keys are repo secrets, never committed.
- The fixer works on the PR's EXISTING feature branch (no new branch, no
  history rewrite, no `--admin`).

## The sweep must be able to SELECT, and able to DISPATCH

A scheduled repair bot has two failure modes that both read as `success` in the
run list, and neither is a model problem:

- **Selection can be structurally empty.** When a sweep filters candidates by the
  head repo being this repository, a workflow that takes all its PRs from a FORK
  selects nothing on every run: the log is a wall of `skip #N (…): a fork
  (<owner>)` and the job concludes green with no work done. Print a reason for
  every pass-over and treat "every candidate skipped for the SAME structural
  reason" as a defect of the filter, not as an empty queue — one fork-aware rule
  (resolve the head repo and push there, or accept the allowlisted fork owner) is
  what makes the sweep able to pick.
- **The dispatch itself is a separate permission.** `gh workflow run` /
  `POST /actions/workflows/<id>/dispatches` needs **`Actions: write`**: an
  owner-scoped PAT that can push and comment on PRs can still be refused with
  `HTTP 403: Resource not accessible by personal access token`. That is the
  token, not the sweep logic. Prefer `github.token` where the job already
  declares `actions: write`, otherwise widen the PAT deliberately and record the
  required scope in the workflow comment.
- **Verify a working sweep end to end once**: a run in which one PR is selected
  AND the dispatched repair run appears under the workflow's Actions tab. A
  `success` conclusion with no dispatched run and no PR change is a no-op, and a
  bot that never dispatches can stay "green" indefinitely.
- Diagnose a red sweep by its refusal, not by re-reading the code:
  `gh run view <id> --log-failed | grep -E "Resource not accessible|403|\[sweep\]"`.

## When several bots write to the same PR

Collision safety (`--force-with-lease` vs fast-forward), the claim protocol that stops two bots
starting one item, rebase tree-verification, and the base-moved-while-working rule live in
`references/multi-bot-coordination.md` — read it before adding or changing a second bot that writes
to PR branches or picks from a shared backlog.

### The engine gate must be real and armed

A bot that runs Hermes in a container must gate on the ENGINE actually being configured inside the
image, not on plugin files existing:

- **Verify the engine setting inside the image, not the host**: `context.engine` plus the plugin's
  mode (e.g. `context_engine_mode apply`) must be set and asserted at BUILD time, so the image
  itself carries the engine. The host's `~/.hermes/config.yaml` is the reference shape to compare
  against.
- **Arm the gate so a job does not start without it** (`NERVE_REQUIRE=1`): a preflight that only
  warns lets a run proceed with the engine silently off. Give EVERY bot workflow the gate, not just
  the first one.

## A conflicted PR is SILENT, not merely red

Two things about a `CONFLICTING` PR trick a repair loop into thinking it is fine:

- **A conflicted PR runs NO workflow runs at all.** GitHub cannot build `refs/pull/N/merge`
  for a conflicting PR, so `validate`, `live-smoke`, `pr-closure`, `auto-merge` are ABSENT,
  not failed, and `gh pr checks` answers `no checks reported`. An empty check list on a
  conflicted PR is therefore a SILENT ALARM, not a quiet queue — and nothing in the repo's
  failure path fires for it (the queue alarm covers a stuck job, not a PR that runs nothing).
  When triaging "PR is red", check conflict first: `gh pr view <N> --json mergeable`. A
  scheduled sweep that lists open PRs must flag the empty-run state, or green-over-red goes
  unnoticed. (`gh pr checks` returns PENDING/QUEUED for the four absent jobs — read
  `mergeable`, not the check states, to see it.)
- **Push a repair to the PR's ACTUAL head branch, never the local worktree branch name.** The
  closure guard can rename the branch (a `-<issue>` suffix that a first PR made the guard
  refuse), so the worktree branch and the PR head diverge. `git push origin HEAD` then writes
  to the worktree's branch — a DIFFERENT ref than the PR tracks — and the PR keeps showing
  GREEN checks over a commit nobody has updated, while every local check agrees with you
  (`git rev-list --count HEAD..origin/master` is 0, a dry-run merge is clean), so the bot
  reports success over a broken PR. Verify the PR's head is on your tip
  (`gh pr view <N> --json headRefName,headRefOid` vs `git rev-parse HEAD`) and push
  `HEAD:refs/heads/<PR head>` (read the head name, never assume it). State that push shape in
  the alarm/comment so a human-fix does the same.
- **A failure-triggered dispatch can never fire for it.** `dispatch-fixbot` hangs off a
  FAILED check, and a conflicting PR has no checks at all — so the only trigger that can
  reach it is a SCHEDULE sweep (`pr-health`-style). That sweep is the repair's entry point:
  for a silent PR on a bot-owned branch (`ci/…`) it DISPATCHES the repair bot (same
  `fix-bot:`-commit cap), and for any other branch it only comments — never dispatch a bot
  to push to a human's branch. One repo, two tokens: the dispatch needs the owner PAT
  (`Actions: write`), the comment needs the default token (`issues`/`pull-requests: write`).
- **A scheduled sweep needs a guard against re-dispatching itself.** Its own comment is the
  idempotence marker: check for it before commenting again, and count the bot's existing
  commits before dispatching, or a twice-an-hour cron starts a repair per tick.

## CI portability pitfalls (Linux + macOS)

- **Never forward an OPTIONAL make variable as `X="$(X)"`.** An unset variable then reaches
  the recipe as the EMPTY STRING, and a Python CLI doing `int(os.environ["X"])` or
  `type=int` on `""` dies with `invalid literal for int() with base 10: ''` — on every run,
  including the ones with nothing to pass. Forward it conditionally
  (`$(if $(X),X="$(X)",)`), and keep the default in the CLI (`--flag X type=int default=N`).
  An empty setting is a MISSING setting; the same rule already governs credentials, where an
  empty value must fail as unset rather than pass as present.

- **Never use GNU `sed -i` in a script or test** — BSD `sed` (macOS) rejects it (`invalid command
  code v`). Use Python for in-place edits, or `sed` without `-i` writing to a temp file. Grep the
  tree for `sed -i` before shipping.
- **A colon-space inside an unquoted YAML scalar breaks the workflow file** (e.g. a step `name:`
  containing `: `). GitHub rejects the file on push with ZERO jobs. Guard it: parse every workflow
  YAML in a test so a broken file fails CI instead of silently producing an empty run.
- **When you add a new `gh` subcommand call to a sweep, the test's fake `gh` stub must answer it**
  — an unhandled call makes the stub `sys.exit`, the sweep dies with empty output, and the failure
  looks like the logic is wrong. Add the handler and a log assertion in the same change.
- **A test fixture must match the real `gh` JSON shape.** `gh pr checks --json` rows are dicts
  (`{"name":…,"state":…}`), not strings; a fixture that passes strings makes the sweep raise
  `AttributeError: 'str' object has no attribute 'get'` while the production code is fine. And a test
  that runs a sweep subprocess must assert `returncode == 0` with `stderr` in the message — otherwise
  the sweep's crash is invisible and you debug the wrong thing.
- **Never push a branch whose tests are red.** A force-push re-triggers CI, so a red branch's CI
  fails loudly and wastes a full run. Diagnose the failure (read the actual assertion/exit, not a
  guess) before pushing; a branch is only shippable when its own suite is green.
