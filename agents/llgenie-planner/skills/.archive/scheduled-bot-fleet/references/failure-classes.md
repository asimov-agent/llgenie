# Bot failure classes: symptom → mechanism → fix

Each entry is written so a future session can recognise it from the log line alone.

## "success" but nothing happened

Symptom: the scheduled run is green; the bot logged a decision for every candidate and picked none.
Mechanism: an input was rejected before the work (a marker it wrote itself, a merge state it could not
read, a remote it does not push to). Fix: make the rejection explicit and counted in the log
(`pass-over: #n <reason>`), and assert in a test that the intended input IS picked.

## `mergeStateStatus: UNKNOWN`

Mechanism: GitHub computes mergeability lazily (seconds after a push). Fix: re-ask
`gh pr view <n> --json mergeStateStatus,mergeable` a bounded number of times (≈4 × 2-3 s), then list
it as deferred-by-name. Never treat `UNKNOWN` as "nothing to do".

## "already handled today" but the attempt failed

Mechanism: the once-per-window check matched ANY comment naming the bot — its own claim, or a failed
attempt. Fix: parse a distinct done-marker with a kind (`rebased` on success, `gave-up` on failure) and
count only the success kind, dated today.

## "already handled today" while the PR is `BEHIND`/`DIRTY`

Mechanism: the daily marker was consulted BEFORE the live merge state, so a PR re-dirtied by a later
`main` push is skipped for the rest of the window. Fix: eligibility = resolved merge state; markers
only cap how many per window. Guard same-run repeats with an explicit `skip` list, and append to it on
failure too (a failed abort leaves the PR dirty and the loop retries the same conflict).

## One action per run, backlog never drains

Fix: loop the decision until it answers `none`, bounded by a max (`MAX_PR`), aborting a half-finished
attempt (`git rebase --abort`) before the next decision.

## A finished implementation discarded at COMMIT time

Symptom: every step green through `implement` and the verdict, then the commit step dies with
`REFUSED: STALE: this checkout is NOT the freshly fetched <base>`; the PR steps are SKIPPED and the
run uploads no patch — the agent's minutes are gone.
Mechanism: the base was asserted TWICE. Correctly at the start, then again when the branch was cut,
using a target that refuses `HEAD != fetched tip`. Between the two the bot worked for 20–30 minutes,
and a merge landed — so the artifact is a refusal over a tree that is legitimately behind.
Fix: assert the base only where work STARTS. At commit time: cut or attach the branch from the current
`HEAD` (reporting `behind_base=N`, refusing nothing), commit, then rebase onto the fetched tip; a
conflict ABORTS the rebase, keeps every commit, and the push proceeds so the PR's fix loop repairs it.
Make the patch artifact upload on ANY rejected push, not only the token-scope rejection.

## The adopt resumed a branch that is not this run's work, and the tree lost files the base added

