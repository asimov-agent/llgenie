---
name: scheduled-bot-fleet
description: Use when verifying or fixing scheduled GitHub bots.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [github-actions, bots, automation, cron, gh, pr-gates]
---

# Scheduled bot fleets (GitHub Actions)

## When to Use

A repo runs bots on cron/dispatch (rebase sweepers, PR fixers, issue implementers, doc refreshers,
registry syncers) and one of them is "not working", or the user asks to "verify each bot" / "why did
it do nothing" / "fix the bot". Also when adding a new one.

Work with the repo's own lifecycle: issue → per-fix git worktree on `feat/*` → OpenSpec change →
tests → gates → PR against the upstream base from the fork head. Never merge.

## Procedure

1. **One overview, then ONE bot at a time.** Sync `origin/main` first and run the read-only fleet audit
   (`scripts/fleet-audit.sh`) so the bot you then fix is chosen from evidence — conclusion, event and the
   decision line — not from whichever run looked newest. Report the whole table (acting / silently idle /
   red / blocked on a setting) and file a tracked issue for every red that is not the one you are fixing;
   then diagnose and fix exactly one. A pass that reports three bots half-diagnosed is worth less than one
   bot fixed and verified, and a red whose fix is a repository setting or an upstream defect is a filed
   issue, never a code change in this pass.
2. **Read the runs, then the failing STEP, then the bot's decision line.** The decision line
   (`[sweep] …`, `action=…`, `rebased=N failed=M`, `triage=…`) is the only evidence of whether it
   did the right thing. **A green scheduled run can be a no-op** — "success" means the script exited
   0, not that it acted.
3. **Classify before fixing:** the bot did the WRONG thing (bad decision), the bot did NOTHING (an
   input was rejected), or the ENVIRONMENT hid the failure (a masked gate, a lost API write). Each
   has its own fix shape; see `references/failure-classes.md`.
3b. **Triage the open issues against the TREE before implementing anything.** For each candidate read
   what the issue *claims* and check it against `origin/<base>`: **obsolete / already covered** →
   close it with the file:line or output that proves it, not with a summary; **real but mis-stated or
   too broad** → refine it, or file the narrower gap as its own issue; **real and actionable** →
   implement it. This user asks for that order explicitly, and it stops a backlog from being worked
   twice: an owed-row or already-fixed issue costs a whole agent slot to rediscover. Never close on
   the issue's own words — prose evidence is refused by the verdict step, and should be refused by
   the human closing it too.
4. **Reproduce the mechanism, not the symptom.** Build the failing input in a scratch git repo with
   a fake `gh` on `PATH`, prove the old code fails, then prove the new code passes on the SAME input.
   A test that stubs the function it is testing proves nothing.
4b. **Prove the pipeline end to end in a THROWAWAY worktree before you spend CI minutes.** Run its
   real mutating entry point (`make <bot>-<run> ENGINE=x`) in `git worktree add --detach ../wt/<name>
   origin/main`, read `git diff --stat` and the generated artifacts, then delete the worktree. That is
   how you learn whether the bot produces the parameters/artifacts it claims at all, and it costs
   nothing: the checkout is untouched, no PR is opened, no runner is queued. Dispatching first and
   reading CI later means every defect is diagnosed at 20 minutes per iteration — the first real
   dispatch of a bot whose legs were never run on real data is where an unusable input and a
   discarded report both surface, at once, on eight parallel jobs.
5. **Fix through the lifecycle:** file or reuse the issue (evidence + "done looks like"), cut a
   worktree off `origin/main`, write the OpenSpec change first, patch the script + workflow, add the
   regression test, run the focused test, then the full suite, then the structural gates. When the
   OpenSpec CLI runs in a container, the change directory is created **root-owned** — run
   `sudo chown -R "$(id -u):$(id -g)" openspec/changes/<name>` before the first `write_file`, or every
   write into it is refused with `Permission denied`.
6. **Ship and stop:** run `git remote -v` before pushing — in some repos `origin` IS the upstream and the
   fork is a second remote (`fork`), so a branch pushed to `origin` cannot be the fork head of a PR and
   `gh pr create --head <owner>:<branch>` fails with "No commits between …"; push to the fork, open the PR against the upstream base naming the issue,
   `closes #n` when it fully implements it, with `Issue/Fix/Benefit/Technical` parts. Report the URL
   and what it waits for. The agent never merges.
   **Back a change OUT if the attempt reaches further than the issue.** A tidy-up that turns out to
   touch two workflows and three fixture repos is a different, larger change than the one filed: revert
   the scratch branch (`git checkout -- . && git clean -fd`), delete it, and post what a correct version
   needs as a comment on the issue — the three call sites found, the fixtures each would need, the
   existing guard that must be re-specified. Landing a half-migrated version of a cosmetic fix while a
   push step is mid-migration loses implementations; an issue comment costs nothing and stops the next
   attempt rediscovering it.
   **But check whether the repo's OWN CI merges.** A green non-draft PR in a repo whose `auto-merge`
   job lands it will be squash-merged minutes after it turns green, whatever the agent intended — so
   say which repo behaviour applies BEFORE opening it, and never describe a PR as "waiting for review"
   when the pipeline will merge it unattended. A branch that encodes no issue number must not carry a
   closing keyword (`pr-closure` refuses it: the branch name is where the closure is proved), so a
   hand-cut branch needs the issue number in its name — the LAST number wins (`ci/<slug>-<n>`), and it
  must END the name: a stray suffix (`ci/<slug>-543b`) makes the closure guard refuse the PR that branch
  just opened, so rename the branch, reopen, and delete the old head instead of forcing the closure
  through.
   An audit that ends on "want me to implement this next, or just do the other thing?" is a wasted
   round-trip: the answer is "file the issue and implement it". When the audit names a defect whose
   fix belongs in this repo, file it AND implement it in the same pass, shipping the defect whose
   symptom is an OUTAGE before the structural follow-up; file the follow-up as its own linked issue
   and say it is next, rather than asking whether to start. Only a decision the user owns (a
   privileged publish, a settings change, a scope cut) is worth a question.

## Always-on rules

- **Never trust the conclusion alone** — read the decision output. A sweeper that rejects every input
  and a fresh one that has nothing to do both print `success`.
- **A no-op is "correctly idle" only if the reason it names is TEMPORARY.** `action=pending` (work already
  open) and `action=none` (nothing eligible) are healthy; `action=busy` is healthy for minutes, not days.
  Check the reason against the state, and check the same reason across several consecutive runs: a bot
  printing the same idle reason every run is starved, not idle. Measured shape: a refiner that stands down
  whenever ANY issue carries the queue label never refines again once the labelled backlog outlives it —
  the condition it yields to is permanent, so the fix is to yield only to a *live claim* (`bot_claims`
  occupancy, a run id in the marker) and skip past a label-only queue to the next candidate, naming that
  it did. A label is a queue, occupancy is a claim; conflating them turns the bot off without a red run.
- **A marker the bot writes is not evidence of work.** Parse a distinct done-marker with a kind
  (success vs gave-up); a claim or a failure must not count as the day's allowance.
- **State decides eligibility, the marker only caps the rate.** `main` moves, so work done an hour
  ago can be stale again; re-decide from the live state.
- **Bounded re-ask beats a silent pass.** An `UNKNOWN`/empty API answer means "ask again, a few
  times", then defer by name in the log.
- **Assert the base ONCE, where work STARTS — never again where it is COMMITTED.** A bot that
  spends 20–30 minutes implementing races every merge: a second `HEAD == fetched tip` assertion at
  commit time refuses a finished implementation and throws it away (no commit, no push, no PR).
  Commit-time shape: cut or attach the branch from the CURRENT HEAD, commit, `git rebase` onto the
  fetched tip, and on conflict ABORT the rebase (every commit intact), push anyway and let the PR's
  fix loop repair it. See `references/failure-classes.md` (base re-asserted after the work exists).
