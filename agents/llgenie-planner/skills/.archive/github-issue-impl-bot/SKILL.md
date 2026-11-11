---
name: github-issue-impl-bot
description: "Use when a bot implements a GitHub issue and opens a PR."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [ci, github-actions, issue-bot, hermes, llm, automation]
    related_skills: [pr-fix-bot, hermes-headless-ci, github]
---

# Issue-implementation bot (Hermes headless)

## When to Use

Wiring or debugging a bot that, given a GitHub issue, runs an LLM (Hermes CLI
headless) to implement it in a container, then pushes a branch and opens a PR.
Distinct from `pr-fix-bot` (which RE-PAIRS an already-open failing PR): this bot
CREATES the PR from an issue. Reference implementation:
`andyholst/trending-local-llms` (`issue-bot.yml`, `scripts/issue_bot.sh`, the
`implement-issue` make recipe) + its `tests/test_workflows.py`.

## Loop shape

1. **Pick ONE issue per run** (a 6-hour schedule sweep, or dispatch by issue
   number). Guard against two implementers racing on the same issue — one
   implementer per issue.
2. Gate on the issue's label (e.g. only `implement`-labelled issues proceed); a
   sweep run on an unlabelled issue just fires and reports "skipped" — the gate
   is what keeps the bot from implementing every filed issue.
3. Checkout the issue-titled branch off the default branch; run the LLM
   implement step in the test container (`make implement-issue`).