Symptom: `OK: adopted ci/<slug> on <sha> (existing-remote-reapplied)`, `behind_base=1`, and then the
very next `make <target>` dies `python3: can't open file '.../scripts/<helper>.py': [Errno 2]` for a
file the base merged minutes earlier.
Mechanism: resuming an existing branch SWITCHES THE TREE to it. A branch left over from an abandoned
attempt (measured: 273 commits it does not share with the base) predates files the base has added, so
the checkout REMOVES them — every later step then runs against a tree older than the Makefile that
invoked it. The same drift makes the post-commit rebase replay ancient history and conflict on the
generated files every time, which reads as "the base keeps moving under us".
Fix: before stashing or checking anything out, count the commits the branch carries that the base does
NOT (`git rev-list --count <base-tip>..<branch>`); above a small threshold (≈20 — a re-run of THIS
issue's work carries a handful, maybe one fix commit) REFUSE, naming the branch, both counts and the
remedy (close its PR, delete the branch, let the sweep cut a fresh one), with an explicit
`--resume-stale` override. Refuse BEFORE the tree is touched so the run's own work, HEAD and the stash
list survive and the run can still report what it built. Then delete the dead branch by hand: a refusal
alone re-offers the same issue to the next sweep every hour.

## A pre-commit guard ran AFTER the step that rewrote the tree

Symptom: a newly added guard step fails on its FIRST production run with "cannot open file
.../<guard script>" — the guard's own file is missing — while the change it protects was fine.
Mechanism: the guard was placed after the branch-adopt/checkout step, and that step switched the tree to
a branch that predates the guard, so the script and its make target were gone before the guard ran. The
message accuses the guard of not existing rather than the ordering.
Fix: a guard that protects a commit or a push runs on the tree the RUN built — before any step that
moves HEAD or switches branches (adopt, resume, checkout) — and the test asserts the ORDER
(`text.find(guard) < text.find(adopt)`), not merely that both appear. Ordering within a step's shell has
the same shape: stage-then-guard is a guard that already lost.

## `fatal: unable to auto-detect email address` inside a rebase

Mechanism: `git rebase` RE-APPLIES commits, so it needs a committer identity even when the commits
already exist and `git commit` earlier worked. A bare container has none configured globally.
Fix: run the identity seam (`make git-identity`) before any rebase, and in the script fall back — only
when `git config user.email` is empty — to the repo's canonical bot identity, printing that it did
(`identity=fallback`). Also label a rebase failure that produced no unmerged paths `rebase=failed`,
not `rebase=conflict`: the two need different follow-ups.

## A green run that closed a duplicate and implemented nothing

Symptom: the run is green, the log ends `verdict=close` / `closed #n with cited evidence`, no PR was
opened, and the user asks why the bot did not implement the issue.
Mechanism: the picker lists only issues carrying its queue label (`agent:implement`, then
`agent:ready`). The issue the bot just retired was filed by a reactor WITH that label; the canonical
issue its evidence cites came from another path and carries none, so the picker will never list it.
Each recurrence therefore burns one of the bot's daily runs retiring a copy of work that stays
invisible — and the bot is ONE issue per run, so it will not switch to the canonical issue in the same
run, however obviously it is the thing to do. Confirm before calling it a defect:
`gh issue view <canonical> --json state,labels` (open + no agent label = invisible) plus the run's
`verdict=` line, and expect `PR: none opened` in the closing comment.
Fix: implement the re-queue in the verdict step — parse the cited references, label each open,
label-free one with the queue label, skip unreadable ones with a printed line, and print the decision
under `--dry`. Test with a fake `gh` that answers the `--json state,labels` lookup and returns non-zero
for a number it does not know; a fake that answers every `issue view` hides the whole class. Until that
ships, unblocking by hand means adding the queue label to the canonical issue (and removing a decided
label if the picker also skips that).

## BOT red on "produced no implementation" over work that was already done

Symptom: the implementer picks an issue, the final step errors `produced no implementation for #n`,
and the issue turns out to be CLOSED with a merged PR that did exactly what it asked.
Mechanism: the pick is a snapshot (`--state open`) and the run then spends minutes working; a merge
can close the issue in that window. The signature of "someone else finished it" is identical to the
signature of a real defect (dead key, burned budget) — same `rc`, same empty diff.
Fix: before declaring failure, read the entity's state through one seam with an explicit contract
(`0` open, distinct code for closed, third for unreadable), end GREEN with one marker-deduplicated
comment when it closed, and keep BOTH the open and the unreadable outcomes RED. Then move the read
EARLIER as well, so a stale pick costs no agent minutes.

## A generated file is stale after a merge, and master is RED with no PR to repair

Symptom: `push` run on the base branch fails a generated-artifact gate (`index is stale`, `112 on
disk` vs `111 in the file`); the PR that caused it was green, and every repair bot needs a PR.
Mechanism: two PRs each regenerate the artifact over a tree that contains only their OWN new entry,
so both write the same count; the squash merge keeps one file and drops the other entry. The red then
lands at the one moment nothing converges it.
Fix: a scheduled KEEPER regenerates + verifies + opens a PR only when a file changed — hourly, since
the slot is the convergence time, and never pushing the base branch. Gate on the diff of EVERY
generated file the keeper owns, and stage them together. Prevention needs a merge queue; state the
window honestly instead of claiming prevention.

## A finished implementation discarded because the agent asked a question at the END

Symptom: the implement leg runs the full 20–40 minutes, the verdict file says `implement`, and the run
then dies with `Input required; detached without cancelling` → `Error 3` → `produced no implementation
for #n`; the commit step is SKIPPED, no PR, no artifact.
Mechanism: the unattended contract (a preloaded `bot-unattended` skill, or the same paragraph in the
prompt) makes an early question unlikely but cannot prevent one — `clarify` is the model's own tool, and
`--yolo --accept-hooks` do not answer it. When the question comes AFTER the work, the exit code is the
only thing that is empty: the checkout is full of a finished change, and a job that maps `rc != 0` to
"no implementation" throws all of it away with the ephemeral runner.
Fix: make the TREE the evidence, not the exit code. After the leg, one step reads
`git status --porcelain` (gitignored scratch such as the captured log and the findings file is invisible
to it) and reports `dirty`; the commit/push step runs on `exited 0` **or** `dirty == true`, the "fail
loudly" step requires `dirty != true`, and the salvage step prints a `::notice::` naming the exit code.
A clean tree with a non-zero exit stays red, because there is nothing to review. Test it by executing
the shipped step's own `run:` text in a real git repo, clean and then with one changed file — a YAML
assertion on the `if:` alone cannot tell you the step reads the tree at all.

## A job that runs the suite checks out a shallow clone, so its QA pass is permanently red

Symptom: a bot job is green while its log carries `[qa-report] make test reported findings (rc=2)` on
every single run, and the failing module is an identity/history guard.
Mechanism: `actions/checkout` defaults to `fetch-depth: 1`. Any check that reads `git log` (an authorship
guard, a commit-trailer check, a "did this branch carry its own commits" probe) fails there BY
CONSTRUCTION, so a job that runs the suite against the default clone has a red that is not about the
code. It is worse when that QA pass is advisory (`data still lands for review`): the standing red makes
a REAL failure indistinguishable from the noise, the run list shows a green job, and the only signal that
would have caught a bad run is on permanently.
Fix: `fetch-depth: 0` on every job that runs `make test` / a QA report target / the authorship check,
with the reason in the comment so it does not look like a stray default. Guard it over the whole
workflow directory: collect each job whose `run:` blocks call those targets (strip shell comments first —
a target named only in prose is not a call) and require an `actions/checkout` step with
`fetch-depth: 0`, plus a non-vacuous assertion that at least two such jobs were found.

## `make: *** missing separator. Stop.` inside a bot

Mechanism: GNU make parses the makefile before any rule executes, so a rebase conflict in `Makefile`
kills every nested `make <target>` and the agent never runs. Fix: snapshot the Makefile BEFORE the
checkout and invoke through it (`make -f "$MK_SNAPSHOT" <target>`), inlining the agent command in that
recipe. Keep the model derived from the repo's alias variable — a static gate asserts it.

## A failing gate did not stop the push

Mechanism: `GATES="make a; make b; make c"` reports only `c`'s exit status. Fix: chain with `&&`,
and supply what the first gate needs (e.g. the test image) instead of dropping the gate.

## `gh pr create` → 502/503/504/timeout, branch and issue left behind

Mechanism: a lost response is not a refusal; the object may exist. Fix: retry transient statuses
bounded, then adopt an open PR whose head is the pushed branch
(`gh pr list --head <branch> --state open --json number,url`); only if none exists raise, naming the
issue and branch so a human can finish.

## Every fork PR is rejected

Mechanism: eligibility resolved the PR's head to the base repository, or the push used `origin` where
the head lives elsewhere. Fix: read `headRepositoryOwner`/`headRepository`, fetch/push that remote
with `--force-with-lease`, and keep third-party forks out with an explicit owner check.

## A 120-minute job killed at the cap, work lost

Mechanism: the model step has no budget of its own, so GitHub's job timeout kills the runner before
detect/commit/push can run. Fix: `timeout-minutes` on the agent step below the job's, `always()` on the
salvage steps, and a failure line naming the budget and what survived (tree/branch/pushed).

## A smoke test that "proves the model works" fails on a clean runner

Mechanism: the smoke judged a store that only exists after a previous run. Fix: judge the store the
run creates; a missing pre-run file is normal, not a credential or image problem.

## `no open PR needs rebasing` while a PR is diverged or `CONFLICTING`

Symptom: the sweep is green, prints one `pass-over:` per open PR, then `action=none` / `rebased=0
failed=0`, and the PR the user is asking about still reads `BLOCKED` or `DIRTY` afterwards.
Mechanism: there are THREE independent skip reasons behind the same line, and only one of them is a
judgement about the PR:

- `is BLOCKED against main` / `is UNSTABLE against main` — the merge-state list (`NEEDS`) accepted only
  `BEHIND`/`DIRTY`. `mergeStateStatus` reports a single state, so a required review HIDES that the branch
  is behind; the branch is also not yet `DIRTY` because the base has not touched its files. Divergence
  must be measured directly:
  `gh api repos/<o>/<r>/compare/<base>...<tip> --jq '{status,ahead:.ahead_by,behind:.behind_by}'`
  (`{"status":"diverged","ahead":1,"behind":2}` is a real rebase, whatever the merge state says).
- `is held by another bot: commented on by <login> N min ago without a done comment` — comment
  occupancy (see below). The merge state was never examined.
- nothing at all — the branch really is current.

Fix: read the reason, never the summary line. For an occupancy skip, release the subject with the
bot's `done` marker or wait out the claim TTL; widening `NEEDS` does not help, and dropping the
occupancy check lets two runs rebase one branch concurrently.

## Any recent non-`done` comment occupies the subject — your own included

Symptom: a PR is `CONFLICTING`, the bot that owns rebasing it skips it naming the PR's author and an age
in minutes, and the comment it quotes is an ordinary status report with local gate output.
Mechanism: occupancy is "the newest non-self comment has not been concluded by a `done` marker", so
EVERY comment — a human's evidence dump, a reviewer's note, another bot's progress line — is a claim
held for the claim TTL (30 min in these repos). Nothing distinguishes prose from a claim unless a kind
is parsed.
Fix: treat it as a protocol. Conclude a comment with the bot's `done` marker when a bot must act next,
and when reporting to the user say plainly that the subject is held and for how long rather than
re-running the sweep. Do not "fix" the matcher to ignore human comments without also reading the
concurrency reason it exists for.

## A `workflow_run` merge job goes red over a PR that already merged

Symptom: the first run after the merge workflow lands is `failure` in ~10 s, the resolving step exits 1
with `gh: Not Found (HTTP 404)`, and the PR it names is already `MERGED`.
Mechanism: the job resolves its PR from the completed run
(`gh api repos/$REPO/actions/runs/$RUN_ID/pull_requests`) and falls back to
`gh pr list --head <owner>:<branch> --state open`. For a run belonging to a PR that has since merged,
both are empty — correct for an OPEN PR, wrong for a landed one.
Fix: distinguish "no open PR because it merged" (landed — exit 0, say so) from "no open PR and it is not
merged" (the green PR was dropped — exit non-zero, loudly). Reading `state` before deciding is the whole
fix; a blanket `exit 1` on an empty resolution reddens every post-merge bootstrap run.

## A refresh PR red on a data guard that names a captured figure

Symptom: `validate` red inside a gap-analysis module, with a line like
`model/engine/field on <post> (captured ['5.95GB'])`, while the store row for that post plainly exists.
Mechanism: two independent causes, and the line tells you which.

- The merge rule PINNED or SHRANK the figure. A loop that fills a dimension "only when the row has
  none" forbids RAISING as well as overwriting; and when the group's representative row is the one
  carrying the smaller figure, the merge writes that smaller one over the better one. The defect is in
  the rule, not the refresh — the PR did nothing wrong.
- The guard's whitelist does not list this model. Such a check enumerates the models whose figure
  legitimately lives only in prose, so a new model is a CAPTURE gap, not an error.

Fix: for the rule, make numeric dimensions raise-only — a comparable figure on both sides keeps the
larger (`950MB` never beats `1.2GB`), an unstated side fills, a text dimension is never replaced by a
different spelling, and `None` is never stored — then test the REAL merge function in both arrival
orders plus the shrink case. For the whitelist, write the stated value into the structured field and
re-run; widening the set turns a capture gap into policy. Either way regenerate the README afterwards,
because the store changed and the generated file must match it.

## A bot job reds in a gate step — the image BUILD underneath it

Symptom: the job dies in a step whose name is a *gate* (`Prove the … is active`, `preflight`, `smoke`),
several unrelated bots go red inside the same hour, and none of them is on code the change that “caused”
it touched.
Mechanism, in three links:

1. the job needed a runtime image whose tag is a hash of its Dockerfile + install scripts; that tag moved
   when some merged change edited one of those inputs;
2. the image is published only by HAND (a separate owner-guarded dispatch, excluded from the normal image
   publish because the default token may not create the package), so nothing publishes the new tag on
   merge and no CI job builds it on the PR — the PR went green having never built the thing it changed;
3. the next bot job finds `<tag> is not published (an edited Dockerfile or lockfile): building <local>
   here`, builds inline, and THAT build is the first time in days the floating half of the image is
   resolved (a `latest`-fetching CLI installer, a plugin installed with live dependency resolution). A
   change upstream in either one breaks it, with no repo change at all.

Read the tell before theorising: `docker pull <ref>` in the log = the published, already-tested artifact
ran, so the image is innocent; `is not published … building here` = the run is compiling its own toolchain
and every later error belongs to that build. Then read the docker build step numbers (`#11`, `#12`) and the
install script's own `fail` line, not the gate step's name.

Sub-mechanism worth knowing: a plugin installed with dependency consent gets a generated uv workspace, and
`uv lock` resolves UNIVERSALLY — every marker split, not just the runner's. An optional extra that pulls a
package with no wheels for a split the project never targets (e.g. `torch` under
`python_full_version >= '3.14'` + android) makes the whole lock unsatisfiable: `error: No solution found
when resolving dependencies for split (markers: …)`, then `Plugin '<x>' conflicts with the dependencies
pinned by Hermes core … it was not admitted`, then the install script's hard gate failing and the build
exiting non-zero. The unused extra is the cause — check whether the code imports it lazily before assuming
the package is required.

Fix (a) — take the unused extra out of the resolution, and know that the OBVIOUS fix does not work.
Adding `[tool.uv] environments = [...]` to the plugin's own pyproject is the hint uv prints, and it fails
anyway: the host CLI generates its own workspace for the plugin's dependencies and does not inherit the
plugin's `[tool.uv]`, so the identical `uv lock exited 1` comes back. What does work is three explicit
steps instead of one consented install: install with `--no-deps` (clone + provenance, resolve nothing),
remove the unused extra from the **installed** copy's pyproject, then run the CLI's `enable` subcommand,
which resolves a graph that now has a solution. Make the removal ASSERTED — match the extra's own line
and exit non-zero when it is absent — so a future pin that renames or drops it fails the build pointing
at the decision instead of resolving extras blind, and keep every enabled/pinned/configured proof
afterwards. Never turn the gate into a warning: a silently plugin-less bot is the defect the gate
exists for.

Reproduce the failing layer in seconds, not minutes: do NOT build the whole image. Run its install
scripts inside the image's BASE (the repo's own test image) in a throwaway container — copy them in, run
the CLI install then the plugin install, `tail` each — and you get the real resolver output on the real
base. Use the same container to A/B a candidate fix by pointing the CLI's home at two different temp
dirs and running both variants, so "this fix works" is measured rather than reasoned.