- **That commit-time seam must REFUSE a branch that is not this run's work, and a guard runs BEFORE the
  step that switches the tree.** Resuming an existing branch switches the tree to it: a branch left over
  from an abandoned attempt (tens-to-hundreds of commits the base does not have) predates files the base
  added, so the checkout DELETES them and every later step runs against a tree older than the Makefile
  that invoked it (measured: the guard added that same day failed with "cannot open file .../<guard>",
  because the adopt had just deleted its own script). Count what the branch carries that the base does
  not and REFUSE above a small threshold (a re-run carries a handful) BEFORE touching the tree, naming
  both counts, the remedy and an explicit override; put every pre-commit guard before the
  adopt/checkout step and assert the ORDER in the test, not just its presence; and delete the dead
  branch afterwards, because a refusal alone re-offers the same issue to the next sweep every hour.
- **Before declaring a run failed, re-read the state of the thing it was working on.** "verdict said
  implement, nothing implemented" has two opposite causes: the agent broke (red) and *someone else
  finished it while the run was in flight* (a green no-op with one comment). Expose the state read as
  its own make target with a contract — `0` still open, distinct non-zero for closed, a third for
  unreadable — and keep an unreadable state RED. Silence is not evidence.
- **Every GENERATED artifact needs a scheduled keeper, on a slot that converges.** A generated file
  that two PRs each regenerate over their own tree is stale the moment both merge (the squash keeps
  one file), and the red lands on the *push* to the base branch, where the PR repair paths do not
  reach. One keeper job regenerates + verifies + opens a PR ONLY when a file changed, on an hourly
  slot (not daily — the slot IS the convergence time), and never pushes the base branch.
  The same "lands on the base branch" trap catches a LIFECYCLE artifact: a change record that names
  its own PR (an OpenSpec change with a `PR:` line, a tracker row) reds the base-branch check the moment
  that PR merges, and nothing in the PR path repairs it — so finish the move as soon as the merge lands, in
the next PR, instead of discovering it from a red base-branch run. A record that carries NO PR line
does not trip that check, which is why adding the line later is what forces the archive.
- **A recipe whose stdout a step CAPTURES or REDIRECTS must be silenced (`@`).** `make` echoes
  every recipe line to stdout, so `OUT=$(make <target>)` holds the command line as its FIRST line and
  `make <target> > artifact.md` writes it into the artifact; a parser then reads a command as a
  value. Measured twice in production on the same bot: the numeric check rejected the sweep's own
  queue and two hourly runs implemented nothing, and every unit test stayed green because the step
  test STUBBED `make` — the stub prints only the value, so the echo the real recipe contributes is
  exactly what the test cannot see. Silence the recipe and guard the SHAPE, not the instance: parse
  the workflows for `$(make <t> …)` and `make <t> … > <file>` (a `*.log` capture is exempt), and
  require every resolved recipe's command lines to start with `@`, non-vacuously and with the
  measured target pinned. The same guard belongs at the commit step for markers: `git add -A`
  commits `<<<<<<<` into any tracked file, and a marker inside a PARSED file (Makefile, a workflow,
  a module) makes the next `make` die (`missing separator`) — resolve conflicts in the helper that
  creates them (take the run's own side of the carried work), never leave them for the commit.
- **`make` REWRITES a child's exit code, so a caller that compares `$?` to a documented non-zero
  code is reading dead code.** `make` exits **2** for ANY failing recipe and prints the child's own
  code only inside its message (`make: *** [Makefile:403: target] Error 3`). A helper whose
  documented contract says "exit 3 = conflicting rebase, work kept, push anyway" therefore NEVER
  matches from `make target || rc=$?` — and the failure is silent, because the step's `= "3"`
  branch simply never runs while the `else` arm refuses a finished run. Measured: an implementer
  committed 6 files, read `rebase=conflict`, then refused to push with `rc=2 — refusing to push`.
  Fix at the TARGET, so every caller inherits it: `rc=0; <script> … || rc=$?; if [ $rc -eq 3 ];
  then echo "<key>=conflict"; exit 0; fi; exit $rc` — and write it `rc=0; cmd || rc=$?` rather
  than `cmd; rc=$?`, because under `bash -e` (every workflow `run:` block, and a step test) the
  `-e` aborts before the assignment and the code is lost a second time. Leave the caller a plain
  `make <target>` plus `set -e`; the target owns the contract. The same class as the captured-stdout
  rule above: a documented output consumed through a layer that changes it.
- **A delivery alarm that measures TIME alone cannot see a run that failed ON TIME.** A sweep
  delivered two minutes ago and dead inside its first job is "fresh" to an age check, so the alarm
  proves the cron and not the work — measured: two failing sweeps read healthy while the queue did
  not drain for hours. Inside the window, a conclusion other than `success` is a verdict of its own:
  mark it FRESH, say the queue did not drain, keep the run URL, and let `cancelled` be loud too
  (excuse it only when a NEWER run succeeded). Check the TEST as carefully as the code: a fixture
  dated OUTSIDE the staleness window exercises the staleness path, so the case passes for the wrong
  reason — put the failing sample INSIDE the window and assert the fresh-red exit code through the
  CLI.
- **Enumerate every shape of "silent" before writing an alarm — one reader per shape.** A fleet's
  silence has five distinct states and a check that reads only one of them certifies the others:
  a job stuck `queued` (a runner label matching nothing NEVER fails, it just never concludes); a run
  delivered and red (an age-only check calls it fresh); a run green that produced nothing (a correct
  no-op looks identical); a scheduled slot the platform DROPPED (no run row exists at all, so every
  reader that starts from runs is blind — only the age of the produced ARTIFACT sees it); and a whole
  pipeline red on every one of its own runs (nobody reads its tab, so the alarm that broke is the one
  nobody notices). Wire one alarm per state, and give each a dry/`--list` mode that prints what it
  evaluates, so an empty roster can never pass as health. Recipes: `references/alarm-design.md`.
- **A guard or alarm that derives its roster must prove the roster, not just read it — and must be
  falsifiable.** A discovery regex over config silently under-matches: one that did not tolerate a
  trailing comment (`- cron: "…"  # twice a day`) listed four of eight pipelines while reporting
  success. Assert that known members ARE found and a known non-member is NOT, expose the list for the
  test to read, and then falsify the guard itself — mutate an input and watch it red. A rule whose
  assertion compares a value to itself, or a fixture that already satisfies the new check, locks
  nothing. Corollary: when a NEW rule's first run lists a dozen pre-existing hits that all look
  idiomatic, the RULE is too broad — tighten it to the precise defect (a same-step override assigning
  a DIFFERENT value, not any mention of the key) instead of rewriting a dozen files to suit it.
- **An option whose value is read from a live API must degrade loudly, never refuse.** A CLI whose
  `--kind`/`--label` comes from a `gh` read at run time, parsed with `choices=(…)`, exits 2 on an
  unexpected value — mid-step, after the work is done, so the bot never opens its PR and the failure
  reads as a code defect. Parse lenient and validate after: fall back to the documented default and
  say so on stderr. Reserve refusal for a value a HUMAN typed.
- **A follow-up branch must not name an issue it does not fix.** A branch ending `-<n>` binds that
  number: the closure guard refuses a body without `closes #n`, and a follow-up to an ALREADY-MERGED
  issue cannot legitimately close it. Name follow-ups without a number and use `Refs #n` in the body.
  Run the closure guard on its own line, never piped — `… | tail -1` (or any pipeline) swallows its
  exit status inside a `&&` chain, so the PR opens anyway and reds one check on a technicality.
- **A shell list of gates must be `&&`.** `a; b; c` reports only `c`'s status and swallows a failure;
  provide what the failing gate needs instead of deleting it.
- **Never pipe a state-changing command inside a `&&` chain — the pipe's status is the FILTER's.**
  `git merge origin/<base> 2>&1 | tail -1 && make <regen> && git add -A && git commit …` runs the
  regeneration and the commit even when the merge FAILED (`Automatic merge failed; fix conflicts`),
  because `tail` exits 0. The result is a commit carrying `<<<<<<<` into a tracked file — measured on a
  generated-index merge where the marker landed mid-suite and only the repo's own marker guard caught
  it. Same rule as the closure guard: run merge/rebase/apply on its own line, read its exit status, and
  check `git status --porcelain` for `UU`/`AA` before any regenerate-and-commit step; a marker that
  reaches a commit disables every later `make` on that tree.
- **A lost write is not a refusal.** Retry 502/503/504/timeout a bounded number of times, then adopt
  an existing object (PR by head branch) instead of duplicating it.
- **Long model legs get their own budget** below the job's `timeout-minutes`, and the salvaging steps
  (detect change, commit, push, open PR) run with `always()` — otherwise the cap kills the runner and
  the work with it.
- **The TREE is the evidence, not the exit code.** A leg that exits non-zero may still have produced the
  whole change — the model asked one question at the end (`Input required; detached without cancelling`,
  rc=3), or a wrapper returned the wrong code — and a job that maps `rc != 0` to "no implementation"
  throws 30 minutes of work away with the runner. After every model leg, read
  `git status --porcelain` (gitignored scratch is invisible to it) and let commit/push/PR run on
  `exited 0` **or** a dirty tree, with a `::notice::` naming the exit code; keep a CLEAN tree with a
  non-zero exit red, because there is nothing to review. Mechanism and the test shape (execute the
  shipped step in a real repo, clean and dirty): `references/failure-classes.md`.
- **A captured exit code that nothing acts on is a green lie.** The shape: a step runs the checker,
  writes `green=false` into `$GITHUB_OUTPUT` and exits 0 so the downstream reporting steps still run —
  and no later step ever reads it. The run reports success over a red PR (measured: `[fix-loop] still
  RED after 3 fix round(s)` in the same job that showed `completed/success`), so the queue treats the
  branch as finished and nobody repairs it. Every captured verdict needs a terminal step that fails on
  it (`if: steps.<x>.outputs.<v> == 'false'` → `exit 1` naming the subject and the artifact), and a
  test that asserts that step exists, carries the condition and sits AFTER the step that produces the
  value.
- **Raising the attempt count is a WALL-CLOCK change, not a constant.** `rounds x (check + repair)` must fit
  the job's `timeout-minutes`; five rounds of a 20-min check plus a 30-min repair need 250 minutes, so a job
  still capped at 180 is cancelled mid-round and the extra attempts never run — the feature ships, passes its
  own test, and cannot do the thing it advertises. Raise the cap in the same commit, keep the arithmetic in a
  typed test (`assert job["timeout-minutes"] >= rounds * (CHECK + REPAIR)`), and read that test's line before
  believing a red is about the bot's logic.
- **`-e NAME` in an agent leg is for CREDENTIALS only.** A path, a mode or a check name forwarded that way is
  refused by the credential-allowlist test (`an agent leg forwards a credential the agent's shell is not
  proven to see: ['FIX_REPORT_FILE']`) because the one list of keys a container may receive is the same list
  every leg is proven against. Pass the value from make INTO the container instead: `bash -lc '…
  FIX_REPORT_FILE="$(REPORT_FILE)" scripts/loop.sh'` — make expands the variable before the shell sees the
  quoted command, so nothing credential-shaped crosses the boundary and the value still arrives.
- **A leg's input is a CONTEXT BUDGET, bounded in TOTAL — not per file.** A brief builder that caps
  each file at 20 KB and then concatenates "every doc file matching a glob" hands the model whatever the
  tree happens to contain: measured, one engine's brief was 1 844 709 bytes over 214 files (424
  sections), dominated by benchmark-result pages, while the one file that PROVES the flags — the root
  `CMakeLists.txt` — was cut at the per-file cap before its `option(...)` lines. Shape: exclude noise
  trees outright (`bench/`, `benchmarks/`, `examples/`, `tests/`, `fixtures/`, `apps/`) with the noise
  rule winning over any always-include rule; give the evidence files their own SHARE of the budget
  (root first, a cap per file AND a cap together) so they cannot consume it all; rank the rest by the
  domain's own vocabulary; stop at a total (~80 KB) and PRINT how many files were omitted, so the
  leg knows its input is a selection and a reviewer does not assume the whole tree was read. Watch the
  glob too: `Path.match` does not let `**` cross zero directories, so `docs/**/*.md` matches nothing at
  the root and a `docs/BUILDING.md` — often the page documenting the flags — is invisible; list
  `docs/*.md` explicitly.