4. Commit, then **push with an owner-scoped PAT** (`FIXBOT_DISPATCH_TOKEN`), not
   `GITHUB_TOKEN` — `GITHUB_TOKEN` creates a PR whose `pull_request` run never
   starts. The dispatch trigger must not use a `workflow_run` trigger (bot-pushed
   commits don't re-trigger; explicit dispatch is the way).
5. Open the PR **ready for review — NEVER `--draft`**. A draft is excluded by
   the squash+auto-merge gate (`pull_request.draft == false`), so a draft run
   is valid, green and permanently unmergeable while it reports success; a
   "holding for review" change is the ready PR plus the required checks, never
   the draft flag. Put `closes #<issue>` in the body.
   Reference the issue in the PR
   body; keep the issue/PR/facts aligned (the repo's AGENTS.md is the referee).
6. Monitor the pipeline YOU created until it settles; squash+auto-merge to one
   Conventional Commit on approval (no review yet -> don't squash).

**Deliver the PR as soon as the change is green enough for CI to referee.** Once the
affected tests and gates pass locally, commit, push and open the PR — do not keep
iterating on local verification. The PR is the deliverable, and CI is the authority
for the full suite. Run the full suite in the background while you push, or let CI
run it, but do not block the PR on a long local run.

### Keep the decision ahead of the implementation, and keep repair out of this job

The `implement` / `refine` / `close` verdict is worth its own leg BEFORE the implement step rather
than a decision the implementer reports afterwards: a `refine` or `close` then costs minutes instead of
the hour an implementation run takes (measured: ~60 min for a single implement step, on both a bot
that decides first and a sibling that decides inline).

Keep the PR repair loop OUT of this job. A job that implements, then repairs its own PR, spends its
whole 120-minute budget in one place with no independent referee, and duplicates whatever bot already
owns repair (`pr-fix-bot`). If a sibling repo folds decide+implement+fix into one job, copy only its
cheap half: a seconds-long gate BEFORE the push (`lint`, docs coverage, wiring, workflow validity, PR
hygiene, openspec-tasks). That catches the reds bot PRs actually arrive with — bookkeeping, not logic —
without a second repair path and without touching the budget.

## A bot leg's contract belongs in a Hermes project skill, not in the prompt string

When a leg's rules live as one inline `hermes -z "…"` argument (or a `*_rules.md` concatenated into
it), move them to `<repo>/.hermes/skills/<name>/SKILL.md` and preload them with
`hermes -z "<pointer naming the input/output/parameters>" -s <name>,bot-unattended`. The shared
unattended contract (never ask, never wait; exit 3 means "asked for input") goes in ONE skill every
leg preloads beside its own, instead of being pasted into each prompt.

- **Register the directory with `skills.external_dirs`, not project trust.** `trusted_project_dirs`
  needs a recent CLI; older pinned `hermes-agent` releases resolve no project skills and the leg then
  runs with NO contract while reporting success. `external_dirs` works across versions and needs no
  cwd — register the mount path the leg runs in (`/repo/.hermes/skills`) at image build time and read
  the value back.
- **Write the key through the CLI, then READ IT BACK — do not hand-roll a YAML writer.** The
  value's shape varies by version: a newer CLI refuses a bare string ("must be a list") and stores a
  JSON array as a real list; an older one stores `'["/x"]'` as an opaque STRING that resolves to one
  non-existent path. So pass a JSON array (`hermes config set skills.external_dirs '["/repo/.hermes/skills"]'`)
  and prove it landed by reading it back (`hermes config get skills.external_dirs` prints `- /repo/…`
  per entry, or `[]`), which is the same assertion the setup should ship as `--check`. The tempting
  alternative — editing `config.yaml` directly — needs PyYAML, and a repo's Python often has none
  (its requirements are the app's deps, not Hermes's), so the hand-rolled writer dies with
  `No module named yaml` inside the very image that was supposed to be provisioning itself. Keep the
  script idempotent and exit 2 on a missing CLI or directory, never a silent pass.
- **Register at SETUP time, not only in the image build.** A published base image is rebuilt only
  when its Dockerfile hash changes, so an image built before the seam existed carries no
  `external_dirs` while the repo mount does — every leg then preloads nothing and still reports
  success. Put the registration (and the read-back) in the target every leg runs first
  (`make _setup`), and prove it by running that target in the OLD published image with the new tree
  mounted and reading `hermes skills list --source local`: the skills must appear as `external`.
- **Prove the load, do not infer it.** `agent.skill_commands.build_preloaded_skills_prompt(names)` is
  the function `hermes -z … -s` calls before the first turn: it returns
  `(prompt_text, loaded, missing)`. Feed each leg's `-s` list against a home registered by the same
  script and assert `missing == []`, the preload preamble is present, and each skill's `description`
  appears in the rendered prompt. Negative case: an unregistered home returns everything missing.
  Run it where hermes-agent is importable and FAIL loudly when it is not — never skip.
- **Update the tests that pinned the old prompt text.** `grep -rn` the test tree for the retired
  phrases; each assertion becomes "the leg preloads the skill AND the skill file carries the rule".
  Deleting them drops the lock the rule was bought with.
- Keep a structural gate (a leg with no `-s`, an unknown name, a frontmatter/directory mismatch, a
  prompt over a pointer budget, a skill nothing preloads) in the unit stage, with each failure shape
  proven RED against a fixture tree.

Depth (llgenie's implementation, the `bot-unattended` skill, registration script and the live proof):
skill `llgenie-engine-image-ci`, `references/agent-skill-legs.md`.

## When asked to "fix" a PR, check it is not already merged first

A request to "work with PR #N and fix it" often names a PR that has already
merged. Before treating it as open work, read its state: `gh pr view <N>
--json state,mergedAt,mergeCommit`. If it is MERGED, the actionable work is
NOT the PR — it is the follow-up issues the PR's own `Not covered` section
filed (each is a first-class, linkable issue by the repo's out-of-scope rule).
Read that section, list each named issue's state, and route the work there.

- **A merged PR's `Not covered` items are the real queue.** The PR body names
them by number; check each one's state (`gh issue view <N> --json
state,closedAt`) and whether a later PR already closed it. Do not re-open or
re-implement a follow-up that a merged PR already landed.
- **Distinguish a code defect from a maintainer decision.** A follow-up whose
body ends by asking the owner to pick among named options ("Please pick one
rather than leaving the queue unowned") is a DECISION, not a bug to fix —
implementing one option unilaterally is out of scope. Surface the decision and
the options to the user and let them choose; only a follow-up with a concrete
"Done when" that is a real defect (e.g. a test that matches substrings instead
of the decision) is safe to implement directly.
- **Verify the issue↔PR linkage before claiming alignment.** The merged PR's
`Not covered` must name each follow-up by number, and each follow-up must link
back to the PR/issue it came from. A follow-up that does not trace back is a
workflow defect to flag, not to assume.

## A protected rulebook edit is a BLOCKER, not a retry

The repo's own rulebook (AGENTS.md) can be file-protected so an edit routes
through a human approval gate that times out on an unattended run — not a
prompt-wait you can answer in the moment. When a change owes the rulebook a row
or a sentence by the repo's own rules (a new validator guard, a new rule), that
write is REFUSED even though every other file in the change edits fine. The two
wrong moves both silently leave the PR self-inconsistent: retrying the write in
a loop, and routing around the protection (a second file-edit mechanism, a
"run as root" escape, hand-editing by another path). Treat the refusal as a hard
blocker the first time it happens:

- Record the owed edit's EXACT intended text and the fact the write was refused
  in `findings.md` (the analysis file an implementation must ship), so nothing
  is lost and the gap is named.
- Post the rule-mandated disclosure on the issue (e.g. the repo's rule that an
  AGENTS.md change must be announced and is review-required) and say flatly that
the write is blocked on the protected path.
- Report it to the owner as "needs a consented run or a manual apply", not as
done. A green PR whose rulebook now contradicts it is still incomplete — say so.
- **Attempt the rulebook diff ONCE per change before declaring it owed.** The gate
  can be granted — sometimes later in the same session, sometimes in a follow-up
  run — so a write pre-deferred on the first refusal leaves prose that is out of
  date the moment the rows land. What must never happen is a LOOP re-attempting
  the same write inside one run.
- **An owed-row BACKLOG is one batched change, not N.** Verify each owed issue's
  exact text against the CURRENT file before touching it (a later rule often
  already carries it, so some are closeable with that row as the evidence), write
  the survivors in a single branch, and bind every issue with its OWN
  `Closes #<n>` line — a chained `Closes #a and #b` closes only `#a`. Leave an
  issue open when its own body does not name the target (which §, which row,
  which test): writing that row would be a guess, and a guessed rulebook row is
  worse than a missing one. Depth: `containerized-ci-pipeline`,
  `references/cron-delivery-and-bot-queues.md`.
- Every future implementation in the repo hits the same wall: once refused,
  surface it once and move on; never burn the run re-attempting the same write.

## Verify the issue is still live BEFORE implementing it

When asked to work a queue of open issues one at a time, do not trust the list:
map open issues to open+merged PRs programmatically (`gh issue list --state
open` joined to `gh pr list --state all` by the issues the PR bodies close),
then confirm each "no PR yet" issue's claims still hold against the CURRENT
tree before starting. An issue filed against earlier code is frequently
already fixed, duplicated by a later one, or carrying evidence a merged commit
invalidated. Re-derive the queue each time rather than reusing yesterday's —
filter by head commit, and `git fetch` the base right before each cut (rule:
base asserted, never assumed).

- **A freshly filed `agent:implement` issue can be implemented and merged by the repo's own bots
  within hours.** Re-read `gh issue view <n> --json state` and the open+merged PRs before you start
  work on it: the chain picks labelled issues on its own schedule, so a queue built from yesterday's
  `gh issue list` is a report, not a work item. The same staleness applies to the tree: answer "does
  X exist in the repo?" from `git fetch origin main` + `git show origin/main:<path>` /
  `git grep <symbol> origin/main`, never from the working checkout — with auto-merge landing
  continuously the checkout is routinely many PRs behind (a whole `.hermes/skills/` tree was missing
  locally while `origin/main` already carried it), and a missing directory proves nothing.
- **Issue↔PR linkage is by `closingIssuesReferences`/pr-closure, never by
  "the body mentions #N".** A merged PR whose body merely CITES an issue (a
  refresh PR referencing its tracking meta-issue) shows up as "this issue has a
  PR" under a body-text scan and hides the real absence. Query the issues each
  open+merged PR actually closes, then the inverse is honest.
- **A subagent's structured verdict is not recoverable from its logs.** The
  live-transcript truncates a subagent's JSON result (`…(+N chars)`) and the
  delegation manifest holds only goals/status — the machine-readable verdict is
  gone once delivered. Either keep what you ask for compact enough to survive
  the cap, or re-derive the verdicts against the tree yourself (the decisive
  check) rather than trusting an unrecovered log as evidence.

## A coverage/classification guard surfaces gaps the issue did not inventory — fold them in

When an issue asks for a coverage/inventory guard ("every X is PR-exercised or names a test that covers it"), run the new guard against the REAL tree before finalizing and EXPECT it to flag entries nobody had classified — the issue often under-scopes which instances exist (a workflow that is dispatch-only in a way the issue never named, a model with no measurement). Those findings are the guard earning its keep, not over-strictness: fold the found entries into the manifest/coverage map (naming the test that covers each) rather than weakening the guard, and report them as real gaps the issue had missed. Let a new guard's first real-tree run be part of the deliverable, not an embarrassment to suppress.

## Triaging a tech-debt backlog: verify by RUNNING, never by reading

When asked to "look over the open tech-debt issues and see if they still make
sense, one at a time", each body is a hypothesis about code that has moved.
Do not trust it — RUN the claim against the freshly fetched tree and classify
each issue by what the run shows:

- **Still stands** → keep it open; it is the real queue.
- **Already fixed** → close it, citing the commit/PR that fixed it as evidence
  (a merged commit may have invalidated the premise).
- **Premise no longer true** (the environment changed — a dependency now
  present, a path that moved) → close as not-planned, naming what changed.
  This is a legitimate close, not a dismissal.
- **Stale but the underlying gap is real** → retitle to current reality and
  re-measure the claim rather than closing; a title that names an obsolete
  mechanism sends the next implementer at the wrong target.

Then implement the survivors as tracked OpenSpec changes, each with a guard
proved RED before shipping. The RED proof is the load-bearing step: mutate the
code to the exact failure shape the guard exists to catch, confirm the test
FAILS, then revert and confirm it passes again. A guard never seen red may be
vacuous — it can pass on the defect it claims to prevent (a marker-word
assertion `"closes #" in body` stays green for the chained `Closes #a and #b`
body the guard exists to refuse). Feed the guard's own parser the two real
failure shapes, not just the happy path.

### Make the triage decision deterministic, and prove it with a mock item per verdict

An LLM prompt that says "re-check the issue against the fetched base" is not a
control. The decision has three outcomes — implement / refine / close — and each
needs a mechanical gate plus a fixture that drives the REAL script:

- **Gate the verdict on TREE evidence, in both directions.** A `close` or
  `refine` verdict whose `EVIDENCE:` block names no `path:line`, no checkable
  path and no `make` / `python3` / `gh` command is REFUSED (exit 2, the item
  untouched). Without it a lazy close buries a live gap and a lazy refine parks
  one; a prose-only "it is old and probably fixed" must fail, and the refusal
  text must say what a citation looks like.
- **One item per run is the HEAD of one oldest-first order**, never "all
  candidates". A multi-label queue needs one `gh issue list --label X` call per
  label (`--label a --label b` is an AND), unioned **by item number** and sorted
  by `createdAt`, so the labels compete on age instead of on read order. Any
  item with an implementer branch — or an OPEN PR from such a branch — is
  dropped from the queue entirely, not listed as held.
- **Prove it with one mock item per verdict, only the external CLI stubbed:**
  implement → nothing applied, no label, no close; refine → ONE restatement plus
  the refine label and never a close; close → closed plus the closed label;
  prose-only evidence → refused for `close` AND `refine`. Never monkeypatch the
  decision function itself — such a test stays green when the function is
  deleted, which is the whole failure it was meant to catch.
- **File the issue first, then name the branch from the number it RETURNS.**
  `gh issue create` prints a number that is regularly one off the one you
  expected (another create or a PR consumes it), and a `pr-closure`-style guard
  binds branch → issue: a branch named from a guess closes the wrong issue or
  fails the guard, and the rename also drags the proposal/findings text.
- **A cogwheel-only fix (a second cron slot, a delivery alarm) is its own
  change**, because the cron runtime is not the queue logic; depth in
  `containerized-ci-pipeline`, `references/cron-delivery-and-bot-queues.md`.

### Assert the base ONCE, and adopt + rebase instead of re-asserting at commit time

The base assertion that protects a run at its START is a data loss at its END. The run spends
20–30 minutes implementing while the merge bot keeps landing PRs, so the commit step must NOT
re-check `HEAD == fetched origin/<base>`: that refusal (`REFUSED: STALE: this checkout is NOT the
freshly fetched origin/master` → `make: *** Error 1`) throws away a finished implementation with
no commit, no push, no PR and no artifact. The shape that holds:

- **adopt** at commit time — cut the branch from the CURRENT `HEAD` (carrying the agent's
  uncommitted edits) or attach it on a re-run, and report `behind_base=N`;
- **commit**, then **rebase** onto the freshly fetched tip; on conflict `git rebase --abort`,
  keep every commit, print the conflicted paths, and exit a distinct code the caller treats as
  "push anyway" — the PR then carries the conflict and the fix loop resolves it;
- keep the start-of-run assertion where it belongs (a `base-check` step before any work), and
  keep an `advance` (fast-forward a clean checkout) for fan-in jobs that wrote nothing.

Each step of the pair also needs a stub `make` in the workflow test that maps the NEW target name
to the real script — a stub that derives the script's subcommand from the target name silently
calls the wrong mode for a renamed target and reds five unrelated checks.

### A verdict of "implement" with no file changes is not automatically a failure

That signature means either the agent failed (dead key, burned budget — keep it RED) or somebody
else finished the issue mid-run, which is routine when a merge bot is landing PRs: the sweep can
pick an issue and have its PR merge and close it minutes later. Ask the issue's state through ONE
seam before declaring red — `0 = open` (red), `4 = closed` (**GREEN**, with one
marker-deduplicated comment saying it was closed in flight), `2 = unreadable` (**red**; a state
you cannot read is never evidence). Never collapse 2 into 4, and read it from `gh issue view <n>
--json state`, not from the run's own verdict file.

## Challenge the issue's stated fix before implementing it

An issue's "Done when" is a hypothesis, not a spec. When the proposed mechanism
(the boundary, filter, watermark, migration) would break a writer or reader the
issue did not inventory, the fix as written is UNSOUND and must not be shipped
literally. The classic tell: a data file whose NAME embeds a UTC timestamp but
which a repair step rewrites IN PLACE keeping that name — e.g. an ingestion
"merge only files newer than X" boundary keyed on the filename timestamp. A
repair pass and a converge-by-remerge loop both depend on re-reading files
whose content changed while the name/timestamp froze, so the timestamp boundary
silently drops their corrections (and can stall the repair loop from ever going
green). Before touching the core ingest/merge path: trace (a) every writer
that mutates the target files and whether it preserves name/timestamp, and
(b) every reader that must re-read a changed file to converge. If the proposed
boundary drops corrections or stalls a repair loop, STOP and surface the design
conflict to the owner with a SOUND alternative (an explicit per-file
content/mtime fingerprint that changes on rewrite — not a timestamp frozen at
creation) and let them pick the approach. Do not implement the unsound version
and do not silently swap in your own design; report the conflict and the
options.

## A contract field the store already violates cannot be narrowed to an enum

A tech-debt issue that asks to tighten a contract field (a `string` the docs describe as an
enum — e.g. `vram_tier` documented as six capacity categories but declared a bare `string`)
meets the repo's additive-only rule: an `enum` REJECTS the existing store, and a change that
makes current data fail is forbidden. Do not ship the enum. The honest first step is a
**report-only check** that makes the drift visible and never fails a run:

- Print the field's distribution and name the defect shapes — a unit-less value is the same
  category misspelled (`48` is `48GB`), a value outside the documented categories is a
  measurement wearing a category's hat (`9GB`), and a value that is a different KIND of state
  (`CPU`) is deliberately NOT flagged — that is the contract decision, filed as its own issue,
  not a red build.
- Normalise only the LOSS-LESS spellings in the store (a bare `48` → `48GB`); leave the
  real-information values (`9GB`) alone and let the report surface them for a human.
- A report-only check is still a real guard: register it under a stage and select that stage
  with a make target (rule 6d), and prove its test RED (the check missing → the guard fails
  naming it) and GREEN.
- When the data change also needs the README re-rendered, use the repo's dedicated
  `make render-readme` target so the change carries the cell text and `check_no_value_loss`
  stays green — a docs/template change no longer forces store churn.

## The workflow-scope token rejection (PITFALL)

A PAT without **`Workflows: Read and write`** (classic PAT: the `workflow`
scope) cannot push a change that touches `.github/workflows/**`. GitHub rejects
it at the push AFTER the commit already landed locally — and the committed work
dies with the short-lived CI runner unless you preserve it. The rejection is
authorization, NOT a data/CI problem.

- **Fail loudly, don't fake green.** Detect the rejection, comment on the issue
  naming the exact missing permission and the token to fix, and leave the run
  RED on purpose. Never report success on a push that was refused.
- **Never throw the agent's work away.** On this rejection, write
  `git format-patch HEAD~1` to `issue-implementation.patch`, upload it as a CI
  artifact, and tell the owner to `git am` it once the permission is granted.
  ~30 minutes of agent work surviving the runner is the difference between that
  issue being cheap to finish and being fully redone blind.
- **Strip scratch artifacts before any push** (`git rm --cached '*.patch'`,
  `.rej`, `.orig`). A change that only ever lives in a `.patch`/`.rej` file is
  not an implementation — do not let it reach the remote.

### Beyond the push: the writes a bot leg makes at RUN TIME are a second, narrower token surface

`Resource not accessible by personal access token` raised at a bot leg's FIRST
write is a SCOPE verdict, not a code bug. One PAT can push branches and comment
on PRs while being denied **`Issues: write`** (`addComment` on an issue — a
claim comment, a verdict comment, a label) and **`Actions: write`**
(`POST /actions/workflows/<id>/dispatches`, i.e. a sweep dispatching the repair
workflow). Either refusal makes that leg red at its first step on EVERY run, so
the pipeline reads as flaky instead of broken.

- Diagnose before touching code: read the workflow's `permissions:` block
  beside that step's `GH_TOKEN:`.
  `gh run list --workflow <w>.yml --limit 5 --json databaseId --jq '.[].databaseId'`
  then `gh run view <id> --log-failed | grep -E "Resource not accessible|403"`
  names the exact capability (`addComment`, `/dispatches`) and therefore the fix.
- When the job already declares `issues: write` (a `permissions:` block on a
  `GITHUB_TOKEN`-backed job), the write should go through `github.token` and the
  owner PAT should be reserved for the PUSH — the repo often already holds a
  credential that can make the write, and the leg just does not use it.
- Widen the PAT only as a deliberate, documented change (the required scopes
  written in the workflow comment), never as a silent fix buried in a recipe.
- Lock the pairing in a test: the fake-`gh` argv assertion for the write plus
  the workflow's `GH_TOKEN:` value for that step. A leg that lacks the
  capability should fail in seconds, naming the missing scope, instead of after
  a 20–30 minute model call.
- **`git push` does not use `GH_TOKEN`.** It uses the credential
  `actions/checkout` persisted into the remote URL; `GH_TOKEN` only
  authenticates the `gh` CLI. A pushing job is therefore safe when its checkout
  was handed the PAT even if the step env says `github.token` — and a test that
  asserts the push credential must look at step env, job env **and** the
  checkout step's `with.token`, or it reds correct code.
- **Verify the fix with a REAL dispatch from the branch, not just a green unit
  test.** `gh workflow run <bot>.yml --repo <o>/<r> --ref <branch>`, then read the
  run and the artefact the leg exists to write (a claim comment, a review, a
  report). A leg that failed at its first write on every schedule turns
  `completed/success` and its posts appear on the issue — that is the evidence;
  "the step no longer 403s" is not.
- **After the fix merges, dispatch once more on `--ref main` — and never count a
  scheduled failure that predates the merge as disproving it.** Merge and failure
  timestamps are the whole argument: read `gh pr view <n> --json mergedAt` beside
  each failing run's `createdAt` before touching code again. A run that died at
  its first write 20 minutes before the merge landed is the OLD workflow; the
  same leg dispatched on `main` afterwards finishing `completed/success` with the
  comment/review on the issue is the proof.
- **Adding the bot's trigger LABEL is the dispatch — do not also `workflow_dispatch`.**
  `gh issue edit <n> --add-label <trigger>` fires the `issues: [labeled]` run at once;
  dispatching the workflow on the same issue queues a SECOND run behind it (the
  concurrency group does not cancel). Pick one, or cancel the queued duplicate with
  `gh run cancel <id>` the moment you see two runs for one issue.
- **A bot leg's first end-to-end exercise is worth the run.** When a leg has never
  reached its later steps (nothing was ever labelled, no PR ever needed repair),
  measure what has actually run: read the job's per-step conclusions
  (`steps[] | "\(.number). \(.name) -> \(.conclusion // .status)"`) and report the
  boundary honestly — "steps 1-9 success, implement in progress" is a verified
  claim; "the bot is green" is not.
- After switching a step's token, grep the test tree for the old literal: an
  existing test that pins `GH_TOKEN == '${{ secrets.BUMP_TOKEN }}'` for that step
  will red the suite, and its update must carry the new rule (token **and** the
  declared permission), not merely the new string.

### A green scheduled run is not a working bot

`completed/success` means the job exited 0, not that the bot did anything. When
asked "are the bots working?", produce per leg: the last N conclusions, the
leg's own decision line, and whether the write it exists to make is actually
visible (a comment, a dispatched run, an opened PR).

- `gh run list --workflow <w>.yml --limit 5 --json status,conclusion,createdAt`
  first — a leg that fails on every schedule is invisible in "the bots are up"
  and obvious here.
- For a `success` run, read the decision lines (`action=none`,
  `[sweep] skip #N …`, "no open PR needs rebasing"): a no-op and a working leg
  are identical in the conclusion column. A sweep that skips every candidate
  for a STRUCTURAL reason (every PR head lives on a fork) reports success
  forever while repairing nothing.
- A `skipping` row in the checks table is a planned matrix skip, not a job —
  never count it as a failure or as coverage.
- Anything not exercised end to end is reported as **unverified**, never as
  working: split the answer into what the run proved (a live model call, a tool
  call, a credential visible in the agent shell) and what is still blocked,
  naming the blocking issue per bot.

## A bot PR can be a STUB: assert a real diff before you review its content

Read the SHAPE of the diff first, its content third. A bot PR whose entire diff is one orchestrator
scratch file (a verdict line like `TRIAGE: implement`) is not a small change — it is a **failed run
wearing a green pipeline**, because every downstream gate judges only the files that are there.

- **Open with** `gh pr view <N> --json additions,deletions,changedFiles,files` then `gh pr diff <N>`.
  A diff that touches none of the code the issue's acceptance criteria name is a stub: report that
  the issue is still unimplemented and close the PR instead of reviewing it.
- **`closes #<issue>` on a stub is worse than no PR at all.** Merging it closes the issue having
  done nothing, so the issue's state stops being evidence about the code. Never leave one open
  "for review".
- **`git add -A` in the commit step stages the run's own scratch.** A triage/verdict step that
  writes a file at the repo root leaves it in the tree; a reset list naming only SOME of them
  (`git reset -q -- issue.md`) lets the rest in. Stage explicit paths, or reset every scratch file
  the run writes, and `.gitignore` them so a stray is never stageable.
- **The leftover scratch defeats the "nothing to push" branch.** `git diff --cached` cannot be
  quiet while a scratch file is staged, so a no-op implementation still pushes a one-line branch
  and opens a PR. Assert the staged paths include a real (non-scratch) change before `git commit`.
- **The implement recipe's `rc=0` is not proof of work.** An agent that exits 0 having changed
  nothing sets `implemented=true`, which SKIPS the "fail loudly when the implementation did not
  happen" guard — so that guard must key on a non-scratch file change, never on the exit code.
- **A placeholder PR body passes a "non-empty body" hygiene check.** A default `--wants` sentence
  ("verification notes land on the PR as CI runs it") carries no `Issue:`/`Fix:`/`Benefit:`; a
  guard that only rejects EMPTY bodies stays green. Reject the placeholder too, or derive the body
  from the run's facts.
- **Diagnose the missing work from the RUN, not the diff.** `gh run view <run> --json jobs` → read
  each step's conclusion, then the redacted transcript tail (`--log-failed`, or the scrubbed
  artifact). An `implement` step that succeeded plus a commit step that pushed one file means the
  agent's work went somewhere else — find where it wrote before re-running anything.

### The agent's worktree escapes the container's bind mount

A repo whose `AGENTS.md` mandates `git worktree add ../<repo>-wt/<name>` is a trap for an agent
running inside `docker run -v "$CURDIR":/repo`: `../` from `/repo` is OUTSIDE the mount, so the
worktree and its commit live only in the container's writable layer and `--rm` destroys them. The
host checkout then holds just the scratch files — exactly the stub above. Resolve the conflict the
prompt may not leave ambiguous: either tell the implement agent the mounted checkout IS the repo
(work in place; do not create a worktree or a branch) or place the worktree INSIDE the mount
(`/repo/.wt/<name>`, gitignored), and assert the implementation landed in the mounted tree before
committing. A bot run whose transcript says "committed at <sha>, nothing pushed" is this failure,
not a scope rejection.

### Fixing these defects: five remedy shapes

Diagnosing a stub bot PR is half the job; these are the code shapes that close each defect. In every
one, success is DECLARED FROM THE TREE, never from a process exit code:

- **Measure the implementation from the tree.** A `changed` subcommand reading
  `git status --porcelain --untracked-files=all`, ignoring the run's own inputs, printing
  `changed=true|false`, and exiting 2 when git cannot read the tree. Gate BOTH the push step and the
  fail-loud step on it, and delete the `implemented=` flag derived from `rc`.
- **Ignore the run inputs, never reset them.** Every file a leg writes at the repo root goes in
  `.gitignore`; delete any `git reset -- <file>` denylist. Lock it with REAL git: `git -C <repo>
  check-ignore -q <name>` per name, plus a throwaway repo holding the same `.gitignore` where a
  written scratch file must not appear in `git status --porcelain`.
- **Build the PR body from the run and refuse a thin one.** The implement step writes `pr-body.md`
  with `Issue:` / `Fix:` / `Benefit:` / `Technical:`; the opener validates each part is non-empty and
  that `#<issue>` appears, appends the pushed commit's `git show --stat`, and exits BEFORE any `gh`
  call when the file is missing or thin. A source-level "body is non-empty" check cannot see a
  runtime-built placeholder — the rendered check belongs in the unit suite.
- **One write, one token, and the DENIABLE write first.** `_gh(..., token=)` sets `GH_TOKEN` for that
  child process only; post the issue comment with the issues-scoped token, then create the PR with
  the PAT. Ordering is part of the fix: a token that cannot comment then costs a comment attempt
  instead of a PR nobody has claimed. Prove the routing with the real `gh` and a bogus per-call token
  (401 = the token reached the child, an ambient credential would have answered).
- **A live-network test belongs outside the gate.** Move it by exact node id into the roster's
  `deselect` plus a dedicated `make <name>-live` target (never a `-k` expression), keep the hermetic
  half of a mixed test in the gate, and remember `faulthandler_timeout` only PRINTS a dump — a
  five-minute stall still reports `passed`.

Running several of these in one session: `references/multi-pr-batch.md`.

### A detached run that left work behind is SALVAGED, and a red loop reds the RUN

A preloaded `bot-unattended` skill reduces the `Input required; detached without cancelling` (rc=3)
failures but does not eliminate them: a model can still call `clarify` once, including AFTER doing
the work. Two rules make that survivable and honest:

- **Never key "was there an implementation?" on the exit code.** Read the TREE
  (`git status --porcelain`, which ignores the gitignored scratch the run writes) and report
  `dirty=true|false` from it. Then let the commit/push/PR steps run on `rc == 0` **or** `dirty`, and
  keep the "fail loudly" step from firing when the tree was salvaged — a finished change lost to an
  unanswered question is the same loss as a rejected push. A CLEAN tree with rc=3 stays red
  ("the agent asked for input"): there is nothing to review, and a green no-op over no work is a lie.
- **A captured loop result with no consumer is a green run over a red PR.** When the job runs its own
  fix loop, captures `green=false`, and exits 0 so the outcome comment can post, nothing else reads
  that output: the run reports success while the PR sits unmergeable. Add a terminal step gated on
  `steps.loop.outputs.green == 'false'` that exits 1 and names the PR, and assert in the workflow
  test that the step exists, its condition is exactly that output, and its body really exits
  non-zero.
- **Leave the lifecycle finished in the same session.** A gate that reds the PUSH to the base branch
  ("an ACTIVE change names a MERGED PR" → archive it, a stale generated index) has no PR repair path
  reaching it: the merge that triggers it is the last step anyone watches. Archive the change and
  regenerate the index in the same session the PR merges, or the base branch stays red and blocks
  every following PR.

## Verify the bot's PR before you finalize it

An implementer bot produces a *plausible* PR; the gaps are conventional, not logical, and a
rebase onto current `main` is what exposes them. Check every one, then amend them into the bot's
single commit (keep its authorship) rather than opening a follow-up:

- **A design flip reds the tests that pinned the old design — that is the suite working, not a flake.**
  When a change replaces a mechanism (a prebuilt image becomes a source build, an inline prompt becomes
  a preloaded skill, a hand-rolled path becomes a generated one), grep the test tree for the retired
  literals (upstream image names, `/app/<binary>`, the old prompt phrases) and rewrite each assertion
  to the NEW contract — never delete it, or the lock the test was bought with is lost. A unit job that
  reds immediately after such a change is the suite encoding the old design; fix the assertions, not
  the code they now correctly reject.
- **Verify the replacement by RUNNING it, and paste the real output.** Build the artifact, run the
  target, report the actual line that proves it (an image tag, a `commit <pin8>`, a flag verdict).
  Reading the generated file, the params JSON or the diff is not evidence, and "it should work now"
  is rejected — say which actor performs the step (CI, not an agent) and show what it produced.
- **A coverage claim is a per-cell table on the issue, never a sentence.** When the change claims
  every member of a matrix (engine × arch, workflow × input, model × measurement) is built and
  verified, post one row per cell with its state and its evidence, and keep the states honest:
  `verified` (image tag + the `commit <sha>` the binary printed), `failed → fixed in <sha>` for a red
  the run actually FOUND, `in flight` for a row it had not reached. An all-green summary written
  before the run settled is the failure shape; the ticket asked for the permutations, so the table
  IS the answer.
- **Reconcile a derived table against the matrix total before publishing it.** Parse the run's own
  result lines and map the ARTIFACT name to the source id first — an image is `llama-cpp` where the
  engine id is `llama.cpp`, and that mismatch silently drops rows (a table that reported 9 verified
  where the log held 18, then under-reported the very coverage it existed to prove). Assert
  `verified + failed + in_flight == rows in the matrix` before posting, and let the row count come
  from the committed params/matrix call, never a hand-written list.
- **Expect one real red in a cell that had never executed.** A variant that was prebuilt, or a leg
  that was never dispatched, has never run its own recipe, so its first execution is where a latent
  bug lives (a shell separator inside a flag string; a CLI with no `--version` at all). Finding it is
  the sweep earning its keep — fix the root cause, pin it with a test that names the shape, and re-run
  that cell; never soften the sweep because one cell was red.
- **The rebase first, verdict second.** Rebase onto the latest `main` and run the bot's OWN test
  suite. When its tests fail, decide per failure whether the TEST is wrong or the TREE is — in
  practice it is tree drift: a target or file `main` gained while the PR was open, so the bot's
  assumptions (counts, lists, `.PHONY`, docs coverage) no longer hold. Never weaken the bot's
  test to make it pass; fix the tree.
- **A gate the bot shipped will catch `main`'s own drift.** A docs/coverage gate earned its keep
  on its own merge: `make issue-bot-image` (added by a sibling PR) was user-facing, printed by
  `make help`, and documented nowhere. Fix the artefact the gate names, in the bot's commit.
- **`.PHONY` / the target index.** A target the bot defines but does not declare `.PHONY` can be
  shadowed by a same-named file — and the bot's own wiring test often asserts it. Add it.
- **Issue numbers.** Bots mis-cite: a help line or comment may name the wrong issue (e.g. the
  flaky-fetch issue instead of the docs issue). Cross-check each `#N` against the issue the PR
  closes.
- **On rebase, a GENERATED file (e.g. `OPENSPEC.md`, an index a generator
  builds) conflicts even when the working tree is untouched.** Do not hand-merge
  it — regenerate it from the generator in the same commit and let the result
  overwrite the conflict. This mirrors the repo rule that derived artifacts are
  regenerated, never hand-edited.
- **A generated index that GATES the merge is verified against each PR's OWN
  tree, never the merge result — the last PR merged wins the file.** When
  `validate` checks a generated file (e.g. the OpenSpec index) against the
  live change dirs and every PR regenerates it from its own base, an
  out-of-order squash-merge lands it stale on the merged tree. The gate then
  goes red on `master` with no repair path: fixing requires a PR, but the red
  gate blocks merging — a deadlock. Unblock by regenerating the index on
  `master` as its own reviewable change; the durable fix is to verify/repair
  the index against the MERGE RESULT (a post-merge job that regenerates when
  the drift is only the generated file) or make the file merge-safe. Never let
  a gate rest on a per-PR-base check of a file the squash-merge rewrites.
- **When master is actively moving, EXPECT your PR's first `validate` to red
  with the index-stale signature** (`OPENSPEC.md is stale (N active on disk vs
  M)`, or `count line says 'Active changes: M', disk needs 'Active changes:
  N'`). It is drift, not your change: master gained a change dir after you cut
  the branch, and validate runs on the MERGE result, not your PR's tree.
  Repair is deterministic, not debugging — `git fetch`, rebase onto
  `origin/master`, `make openspec-index`, amend into your commit,
  `git push --force-with-lease`. Do not chase your own diff; regenerate and
  re-push.
- **A green PR whose `auto-merge` job dies with `GraphQL: Pull Request has merge
  conflicts` is this same drift, not a broken merge job.** `validate` and
  `live-smoke` pass on the PR's own tree while GitHub cannot build the merge ref,
  because a file every merging change REWRITES (a generated index, its count
  line) was re-staled by a sibling merge that landed after this branch was cut.
  Repair the BRANCH, not the workflow: `git fetch`, `git merge origin/master`,
  let the GENERATOR rewrite the file (`make openspec-index` or the repo's own
  reindex target) instead of hand-merging it, commit, push. Expect to repeat it —
  every new merge re-stales the file again, so land this repair promptly.
- **Never finish that repair with `git commit --no-edit`.** When the merge
  completes by itself there is no merge state left, so the regenerated file is a
  plain staged change and `--no-edit` aborts with `Aborting commit due to empty
  commit message`; the push that follows then sends the MERGE commit carrying the
  base's stale copy, so the branch reads repaired while the file is old. Commit
  with a message file (`git commit -F msg.txt`) and prove the content landed:
  `git show HEAD:<file> | grep <the count you regenerated>`.
- **A merge of the moving base can commit CONFLICT MARKERS and stay green.**
  When you `git merge origin/master` and chain the follow-up with `&&`
  (`git merge … && make openspec-index && git add -A && git commit`), a
  conflicted file is staged by `git add -A` with `<<<<<<<`/`>>>>>>>` markers
  still in it and the commit SUCCEEDS — the branch pushes, CI runs, and the
  only signal is a red validate on a file that "looks merged". This bit twice
  in one session. The safe shape: run the merge ALONE, then check
  `git status --porcelain | grep -E '^(UU|AA)'` for unresolved paths BEFORE
  staging anything; resolve each (union-merge the two sides, then
  `grep -c '^<<<<<<<'` to prove zero markers remain and re-run the file's
  module) and only then `git add -A`. Never let `git add -A` run in the same
  `&&` chain as the merge.
- **The index-stale red is SYSTEMIC, not a one-off: EVERY merge re-stales
  every open PR's index, because the gate runs on the merge result and every
  change edits the same generated file.** When you are landing a batch of
  PRs, expect each one to red `[openspec-index] FAIL … (N active)` on its
  first validate after the previous merge, and absorb it by merging the base
  + regenerating before each push. Do not treat each occurrence as a fresh
  debugging problem — it is the same deterministic repair every time. The
  durable fix is a DESIGN change (verify/repair the index against the merge
  result, or make the file merge-safe), not a per-PR regeneration; flag it
  as its own considered change rather than rushing it mid-batch.
- **A red check's message must name the drift it actually found.** An index
  check that reported "rows data changed (issue/PR/specs/tasks)" when only the
  count line had drifted sent the repair at three fields that had not moved;
  the message is part of the gate's contract. When diagnosing, decode the
  message's claim before trusting its verdict — count line vs rows vs missing
  row are different repairs.
- **The OpenSpec change.** The lifecycle wants one per behaviour change and bots often omit it:
  `openspec/changes/<name>/` with `.openspec.yaml` (`schema: spec-driven` + `created:`), plus
  `proposal.md`, `specs/<name>/spec.md`, `tasks.md`.
- **The PR body** must END with the deliberate `closes #<issue>`; a bot body often mentions it
  early and then keeps growing, so the keyword is no longer last. Re-place it and re-check.
  **One closing keyword per issue** — GitHub's reference parser does not chain after a
  conjunction, so `Closes #a and #b` closes only #a and leaves #b open after the merge; use a
  separate `Closes #a`, `Closes #b`.

## Name the PR branch `<topic>-<issue>` and dry-run the closure guard before creating the PR

When the repo owns a `pr-closure` guard that binds the issue from the BRANCH
NAME (a branch ending `-<issue>` must close that issue in its body), naming
the branch with the issue's number and writing a `Closes #<issue>` body line
makes the repo's auto-merge job close the issue automatically on merge — no
hand-close, no orphaned-issue cleanup after. Before `gh pr create`, dry-run
the guard against the exact branch + body file so you never open a PR that
fails it first try:

```bash
python3 scripts/pr_closure.py --branch ci/<topic>-<issue> --body-file <body.md>
# exit 0 = pass; read which references it bound
```

A PR whose branch carries NO issue number cannot use `closes` (the guard fails)
— it must use `Refs`, and the issue is then left OPEN after merge, needing a
deliberate hand-close. Prefer naming the branch with the issue so the merge
closes it for you. **Naming ONE issue in the branch is enough to close SEVERAL
in the body**: the guard binds each `closes` keyword to its own reference and
accepts a branch naming a subset of the issues it closes (`closes #a` and
`closes #b` on a `-a` branch pass). If the guard refuses a branch that carries
no issue number, rename the branch to include one of the issues the body closes
and re-run the dry-run — do not drop the `closes` lines.

## Monitoring a bot run without hammering the API

When asked to "watch" a bot run, don't poll the API in a tight loop — the
implement step takes ~30 min and identical polls burn turns and trip the
runtime's repeat-call guard. Start a background watcher that exits when the run
settles and notifies you:

```bash
gh run watch <run> --repo <owner>/<repo> --exit-status --interval 60 \
  > /tmp/watch.log 2>&1   # run in background with notify-on-exit
```

Then, on completion, read the run's step conclusions, artifacts, branches and
PRs in ONE call:

```bash
gh run view <run> --repo $r --json status,conclusion
gh run view <run> --repo $r --json jobs --jq '...steps...'
gh api "repos/$r/actions/runs/<run>/artifacts" --jq '.artifacts[] | .name'
gh api "repos/$r/git/matching-refs/heads/<prefix>" --jq '.[].ref'
gh pr list --repo $r --state all --json number,headRefName,state
```

A `completed/failure` run whose `implement` step SUCCEEDED but whose
`Commit + push` step shows `SCOPE_ERROR` is the workflow-scope rejection, not
an implementation failure — the work is preserved as the artifact and the run
is red on purpose.

## Reading PR CI status: roll up the checks, never trust a lone `pending`

`gh pr checks <N>` prints one row per job. On a repo where runners are scarce
(e.g. a single macOS-15 Intel pool, or few self-hosted runners) most of the
table sits in `pending` for a long time — that is the QUEUE, not a failure. Do
not poll-print the whole table; roll it up and list only the rows that are not
pass:

```bash
gh pr checks <N> --repo <o>/<r> | awk -F'\t' '{print $2}' | sort | uniq -c
# → 14 pass / 12 pending / 1 skipping
gh pr checks <N> --repo <o>/<r> | grep -v "\tpass"   # the actual waiters
```

- **`pending` ≠ broken.** Resolve each waiter via the jobs API to see whether it
  is `queued` (no runner assigned yet — `runner_name` empty, `labels` name a
  scarce pool) or `in_progress` (a runner owns it):
  `gh api repos/<o>/<r>/actions/jobs/<id>` → `status` / `runner_name` /
  `labels`. A `queued` job on a scarce pool is just waiting; do NOT restart the
  run, re-push to "kick" it, or churn — that only resets its place in line.
- **`skipping` is a planned skip** (a matrix row that doesn't apply), listed
  separately from failures and never nagged.
- **A PR that is `CONFLICTING` shows NO checks at all.** `gh pr checks <N>` answers
  `no checks reported on the '<branch>' branch`, which reads exactly like a workflow that never
  triggered. Resolve it with `gh pr view <N> --json mergeable`: `CONFLICTING` means the base moved and
  GitHub cannot build a merge ref, so no run exists to be pending. Rebase onto the current base and
  push again — do not go debugging the workflow, and do not re-dispatch it.
- **The same `no checks reported` line is also correct for a minute after YOUR OWN push.** Run
  creation lags the push, so an immediate `gh pr checks` answers "no checks" on a perfectly healthy
  branch; poll once more before suspecting the workflow. Rule of thumb: zero checks + `mergeable:
  UNKNOWN` = wait; zero checks + `CONFLICTING` = rebase.
- Wait in a background watcher on a fixed cadence (sleep ~2 min between polls,
  notify on settle) rather than a tight loop, and report the rollup when it
  settles — not the row-by-row table.

## Reviewing an unpushed implementation artifact

When the scope rejection preserved the work as `issue-implementation.patch`, a
reviewer must verify it BEFORE applying — the artifact is the bot's self-report,
not proof. Apply it onto the exact base commit the run used and run the repo's
own gates on the result:

```bash
gh run download <run> -n issue-implementation-patch -D /tmp/ib-art
cd <worktree> && git checkout -b review/<slug> <base-sha>
git am /tmp/ib-art/issue-implementation.patch
make test && make validate-data && make secret-scan   # + any new guard the patch adds
```

- Run the NEW guard the patch introduces too (`make nerve-check` in this
  class), not just the pre-existing gates — a guard that never runs is dead.
- Diff the implementation against the issue's acceptance clauses one by one;
  a correct implementation may legitimately CORRECT the issue's prose (e.g.
  the issue names `JEV_KEY` but the pinned plugin source resolves
  `OPENROUTER_API_KEY`). Verify the name against the code that reads it, not
  the issue text — wiring a variable nothing reads is worse than none.
- File real findings as separate issues (dangling rule reference, a guard that
  can silently skip) rather than folding them into the review.
- **Bot artifacts are NOT deterministic across runs.** Re-running the same
  issue can produce a different (and possibly wrong) implementation — one run
  pins the plugin by commit and wires the provider's real env var, the next
  installs it unpinned and wires the issue's provisional name. Never assume the
  latest artifact supersedes an earlier one; diff the two and verify each
  against the code that reads the value before choosing.
- **A bot blocked by token scope is not a blocked issue.** If your own token
  can push workflow files (it pushed the bot's own workflow), apply the correct
  artifact on the run's base commit, run the gates, and open the PR yourself —
  the bot's PAT gap is an authorization problem, not a reason to leave the work
  unlanded.

## Posting a comment/body: use a FILE, never `--body "$(...)"`

See `references/issue-triage-and-closing.md` and `references/bot-artifacts-and-parsers.md`.

An issue/PR comment body goes through the SHELL. A body containing BACKTICKS (a PR title quoted as
`` `test(hub-probe): ...` ``) or `$()` is command-substituted before `gh` ever sees it: the backticked
segment is replaced by the (empty) output of the command inside it, the quotes are eaten, and `\n`/`\u2014`
escapes land as literal text. `gh` exits 0 and the comment posts MANGLED — the failure is invisible in the
exit code and only shows in the rendered thread.

- Write the body to a file (`write_file`) and use `--body-file <path>`. One extra call, no quoting rules.
- Same for a commit message: `git commit -F <file>`. The file must START with the typed subject
  line (`type(scope): imperative summary`) followed by a blank line and the `Issue:` / `Fix:` /
  `Benefit:` body — `-F` takes line 1 as the subject, so a body-only file is not a message.
  Do not combine it with `-m ""` (an empty `-m` aborts the commit) and do not send the commit's
  stderr to `/dev/null`: `Aborting commit due to empty commit message` is the only signal that the
  commit never happened. Confirm with `git log --format='%h %an <%ae> %s' -1` after committing — a
  staged tree is not a commit.
- Verify the artifact after posting — `gh api repos/<o>/<r>/issues/<n>/comments` and read the BODY back. A
  successful exit code is not a successful comment (the same rule as any external write).
- To repair one: `gh api -X DELETE repos/<o>/<r>/issues/comments/<id>` then repost from the file. Get the id
  from `gh api repos/<o>/<r>/issues/<n>/comments --jq '.[].id'`.

## Pitfalls that cost a review cycle

- Dozens of issues? `references/backlog-triage.md`.
- **A step's env must carry every variable its message interpolates.** A
  fail-loud step that prints `the push of the #$ISSUE branch` but only sets
  `RC`/`SCOPE_ERROR` in its env emits `the push of the # branch` — the one line
  a human reads first loses the issue it was about. Assert the env key in the
  workflow test, not just the message text.
- **A guard that finds its target by slicing a fixed-length window after a
  marker string is brittle: when the marker also appears in unrelated text (a
  comment above the code), a longer change pushes the real target out of the
  window and the guard reds on the WRONG reason while the asset is intact.**
  Assert the target inside the concrete command/recipe string (structural), never
  against a character-slice of the file. When a hardened guard goes red, first
  ask whether the assertion measured the file or the behaviour before trusting
  or dismissing its verdict — then prove it measures the right thing in BOTH
  directions (target present -> pass; target removed -> fail).
- **A second bot agent may be working the same repo simultaneously and can land
  your issue before you push.** They share the same `*_wt` worktree root, so a
  worktree dir may already be occupied or the fix you staged already merged.
  Claim the issue early with a comment (name the branch you plan to use), `git
  fetch` loudly right before opening the PR, and if a sibling's commit carried
  the identical fix, verify it and close rather than reopen.
- **A guard that asserts "X is in the image" silently degrades when CI pulls a
  stale prebuilt base.** If the plugin is installed by the Dockerfile but the
  CI job pulls the base image from a registry rebuilt only on a schedule, the
  guard's presence assertion becomes a `SKIP ... PASSED` note between rebuilds
  — the same class as the repo's "no skipped tests" rule. Make the base rebuild
  on Dockerfile change, or split the guard so the presence check FAILS loudly
  when it cannot run.
- **A rule reference is a promise: verify the rule exists.** Wiring that cites
  `AGENTS.md rule 3e` in six places but never adds the rule leaves a dangling
  pointer — the durable rule silently stops being durable. Search the cited
  file for the rule before shipping the reference.
- **A string-replace that wires a new test into a `main()` runner is a silent
  no-op when the anchor line is absent.** If you insert a call after an anchor
  (`s.replace(anchor, new + anchor, 1)`) and the anchor does not exist in the
  branch — e.g. it came from an UNMERGED sibling PR — the replace does nothing
  and the new checks never run, yet the suite still passes (the count just
  doesn't grow). Assert the anchor is present (`assert old in s`) before
  replacing, and after running grep the output for the NEW check names, not
  just the pass/fail count — a guard that never executes is the vacuous-guard
  failure shape wearing a green suite.

## A commit-message guard is not enough: GitHub synthesizes the trailer from the AUTHOR identity

When a repo needs to forbid a crediting trailer (e.g. `Co-authored-by: Hermes Agent <...>`), a guard that scans only the commit MESSAGE is defeated by the squash merge: GitHub builds the squashed commit's trailer from the AUTHOR identity of a commit inside the PR, so a commit authored as the disallowed identity but carrying NO trailer in its own message passes a message-only scan and lands the trailer on master anyway. The guard must read the IDENTITY (author AND committer) and the message together.

- **Scan the range `origin/master..HEAD`** — the commits a PR ADDS — never history. The pre-existing trailer in master's ancestry must not re-red the guard on every PR.
- **Empty range is NOT a violation.** `origin/master..HEAD` on a branch tip equal to base is 0 commits = nothing new to gate; exit 0. But a range git CANNOT resolve (a missing base ref, a shallow checkout) must FAIL LOUDLY (exit 2), never read as "no commits, pass" — that is how a shallow CI clone silently disables the guard. Give the validate checkout `fetch-depth: 0`.
- **Allow the repo's own bot identity** (`github-actions[bot]` authored, GitHub committer) or every refresh/fix/issue-bot PR reddens.
- **Check every crediting trailer keyword** (`Co-authored-by`, `Signed-off-by`, `Reviewed-by`, `Tested-by`, `Acked-by`, `Helped-by`), not just `Co-authored-by` — a disallowed identity can be credited under any of them.
- **Prove the identity half with the exact measured shape**: a commit authored as the disallowed identity, committed as the allowed one, message with NO trailer — the test must FAIL on a message-only guard and PASS on the identity+message guard.
- **Wire it like any guard**: a `make check-<name>` target + `.PHONY` + append the test to the `_test` chain + run it in qa-validate's `validate` job + `fetch-depth: 0` on that checkout. The self-test runs the guard over THIS repo's own commits (a rule the repo violates is not a rule).

### A guard answers WHO is allowed, never HOW MANY SPELLINGS one person uses

The identity-message case above forbids a DISALLOWED identity. The inverse, subtler failure: the SAME allowed person under TWO spellings, so GitHub credits one human twice in the squash message. Measured: the owner's merge commits read `author=Andy <andy.holst@protonmail.com>` (the merge actor's account) + a synthesized `Co-authored-by: andyholst <andy@holst.se>` — because the PR's commits were authored under the SECOND spelling and GitHub builds a credit from the author identity of a commit inside the PR, while the merge actor is a DIFFERENT spelling of the same person. The guard was green the whole time: `andy@holst.se` is individually "allowed", and the repo had no notion that it is the SAME human as the committer.

- A repo that squash-merges with the owner's account must not trust a per-identity allowlist. Model each person as ONE canonical `Name <email>` (the identity the merge actually credits) plus the spellings that identify them (`person_of`, `canonical_for`), and refuse: (a) a commit that credits its OWN author/committer a second time in any `Co-authored-by`/`Signed-off-by`/etc. trailer (the measured squash shape verbatim — author/committer is one spelling, the trailer credits the other), and (b) an author/committer written as a NON-canonical spelling of a known person, naming the canonical pair to use — the spelling is precisely what triggers GitHub's duplicate credit.
- A genuinely DIFFERENT person beside an allowed author (e.g. `Asimov Agent` next to an Andy-authored commit) keeps passing — that is two people doing one thing, which is what a co-author trailer is FOR. Do not over-rotate and forbid legitimate distinct co-authors.
- The merge-time squash is where the duplicate is MINTED, so gating the PR's own commits is the correct place: refuse on the range `origin/master..HEAD` BEFORE merge, so the offending spelling never becomes a squash.
- **The fix's own commit must be authored as the canonical identity** (commit with `-c user.name='Andy Holst' -c user.email=<canonical>`), or the PR that introduces the guard adds exactly the duplicate it forbids. Prove it: run `make check-commit-authorship` on the branch and confirm the new commit passes.
- Count, don't eyeball: `git log --format='%an <%ae>' | sort | uniq -c` over the range surfaces the multiplicity; a self-credit that spans the owner's two spellings shows as one human credited twice. Feed the guard the measured offending commit as a load-bearing fixture so the violation is locked.

## Test the REAL push script, not a mock

Verify the actual commit+push step end-to-end against a real git remote whose
surface rejects workflow files — never a stub of the script:

- Build a temp clone, set up a **bare remote with a `pre-receive` hook** whose
  exit code reflects GitHub's message when the pushed commit touches
  `.github/workflows/**` (e.g. exit 1 when any changed path is under that
  dir).
- Drive the real script with `GIT_DIR`/origin pointed at it. Assert: the push
  step does NOT fail on the scope rejection, it reports `scope_error=true`,
  nothing reached the remote (the branch is absent there), the unpushed
  implementation is preserved as a patch artifact, a NORMAL push still works,
  and the committed artifact file is not itself pushed.
- Run the same script in a clone with NO rejecting hook to assert the happy
  path (push succeeds, commit carries the implementation).
- A test that only greps the workflow YAML for a step name proves wiring, not
  behaviour — keep the YAML-grep assertion AS WELL as (not instead of) the
  real-push test. The real-push test must fail on the pre-fix tree.

The hook approach matches the repo rule that business logic runs unmocked: the
production script runs, the only stand-in is the external remote.

## Every command a CI workflow runs is a make target

A bot workflow must call `make <target>` for anything that touches repo logic —
never `python3 scripts/...` or `scripts/*.sh` directly. The make target is what
makes the command reusable locally AND by the pipeline, and the wiring guard
(`make check-wiring`) enforces that every script is wired to a target CI runs.
Only `gh`/`git` orchestration (guard, PR resolution, commit/push, comment) stays
inline — that is workflow plumbing with no repo logic.

- Give each script a dedicated target (`fix-bot-sweep`, `fix-bot-report`,
  `agent-image-ref`, `fix-loop-image`) and add it to `.PHONY`. A target that
  only exists as a substring of a bigger recipe is not discoverable or
testable on its own.
- **Never insert a new target between an existing target line and its recipe.**
  A Makefile recipe is the tab-indented lines immediately after the `target:`
  line, so a new block pasted after `foo:` becomes the OWNER of foo's commands:
  the new target silently runs the old recipe and `foo` runs nothing (it still
  "succeeds", so `make -n foo` is the tell). Insert after the last tab-indented
  line of the preceding recipe, then verify BOTH targets with `make -n <old>` and
  `make -n <new>` before trusting the file — a vacuous target is invisible in a
  green run.
- When a make target needs a value the workflow resolves (an image ref, a
  report path), accept it as a make variable override (`AGENT_IMAGE=...`,
  `LOG=...`, `REPORT=...`) so the workflow and a local run share one command.
- Codify the rule in the repo's AGENTS.md under the execution-environment
  section so the agent itself follows it.
- Test the make targets' underlying scripts (exact argv via a stubbed external
  CLI) AND assert the workflow calls the make targets; the git commit/push step
  is orchestration and is intentionally not unit-tested.
- **Assert the make target's exact recipe with `make -n <target>`**, not just
  the script's argv and the workflow's wiring. Shell out to `make -n` and assert
  the printed recipe contains the exact command (`python3 scripts/... --repo ...`,
  `docker run ... scripts/fix_loop.sh`, the `-e NOUS_API_KEY`/`-e GH_TOKEN`
  flags). This proves a local `make` and the pipeline run the identical command.
- **Pass make-target variable overrides as command-line args, not env vars.**
  A Makefile that hard-defines a variable (`REPO := $(shell pwd)`) ignores an
  env var of the same name — `make -n fix-bot-sweep REPO=...` (command-line
  arg) overrides it, `REPO=... make -n fix-bot-sweep` does not. In the test,
  build the args list `[f"{k}={v}" for k, v in vars.items()]` and append to the
  `make -n` invocation.
- **A capability that exists but no workflow CALLS is invisible to the wiring
  guard, and a test that only greps a README line cannot see it either.** The
  guard requires a DOCUMENT (a README row, a test name) to reach CI — so a make
  target that exists, is `.PHONY`, is asserted by a test, and is documented can
  still be unreachable from any real run: "the script is wired" and "the leg is
  used" are two different facts, and the second can be false while the first is
  green. Close it with a DERIVED assertion, never a hardcoded call-list: parse
  the Makefile's target→prerequisite graph, expand every target CI actually
  reaches transitively, and assert the seam is in the closure (`make
  agent-fetch` must be reached through `make issue-evidence`). A derived-roster
  check stays correct as targets are added or renamed, where a hand-written list
  goes stale the moment a new leg is added and silently re-opens the gap.

## When a bot publishes transcript/output to a log or output file, guard the whole-stdout shapes

A bot that prints anything needs the right exposure rule. GitHub masks only
*registered* secret values in the job log, so a transformed value or a whole
copied stream sails past. Two shapes a bot pipeline actually produces when it
publishes output:

- **Whole stdout into `$GITHUB_OUTPUT`** (`cmd | … >> "$GITHUB_OUTPUT"`,
  `$(cmd) >> "$GITHUB_OUTPUT"`). The file must hold `key=value` only, so
  `make` echoing its recipe line is enough to fail the step with `Invalid
  format` AFTER the work is done. The safe form is the quoted computed value
  `echo "k=$(…)" >> "$GITHUB_OUTPUT"`; keep it green.
- **Whole stream into the job log** (`… | tee /dev/stderr`, `/dev/stdout`).
  `tee <file>` is file-only and fine.
- **A wrapper that discards a sub-command's diagnostic output (`make _setup
  >/dev/null`) hides the ONE line that explains a failure — restore it to
  STDERR (`1>&2`), not stdout.** The target's own stdout is often parsed by a
  caller (a smoke verdict, a check report), so sending the seam's output to
  stdout would pollute that parse; `make _setup 1>&2 && make _hermes-smoke`
  keeps the diagnosis in the job log while the target's stdout stays clean.
  Guard it by scanning the real Makefile for every `sh -c "make _setup …"`
  wrapper: assert the wrappers are found (non-vacuous), none contains
  `_setup >/dev/null`, each keeps it, and assert the specific measured targets
  by recipe. Prove RED by stashing the pre-change Makefile (`git stash push
  -- Makefile`, run, `git stash pop`).

Two more rules that are easy to miss:

- `${{ github.token }}` interpolated *inside a `run:` block* is the same
  credential as `secrets.GITHUB_TOKEN` — it becomes script text, `ps` and
  `--debug` output. The safe shape passes it through `env:`. Match the dot and
  both bracketed spellings (`github['token']`, `github["token"]`).
- **A redaction seam a leg's `exit` cannot skip**: run the redactor in a
  subshell that preserves the leg's exit status (a `$(call scrubbed_run,…)`
  wrapper around the recipe), so a leg that exits early still redacts before
  anything reaches a log or an upload artifact.
- **Porting a pipeline rule from a sibling repo over-matches `a || b`.** The
  source's loose `|` flags the shell-or chains the target repo's scripts
  really use (a chain ending in `>> "$GITHUB_OUTPUT"`). Tighten to a single
  pipe with lookarounds (`(?<!\|)\|(?!\|)`) and re-verify against the real
  tree — the port must be a strict improvement, not a loosened copy.
- Pin every rule in BOTH directions (one violating fixture, one safe
  counter-shape) plus a tree-wide check that the repo itself stays clean.
- **A tree-wide scan that forbids a literal must not be defeated by its own test or its own docs.**
  Build the forbidden value from pieces (`"Reply with " + "exactly: ok"`) so the test file does not
  carry it, and scope the scan to the files that can actually carry the rule (the Makefile,
  workflows, `scripts/`, container files) — a markdown doc or the test explaining the old shape may
  legitimately quote it, and a scan that includes them reds on history rather than on a regression.
  A script's own docstring quoting the retired prompt is the same trap: describe the old shape in
  words, do not paste it.

Deeper guidance is in the sibling repo skill `llgenie-engine-image-ci`, file
`references/secret-exposure-guards.md` (load via skill_view with that
file_path).

## Wire the test suite by DISCOVERY, never by enumeration

A suite wired as `python3 -m pytest tests/ -q 2>/dev/null || (python3 tests/a.py &&  … N files …)`
enumerates every test on ONE shared Makefile line: every change that adds a test appends to that
line, so two concurrent changes — two bots, or a bot and a human PR — collide on it by
construction. The hand-merge is ALWAYS in the wiring, never in the code under change; that
signature (a merge-DIRTY PR whose only conflict is the Makefile / a rules catalogue / a generated
index, never the diff itself) is how you recognise the pattern. Fix it ONCE:

- Add a discover-all entry point (`tests/run_all.py`) that globs `tests/test_*.py` in sorted
  order, runs each with the same interpreter, prints a per-file banner + summary, and fails
  CLOSED on a failing file AND on an EMPTY discovery — an empty run must never report green.
- Point `_test` at it; the recipe must not name a test file, so adding a test edits only the
  test's own file and no two changes collide.
- REWRITE the guard that asserted a test "runs in the suite" by grepping the Makefile for a
  filename: after the change that grep fails on CORRECT code. It must assert instead that `_test`
  runs the entry point and that the entry point's discovery equals every `tests/test_*.py` on
  disk, and must name which funcs/chains it drives (a docs/spec row that cites these tests needs
  the real function names, not ones you guess).
- Verify through the REAL fallback path: in the test image `pytest` is often absent, so `_test`
  ALWAYS takes the discovery branch — run that, never a mock of it. Prove a newly-filenamed test
  is wired without the Makefile naming it.
- The rule generalises: any "list of N that every change appends to" (a Makefile chain, an
  allowlist, a documented catalogue) is a merge-collision line. Make it derived or discovered, not
  hand-edited per change. Removing one collision point does NOT fix the siblings — a generated
  index and a rules doc that every change also edits stay collision points; flag them as their own
  change rather than expanding this one.

## Replacing a literal with a variable: grep the WHOLE tree, and make the tests read the definition

When a value has one definition and many call sites (an alias, a model name, a
flag set) and you refactor the literals to a variable, the literal lives in MORE
places than the recipes — a vacuity-count regex that counts matching lines, a
falsification fixture that feeds a fake Makefile, and `make -n` dry-run
assertions that check the expanded command. Each breaks differently:

- A guard that counts lines matching the OLD literal goes VACUOUS (count=0)
  the moment the literal is replaced — it passes on finding nothing, so the
  "guard not vacuous" check must count the NEW variable form, not the old
  literal.
- A fixture that feeds a fake Makefile must carry the new shape too, or the
  falsification test stops exercising the rule it claims to prove.
- A `make -n` dry-run assertion that checks for the literal string fails on
  CORRECT code after the refactor; it must compare the EXPANDED flag against
  the value parsed from the definition.

So before touching the literal, `grep -rn` the WHOLE test tree for it (not just
the file you are editing — the first patch caught two of three sites), and after
the refactor make the tests READ the definition (parse it from the Makefile)
rather than pinning the value: a suite that hardcodes the value defends the
drift the refactor exists to remove.

- **A roster keyed on the COMMAND TEXT goes stale when the command moves into a script.** A test
  that derives "which legs call the model" from `"hermes -z" in recipe_body` drops the leg the
  moment the recipe becomes `python3 scripts/<x>.py` (which invokes the CLI itself) — the roster then
  asserts a shorter list while the leg still runs. Teach the predicate the new seam
  (`"hermes -z" in body or "scripts/<x>" in body`) rather than deleting the leg, so the rule (every
  model-calling leg stays inside the redacting wrapper) survives the refactor.
- **Splitting one variable in two breaks equality asserts on the old spelling.** `A := -m X`
  becoming `B := X` + `A := -m $(B)` reds a test that asserts the original line verbatim. Update it
  to assert BOTH lines — the single source and the derived flag — which is the new contract. Re-check
  every "the flag must not appear in the Makefile" assert too: a script's own `--alias`/`--model`
  parameter legitimately appears now, so scope that check to the CLI's invocation lines, not the file. Prove RED by stashing the pre-change file
(`git stash push -- <file>`, run, `git stash pop`) and watching the vacuity
counts drop to 0, then GREEN after.

## Editing workflow YAML and test files: prefer a Python string-replace

The fuzzy `patch` tool repeatedly corrupts workflow YAML and Python test files
when the edit span is near a block boundary — it shifts indentation, duplicates
or drops a line, and can nest a new function inside the previous one (an
`IndentationError` that is invisible in the diff). When editing a `run:` block,
a `.PHONY` list, or a test function, do the replacement with a Python script
that reads the raw file, asserts the exact old block is present, replaces it,
and writes back — not with the fuzzy patch tool. Verify with a YAML/`ast` parse
and a `make -n help` parse after.

## The deterministic dispatcher (the unit-testable core)

Keep the pick/claim/cap logic in a **stdlib-only script with no LLM** — the
LLM step is a separate `make implement-issue` recipe the workflow calls. The
dispatcher is what the no-mock tests exercise; the agent step is not unit-tested.

- **Emit machine-readable `key=value` lines for the workflow to parse**, AFTER
the human log line: `action=dispatch`, `issue=11`, `branch=agent/issue-11-slug`,
`pr_url=...`. The workflow does `out=$(make issue-bot-dispatch ...)` then
`sed -n 's/^branch=//p'` on it. A bare human log line is not parseable.
- **A label event / manual dispatch must PIN the exact issue** (`FORCE_ISSUE`
from `github.event.issue.number || inputs.issue_number`), not fall back to
picking the oldest. The label is the explicit ask for THAT issue; only a
schedule run lets the dispatcher pick. A forced issue that is not `open` is
reported as `action=none`, never claimed.
- **Cap before any work, counted from GitHub** (`gh search prs --author <bot>
--created ">=today 00:00Z"`), and make the boundary a NAMED test: at 3 the 4th
attempt exits 0 and opens/comments nothing; at 2 it proceeds.
- **`<bot>` must be the identity `open-pr` actually produces.** A PR opened with
  `GH_TOKEN=<owner PAT>` is authored by the PAT's OWNER, not by
  `github-actions[bot]` — so a cap whose filter names the bot login matches
  nothing, reads 0 on every run, and the "hard bound" becomes decorative (two
  bots that were meant to share one 3-per-day budget both see 0). Verify the
  count against a day the bot really opened a PR and require a non-zero number;
  keep the rule in ONE place, since every bot spending that budget re-implements
  it otherwise. Commit authorship and PR authorship are two different facts —
  the committer identity being enforced does not make the PR's author the bot.
- **Count the ARTEFACT the dispatcher creates, not an author login.** Filter on the
  branch shape `dispatch` itself writes (`agent/issue-<n>-<slug>`, read with
  `gh pr list --json headRefName,author,createdAt`), not `--author`: the token owner
  also authors every SIBLING bot's PR (engine bumps, registry syncs), so a login filter
  is wrong in both directions — it misses this bot's own PRs and would count work that
  is not this bot's. When you prove the numerator, prove it against a PR of the SAME
  kind; a day full of engine-bump PRs proves nothing about this cap, so a "7 PRs, cap
  read 0" measurement can be true and still point at the wrong fix.

## The fake-`gh` test pattern (assert the argv, never mock the logic)

Point the dispatcher at a `gh` on PATH that records every argv as one JSON line
and answers the queries — the same shape `test_engine_skill_gap.py` uses. The
product's `count`/`dispatch`/`open-pr` run for real; only the GitHub API is a
stand-in. Two traps when generating that fake script:

- **`gh search prs --json number` returns a BARE array** (`[{"number":1},...]`),
not `{"items":[...]}`. Parse `json.loads(out or "[]")` and take `len` — do not
look for an `items` key.
- **When the fake `gh` is written as an f-string, embed the fixture data as
top-level constants** (`PRS = ...`, `LABELED = ...`, `VIEW = ...`) and reference
them inside the generated script. Do NOT interpolate an expression that
references a variable that only exists inside the generated script (e.g. a
`lab` local read from argv) — at host scope that name is undefined and the
f-string either emits a literal `NameError` or, with `{...}` braces, a Python
set literal that breaks `json.loads`. Constants at the top of the generated
script keep the argv-assertion logic clean.

More traps when the fake `gh` must also WRITE state (an `issue create` handler
that appends to a store):

- **`grep -c` on an empty file prints `0` AND exits 1**, so
  `n=$(( $(grep -c . store || echo 0) + 1 ))` emits `0` twice (`0\n0`) and fails
the arithmetic expression in `sh` — the create never runs and the bot aborts
mid-filing. Use two plain shell lines: `n=$(grep -c . store || true)
n=$(( ${n:-0} + 1 ))` (the `|| true` swallows the exit 1 without emitting a
second `0`).
- **Assert the ARTIFACT a side-effect writes, not a status line it prints.** A
message may only print on a sibling code path (an explicit
`--write-flags`-style flag) and stay silent on the path under test — asserting
the log text then fails for a WRONG reason, or passes while the real write is
missing. Read the file the handler wrote and assert its contents/signature
instead.

## File each recurring issue once: a body signature marker, searched `in:body`

A bot that files the SAME class of issue (a data-gap report, a stale-data alert,
a sync diff) on a schedule re-files every run when its only dedup signal is a
baseline that reaches the repo only through the issue's OWN PR (the baseline
merges with the PR, so two runs before that merge see the same change — and a
PR closed without merging re-files it forever). Make one stable id of the
CONTENT and let GitHub's issue search be the dedup store:

- Append an invisible HTML-comment marker to the body
  (`<!-- data-<kind>-signature: <sha12> -->`) where `<sha12>` hashes the
  report's changing part (the headline/signature), NOT the timestamp you would
  naturally include — the marker must be stable across runs.
- Before filing, `gh issue list --label <label> --search <sha12> in:body
  --json number,state`; an **OPEN** match means it is already filed: log its URL
  and exit, and write NO baseline (the run filed nothing).
- A **CLOSED** match never suppresses: a closed issue means the work was done or
dropped — the set re-appearing later is new information, so file again.
- Drive the REAL filer and test it by hand-shaping the marker: run 1 files
exactly one issue carrying a nonempty 12-hex sig and writes the baseline; run 2
against the same stale baseline files NOTHING and says so; run 3 with the store
flipped to `CLOSED` files again. Prove the dedup is real (a gate, not a
loosened assertion) by rerunning the SAME tests against the PRE-fix script
(`git show origin/master:<path> > <path>`), watching them FAIL (a second
`issue create`), then restore the fix and see them PASS.

## A terminal verdict must leave the surviving work REACHABLE by the picker

The picker is label-driven (`gh issue list --label <trigger>`), so a verdict that retires an item can silently
orphan the work it points at — and the run then reads as "success, nothing implemented" forever:

- **A `close` that cites a canonical issue must QUEUE that issue.** A duplicate/invalid close whose evidence
  says "duplicate of #N" and leaves #N unlabelled retires the copy while the real defect stays invisible: the
  next run picks another copy, closes it the same way, and the canonical issue is never implemented. Read the
  `EVIDENCE:`/`REASON:` blocks for `#<n>`, and for each referenced issue that is **open** and carries **no**
  agent label, add the trigger label. Skip the issue being closed, skip closed ones, skip ones already decided
  or already queued, and treat an unreadable reference (a PR number, a typo) as "not an issue" — the close
  already happened and must not crash. Prove it against a fake `gh` that records `issue edit <n> --add-label`.
- **A "decided" label that the picker also excludes must not be set by a verdict that is meant to move the
  item FORWARD.** Measured: a `refine` posted an implementable restatement and added the refined marker, which
  was also in the decided set, so the just-improved issue became unpickable — permanently, until a human edited
  labels. Two verdicts need two opposite label effects: `close` retires (label out of the queue), `refine`
  improves and must stay queued (marker for the audit trail, but the trigger label remains, or is re-applied).
- **Diagnose "why didn't it implement #N" from labels, not from the run's conclusion.** `gh issue view <n>
  --json state,labels` plus `gh api repos/<o>/<r>/issues/<n>/events --jq '.[]|select(.event|test("labeled|unlabeled"))'`
  shows which label parked it and WHO set it — a bot re-adding a decided marker after a human removed it is the
  signature above, not a picker bug. Then read the run's decision lines (`picked #N`, `Verdict:`, `PR:`) and the
  bot-claim comment before concluding the leg is broken.

## The filed issue's LABEL is the downstream chain's trigger

A bot chain that reacts to newly-filed issues (`issues: [opened]`) or an hourly
sweep (`gh issue list --label X --state open`) selects work by label. An issue
filed without that label is invisible to the WHOLE chain: the sweep logs
"backlog empty" and skips implement, and the ticket sits open forever with no
implementer. `gh issue create --label X` can return exit 0 while applying NO
label — the CLI silently drops it — so a create that reports success can still
file an invisible issue.

- After `gh issue create`, verify the label landed: `gh issue view <number>
  --json labels`; if absent re-apply with `gh issue edit <number> --add-label X`,
  re-check, and FAIL loudly if it still is not there. An issue nothing will ever
  implement is worse than a red run.
- When a sweep reports "every open labelled issue has an implementer" but you
  know an open gap ticket exists, hunt for the UNLABELLED sibling — it was
  likely filed in a window before the label-verify fix landed and never repaired.
- Repair an orphaned ticket with `gh issue edit <number> --add-label X`; the
  next sweep then picks it up. The orphan is usually the SECOND of two issues
  filed close together — the first got a manual label, the second did not.

## Publishing a NEW container image to GHCR (the agent image)

When a bot runs in a dedicated agent container (Hermes CLI + git/gh/docker
tooling, built FROM the repo's test image), publishing that image is a
privileged action and needs its own guarded path — do NOT fold it into the
per-PR `ci-images` job that publishes the test/openspec images.

- **A brand-new org package cannot be created by `GITHUB_TOKEN`.** The default
  token is an installation token and is denied `Create organization package`;
  it CAN update packages that already exist (which is why the existing images
  publish fine and only the new one fails). The failure surfaces as
  `error writing layer blob: denied: installation not allowed to Create
  organization package` at the `--push` step. Fix: log into GHCR with an
  owner-scoped PAT (`write:packages`) for the publish job, or pre-create the
  package once with a PAT so the workflow token can update it thereafter.
- **Check the repo OWNER's account type and what the WORKING sibling publish
  already uses before reaching for a PAT.** Measured on a repo owned by a USER
  account (not an org): `ci.yml`'s `ci-images` job already publishes the test and
  openspec images to the same `ghcr.io/<owner>/` namespace with
  `secrets.GITHUB_TOKEN` + `packages: write` logged in as `github.actor`. The
  agent-image job, which used an owner PAT instead, failed its own pre-flight
  with `403 DENIED permission_denied: The token provided does not match expected
  scopes` — the PAT had no `write:packages` at all. So: prefer the credential the
  sibling publish path proves works; the "org package" denial does not apply to a
  user-owned namespace; and only widen a PAT when the token exchange itself
  refuses. A push-check that costs seconds (ask for a push-scoped token, then
  initiate an empty blob upload) is the cheapest way to know before the build.
- **Read the published package under the OWNER, and verify the tag by pulling it.**
  `gh api /user/packages/container/<name>/versions` lists the AUTHENTICATED user's
  packages, so on a repo owned by another account it answers
  `Package not found` even though the image is published — use
  `/users/<owner>/packages/container/<name>/versions`. And prove the artifact by
  `docker pull <ref>` then reading the thing it was built for inside it
  (`docker run --rm <ref> bash -lc 'hermes config get …'`), never by trusting the
  build log.
- **A branch `workflow_dispatch` publishes the SAME tag `main` will compute** when
  the image's hashed inputs are unchanged (`python3 scripts/ci_images.py ref agent`:
  the Dockerfile + every COPY'd install script, not a workflow or README edit). That
  is how you exercise the publish path without merging anything.
- **Give the image a dedicated make target** (`make publish-agent-image` =
`scripts/ci_images.py publish agent`) plus `agent-image` / `agent-image-pull`
mirroring the test/openspec targets, and add all three to `.PHONY`. A target
that only exists as a substring of `publish-ci-images` is not discoverable or
testable on its own.
- **Guard the publish workflow like the bot workflows**: `workflow_dispatch`
only (GitHub's own write-access gate), then a `guard` job that re-checks the
actor + triggering actor is the owner or a collaborator with
write/maintain/admin BEFORE any secret is read, then the publish job. Same
shape as the issue-bot/fix-bot guards.
- **Copy an existing guard step VERBATIM when you add a guarded workflow.** A
  repo that has several guarded bots usually also has a test asserting EVERY
  guard step is byte-identical (`test_every_guard_step_is_byte_identical`),
  because a guard that drifted in one file is a guard nobody reviewed. Rewriting
  the comments, the refusal wording ("Refused:") or the log line — even with the
  same logic — reds it with a diff of two near-identical blocks. Take the whole
  `guard:` job from an existing workflow (e.g. the engine-bump one), swap only
  what differs, then check the guard test before running the rest.
- **The agent image is built FROM the test image's published hash tag**, so its
own tag must fold in the test image's tag (a rebuilt base re-tags the agent,
else the agent silently keeps an old base) and the build passes
`--build-arg TEST_IMAGE=<hash>`. Assert both in a test: `publish agent` emits
`--build-arg TEST_IMAGE=ghcr.io/.../test:<12hex>` and its build context holds
the agent Dockerfile + the install script it COPYs.
- **Secrets are never baked into the image** — `NOUS_API_KEY` / `GH_TOKEN`
arrive at run time (`docker run -e ...` or the job env). The image carries the
CLI + tooling only.

## The bot's model alias is a pin: verify the SNAPSHOT, and give the alias a budget

The bots call the provider through a custom alias (Hermes's bundled `nous` provider is OAuth-only, so
a secret key only works through `provider: custom` + `base_url` + `key_env`). Three things about that
alias get silently wrong:

- **A model id with a snapshot suffix is a DIFFERENT model, and both ids answer `200`.**
  `…/deepseek-v4.1-flash` vs `…/deepseek-v4.1-flash-1017` differ in `canonical_slug`, serving
  provider and price. Compare `canonical_slug` / `name` / `created` from the catalogue's `/models`
  (it answers with no key), never "it returned 200" and never the id's prefix.
- **A test asserting a model-id PREFIX is not a pin** — any newer snapshot satisfies it, so a stale
  pin ships green. Assert the exact id, and put the id in ONE declared constant that a `make
  check-<name>` gate compares against every file that carries it (the Dockerfile `ARG`, the install
  script default). Point that gate at the UNTOUCHED base checkout and require it to FAIL: a gate
  green only on your own tree has not been shown to catch anything.
- **Write `max_tokens` AND `context_window` on the alias.** Leave them out and Hermes budgets the run
  from the models.dev catalogue, which has no entry for a snapshot id — a 120–180 minute bot job then
  runs on a default window instead of the model's real one. Copy the numbers from the catalogue's
  `context_length` / `max_completion_tokens`, and assert all of `model`, `provider`, `key_env`,
  `max_tokens`, `context_window` in the image BUILD, so a half-written alias fails the build rather
  than mid-run.

Proving it needs a live call, not a config read: `hermes-smoke`-style one-shot through the alias
proves text, so ALSO run one prompt that must use a tool ("run `printf ok` with your terminal tool and
reply with only its output"). The transcript is the evidence, not the reply: see
`references/proving-tool-use.md` for the marker-file trick, the `$HERMES_HOME/state.db` read
(`sessions` + `messages`), and the things that are NOT proof (`tool_call_count`, a process exit
code, the agent's own report). When the agent's shell has no provider key (Hermes strips provider
credentials from its terminal tool), read a token from the local auth store instead of concluding the
endpoint or key is dead:

```bash
export NOUS_API_KEY="$(python3 -c 'import json;print(json.load(open("$HOME/.hermes/auth.json"))["providers"]["nous"]["agent_key"])')"
```

For the llgenie-specific paths, the live-verification commands and the repo mechanics around them,
see the sibling skill `llgenie-engine-image-ci`, file `references/bot-model-wiring.md`.
For auditing every scheduled bot workflow (the run-reading procedure, the `github.token`-vs-PAT write
table, GHCR publishing, and the worktree / `openspec-new` / unit-suite traps), see that same skill's
`references/bot-workflow-audit.md`.
For a batch of issue→branch→PR changes in one session (worktree/branch per issue, root-owned
OpenSpec dirs, sequential unit suites, roster coupling between sibling PRs), see this skill's
`references/multi-pr-batch.md`.

## Classify a link by what its status MEANS (gated is not dead)

A probe that treats every non-`200`/`206` answer as dead calls a **gated** file dead —
`401`/`403` means the file exists and this token may not read it — and reds the whole sync on
a file that is there, one gated model blocking every other model's refresh. Classify
`ok` (200/206), `gated` (401/403) and `dead` (everything else), fail only on `dead`, and
print the gated count so it stays visible. Match the repo's existing web-coverage rule (a
credential-gated URL is reachable, not dead) instead of inventing a second policy.

A gate that compares committed artefacts against LIVE upstream data can red locally and pass
in CI, because the runner holds a token or egress the host does not. Before filing a defect:
run that target inside CI's own log (`gh run view <id> --log | grep <target>`) and look for
`make: ***`. Red locally + absent from CI's log = environment (token/network), not a code bug.
If a CI log DOES show the FAIL text but no `make: ***` near it, the line came from a test
asserting the message rather than from the gate — resolve which make level emitted it before
concluding the gate is red or silently swallowing a failure.

## Container reuse for validation

Run the deterministic gates and the LLM implement step in the repo's test
container image (`docker run --rm -v "$PWD":/workspace -w /workspace
<test-image> make test` / `python3 tests/test_workflows.py`) so behaviour is
byte-identical to CI. Verify against freshly-synced data so a passing test is
not an artefact of stale input.

- **A HOST-side `python3 tests/<module>.py` is a silent FALSE GREEN.** The test
  image's deps (PyYAML and the repo's other pinned test requirements) live only in
  the container; on the host the module prints `SKIP: PyYAML not installed` and
  still exits 0 — the check never ran, yet it reads as a pass. Run a single
  module in the test image too (`docker run --rm -v "$PWD":/workspace -w
  /workspace <test-image> python3 tests/<module>.py`), and treat any local print
  of `SKIP:`/`not installed` as "did not execute", never "passed".

- **A test that reads REAL git history (a self-test over `master`'s own commits) needs TWO things to run in the test container, and each failure misleads differently.** First, the worktree's `.git` is a FILE pointing at the parent clone's `worktrees/<name>` — a bare `docker run -v <worktree>:/workspace` cannot see it and git dies with `not a git repository`; the `make test` target mounts the parent `.git` at its host path, so a standalone run that omits it fails for a DIFFERENT reason than the Makefile path does. Second, inside the container the uid differs from the host owner, so even with the parent `.git` mounted, git refuses with `detected dubious ownership in repository at '/workspace'`. Make the TEST tolerate both: set `GIT_CONFIG_GLOBAL` to a temp gitconfig holding `safe.directory = *` (the container's environmental reality, never a weakening of the guard's own call), restore it after, and skip openly (never pass vacuously) only when the repo genuinely cannot be read. Run such a history test under `make test` in the container, not as a bare `python3` on the host — a host run prints `SKIP`/`not installed` and still exits 0, a silent false green.
- **Root-owned files a container leaves inside a worktree (pycache, build
  artifacts) make `git worktree remove` and plain `rm -rf` fail with EPERM.**
  After pruning the tree from `git worktree list`, remove the directory through
  a docker bind-mount that runs as root:
  `docker run --rm -v "$PWD":/wt alpine rm -rf /wt/<worktree>`.
  Prefer that over `sudo`: a backgrounded shell cannot prompt for a password
  (`sudo: a terminal is required to read the password`), and a cached sudo
  timestamp expiring mid-session turns a later `sudo rm -rf` into the same
  failure — the container path needs no privilege at all.
- **`git merge-base --is-ancestor <branch> origin/main` is FALSE for a
  SQUASH-merged branch.** The squash rewrites the commits, so ancestry says
  "not merged" for every branch the gate already landed and a cleanup loop will
  keep them forever. Decide with `gh pr view <n> --json state` (or
  `gh pr list --state merged --head <branch>`); use ancestry only to ask
  "is this commit already in main", never "did this PR merge".
- **A timed-out terminal call kills the CLIENT, not the container.** When a
  docker-wrapped `make test`/`make validate` (a `docker run … make _test`
  recipe) call times out, the container keeps running to completion in the
  background. Do NOT re-run the target — that starts a second container
  contending for CPU and doubles the wait. Check `docker ps` for the orphaned
  container and let it finish (or kill it), then read its log. The
  process_manage "starting 0 s" spinner is a display field that never updates,
  not a stalled job — verify liveness with `ps -o pid,etime,stat -p <pid>` and
  `docker ps`, never the spinner.
- **The discovery test runner buffers per-module and prints NOTHING until the
  end** — a long `make test` shows no output for minutes, so silence is not a
  stall. Use `process_manage wait` (or background with notify-on-exit) and
  read the log's `rc=` line when it settles; do not poll or re-run on the
  absence of output. A background call whose output is piped through a
  truncating filter shows an EMPTY preview for the whole run; to answer "is it
  progressing?" read the running container's own log instead — `docker logs
  --tail 1 $(docker ps -q --filter ancestor=<test-image>)` prints the pytest
  percentage, and no container means the suite already exited.