Fix (b) — close the shape: build (do not publish) that image in CI on any PR that moves its hash so
the build cannot rot unnoticed, publish it on merge so bot jobs stop rebuilding inline, and pin what the
build installs so the tag means what it claims. An artifact published only by hand is an unvalidated
artifact.

## Gate failures that are NOT the bot's behaviour

- `openspec-tasks-check`: any unticked `- [ ]` reds the OpenSpec CI job — usually an unticked
  verification task, not a spec error. When it fires on an IMPLEMENTER's own PR, the change record is
  usually complete and only the bookkeeping is missing (the agent writes the change first, then never
  returns to tick boxes): the fix loop cannot help, because a round that changes nothing stops it
  (`round 2 fixed nothing: the failure is byte-identical`). Repair shape — read `tasks.md`, verify each
  box against the tree, tick the ones that are genuinely done, and REWRITE a task that cannot be done
  here (a protected file such as the rulebook) as "OWED, not applied" with the exact text recorded in
  `findings.md` for an approver; leaving it unticked means the gate can never pass, and faking it is
  worse than the red.
  **A repair round may RE-CREATE the change instead of ticking it.** Because the leg writes the change
  before it knows what it will edit, a later fix round can conclude the record is wrong and add a SECOND
  change directory for the same work — different name, its own `tasks.md` with every box unticked, and a
  constant the shipped code never implemented (a `SCRAPE_ASK` beside a shipped `SEARCH_TOOL_ASK`). The
  gate then reports the NEW directory, so it looks like the bookkeeping you just fixed regressed. Read the
  unticked path it names, compare both directories against the code (`grep` the constant the tasks name —
  absent = never implemented), keep the one that matches what shipped, `git rm -r` the duplicate, and say
  so in the commit message: two records for one change is a duplicate, not an additive requirement.