- **A report-only outcome must still write its report and exit 0.** A leg that computes an analysis and
  then hits "there is nowhere to put it" (the skill has no `cmake_flags` block to extend, the target file
  does not exist, every proposal was already applied) currently errors, the workflow's `|| echo
  "::warning::"` swallows it, and the artifact that would have carried the analysis into the PR is never
  written — a paid model call discarded, and `make: *** Error 1` sitting inside a green job reads like
  noise. Split the states: NOTHING TO DO is a success which writes the section that names what was found
  and why it was not applied; a proposal REFUSED by the host's own rules (uncited quote, wrong backend,
  flag absent at the pin) still fails loudly naming it. Report-only is a state, not a blanket
  `continue-on-error`. The check is "did the artifact that carries the analysis survive", not "did the
  step exit 0".
- **Every agent leg is UNATTENDED, and its prompt must say so.** `--yolo` auto-approves shell commands and
  `--accept-hooks` auto-approves hooks; neither answers the agent's own `clarify` tool. A question in a
  detached run makes Hermes print `Input required; detached without cancelling` and exit **3**, the tree is
  unchanged, and the leg reports "changed nothing" — so the reader chases data, keys or an alias and none
  of them is the cause. Put the rule in every prompt that runs with no user ("never ask a question and
  never wait for input; a genuinely open decision becomes a refine with its REASON, or the safest
  reversible choice stated in the output, because a question fails the run"), give exit 3 its own message in
  the failure step, and lock both with a test that reads the real prompt files. Prompt contract and the
  exact wording: `references/agent-leg-prompts.md`.
  **The strongest shape is a preloaded project skill, not a longer prompt** (measured in a second repo:
  three of five issue-bot sweeps died at rc=3 while every prompt said nothing about being unattended).
  Move each leg's contract into `.hermes/skills/<name>/SKILL.md` (`## Inputs`/`## Output`/`## Rules`,
  frontmatter `name` == directory), preload it with `hermes -s <skill>,bot-unattended`, leave a POINTER plus
  that run's parameters in the recipe, and gate it: a leg that preloads nothing, names a missing skill,
  inlines the shared paragraph, or outgrows its pointer budget must fail the same lint CI already runs.
  Two traps, both silent: (a) the directory must be REGISTERED in the Hermes home
  (`skills.external_dirs` — `hermes config get/set` writes a real list; a hand-rolled YAML writer needs
  PyYAML the repo may not have), and (b) register it at SETUP time inside `_setup`, not only in the image
  build — a published base image is rebuilt only when its Dockerfile hash changes, so an old image plus a
  new repo mount would otherwise run every leg with NO contract and report success. Prove it by running
  `make _setup` in the OLD image with the new tree mounted and `hermes skills list --source local` showing
  the skills as `external`.
  **A preloaded contract is necessary and NOT sufficient — design for the question, not only against
  it.** Measured twice: with the unattended rule preloaded and the run's own skill naming the exact
  failure it was handed, the model still called `clarify` once and the leg detached. So the leg's
  SURVIVAL must not depend on obedience: (a) a non-zero exit with a dirty tree is salvaged (see "The
  TREE is the evidence"), (b) the redacted transcript is uploaded so the question is readable, and
  (c) the skill names the failures the leg is actually handed — a contract silent about the most
  common failure leaves the model nothing to do but ask. Add the missing case to the skill first,
  then re-measure: if the detach survives that, the cause is in the leg, not the prompt, and the
  transcript is the only thing that will name it.
- **Once a fleet has more than two legs, the contract is a PROJECT SKILL, not a prompt string.** A repo with
  N legs ends up restating the same rules N times, in a file where nothing can tell a leg that lost its
  contract from one that never had it. Shape: `.hermes/skills/<name>/SKILL.md` (frontmatter `name` equal to
  its directory, `## Inputs` / `## Output` / `## Rules`), one shared `bot-unattended` skill preloaded beside
  every leg's own, each leg running `hermes -s <skill>,bot-unattended` with an inline prompt that is a POINTER
  plus that run's parameters, the directory registered in the container's Hermes home at setup (and read
  back — an unregistered directory runs every leg with no contract and still reports success), and a gate in
  the lint stage. Registration, the gate's check list and the pointer budget: `references/agent-leg-prompts.md`.
- **A leg whose command carries a literal comma loses everything after it, and the run reads as "agent
  failed".** GNU make splits `$(call …)` arguments on commas in the **unexpanded** text, so
  `$(call scrubbed_run,… bash -lc 'hermes -z "…" -s a,b …')` keeps only `-s a`: the closing quote leaves with
  the rest, the shell dies with `unexpected EOF while looking for matching '` and exits 2 **before the agent
  starts**. The exposed shape is a leg that inlines its whole `hermes` command — it must when the tree's
  `Makefile` is the file being repaired — while legs that run a `_<leg>` target never see it. Fix by giving
  the list a variable (`LEG_SKILLS := a,b`, then `-s $(LEG_SKILLS)`): a variable reference contains no comma.
  Diagnose with `make -n <leg>` and count single quotes (odd = truncated); guard it by deriving every target
  that calls `scrubbed_run` from the Makefile, expanding each with `make -n`, and failing on odd quotes or an
  `-s` list that lost its second entry.  A checker that reads legs textually must expand simple Makefile
  assignments first, or it reports the variable name as a missing skill. Mechanics, the other two
  shell traps that read as "the bot did nothing", and how to prove a leg from its expanded recipe:
  `references/leg-shell-safety.md`.
- **Under `set -o pipefail`, every reader in a leg's pipeline must read to EOF.** `grep -q`, `grep -m1`
  and `| head` exit at the first match, the writer takes SIGPIPE, and the pipeline reports **141** —
  which a probe reports as "missing (… exited 141)" on a perfectly healthy binary, sending the reader
  after the engine/binary instead of after the reader. Use plain `grep`, `sed -n '1p'`, `cut`, or
  capture the output to a variable first; when a check must accept several spellings, run every member
  and name the one that failed rather than taking the first answer.
- **Every cron/fork/credential decision lives in a make target**, not in workflow YAML, so it can be
  run by hand. If the user asks "can I run it manually", the answer must already be yes.
- **Trigger a repair bot by the failure it repairs, and bound attempts per HEAD.** A cron is only a safety
  net (hourly crons arrive sparsely — ~9 deliveries in 36 hours, measured); wire `workflow_run` on a failed
  `pull_request` CI run, dispatch the run's OWN PR with the failed job's log as context, and let each
  failure re-arm the next attempt up to N, counted by the bot's own commit prefix. Condition block, the
  unverified-repair path and the diagnostics: `references/repair-bot-triggers.md`.
  **Scope the dispatch to EVERY branch family the fleet opens, not just the one you were thinking of.**
  A condition keyed to the refresher's prefix (`startsWith(head_ref, 'ci/trending-refresh-')`) silently
  excludes the implementer's PRs (`ci/data-gap-<n>-…`), so the bot that most needs repairing has no
  repairer at all and its PR sits red and unmergeable while every run reads green. Enumerate the
  prefixes from the workflows that open PRs, assert each one in the test, and keep the same-repo-head
  and attempt-cap guards.
- **The full suite is the last gate, not the first.** Focused tests first (minutes), then the full
  run in the background writing to a log file, polling the log — a 10-20 minute suite does not fit in
  one blocking call. Launch it as a tracked background job whose recipe appends its own `EXIT=` line to
  that log, then poll the FILE; `sleep 600; make test-unit` inside a foreground call is NOT background —
  the call's own timeout kills the process tree mid-run and the log simply stops at whatever percentage
  it had reached, which reads like a hang and costs a full re-run.
- **Split the gate set by what it needs.** Deterministic stages (store / README / contract checks) run
  in seconds and belong in your own loop; a stage that resolves links or otherwise fetches over the
  network takes many minutes and any per-call timeout will cut it off mid-run (`Terminated`, which
  reads like a failure and is not one). Run the deterministic stages, then leave the network-bound one
  to CI and say so in the PR. A data-only change still needs the generator re-run (the repo's
  `render-readme`-equivalent) or the generated-file gate reds.
- **Treat the first full-suite failure as real.** Static gates in these suites catch a hardcoded model
  alias, a lost step env, or an index-based assertion. Fix the code, never loosen the test.
- **A job that runs the suite needs the full history, or its QA pass is permanently red.**
  `actions/checkout` defaults to `fetch-depth: 1`, and any check that reads `git log` (authorship, commit
  trailers) fails there BY CONSTRUCTION. When that QA pass is advisory ("data still lands for review")
  the standing red makes a REAL failure indistinguishable from noise while the job reads green — the one
  signal that would catch a bad run is on for ever. Give every job that runs the suite / a QA report
  target `fetch-depth: 0`, and guard it across the whole workflow directory (strip shell comments first:
  a target named only in prose is not a call).
- **One passing member never vouches for the set, and an issue's literal assertion is not the spec.** A
  check that exits 0 on the FIRST of N items that answers (a probe over flags, a matcher over spellings,
  a sweep over refs) is green while N-1 are dead. Run every member, report one verdict per member, and
  fail on the member that failed, naming it. Before implementing the assertion an issue asks for, measure
  the data it assumes: an issue asked to assert one flag for every engine, and the generated manifest
  showed none of them documents that spelling while six document another — the literal fix would have
  reddened the whole matrix. Implement the strongest rule the data supports (each documented member
  individually, plus at least one answer per FAMILY of spellings), and put the deviation with its
  measurement in the PR body.
- **Re-specify the tests that pin the old contract at the SAME strength.** A behaviour change breaks them;
  the fix is not to delete or soften them. The probe that used to return one exit code now asserts the
  dead member is reported dead and the live one alive; a test that asserted the stranding your fix removes
  becomes two cases (the corrected policy plus the boundary that must not change), with a docstring saying
  what it used to assert. Then prove the new cases RED on the base by swapping `git show origin/<base>:<file>`
  back in and restoring it — a case that passes on both is a guard, and say so instead of calling it proof.
- **A machine-readable line parsed in two languages is a platform seam.** A bash probe emits
  `KEY <name> <rc> <bytes>` and Python parses it; BSD `wc -c` pads its count (`      12`) where GNU does
  not, so a single-space regex matches nothing on macOS, every item reads as "never probed", and the check
  is green on Linux and red on macOS. Normalise in the PRODUCER (`| tr -d ' '`, default to `0`) AND accept
  `\s+` in the parser, then pin the padded shape in a test. Same rule for any `awk`/`sed` field a workflow
  slices out of a bot's own output.
- **`mergeStateStatus` reports ONE state, so `BLOCKED` is not proof a PR is current.** A swept PR can be
  `mergeable=MERGEABLE` + `BLOCKED` (a required review) while its branch is genuinely diverged from the
  base; GitHub surfaces the review block and hides the behind-ness. The next base push onto the same
  files then flips it to `DIRTY`/`CONFLICTING` — the "it already merges cleanly" premise expires silently.
  Measure staleness where it is defined, never from `mergeStateStatus`:
  `gh api repos/<o>/<r>/compare/<base-sha>...<head-sha> --jq '{status,ahead:.ahead_by,behind:.behind_by}'`.
  A sweeper whose `NEEDS` is only `BEHIND`/`DIRTY` therefore skips a diverged PR and reports `action=none`
  honestly-but-uselessly: `BLOCKED` explains why it cannot MERGE, not why a rebase is pointless. A rebase
  also restarts the CI run that a `workflow_run` merge gate needs, since that trigger does NOT fire
  backwards — a PR whose green run predates the gate is never considered until a fresh push runs CI.
- **A failure is a work item only while its SUBJECT still exists, and the producer of duplicates stamps them with the label the dedupe sweep protects.** A reactor that files per failed run without asking "is this still work?" manufactures the exact backlog the duplicate sweep exists to retire — and it hands each one the queue label (`agent:implement`), which the sweep treats as a claim, so the sweep can never touch them. Check both halves when auditing: `git`/`gh` the issue's subject (a `pull_request`-event run → is an OPEN PR still on that head? a `push` run → did a LATER run of the same workflow on the same branch succeed?) before believing an issue is work. Measured 6/6 reactor-filed issues were failures whose PR had merged before the issue existed. Fix the source, then file the sweep's blindness separately (label-vs-claim is the policy bug).
- **An UNKNOWN is never a retirement verdict.** The check that decides "file nothing" must distinguish absence (no open PR / a later success — real evidence) from an unreadable answer (a failed `gh` read, a fifth-party fork whose state no token can read). Print the reason and KEEP the work item; a failed read that deletes a real issue is worse than a duplicate.
- **A pruner that keys worktrees by branch name silently loses detached ones.** `{t.branch: t for t in trees if t.branch}` never matches a detached worktree, so the plan promises `prune N branches, 0 worktrees`, skips `git worktree remove`, and `git branch -D` then fails (or, when git allows it, deletes the ref and strands the directory). Any `prune`/`remove` helper must make the plan and the apply step read the SAME decisions — a summary that contradicts the plan is the bug, not a cosmetic wart. Fix shape: index detached worktrees by their HEAD commit and adopt EXACTLY ONE whose HEAD equals the branch's tip (a detached checkout parked on any other commit matches nothing and must stay), then run it through the same dirty/own-worktree guards and remove it before the branch. Expect an existing policy test to assert the old stranding — re-specify it as two cases (tip-matched: both gone; elsewhere: untouched). Tip-matching is still not the whole story: the tool can refuse the delete for a worktree its own listing shows as bare `detached` with NO branch line, whose HEAD is neither the branch tip nor in the branch's history — the association exists ONLY in `git branch -D`'s refusal, so the apply step must act on that refusal instead of the plan. Split it two ways: a refusal naming a worktree that is detached, branch-less and clean is debris (remove it, retry the delete ONCE, a second refusal stays an error naming it); any other holder — a branch checked out there, uncommitted or unmerged work — makes that item a KEEP with the reason printed. A legitimate hold reported as a non-zero exit is a defect in the helper, not a finding: one item a sweep may not touch must never red the whole run, and `--force` is not the answer because it deletes work in progress. When the platform will not reproduce the refusal in a fixture (git allows the delete there for reasons of its own), drive the real apply step with the tool's REAL message rather than shipping a synthetic case that passes for the wrong reason — and say in the PR that the fixture could not reproduce it.
- **A pass-over reason is only a diagnosis once you read WHICH reason.** `no open PR needs rebasing`
  collapses at least three different states: a merge-state skip (`is BLOCKED`/`UNSTABLE` against base),
  a comment-occupancy skip (`is held by another bot: commented on by <login> N min ago without a done
  comment`), and an already-current branch. Only the first is a judgement about the PR; the second means
  the sweep never looked at its conflict at all. Enumerate the `pass-over:` lines before concluding
  nothing is wrong, and do not loosen the merge-state comparison to "fix" a comment skip.
- **Any recent non-`done` comment HOLDS the subject for the claim TTL — including a human's own.** The
  occupancy matcher treats every comment since the bot's own last `done` marker as another actor's live
  claim, so a status/diagnosis/evidence comment posted on a PR freezes that bot on it until the TTL
  expires. That is deliberate (it stops two actors rebasing the same branch concurrently) and the fix is
  a protocol, not a code change: end a comment on a bot-owned subject with the bot's `done` marker, or
  expect that subject to be skipped and say so instead of re-running the sweep and waiting.
- **Before diagnosing a bot's red, find out whether the job PULLED its runtime image or BUILT it.**
  The image-layer lines are the tell: `docker pull <ref>` means the published, already-tested artifact ran;
  `<ref> is not published (an edited Dockerfile or lockfile): building <local> here` means the job resolves a
  floating upstream inline, on the runner, minutes into the run. A red inside a step whose name is a *gate*
  (`Prove the … is active`, `preflight`, `smoke`) is usually the image BUILD underneath it — read the docker
  build step numbers (`#N`) and the install script's own `fail` line before theorising about the gate or the
  bot's logic.
- **An image that is only published by hand is unvalidated on the very PR that changes it.** Nothing builds
  it on `pull_request` or push, so a merged change to its hash inputs goes green, its new tag is never
  published, and every bot job then rebuilds it inline — which makes the FIRST build after that change the
  place where the floating half (a `latest`-fetching CLI installer, live dependency resolution) is resolved
  for the first time in days. The symptom is unmistakable once seen: several unrelated bots go red within the
  same hour, all in the same gate step, none of them on code they own. Fix the shape, not the symptom: build
  (never publish) the image in CI on any PR that moves its hash, publish on merge, and pin what the build
  installs so the tag means what it claims. Depth: `references/failure-classes.md`.
  Fix shape when the build dies on a plugin/package's optional extra under a universal lock: scope the
  install to what the image USES — install without dependency resolution (`--no-deps`), remove the one
  unused extra from the INSTALLED copy while asserting it was there, then enable (which resolves the
  now-satisfiable graph). Do not reach for the resolver knob first: a `[tool.uv] environments` table in
  the plugin's own pyproject is NOT inherited by the workspace the orchestrator generates — measure it
  in a real container against the real pin, and put both outcomes (what failed, what worked) in the PR
  body, because the next reader will try the obvious knob too.
- **When a gate "defers" on a fork PR, the credential is the first suspect — before merge state.** A
  `pull_request` run from a fork has NO repository secrets (an empty env line, not a masked one), and a
  PR opened with `GITHUB_TOKEN` starts no workflows at all, so it has zero checks. Both look green and
  both merge nothing. Read the step's env block and `gh pr checks` first; see
  `references/github-actions-credentials.md`.

## Adding a new bot

- One workflow, one `make` entry point per phase (brief/doc/publish style), one `.PHONY` target each.
- Guard first: actor permission (owner/collaborator), then env, then image pull/build — before any
  secret or container work, so a bad dispatch costs seconds.
- Deterministic parts in stdlib python (`git`/`gh` only); invoke a model only for the step that needs
  judgement, and pass it through one make target.
- Redact the agent stream: capture to a log, print a bounded scrubbed tail, upload the scrubbed file —
  and upload it on EVERY outcome (`if: always()`, `if-no-files-found: ignore`), never only on success.
  A leg that detaches leaves a three-line tail and nothing else, so the question the model asked is
  unrecoverable and the next diagnosis is a guess; the REDACTED log is the artifact, the raw capture
  never is.
- Refuse the publish unless the run is on the expected branch and only the intended file(s) changed —
  enforce the boundary in code, not in the prompt.
- **A sweep that compares subjects across the whole backlog declares a PROTECTED-LABEL set and honours it
  on both sides.** Any bot that acts on more than the one item it was handed (a duplicate finder, a bulk
  closer, a re-tagger) can silently undo another bot's work: an issue labelled `agent:implement`/
  `agent:ready` is being implemented, one labelled with a refine marker has a restatement, one already
  retired must not be retired again — so exclude those from the CANDIDATE list AND re-check the target
  immediately before mutating it (a label can land between the pick and the apply, and the sweep runs
  minutes later). Card: helpers such as `PROTECTED_LABELS` + `is_protected()` used by both the picker and
  the apply path, with one test per protected label and one that a claimed TARGET is left untouched.
- **A bot-GENERATED tracker issue is not a duplicate candidate.** Issues a bot files per run (a refresh or
  report tracker) are near-identical BY CONSTRUCTION — same title template, only the timestamp differs — so a
  token comparison pairs two of them at a high score and hands the model a question with no answer, spending
  the run's one decision on machine noise. Exclude an issue whose body carries a generator marker
  (`<!-- <name>-bot:`), keep that filter next to the protected-label one, log the count skipped, and lock it
  with a test using two generated bodies plus one human one.
- **Dry-run the candidate finder against the LIVE backlog before shipping it.** A deterministic selector's
  false-positive class only appears on real data: run the read-only pick against the real repo (it writes its
  scratch file and mutates nothing) and read the pair it names before opening the PR. That one run is how a
  generator-vs-generator false pair and a genuine filed-twice duplicate both surfaced, and the same output is
  the demo to quote in the PR body.
- **A pair picked deterministically still needs the model's verdict, and the verdict needs evidence.**
  Token-overlap ranking (title+body Jaccard, the OLDER item canonical) finds candidates cheaply, but
  "similar words" is not "same defect": have the model answer `DUPLICATE: #<older>` with a quoted
  `EVIDENCE:` block or `DISTINCT:` with a `REASON:`, refuse the mutation when the evidence block is empty,
  and queue the canonical item so retiring the copy never loses the work.
- The PR body comes from the run (`closes #n`), never `--body-file -` and never hand-typed prose that
  contradicts the code.

## Pitfalls

- **A bot's own repair round can invent a SECOND change record for work it already did.** When a bot
  PR is red on the change-record gate (`openspec-tasks-check`, a spec lint) while every test is green,
  list the change directories before ticking a single box: a repair round that re-planned the job
  writes a NEW directory beside the original (different names, all boxes unticked) instead of
  completing the one already there. Keep the record whose task text names the symbols the code
  ACTUALLY defines (compare its named constants/targets against the diff), delete the duplicate in the
  same commit, and say in the commit message that it is a duplicate the same PR created — that is
  housekeeping, not data loss, and an "additive only" rule about stored data does not apply to it.
  Then tick only the boxes you verified against the tree, and rewrite any task that cannot be done
  (a protected-file row) as an explicit OWED note instead of leaving it unticked.
- **The bot's own commit step must refuse a conflict marker, not just the merge that produced it.**
  `git add -A` commits `<<<<<<<` into any tracked file and a marker inside a PARSED file (Makefile, a
  workflow, a module) makes every later `make` die with `missing separator` — measured twice, once in
  the Makefile where the following target could not parse its own file. Resolve conflicts where they
  are created, AND put a tracked-file scan (`^<<<<<<<`, skip binaries, ignore untracked) immediately
  before `git add -A` in every bot that commits, wired into the fast lint gate too. Run it BEFORE any
  step that switches the working tree to a branch: an adopt/checkout can DELETE a file the base added,
  and the guard then fails on a missing script instead of on a marker — assert the ORDER in the test.

- **Run a failing test module INSIDE the CI image, not on the host.** A module that SKIPs locally
  (a missing optional import in the image's requirements) reports green on the host and fails in the
  pipeline. `docker run --rm -v "$PWD":/workspace -w /workspace <test-image> python3 tests/<m>.py`
  is the only green that counts; a local `PASSED n | FAILED 0` with no checks printed is a SKIP.
  When the module shells out to real `git`, ALSO mount the PARENT clone: in a worktree `.git` is a FILE
  pointing into it, so without that mount every `check-ignore`/`for-each-ref` answers non-zero and reads
  exactly like "my change broke the roster test". Copy the Makefile's own container options instead of
  hand-rolling the run command.
- **`docker run` without `-i` silently feeds the container NOTHING.** Piping a producer's stdout
  into a second `make` target, or a heredoc into `python3 -`, reads as empty input rather than an
  error: the consumer answers as if its producer emitted nothing. Keep a
  producer-and-consumer pair in ONE process, or add `-i` deliberately
  and say why in the target's comment.
- **A merge that auto-commits swallows the regeneration you stage after it.** `git merge
  origin/<base>` can complete on its own; after that, `git add <generated>` + `git commit --no-edit`
  aborts with "empty commit message" (there is no merge in progress to reuse a message from) and the
  push goes out WITHOUT the regenerated file. Commit the regeneration with an explicit message and
  re-read `git show HEAD:<file>` before pushing — otherwise the next CI run reds on a stale generated
  file and the push looks like it carried the fix.
- **A rendered file is not the file: elided or substituted text reads exactly like a real defect.**
  Tool output that shows a credential-shaped or abbreviated literal (`Authorization: Bearer ${FI...KEY}`,
  `Bearer ***`) may be a REDACTION of a correct value, not the value on disk — and the eye reads it as the
  bug the repo once had. Before filing or fixing anything on the strength of a suspicious string, count it
  programmatically (`python3 -c 'import pathlib;print(pathlib.Path("Makefile").read_text().count("FI...KEY"))'`
  → `0` means the file is fine) and read the real bytes of that one line. The repo's own test that asserts
  the bad spelling is absent is the cheapest confirmation.
- **A repo-wide replace driven by `git grep -l` misses the files you just created.** Untracked files are
  invisible to `git grep`, so a sweep that renames an issue number, a marker or a symbol across the tree
  silently leaves every new script, skill and test on the OLD value — and the new files are exactly the ones
  the change is about. Enumerate the new paths explicitly (or `grep -rl` over the tree with a binary guard),
  then re-run the generator that derives text from them, because a derived block that embeds those values is
  now stale.
- **Regenerate a derived document LAST, after the final wording.** A generated block that is derived from
  the tree (targets, scripts, and the issue numbers in comments) is stale the moment you edit prose again,
  so `make <doc>-refresh` before the last edit buys a red `check` step that reads exactly like a broken
  generator. Order: write everything, then regenerate, then run the check.
  **Your OWN sibling PRs are the worst case:** every merge to the base invalidates the generated index
  in each still-open branch, so serial merges redden each other in turn and the loop feels endless.
  Repair one at a time and deterministically — `git fetch`, `git merge origin/<base>`, regenerate,
  re-run the checks, commit with an explicit message, push. Expect N-1 repairs for N queued PRs, and do
  not read the staleness as a defect in your change.
  **Two generated artifacts stale together:** the same repo usually has BOTH an index and a
  description block, and each has its own refresh target (`make <index>`, `make <doc>-refresh`).
  Regenerate both, or the second gate reds the run you just repaired.
  **Resolving a conflict differs by file shape, and one of the two choices is lossy:**
  - a PURE derived snapshot (an index whose every line is generated) → take the base's side and
    regenerate (`git checkout --theirs -- <generated>` then the refresh target), never hand-merge two
    derived snapshots.
  - a document that carries a GENERATED BLOCK **plus hand-written prose** (a description with a script
    inventory table, a rulebook with an appended section) → `--theirs` DELETES the rows this branch
    added, and the doc's own check then fails with `target X is not described` even though the
    conflict is "resolved". Correct order: take the base's side, RE-ADD this branch's rows on top of
    it, then run the refresh target, then the doc's check.
  - the `Makefile`/workflow side is almost always two INDEPENDENT additions (each PR added its own
    target) → keep BOTH sides in every hunk. Never `--ours`/`--theirs` a file whose two sides are two
    different features: the file parses, the gates pass, and one PR's feature is silently gone.
- **A `PASSED n` that is IDENTICAL to the count before your edit proves nothing — the new checks
  never ran.** Two causes, both silent: the module SKIPped (a missing optional import on the host),
  or the new test function was never added to the module's `main()` list. Assert on the new check's
  own output LINE appearing and on the count having gone UP, not on `FAILED 0`; run the module in the
  CI image before believing either, and repeat after every edit that adds checks.
- **Prove a make recipe by running its REAL text, not a re-typed copy.** Extract the target's recipe
  lines out of the Makefile, strip the leading tab AND make's `@` silencer (it is not shell), then
  substitute what make would: `$(VAR)` → the value, and `$$` → `$`. Run the result with `bash -e -c`
  in a temp dir whose `scripts/<helper>.py` is a stub exiting each code you care about (3, 1, 2, 4,
  0), and assert exit status plus the emitted key. Traps that make the test lie: forgetting `$$`
  leaves `$?` as the PID, `-e` truncates `cmd; rc=$?` before the assignment, and re-typing the recipe
  tests your memory rather than the file. A recipe copied into a test proves nothing.
- **A guard that scans tracked files will FAIL on its own fixture.** Writing a literal marker block,
  token or credential into `tests/test_<guard>.py` makes the guard flag the test file on the first CI
  run (the suite is green locally only if the guard is not run over the tree). Build the fixture from
  parts instead (`"<" * 7`, `"=".join([""] * 8)`, `"TOKEN-" + "x" * 20`) — that is also what makes
  the case unambiguous about which shape is being matched. Add one assertion that a legitimate
  look-alike (a 6-character markdown rule, a padded field) is NOT a finding.
- **When a step's make target changes, the test's STUB `make` must learn it in the same change.**
  Workflow tests map `$1` to the real script; a renamed target hits the stub's `*)` arm and every
  push-path assertion fails with "called an unexpected target". Extend the stub AND update the
  assertions that pin the old target, then prove the NEW guards go red against the base version
  (`git show origin/<base>:<file>`).
- **When a data guard fails on its WHITELIST, capture the value — never widen the whitelist.** Such a
  check enumerates the models whose figure legitimately lives only in prose, so adding a model to the
  set silently converts a capture gap into policy and the guard stops meaning anything. The failing
  line names the model, the field and the value the post states: write THAT value into the structured
  field (an additive merge rule allows raising a stated figure), re-run the module, and let the claim
  disappear on its own. Same rule one level down: a `<=` set assertion is a diagnosis, not an
  obstacle.
- **Date a weekly bot's red against the fix before filing anything.** A weekly (or 6-hourly) bot's newest red
  can be older than the commit that already fixed it: compare the run's timestamp with `git log -1
  --format=%ci origin/<base> -- <script>` and the merge date of the fixing PR before writing an issue, or the
  fleet costs a duplicate work item per cycle. Same check for a "failure" whose cause was an upstream data
  loss: read the guard's own line (`LOSS: …`, `FAILED: N loss(es)`) — a guard doing its job is a BLOCKED bot
  with an upstream owner, filed as its own issue with the measured count, never a code change here and never
  a widened guard.
- **A red data PR is often the merge RULE, not the refresh.** Before touching the bot, read the failing
  module's own line: a footprint that is pinned or shrunk, an id that fails the contract pattern, or a
  value dropped at ingest all present as `validate` red on a PR that did nothing wrong. Fix the rule in
  the ingest/merge script (with a test that drives the real function), not the pipeline wiring.
- **A fork `pull_request` run receives NO repository secrets.** `secrets.*` renders as an EMPTY env
  line (while `GITHUB_TOKEN: ***` renders masked), the job still exits 0, and it did nothing. Read the
  step's own env block from the job log before believing any "deferred" decision; the privileged step
  belongs in a `workflow_run` workflow, which runs with the base repo's secrets.
- **A review-blocked green PR is approved by the OTHER identity first, then merged.** `--admin` is not the
  general fix (GitHub refuses it where the rule is enforced for admins), the merge state must be POLLED after
  the approval (it is computed asynchronously), and a PR authored by the merge account needs a second
  identity's token. That whole chain — predicate agreement, polling, the optional approver secret — is one
  decision table and lives in `github-fork-pr-auto-merge`; do not re-derive it here.
- **A PR opened with `GITHUB_TOKEN` starts no workflows** — it arrives with zero checks and can never
  be green, so every merge gate defers forever. Open PRs with a PAT, splitting the token per WRITE when
  one step needs two capabilities (issue on the scoped job token, PR create on the PAT). See
  `references/github-actions-credentials.md`.
- **A gate that cannot act must be red and must say so on the PR.** A missing credential exits
  non-zero naming itself, and every deferral posts ONE marker-deduped comment per head SHA with the
  reason and what would unblock it — a reason that lives only in a run log is a reason nobody reads.
- **The repo's `AGENTS.md` may be write-protected.** Do not route around the block (no terminal edit,
  no second path): put the exact paragraph in the PR body, say the change is complete without it, and
  name what stays unstated until the owner applies it. Record the same text verbatim in the run's
  `findings.md` under its own heading — that file is what the repo's findings filer turns into a
  tracked issue and what a later change applies — attempt the rulebook write ONCE per change (never
  retry it, never route around the refusal: a second attempt times out exactly the same way and burns
  the round), and when SEVERAL changes owe rows, send ONE consolidated edit — every owed row in a
  single section-table patch, each row naming its change — because a per-change attempt multiplies
  approval prompts that each time out; then say
  in the PR that the hunk is pending rather than describing the change as complete. Consequence you must plan for: **do not cite a rule
  number the rulebook does not declare.** Writing "see rule 6p" into a workflow, a script comment, a doc row
  or a test is a dangling citation, and the repo's own `test_rule_numbers`-style guard fails the suite for
  it — cite the issue instead ("(issue #NNN)") until the paragraph lands, then cite the rule. The same
  applies to a marker string the gate greps for: assert the seam's own documentation in the file you CAN
  write, and print whether the protected rulebook states the rule yet, rather than reddening on prose you
  are not allowed to add.
- `git -c user.name=…` is read verbatim by author gates — set `git config user.name`/`user.email` to
  the exact allowlisted spelling before committing.
- **A commit message with backticks is SHELL, not text.** `git commit -m "… `make check` …"` runs
  `make check` inside the message (double quotes still expand backticks), so the commit lands with a
  sentence where a command's output should be — silently, because the substitution usually succeeds. Pass
  the message on stdin with a quoted heredoc (`git commit -F - <<'MSG' … MSG`) whenever it names a command,
  a target or a file in backticks, and read `git log -1 --format=%B` before pushing.
- A squash merge means a commit pushed to the branch AFTER the merge never reaches `main`; verify with
  `git show origin/main:<path> | grep <marker>` and open a follow-up PR.
- A bot's own claim comment matching its "already done" regex is the classic self-blocking bug; test
  the marker parser against a claim AND a done comment.
- **An empty check list is not a failing check — and `gh pr checks` EXITS NON-ZERO for it.** `gh pr checks
  <n>` answers nothing, or `no checks reported on the '<branch>' branch` on stderr with exit 1, when NO RUN
  EXISTED: suspect the creating token (anti-recursion) or a trigger that does not match the event, not the
  merge logic. Two consequences, both fatal to a sweeper: (1) a helper that treats any non-zero `gh` exit as
  a crash dies on the first check-less PR and the whole sweep is skipped behind its failed `needs:`, so the
  repair loop is dead while the run looks like it simply found nothing; (2) narrowing the guard to that ONE
  message is the fix — return an empty list for `"no checks reported" in stderr.lower()` and re-raise every
  other failure, because a genuinely unreadable API must stay red. Give the test fake `gh` the ability to
  answer that non-zero shape (a scenario key like `no_checks: [<pr>]` that writes the message and exits 1) —
  a fake whose `pr checks` always prints `[]` cannot express the bug. For a fork-head PR whose run exists but
  does not report on the PR, use `gh run list --branch <head>`.
- **The repo's own bot is an App login, so a permission-read guard refuses it and EVERY job never starts.**
  `github.actor` is `github-actions[bot]` whenever the PR was opened or pushed with `${{ github.token }}`
  (and for bot comments), and `gh api repos/<r>/collaborators/github-actions[bot]/permission` answers 404 —
  the `|| echo none` turns that into a refusal. Because the `guard` job is a `needs:` of every other job, the
  run shows one refused guard and no other jobs at all, so it reads like a trigger problem. Admit the bot
  ONLY on a same-repo head: `HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name || '' }}` and let
  it through when that equals `$REPO`; a same-repo head can only be produced by a token with write access, so
  a stranger's fork head and a non-PR event (empty value) stay refused. Expect a bot's own workflow-created
  PR to be the first victim, and note a bot PR that was opened by hand does not reproduce it — its actor is
  the human.
- **A YAML text assertion on a guard is not a guard test.** Extract the step's `run:` out of the workflow and
  execute it with bash against a real fake `gh` on `PATH` — owner → 0, write collaborator → 0, stranger on a
  same-repo head → 1, bot + same-repo head → 0, bot + foreign head → 1, bot + empty head → 1. Reading the
  snippet (does it mention `triggering_actor`, which arm lists which permissions) keeps the RULES from
  drifting across N byte-identical copies; only executing it proves the DECISION. Prove the new case fails on
  the base version by dumping `git show origin/<base>:<workflow>` to a temp file and running the same helper
  on it.
- **A bot's own daily cap silently contradicts its cron.** A `MAX_PER_DAY = 3` under `cron: "43 * * * *"`
  makes 21 of 24 runs idle by design while the schedule advertises hourly, and the idleness is
  indistinguishable from "nothing eligible" in the log. Keep the budget and the documented cadence in one
  place, count it from the bot's own marker (a label or claim touched for any other reason that day must not
  spend it), and make a test fail when the constant and the README/schedule disagree.
- **A fake `gh` must reject the argv vocabulary it does not know.** The complement of the rule above: a stub
  that answers `pr view` with whatever JSON the test handed it, and accepts any `--json` field name, hides an
  unsupported field or flag until production (see `github-fork-pr-auto-merge`, which carries the field
  allowlist recipe). Have the stub validate the requested `--json` names against a captured allowlist and
  exit 1 with `Unknown JSON field` otherwise.
- **A green PR waiting on one slow job is not a merge bug.** The merge job is only created after its
  `needs:` finish (a macOS unit job can hold it for an hour); check for the job's existence
  (`gh run view <id> --json jobs`) before theorising about merge state.
- **A label-driven picker only sees LABELLED issues, so a verdict that retires work must re-queue what
  it points at.** "Why did the bot not implement this?" is answered by the issue's labels, not by the
  run: a duplicate close cites the canonical issue in prose and stops, and if the canonical issue
  carries no queue label (`agent:implement` / `agent:ready`) the picker never lists it — so every
  recurrence files another labelled copy, the bot closes that copy too, and nobody implements the real
  defect. On a close, pull every `#<n>` out of the verdict's evidence/reason and add the queue label to
  each reference that is OPEN and carries no agent label; print-and-skip a reference `gh issue view`
  cannot read (a PR number, a typo, a deleted issue), because the close already happened and must not
  become a crash. The dry run prints the same decision.
- **The "decided" label must not be the same label that makes a refined issue unpickable.** When the
  refine verdict adds a label the picker skips (`agent:refined`), a refine is a one-way door: the
  restatement is posted, the issue becomes MORE implementable, and the bot can never pick it again
  without a human editing labels. A refine must record the refinement and leave the issue queueable —
  swap the decided label for the queue label, or keep the refined marker out of the skip set.
- **A repair loop that verifies only with its OWN check discards every failure it cannot reproduce.**
  A macOS-only job, a GPU-only image test or a network flake is green on the repair runner, so a
  check-then-push-on-green loop pushes nothing and reports "still red" without ever reading the log that
  names the failure. Repair from the failed run's captured log, mark the result `UNVERIFIED`, and let CI
  verify — never present an unverified attempt as a fix. Details: `references/repair-bot-triggers.md`.

- **`gh api` prints a 404's error BODY to stdout, so `$(gh api … || true)` is not "empty on failure".** `number=$(gh api "repos/$R/actions/runs/$ID/pull_requests" --jq '.[0].number // empty' || true)`
  yields `{"message": "Not Found", …}`: non-empty, so the `[ -z "$number" ]` guard never fires (the fork fallback
  written for exactly this case is unreachable) and the multi-line blob appended to `$GITHUB_OUTPUT` kills the step
  with `Invalid format`. `|| true` discards the exit status, never the output. Accept a value only when it is digits
  (`case "$v" in ''|*[!0-9]*) v="" ;; esac`, or `int(v) if v.strip().isdigit() else None`), and keep the parsing in
  one tested script instead of inline shell — the shell version cannot be exercised by the suite.