- `check_docs`: a help-visible (`##`) make target missing from README, or an `agent-wiki/` entry with
  no issue/PR reference.
- `check_wiring`: a script CI runs with no make target, or a file-less target that is not `.PHONY`.
- `check_dispatch_forms`: a dispatch `name` that does not state the work, an undocumented input, or a
  stale README table (regenerate it).
- `check_pr_hygiene`: `--body-file -` is read as a placeholder body; pass a real file.
- `check_pr_authors`: the producer source is parsed — `git -c user.name=…` is read verbatim; set
  `git config user.name`/`user.email` to the exact allowlisted spelling.

## Test shapes that hold

- Drive the real script against a real scratch git repo and a bare remote; put a small `gh` script on
  `PATH` that answers JSON. Assert on the pushed commit, the written files and the decision output.
- Two variants per fix: the OLD code fails on the fixture and the NEW code passes on the same one.
- For a workflow change, parse the YAML and assert on the step's `if:`/`timeout-minutes` — a workflow
  edit with no assertion is untested. A bare `on:` key parses as boolean `True` under YAML 1.1; read
  `doc.get("on") or doc.get(True)`.
- Prove a NEW guard red against the base version of the file (`git show origin/<base>:<path>`) before
  calling it a guard — a check that passes on both versions locks nothing.
- A workflow test that stubs `make` maps `$1` to the real script; extend the stub when a step's
  target changes or every push-path assertion fails with "unexpected target".
- A fixture repo must carry every file the shipped step stages — a step that `git add`s two generated
  files fails on a fixture holding one.
- Run the module in the CI image, not on the host: a missing optional import makes it SKIP with a
  green exit, and a SKIP prints no per-check lines.