- **A DISPATCH runs as the identity of the token that made it.** `gh workflow run` with `${{ github.token }}` produces
  a run whose `github.actor` is `github-actions[bot]`, which every guarded workflow refuses (see the App-login
  pitfall) — so the dispatch itself succeeds, the repair run is born red at its own guard, and the failure reads like
  the bot's logic. Dispatch with the OWNER PAT, passed by ENV VAR NAME only (never on argv, never into a log), and
  make an empty one a loud failure BEFORE the call. The same token usually cannot do the other write (an owner PAT
  often lacks Issues write), so split per capability: the scoped job token for the issue/comment, the PAT for the
  dispatch.
- **`gh run view --log-failed` is empty until the run COMPLETES, and afterwards may carry only cleanup.** While a run
  is in progress every `--log*` call answers "still in progress; logs will be available when it is complete" — read the
  job's STEP list instead (`gh run view <id> --json jobs --jq '.jobs[] | select(.name=="<job>") | .steps[] | "\(.name): \(.status)"'`)
  to see which step is running and how long it has been there, and only read logs once it completes. Once it
  is done, `--log-failed` frequently prints the post-job cleanup tail, so grep the FULL `--log` for `FAILED tests/`,
  `[0-9]+ failed,` and `make\*\*\* Error` rather than trusting the tail. A run whose jobs read green while the run is
  red is a `needs:` cascade: read `gh run view <id> --json jobs` first, then the failing job's own log.
  **A job log containing terminal escape sequences is REFUSED by `gh`, not missing:**
  `gh api repos/<o>/<r>/actions/jobs/<job-id>/logs` exits non-zero with "the response contains terminal
  escape sequences; pass --allow-escape-sequences", and a `2>/dev/null` turns that into an empty file
  that reads exactly like "no log yet". Read a job with
  `gh api …/actions/jobs/<id>/logs --allow-escape-sequences > /tmp/j.log`; `gh run view --log` is often
  empty while the per-job endpoint has the whole thing.
- **Prove a red is NOT yours before touching anything.** Two PRs (or both OS jobs of one PR) reddening on the SAME
  test at the same minute, while `git diff --name-only origin/<base>` on your branch names none of that code, is
  upstream drift — reproduce the case locally on the same branch to confirm, then file it as its own issue quoting the
  upstream value. Live-Hub / live-registry cases that pin an exact upstream filename or a measured t/s do this every
  time upstream renames or re-measures; the fix belongs to that issue, not to the PR you are holding, and a re-run
  will not clear it.

## Support files

- `references/github-actions-credentials.md` — the two silent no-ops (a fork `pull_request` run with no
  repository secrets, a PR opened with `GITHUB_TOKEN` that starts no workflows): diagnosis from the job
  log, the `workflow_run` fix shape with PR resolution, the per-write token split, and the rules for a
  deferral that stays visible on the PR.
- `references/repair-bot-triggers.md` — how a repair (fix) bot is woken and bounded: the `workflow_run`
  trigger and its failure-only condition, resolving the failed run's PR, the failed job's log as repair
  context, per-head attempt counting, the `UNVERIFIED` push path, and the trigger-frequency diagnostics.
- `references/leg-shell-safety.md` — the shell seams of a make-invoked leg or probe: the `$(call)`
  comma truncation and its `make -n` proof, `pipefail` + early-exiting readers (SIGPIPE 141), brace
  expansions swallowed by a `{placeholder}` template, and why a cold-start cost belongs in a warm-up
  step instead of a widened per-case timeout.
- `references/agent-leg-prompts.md` — the prompt as a contract for a detached model run: the unattended
  rule and its exact wording, the exit-code map (`3` = detached because input was required), how to name
  that code in the failure step, the project-skill seam that replaces N inline rulebooks (layout, `-s`
  preload, registration through the Hermes CLI and its read-back, the gate's finding table, the pointer
  budget), and the textual tests that keep every leg carrying the rule.
- `references/workflow-change-contracts.md` — the contract suites a bot/workflow change is gated by
  (credential allowlist, round/wall-clock arithmetic, generated dispatch table, the dispatch guard job, the
  trailing-newline lint), each with its symptom and fix, plus the five-second pre-flight to run before
  pushing instead of learning it from a 12-minute pipeline.
- `scripts/fleet-audit.sh` — read-only fleet audit: every workflow's last N runs and conclusions, then the
  decision lines of each workflow's newest run, so "is this bot acting?" is answered in one pass
  (`REPO=owner/repo LIMIT=5 scripts/fleet-audit.sh`).
- `references/alarm-design.md` — designing an alarm for a scheduled fleet: the five silence states and
  which reader sees each, the artifact-age alarm (timestamp-in-the-name, not mtime; newest scheduled run
  reported so "never started" differs from "ran and produced nothing"; a window shorter than N is not a
  failure), roster derivation that cannot pass vacuously, and the falsification protocol for a new guard.
- `references/failure-classes.md` — symptom → mechanism → fix for the bot defects that recur
  (lazy mergeability, claim-vs-done markers, `make` on a conflicted Makefile, masked gate chains,
  lost writes, fork heads, budget-less agent legs, a base re-asserted after the work exists, a
  rebase with no committer identity, a run that goes red over work someone else finished, a
  generated artifact left stale by a merge, a data guard red on a pinned/shrunk figure or on a
  whitelist), a red inside a gate step whose real cause is the runtime image BUILD (including the uv
  universal-lock that breaks it), plus gate failures that are not the bot's behaviour and the test
  shapes that actually hold.
- **A data-merge rule a bot's PR is red on** (an "additive only" field that must be raised, never
  pinned or shrunk) belongs to the pipeline umbrella, not here: its `additive-merge-semantics`
  reference covers it. A refresh bot's `validate` failure is often the merge rule, not the bot —
  read the failing module's own output line before touching the workflow.
