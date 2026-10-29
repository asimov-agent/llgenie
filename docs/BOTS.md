# Bots, CI and verification

How llgenie's automation works: which bot does what, how a leg runs (Hermes project skills),

which credential reaches which shell, how the transcript is redacted, and how a green PR is

merged. The user guide is `README.md`; the code map is `docs/ARCHITECTURE.md`; each change's

own record is a dated note in `agent-wiki/` with its own row under `docs/changes.d/` — one row per
file, rendered into `CHANGES.md` by `make changes-index` (issue #934).

The sections below follow the legs in the order a change travels: pipeline and skills, the
implementer, credentials and redaction, review and merge, the architecture bot, failure handling,
manual dispatch, verification/CI, contributor rules, and the guards that keep the bots apart.

[Issue implementer](#the-issue-implementer-issue-248) · [Secrets](#no-secret-value-reaches-a-log-283) ·

[Code review](#the-code-review-bot-issue-269) · [Merge](#a-green-conflict-free-pr-is-merged-by-ci-issue-482) ·

[Architecture bot](#the-architecture-bot--docsarchitecturemd-follows-the-code-issue-449) ·

[Run-failure reactor](#the-run-failure-reactor-issue-286) · [Dispatching by hand](#dispatching-a-bot-by-hand-issue-276) ·

[Verification and CI](#verification-loop--ci-containerized--same-everywhere) · [Contributor rules](#documentation-is-part-of-the-change-issue-257) ·

[Trigger guard](#who-may-start-a-bot-or-publish-the-trigger-guard) · [Isolation](#how-the-bots-stay-out-of-each-others-way)

### Bots sync with upstream `main` before they start work (issue #303)

A bot never works from a stale base:

- `make bot-sync-main` — fetch upstream `main` and **reset the working tree to it**. The
  **implementer** runs this before it picks an issue, so the branch it pushes is based on the
  latest `main` rather than on whatever `actions/checkout` happened to have when the run began.
- `make bot-sync-branch` — fetch upstream `main` and **rebase the checked-out PR branch onto it**.
  The **fix-bot** runs this before its repair loop, so a green repair is green on top of current
  `main`. Exit code **2** means the branch does not rebase cleanly: it is reported and left alone,
  because resolving that conflict is the **rebase-bot's** job (`make rebase-bot`, issue #246).
- Both fail loudly if `main` cannot be reached — a bot that cannot sync must not start. The
  fix-bot pushes with `--force-with-lease` afterwards, because a sync rewrites history; if another
  bot pushed meanwhile the push is rejected instead of clobbering it.
- The **fix-bot** repairs a PR whose head is the base repository **or the fork its token may push
  to** (`make fix-bot-sweep OWN_FORK=andyholst`, issue #340). Every llgenie PR is opened from the
  fork, so without the allowlist the scheduled sweep passed over every PR and repaired nothing;
  the branch is now checked out from — and pushed to — the PR's own head remote.
- **The fix-bot is woken by the failure it repairs** (issue #538). `fix-bot.yml` runs on `workflow_run` for
  `CI` when a `pull_request` run concluded `failure`, resolves that run's PR with `make fix-bot-resolve`
  (issue #629), captures the failed run's log, and dispatches the repair for **that** PR
  (`make fix-bot-sweep PR=<n>`). The hourly sweep stays as a fallback. Up to **5** attempts per head
  (`FIX_ROUNDS`/`rounds`, counted by the PR's `fix(bot):` commits); a failure this runner cannot reproduce
  (a macOS-only job, a GPU-only image test) is repaired from the captured log and marked **UNVERIFIED** —
  CI re-runs and re-triggers, so a real flake is retried instead of being dropped because a Linux check
  was green.
- **A failed run whose PR already landed is not a failure** (issue #629). `workflow_run` reports arrive
  after the merge that made them moot, so `make fix-bot-resolve` answers an empty `number=` (exit 0,
  "nothing to repair") and the sweep proceeds as its scheduled form does — it picks the PR that deserves
  the bot, and does nothing when none does. The merge gate keeps the opposite reading: `make
  auto-merge-resolve` still **fails loudly** when nothing resolves, because a green PR must never be
  silently dropped. One resolver (`scripts/resolve_run_pr.py`, `--allow-none`), two documented answers.

Driven by `scripts/bot_sync_main.sh`; `tests/test_bot_sync.py` runs the rules through a real
scratch git repository.

### Every target is declared `.PHONY` (issue #392)

`make` runs a recipe when no **file** carries the target's name, so a target that produces no such
file must be in the `.PHONY:` block — otherwise any file named after it (a left-over scratch file, a
checkout on a case-insensitive filesystem) shadows it and make prints `make: 'test-env' is up to
date.` while running nothing. That is a green run that verified nothing, so `make check-wiring` now
compares the `.PHONY` blocks of `Makefile` and `tools/Makefile` against every target they define and
fails naming each undeclared one; `make wiring-report` prints the declared / recorded / undeclared
counts. A target that genuinely writes a file of its own name is exempt — but only as a dated decision
under `not_phony` in `tests/fixtures/host-only-wiring.json`, which is refused without a reason and
reported stale once the target is declared or gone.

### Every `.PHONY` entry names something that runs (issue #883)

The declaration works in both directions, and only one was checked: a `.PHONY` key whose recipe is
gone (the debris a union resolution leaves when one side's commit is dropped) passed every gate. It
is not a loud failure either — because the name IS declared phony, `make <name>` prints
`make: Nothing to be done for '<name>'.` and exits **0** (measured; the same name with no `.PHONY`
entry fails `No rule to make target`, exit 2). That is the #392 hazard made permanent: a green no-op
that needs no file to shadow it. So `make check-wiring` now asserts the reverse direction too — every
`.PHONY` entry must name a target with a recipe, an inline `;` command, or at least one prerequisite
(a declared alias such as `loop: loop-harness` / `all: generate-requirements venv-install`). A key
with no target at all, and a key whose target has neither a recipe nor a prerequisite, are both
errors; every offender is named in the same pass, so one edit fixes the set. On `main` (measured at
`7e99e199`) there are zero offenders: the four recipe-less keys are all aliases. `make wiring-report`
prints the can-run / no-target / runs-nothing counts.

`make sync-registry` vendors a **normalised** copy of upstream's store (issue #687): `formats`
restricted to the vocabulary, a non-format name restated from the row's repo/id, a duplicate id
dropped — printed, one note per change — while every model row upstream lists is kept, because a
name heuristic cannot tell a finetune from a run on one box. The `registry-sync` workflow runs `make sync-registry` weekly (cron `19 5 * * 1`,
Monday 05:19 UTC), regenerates the quant catalog (`make sync-quant-catalog`), the
trend-list matrix (`make render-trend-list-matrix`) and the per-engine gap
(`make render-engine-skill-gap`), and opens a PR when any of those files changed.
The matrix fixture is the review of the new list: one block per architecture, card
size, and RAM size, in README order, with the server `llgenie --matrix` would put
first. A sync that updates `data/models.json` and leaves the fixture stale fails
`make test-unit`.

A changed store also opens **one** issue that states what changed (issue #704):
`make sync-change-issue` renders `make registry-change-report` — `generated_utc` old → new,
added/removed/renamed model ids, new and gone engines, the `formats` vocabulary, every contract change
(required keys, new `backend` enum values), the README row changes and the derived-table counts — into the
issue shape, labelled `agent:implement`, with a checklist of what llgenie must now do. The workflow runs
it with `if: always()`, so the issue exists even when a gate reds and the PR step is skipped: it is what
the landing change is written from (#677/#693). The body carries a marker for the store's
`generated_utc`, so a re-run updates that issue instead of filing another.

A **green** sync PR is reviewed into its own work item (issue #709). `make registry-review-brief` is
deterministic and offline: it reads the open `chore/registry-sync` PR and every check bucket, and — only
when every check is green — renders the VRAM selection check: for each `(arch, vram, ram)` the trend list
is built from, the models that fit that card and, per model, the server `rank_engines()` puts first with
its measured t/s. It reports `slower-than-class` (the named server is not the fastest of its own rank
class), `no-engine` (a listed model no image can run), `unmeasured` (a named server with no figure) and
`empty-tier` (a card that lists nothing).

The one agent leg runs under `.hermes/skills/registry-sync-review/SKILL.md` and writes `registry-review.md`
only: the issue title and a body in this repository's issue shape, quoting the measured numbers. Then
`make registry-review-publish` files ONE issue labelled `agent:implement`, keyed by the store's
`generated_utc` (`<!-- registry-sync-review: <utc> -->`), editing it on a re-run and linking the store's
change report (#704) instead of repeating it. Every secret-spending step in
`registry-sync-review.yml` is gated on the brief's `action == 'review'`, so an hourly run with no green
PR costs nothing — measured on `main@2cbfb11`, `make registry-review-brief` prints `action=skip` (no open
sync PR) and still renders 92 `no-engine` findings over the 80 cases, on three models
(`nemotron-3.5-lightning-30b-a3b`, `glm-5.3-flash`, `llama-3.1-8b`), each listed on an architecture no
engine image can run it on.

#### The unit gate is hermetic: live-Hub work has its own target (issue #438)

`make test-unit` is the gate every change runs, so nothing in it may leave the machine. Three tests
used to: two answered every link in the README's trend table and in the vendored registry, the third
downloaded a model's full GGUF from the Hub. On 2026-10-21 a run sat inside that download for five minutes while pytest's
`faulthandler_timeout` printed a stack dump — and still reported `4911 passed`, because a dump is not a
verdict — and the link test later went red on a Hub `429` while the tree was fine.

Those three node ids are now **de-selected** from the gate by exact node id (the `deselect` roster in
`tests/fixtures/unit-suite.json`, a dated decision with a reason and its owning target — never a `-k`
expression) and run by:

```bash
make test-hub-live    # the trend/registry links answer, and a missing model really downloads
```

`tests/test_hub_live_target.py` pins both halves: the node ids are out of the gate, the target names
exactly them (and is `.PHONY`), every de-selection still names a test that exists, and each reason names
the target that runs it.

`tests/test_strata_download.py` is the same class of work and is kept out the same way (issue #437: the
macOS runner's `git fetch` of Strata's pinned commit exited 128 and turned the gate red with nine errors
while the tree was fine). It fetches that commit over git, pip-installs the engine's requirements, reads
the live Hub and runs Strata's real `serve/server.py`, so the whole file is recorded in the roster's
`excluded` — a dated decision with its reason, issue, date and owning target — and run by:

```bash
make test-strata-live    # Strata's pinned commit is fetched, its GGUF choices come from the live Hub,
                         # and its real server answers "hi" on /v1/chat/completions
```

A live read that stays IN the gate asserts the invariant it exists for, never a value upstream may
rename or remeasure: the litertlm download plan pins the format and repo (not the build's file name) and
the live-registry ranking case pins "the raw maximum is not the recommendation" (not that some engine is
still unskilled) — both reddened every PR when upstream moved (issue #575).

The Strata live tier derives what it expects from the pin it has just fetched, never from a list in the
test: the families the pinned `setup.py` declares with no `hf` must equal the map's `hub: false` set
(empty at v0.1.43, `nvfp4` at v0.2.7). The hermetic side locks the family SHAPE instead — Hub-hosted
(`repo` + `revision` + `subdir`, no `hub` key) or explicitly not-Hub (`hub: false`, no repo), never
both, never neither — because the v0.1.43 snapshot test red the *correct* v0.2.7 bump on
`nvfp4 unexpectedly marked not-Hub` (PR #605).

`tests/test_strata_live_target.py` pins that boundary hermetically: the file is out of the gate the
aggregator computes, `make test-strata-live` names it and is `.PHONY`, the roster entry names issue #437
and its target, and the file still carries the live work the decision describes.

An upstream engine with no llgenie skill is left out of the startup list (no
image). That omission has to be a **decision**: `data/unsupported-engines.json`
records, per engine, `decision` (`not-shipped` | `deferred`), the `decided` date,
a `reason` and the tracking `issue` — 8 engines are recorded today
(`make engine-skill-gap` prints them, `make render-engine-skill-gap` writes the
per-engine view into `data/engine-skill-gap.json`). An engine upstream adds with
no skill and no entry is **new and unresolved**: `make check-engine-skill-gap`
fails naming it, and the sync opens one tracking issue per new engine, so the gap
is a linkable work item instead of a log line. That issue is created **in the bots' queue**: the sync
passes no `--label` on the create — it is silently dropped on the runner path — and labels the issue
through `POST repos/<repo>/issues/<n>/labels`, then reads the labels back and **fails the step** when
`agent:implement` is missing (`gh issue edit --add-label` is GraphQL `addLabelsToLabelable`, which the
runner's PAT refuses outright — measured on registry-sync run 40682255828; #724/#757). Its body names
`make engine-skill-scaffold ENGINE="<registry name>"` — the target that writes
`skills/engines/<id>/SKILL.md` from the registry's own entry (engine, repo URL, backends) and leaves
every upstream fact it cannot prove EMPTY, so `make skills-validate` names the remaining work instead of
a guessed pin building. The one key it does derive is `os:`: the same backend evidence decides it —
`Metal` alone is `darwin` (a native Apple-Silicon engine, never an image), Metal plus a Linux backend
is `darwin` + `linux`, no Metal is `linux` — and the scaffold's own to-do list states which evidence
produced the value, so a wrong one is corrected from the pinned repo rather than guessed (issue #772).

**Who runs the scaffold: the issue-bot, before the agent starts.** `scripts/issue_implementer.py
dispatch` (the `make issue-bot-dispatch` step of `issue-bot.yml`) recognises a tracking issue by the
title `engine_skill_gap.issue_title()` gives it, runs `engine_skill_scaffold.scaffold()` for that
engine, and appends a `## Scaffold` section to `issue.md` naming the file it wrote, the backends and
what is still empty — so the implement leg starts from a correctly shaped skill instead of a blank
page, deterministically rather than by the agent remembering to. A dry dispatch writes nothing, and a
plain issue gets neither the section nor a file. An engine the vendored store no longer names is
reported in that section instead of failing the run (the issue is then stale, not unworkable).
`data/engine-skill-gap.json` also
names the models no engine can offer at all, so a model cannot vanish from the
list unnoticed. `make skills-validate REGISTRY=data/models.json
UNSUPPORTED=data/unsupported-engines.json` tolerates the recorded decisions per
engine and still fails on an undecided one.

**The sync job carries the new engine; ci-unit refuses it (issue #683).** A store that first names an
engine llgenie does not ship must still be able to land, or the data that names the engine never
arrives and the issue that would decide it never opens. So `registry-sync.yml`'s check step runs that
same command with `ALLOW_NEW_ENGINES=1`: every shipped skill is still validated against the registry
it is about to be read with, a recorded decision is still honoured, and a **new** engine is named
(`[skills-validate] NOTE: … carried`) instead of failing the job. The step right after opens one
tracking issue per new engine, and `make check-engine-skill-gap` in `ci-unit` is what keeps the
resulting sync PR red until each engine ships a skill or gets a dated decision. Measured before this
(2026-10-26): upstream went 23 → 106 models and 8 → 40 engines, `skills-validate` exited 1 with 16
new engines, and no sync PR had landed since 2026-10-13.

That spawn step runs with `if: always() && steps.diff.outputs.changed` (issue #758): a store naming an
unshipped engine is exactly the store whose check step reds, so gating the spawn on that step's
success used to suppress the one work item that explains how to un-red it (measured: run
`40554900569` — check failed with `36 failed, 14486 passed`, the change issue ran, the spawn and the
PR step had no log at all). Its recipe re-checks the store diff and exits before `make`, so a
no-change run still files nothing, and `Open / update the sync PR` keeps its change-only condition: a
file whose checks did not pass is never pushed.

The `engine-bump` workflow runs on its **own** cron (weekly,
Monday `23 6 * * 1`, separate from the registry sync) and pins every engine skill
to the latest upstream commit, opening a PR per changed engine (issue #107):

```bash
make engine-bump-plan [ENGINE=<id>]   # which engines moved upstream (git ls-remote only)
make engine-derive ENGINE=<id> [SHA=] # derive build params from the upstream tree (no LLM)
make engine-bump ENGINE=<id>          # pin + derive + apply + regen (no push)
make engine-bump-daily [DRY=1]        # plan -> bump every moved engine; DRY=1 prints only
make engine-params-review-brief ENGINE=<id>   # the engine's own docs at its pin + current params -> params-review-in.md
make engine-params-review ENGINE=<id>         # Hermes reviews them against those docs (proposes only cited -D flags)
make engine-params-review-apply ENGINE=<id>   # validate proposals (flag AND quote must be in the upstream file),
                                              # apply accepted ones to the skill, regenerate, write the PR section
make test-engine-bump-live            # the pinned TensorFold release archive: list, classify, checksum and RUN it.
                                      # engine-bump.yml runs this after make engine-bump writes the new pin,
                                      # and only for the tensorfold row. ci.yml does not.
make test-hub-live                    # the two live-Hub checks kept OUT of `make test-unit` (issue #438):
                                      # the README's trend links answer, and a missing model really downloads
make test-strata-live                 # the Strata download/serve checks kept OUT of `make test-unit`
                                      # (issue #437): the pinned commit is fetched over git, the GGUF
                                      # choices come from the live Hub, and Strata's real server answers
```

**The derived params are also reviewed against the engine's own documentation (issue #583).** The
bump proves the params *compile*; it cannot prove they are *right for this engine version and this
arch* — the derive is structural (CMake options, renames, recipe `-D` flags, toolchain pins), so a
flag upstream's docs now recommend but the old params never had is invisible to it. After
`make engine-bump` and before the PR opens, the bump job runs the three targets above:
`engine-params-review-brief` writes `params-review-in.md` (the engine's README/`docs/`/backend recipe/
`CMakeLists.txt` at the pinned sha, plus the params this repo builds with), the `engine-params-review`
agent leg (Hermes, project skill `.hermes/skills/engine-params-review/`) writes `params-review.md` as
one `PROPOSE <backend> <-DFLAG> DOC <path> "<quote>" WHY <reason>` line per documented parameter, and
`engine-params-review-apply` decides. The brief is a **ranked, bounded selection** of that tree, not all
of it (issue #597): benchmark/example/fixture trees never enter, the flag-proving files (root
`CMakeLists.txt`, `Dockerfile*`, `docker/**`) are taken first within their own share (45 KB), the rest is
ranked by build relevance — `option(`, `-D`, `CMAKE_`, `CUDA_ARCHITECTURES`, `GPU_TARGETS`, `cmake`,
`cuda`, `rocm`, `hip`, `torch`, `pip install`, `apt-get` — up to 80 KB, and the brief states how many
files the budget left out (`strata` went from 1.8 MB / 424 sections to 81 KB / 8, with its
`docs/AMD_HIP.md` and `docs/DETAILS.md` still in). **The host stays the writer**: a proposal is applied only when
its backend is one the engine builds, the named file exists at the pin, the flag's `NAME` is in it and
the quoted evidence is a substring of it. Anything else is dropped and listed in the PR body under
`Documentation review`, together with what was applied and from which document. A review that
proposes nothing says so; a review that fails never blocks the bump (the PR still opens).
The `engine-bump-rebase` workflow (daily cron `41 5 * * *`, issue #208) keeps
those open `chore/engine-bump-*` PRs current with the latest `main`: it finds
every open engine-bump PR and, when one is behind `main`, forward-merges the
latest `main` into it and force-with-lease-pushes it back — automatically, and
only when the merge applies cleanly (a conflict is left for a human). It reuses
the SAME sync logic via the shared module
`scripts/engine_bump_sync.py` (imported by `scripts/engine_bump_rebase.py`), so
there is no duplicated implementation. Run it locally with
`python3 scripts/engine_bump_rebase.py --dry` to preview without pushing.
Its collaborator guard sends `Authorization: Bearer $TOKEN`, with `TOKEN`
set to `secrets.GITHUB_TOKEN`, the same header `engine-bump` uses.

Before that commit, and only when both the old sha and the new sha are known,
the bump reads `requirements.txt`, `pyproject.toml`, and `Dockerfile` with
`git show <sha>:<path>` and keeps the names the new pin added (issue #186).
A release move compares the old tag's tree to the new tag's tree. A name
already at the old tag is not installed as new. One fixture runs that bump
through the pin and `make generate-engine-params`, and the test reads the
Dockerfile that command wrote. A pin that only removes packages prints those
names. The bump does not commit.

## Bot pipelines are isolated (issue #275)

Every bot runs on **its own pipeline**: a cron minute no other bot owns on any day, and a
`concurrency:` group of its own (`cancel-in-progress: false`) so a manual `workflow_dispatch`
queues behind its scheduled run instead of overlapping it. The current slots:

| Bot | Cron | Minute today |
|---|---|---|
| `issue-bot` | `23 6 * * *` | daily 06:23 |
| `fix-bot` | `17 * * * *` | hourly at :17 |
| `queued-alarm` | `7,37 * * * *` | twice hourly (:07, :37) |
| `engine-bump-rebase` | `41 5 * * *` | daily 05:41 |
| `registry-sync` | `19 5 * * 1` | Monday 05:19 |
| `registry-sync-review` | `55 * * * *` | hourly at :55 (issue #709) |
| `engine-bump` | `53 6 * * 1` | Monday 06:53 |
| `architecture-bot` | `47 */6 * * *` | every 6 hours at :47 (issue #449) |
| `auto-merge` (recheck sweep) | `3,33 * * * *` | twice hourly (:03, :33 — issue #560) |
| `code-review-bot` | `31 7 * * 1` | Monday 07:31 |
| `issue-dedupe` | `51 */6 * * *` | every 6 hours at :51 |
| `issue-refiner` | `43 * * * *` | hourly at :43 |
| `rebase-bot` | `29 */6 * * *` | every 6 hours at :29 |
| `search-smoke` | `11 7 * * *` | daily 07:11 |
| `security-bot` | `9 5 * * *` | daily 05:09 |
| `security-scan` | `5 4 * * *` | daily 04:05 (`docs/SCANS.md`) |

The table is the isolation map, not the full cadence record: every scheduled workflow's own file is the
authority for its cron, and a bot missing here is still inside the guards below.

`tests/test_bot_pipeline_isolation.py` (in `make test-unit`) expands every scheduled
workflow's cron into its `(minute, weekday)` slots and fails if any two bots share one, or if
a bot declares no concurrency group — so a future bot that lands on a used slot goes red at
`ci-unit` instead of silently racing.

**Every minute is odd, and that is enforced (issue #560).** GitHub drops the top-of-hour and
half-hour slots under load — this repository measured it: `auto-merge.yml`'s `*/30 * * * *`
(`:00`, `:30`) produced **0** `schedule` runs of 66 while `queued-alarm` (:07/:37, 53 runs),
`fix-bot` (:17, 48), `issue-refiner` (:43, 45) and `rebase-bot` (:29, 30) all fired normally in
the same window. `every-cron-minute-is-odd` is now part of the same guard: a cron whose minute
field expands to any even minute fails `make test-unit`, naming the workflow and the minute, so
`*/N`-at-zero cannot come back. A second guard, `the-auto-merge-sweep-stays-scheduled`, keeps the
sweep's schedule in place: the always()-on-every-CI-completion retry (#558) cannot retry a
deferral that clears with no push at all, and only the cron can.

## A bot's rules are a Hermes project skill, not a Makefile string (issue #577)

Every agent leg runs under a skill in **`.hermes/skills/<name>/SKILL.md`** — Hermes's own layout —
preloaded with `hermes -s <name>`, and the leg's inline prompt is a pointer plus that run's
parameters:

```make
_issue-bot-triage: # (internal) the decision, not the change
	hermes -z "Follow the preloaded skill issue-triage. Its Input is issue.md and its Output is triage.md." -s issue-triage,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
```

Measured before this (issue #577): prompts of 1005-1629 characters per leg, the same
`UNATTENDED: …` paragraph seven times, and every leg starting with "Load AGENTS.md" to learn what its
own bot may do.

| skill | leg | what it decides |
|---|---|---|
| `bot-unattended` | every leg | the shared unattended contract (never ask, never wait) |
| `issue-triage` | `make issue-bot-triage` | `implement` / `refine` / `close` → `triage.md` |
| `issue-refiner` | `make issue-refiner` | restate the issue or say it is clear → `refine.md` |
| `issue-dedup` | `make issue-dedup` | duplicate or distinct → `dedup.md` |
| `issue-implement` | `make implement-issue` | the change + `pr-body.md` |
| `architecture-doc` | `make architecture-bot-doc` | rewrite `docs/ARCHITECTURE.md` |
| `agent-fetch` | `make agent-fetch` | one masked URL fetch → `$OUT` |
| `rebase-conflict` | `make rebase-bot-agent` | resolve a stopped rebase |
| `pr-fix` | `make fix-loop-image` | repair a red PR check |

**A leg's command must not carry a literal comma (issue #641).** `rebase-bot-agent` is the one leg
that inlines its `hermes …` command inside `$(call scrubbed_run,…)` — it cannot use a `_<leg>` target,
because the container's `Makefile` is the conflicted file (issue #460) — and `$(call …)` splits its
arguments on commas in the **unexpanded** text: `-s rebase-conflict,bot-unattended` kept only
`-s rebase-conflict`, the shell got an unclosed quote, and the leg exited 2 before the agent started
(every conflicted PR stayed `DIRTY`; run 40212644476, #602/#605). The skills now come from
`$(REBASE_BOT_SKILLS)`, and `tests/test_agent_legs_quoting.py` expands **every** scrubbed leg with
`make -n` and fails on an odd number of single quotes or a `-s` list that lost its second skill.

Each skill has three sections: `## Inputs` (the files the host prepared), `## Output` (the ONE file
the leg may write — the deterministic step after the agent does every GitHub write) and `## Rules`
(what it must not do). The fix bot's former `scripts/fix_bot_rules.md` is the `pr-fix` skill now;
there is no second rules file.

**How Hermes finds them.** It reads skills from its own home and from `skills.external_dirs`, so the
agent image registers the checkout's directory once, at build time
(`scripts/hermes_skills_register.py`, called by `scripts/install_hermes_ci.sh`:
`skills.external_dirs` → `/repo/.hermes/skills`, the mount point every leg runs in) and reads the
value back — a registration that did not land fails the build, not a bot run. The script writes a
real YAML **list** because `hermes config set` takes a list on a newer CLI and silently stores a
string on the pinned `hermes-agent==0.19.0`, which then resolves to no directory at all.

```bash
make check-agent-skills       # CI (ci-unit): every leg preloads a real skill, prompts stay pointers
make agent-skills-report      # every leg with its prompt size + preloaded skills, every skill's frontmatter
make hermes-skills-register   # register this checkout's .hermes/skills in a Hermes home (HOME_DIR=, DIR=, CHECK=1)
make test-agent-skills-live   # prove Hermes LOADS each leg's skills (hermes-agent's own preload path)
```

`make check-agent-skills` (`scripts/check_agent_skills.py`) fails a leg with no `-s`, a name with no
skill, a frontmatter `name` that disagrees with its directory, a skill missing one of the three
sections, a prompt over the 400-character pointer budget, an inlined unattended contract, a skill no
leg preloads, a `scripts/fix_bot_rules.md` that came back, or an `AGENTS.md` that no longer states the
rule. `make test-agent-skills-live` is the load proof: it feeds each leg's `-s` list to
`agent.skill_commands.build_preloaded_skills_prompt` — the function `hermes -z … -s <name>` calls
before the model's first turn — against a home registered by the image's own script, and asserts every
name resolved and each skill's content is in the prompt the model receives. It runs in the
`agents-read` job's venv (hermes-agent pinned), so a missing agent is a loud failure, never a skip.

`skills/engines/` is **not** this: those describe inference servers, are read by
`make generate-engine-params`, and are never loaded by an agent.

## The issue-implementer (issue #248)

Nothing takes an issue and produces its first PR — until now. The
`issue-bot` workflow (`.github/workflows/issue-bot.yml`) implements ONE issue
per run, at most **3 per UTC day**, one at a time, each left as a draft-free
reviewable PR that is **never merged**. It replaces the old host watch-loop
in CI (that loop was removed in #210).

The implement step has its **own 90-minute budget** inside the job's 120 (issue #476), so a leg
that runs long fails by name while time remains; the change detection and the commit+push run with
`always()`, so whatever the agent wrote is salvaged into the branch and opened as a PR.

The **dispatcher** is deterministic (no LLM, stdlib only) and is the
unit-testable core — `scripts/issue_implementer.py`:

```bash
gh workflow run issue-bot.yml          # by hand, with NO issue number: the bot picks the oldest
                                       # agent:implement issue itself (then agent:ready), one per run —
                                       # the same pick the daily schedule makes (issue #472). Pass
                                       # -f issue_number=<n> only to pin one exact issue.
make issue-bot-dispatch REPO=asimov-agent/llgenie   # cap -> pick -> claim -> issue.md + branch
make issue-bot-open-pr REPO=<repo> ISSUE=<n> BRANCH=agent/issue-<n>-<slug>  # draft-free PR, never merges
make implement-issue      # the shared Hermes agent step: read issue.md + AGENTS.md, implement, run gates, push nothing;
                          # it repairs the checkout's ownership and validates pr-body.md before it returns (issue #770)
make agent-repo-ownership # give the mounted checkout back to the invoking uid/gid after a root-run container leg
                          # (a root-owned .git/objects makes the next `git add` die; OWNERSHIP_DIR= picks the tree)
make issue-bot-pr-body-check  # refuse a pr-body.md whose Issue:/Fix:/Benefit:/Technical: part is missing or
                              # states nothing (BODY_FILE=, ISSUE=), before the leg spends its gates on it
make issue-bot-image      # build/pull the agent image the bot runs in (same image as the fix-bot)
make hermes-smoke          # prove the alias can CALL A TOOL (a terminal call that prints a per-run nonce), die in seconds
make agent-shell-keys-check  # prove the credential is visible in the AGENT's shell (issue #358)
make issue-bot-triage     # step 1: Hermes REVIEWS the issue.md thread (body + every comment) and writes triage.md
make issue-bot-verdict ISSUE=<n>   # step 2: apply that verdict — implement | refine | close
make issue-bot-changed    # did the implement step change the tree? changed=true|false (run inputs excluded)
make issue-bot-gates      # re-check the FAST gates in order, stopping at the first failure and naming it
make issue-bot-gates-check  # CI: fail when a ci-unit gate is classified nowhere, a fast gate is unwired, or the bot's gate step is not between the detection and the push
```

#### The fast gates are re-checked before the push (issue #475)

The implement leg's agent runs the *slow* gates while it writes the change, and nothing re-checked
the *fast* ones between "the tree changed" and "the branch is pushed" — so CI found the bookkeeping
reds. The run that implemented #407 opened six PRs (#443–#448) that were functionally green and red
only on an unticked `- [ ]` in `tasks.md`, a stale README target list and a wiring count: each
detectable in **seconds** on the host, each worth a CI round trip plus up to an hour of `fix-bot`.

`make issue-bot-gates` runs, in order and failing on the first: `make lint`, `make check-workflows`,
`make check-wiring`, `make check-docs`, `make check-pr-hygiene`, `make openspec-tasks-check`. It
prints each gate as it starts and names the failing one (`FAIL `make check-docs``) so the fix is
obvious; it never runs `test-unit` (the agent already did, and it takes 11–20 minutes). The
issue-bot runs it as a step between `Detect what the implementation changed` and
`Commit + push the feature branch`, conditioned on a changed tree: a red gate fails the job loudly
*before* the branch exists, so nothing red reaches a reviewer and no `fix-bot` cycle is spent. A
`make test-image` step runs first, because `lint` (one of the gates) executes in `llgenie/test`
exactly as `ci-lint` does, and a fresh runner has no such tag — the check fails a workflow that
forgets it.

The gate list lives in **one** module, `scripts/issue_bot_gates.py`: `FAST_GATES` (what the target
runs) and `DEFERRED` (every other gate `ci-unit` runs, with the reason it is not re-checked before
the push). `make issue-bot-gates-check` — also a `ci-unit` step — reads the Makefile and the
workflow and fails when a `ci-unit` gate is classified neither fast nor deferred (the lock that
keeps a new fast gate from being silently skipped), when a `DEFERRED` entry goes stale, when a fast
gate is not a `.PHONY` target or no `ci-*` job reaches it, when the target stops running the runner,
or when the bot's step is missing, duplicated, unconditional on a change, or not between the
detection and the push. `tests/test_issue_bot_gates.py` covers all of it and runs in `make test-unit`.

#### The model the bots call (issue #405)

Every bot leg — `issue-bot`, `fix-bot`, `issue-refiner`, `rebase-bot`, `agent-fetch` — runs the
Hermes CLI inside the agent image and calls **one pinned snapshot** through the custom provider alias
`nous-deepseek`:

```
deepseek/deepseek-v4-flash-0731          (alias nous-deepseek, provider=custom,
                                          base_url=https://inference-api.nousresearch.com/v1,
                                          key_env=NOUS_API_KEY,
                                          max_tokens=16000, context_window=1048576)
```

The `-0731` suffix is the **snapshot** (2026-07-31) of DeepSeek V4 Flash. The endpoint has no
`deepseek-v4.1-flash-0731`. Dropping the suffix changes the model: the unsuffixed
`deepseek/deepseek-v4-flash` resolves to `canonical_slug …-20260423` (the April release), and it
also answers `200` — so a bot job cannot tell the two apart. That is the same class of miss as
#405, when a prefix assert let the bots run a different snapshot than the one the pin named.

```bash
make model-pin-report     # the pinned snapshot, every place that declares it, and each finding
make check-agent-model    # the gate (stdlib only, no network, no key) — run by ci-unit
```

The pin lives in **one module**, `scripts/agent_model_pin.py` (`MODEL_ID`, `MAX_TOKENS`,
`CONTEXT_WINDOW`), and `make check-agent-model` compares it with the two files that carry it: the
agent Dockerfile's `ARG HERMES_MODEL_ID` default and the install script's `MODEL_ID` default. Both are
build inputs of the image hash, and the build itself asserts the alias landed with the model id, its
`max_tokens` and its `context_window` — so a half-written alias fails the build, not a 120-minute run.
**To move the pin:** change the three values in `scripts/agent_model_pin.py` and the two defaults,
then `make check-agent-model` (it names any place still behind).

#### What `make hermes-smoke` proves (issue #407)

The smoke used to ask for the sentence `ok` and assert it came back — and a model whose tool calling is
broken, disabled, or unsupported on the current snapshot answers `ok` too. Every leg it guards is a
tool-using agent (`implement-issue` runs `make` gates through its terminal tool, the fix loop hands the
agent a failing check, the refiner writes `refine.md`), so the smoke proved the one capability it did
not need and missed the one it did.

It now proves the tool call, with a value the model cannot produce without one:

```bash
make hermes-smoke     # inside the agent image: nonce file -> terminal call -> transcript verdict
python3 scripts/hermes_smoke.py run --alias nous-deepseek    # the same proof, from the host
python3 scripts/hermes_smoke.py prompt --token-path /tmp/x   # just the prompt it would send
```

1. it writes a random `smoke-ok:<nonce>` into a token file; the prompt names the **file**, never the value;
2. the agent is told to run one exact command with its terminal tool —
   `printf 'smoke-ok:%s\n' "$(cat <file>)"` — and to reply with only that output;
3. the run passes only when the session it created (read from `$HERMES_HOME/state.db`, the store
   `hermes sessions list` reads) carries a `role='tool'`, `tool_name='terminal'` result containing the
   nonce **and** the final answer carries it too.

Every other outcome fails in seconds with a named reason: no new session / no readable transcript, a
tool call to anything but `terminal`, a terminal call that did not print the nonce, or an answer that
does not carry it. A `tool_call_count` above zero is not evidence — only the transcript is. So a model
whose `tools` were dropped, disabled or broken by a snapshot change reds the smoke before the
120-minute step it protects, which is the whole reason the smoke exists. `issue-bot.yml` runs
`make hermes-smoke` in the same place as before; `tests/test_hermes_smoke.py` locks the prompt, the
four verdicts and the wiring (`make test-unit`), so a future edit cannot turn it back into a sentence.

**The bot decides before it implements.** It reads the issue *and its whole comment thread*
(`gh issue view <n> --json number,title,body,state,author,labels,comments` — the comments come with the
JSON, and `gh` **refuses** `--comments` together with `--json`, which is what broke every dispatch
until #268 fixed it), because the thread is where an issue is usually specified: a body
that says "add `--foo`" with a later comment "only for CPU builds" is a different issue. It then
picks ONE verdict, written to `triage.md`:

- **`implement`** — actionable as written; the branch/gates/PR path runs as before.
- **`refine`** — a real decision is still open or the acceptance criteria are missing: the bot
  posts ONE comment with an implementable restatement and labels the issue `agent:refined`. No PR
  that run; it does not rewrite someone else's issue body.
- **`close`** — already implemented, superseded, a duplicate, or not a change this repo can make:
  the bot comments the reason **with the evidence it checked** and closes the issue. A close
  whose verdict carries no evidence is **refused**, because "hard" or "vague" is a refine.

An issue labelled `agent:closed` is never picked again, so a close cannot loop, and it opens no PR — so
it does not consume the 3/day PR cap. **`agent:refined` is a marker, not a decision (issue #522):** the
restatement makes an issue *more* implementable, so a refined issue stays in the picker and the refine
verdict also adds `agent:ready` when the issue carries no queue label. While `agent:refined` sat in
`DECIDED_LABELS`, every issue the hourly refiner touched became invisible to the implementer — a refine was
a one-way door.

**Every agent leg is unattended, and its prompt says so** (issue #543). `--yolo` auto-approves shell
commands and `--accept-hooks` auto-approves hooks, but neither answers the agent's own `clarify` tool: a
question in a detached run makes Hermes print `Input required; detached without cancelling` and exit 3,
leaving the tree unchanged and the leg reporting "changed nothing". Each of the five `hermes -z` prompts
(triage, implement, refiner, architecture, fetch) and `scripts/fix_bot_rules.md` therefore require: never ask,
never wait; a genuinely open decision becomes a `refine` with its `REASON` (or the safest reversible choice,
stated in the output). `issue-bot.yml` reports `rc=3` as "the agent asked for input" instead of
"changed nothing".

**A `close` queues what it cites** (issue #521). The picker only lists `agent:implement` (then
`agent:ready`), and the canonical issue a duplicate points at usually carries neither — so retiring
the copy left the real work queued nowhere. Measured: #400 was closed as a duplicate of the
unlabelled #254, and two days later #440 was closed as a duplicate of the unlabelled #399, with the
defect never once implemented. `apply-verdict` now reads the `EVIDENCE:`/`REASON:` blocks, and every
cited issue that is **open** and carries **no** agent label gets `agent:implement`, so the next run
implements the canonical issue. A cited PR number, typo or closed issue is printed and skipped, and
the issue being closed is never re-labelled.

#### The implementer edits `/repo` in place (issue #426)

`make implement-issue` runs Hermes in a `--rm` container with **one writable mount** —
`-v "$(CURDIR):/repo" -w /repo` — so the leg tells the agent, as a hard rule, that `/repo` is the only
tree it can write and the tree the job commits: edit it in place, **no git worktree**. AGENTS.md's
worktree rule is for a host agent with a real filesystem; inside this container `../llgenie-wt` is
`/llgenie-wt`, outside the mount, and it is deleted with the container — measured:

```
$ docker run --rm -v "$PWD":/repo -w /repo alpine:3 sh -c 'mkdir -p ../llgenie-wt/probe && echo lost > ../llgenie-wt/probe/f'
inside the container it exists: lost
$ ls ../llgenie-wt/probe
ls: cannot access '../llgenie-wt/probe': No such file or directory
```

The job — not the agent — commits and pushes, and `make issue-bot-changed` measures `/repo`, so work
done elsewhere is a loud failure rather than a silent one. `tests/test_bot_in_place.py` pins the prompt
rule and the single mount.

#### "Implemented" is measured from the tree (issue #428)

Hermes exits 0 whenever the conversation ends — including a run whose work was written outside the
checkout (run 39513850754 "committed" a file inside a container worktree that `--rm` deleted). The
workflow therefore never infers the outcome from the exit code: a `Detect what the implementation
changed` step runs `make issue-bot-changed`, which answers from
`git status --porcelain --untracked-files=all` with the bot's own run inputs excluded. The push step
requires `changed=true`, and the "fail loudly" step fires when the agent failed **or** the tree changed
nothing — so a no-op run pushes nothing, opens no PR, and reds the job naming the issue. A `git` that
cannot read the tree exits 2: an unreadable tree must never look like a green run.

#### A bot's run inputs are never repo content (issue #427)

Every leg writes its run input at the repo root: `issue.md` (the dispatcher), `triage.md` (the verdict),
`refine-in.md` / `refine.md` (the refiner), `pr-body.md` (the implementer), `comment.md` (the outcome
comment). They are **run inputs, not a change**, and `.gitignore` carries the whole set — so the push
step's `git add -A` stages repository content only and a run that implemented nothing stages nothing.

That is enforced, not remembered: `tests/test_bot_scratch_ignored.py` asks **real git** whether each
name is ignored, cross-checks the roster against the files that write them, and fails if a workflow
answers a missing entry with a `git reset -- <file>` exclude — that denylist is what committed
`triage.md` (`TRIAGE: implement`) as the "implementation" of #407 in PR #424. A new run input therefore
needs its `.gitignore` line (and the roster), not a wider `git reset`.

#### A bot PR's description comes from the run (issue #429)

The PR body used to be a fixed string — `--title "issue-bot implementation"` plus
`--wants "Verification notes land on the PR as CI runs it."` — so every bot PR opened with the same
three lines and no description of the issue, the fix or the benefit, while carrying `closes #<n>`.

Now the implement step writes `pr-body.md` (a run input, ignored like `issue.md`) with the four AGENTS.md
parts, and `make issue-bot-open-pr` builds the PR from it:

* the subject is the issue's own typed Conventional Commit (else `feat: <title>`) plus `(#<n>)`;
* `Issue:` must name `#<n>`, and `Issue:` / `Fix:` / `Benefit:` / `Technical:` must each carry real
  content — otherwise the command **refuses before it calls `gh`**, naming what is missing;
* the pushed commit's own file list (`git show --stat`) is appended, then `closes #<n>`.

`tests/test_bot_pr_body.py` is the rendered check `make check-pr-hygiene` cannot be: it runs the real
renderer, so a body that says nothing fails `make test-unit` instead of reaching a reviewer.

#### Each write uses the token that can perform it (issue #430)

The PR step makes two different writes and needs two different tokens. `GH_TOKEN: ${{ github.token }}`
(`issues: write`) posts the comment that claims the issue and the `pr-open` marker;
`PR_TOKEN: ${{ secrets.BUMP_TOKEN }}` (the PAT) opens the PR, because a PR opened with `github.token`
does not trigger CI. One token for both is how a run created PR #424 and then died on
`addComment` — red after the side effect, with the issue looking unclaimed.

`open_pr()` therefore takes a per-call token (`_gh(…, token=)` sets `GH_TOKEN` for that child process
only) and posts the **comment before the PR**, so a token that cannot comment costs a comment attempt
and never a PR nobody has claimed. `tests/test_bot_pr_tokens.py` runs a real fake `gh` that records the
token it actually received, per call.

make rebase-bot-sweep     # which ONE open PR needs rebasing (BEHIND/DIRTY against main), with the reason for every pass-over
make rebase-bot PR=<n> HEAD_BRANCH=<b> HEAD_REPO=<owner>   # rebase it (agent resolves a conflict), verify, push --force-with-lease
make rebase-bot-abort     # abort a stopped rebase and return the tree to main (the run loops over many PRs)
make rebase-bot-agent     # the conflict hand-off: it asks Hermes to resolve a stopped rebase (the conflict prompt arrives on STDIN) and runs INSIDE the agent image
**Every open PR is kept on `main` by a third bot** (`rebase-bot.yml`, issue #246), because
AGENTS.md's rule is that a branch behind `main` cannot be merged — so a stale PR blocks itself.
It runs **every 6 hours** and drains the backlog: **every eligible PR per run**, oldest first,
bounded by the `max_prs` dispatch input (default 10) and by the sweep's daily cap. A PR whose
rebase fails is aborted (`make rebase-bot-abort`), reported, and the run carries on.
- `make rebase-bot-sweep` decides *which* PR — an open, non-draft PR against `main` whose merge
  state is `BEHIND` (a clean rebase) or `DIRTY` (conflicts). GitHub computes mergeability
  **lazily**, so a PR the list reports as `UNKNOWN` is re-asked through `gh pr view
  <n> --json mergeStateStatus` (bounded: `UNKNOWN_ATTEMPTS` re-queries, `--unknown-attempts` /
  `--unknown-delay`); a PR that stays `UNKNOWN` is reported as **deferred to the next run**,
  never silently counted as "needs nothing" (issue #453). It states a reason for every PR it
  passes over, never picks the same PR twice in one run (`SKIP=`, issue #467), and counts today's
  `<!-- bot-done: rebase-bot … rebased -->` markers toward the daily cap **without** treating them
  as a bar: a PR that a later merge re-dirtied is rebased again the same day. A **plain comment
  holds nothing** — a status note on the PR does not stop a rebase of a branch that is behind
  `main`. Only a `bot-claim` marker from another bot does, and only while it is fresh. A claim or a
  `gave-up` from a failed attempt is never the record (issues #457/#467) — so no label is invented
  and no PR is rebased in a loop — and it skips a fork it cannot push to.
- **It keeps out of the other bots' way.** It skips a PR with checks **in flight** (rebasing
  would cancel the run deciding it), and leaves a **red, merely-behind** PR to the fix-bot — a
  rebase fixes staleness, not a failing test — while still taking a **conflicted** red PR, since a
  rebase is the precondition for fixing anything on it. The implementer cannot be raced (it pushes
  a new branch and only then opens the PR, so its PRs are fresh by construction), and the refiner
  never touches a branch. If the rebase bot and the fix-bot ever do collide, the fix-bot's plain
  fast-forward push and this bot's `--force-with-lease` mean the **second one is rejected loudly**:
  nothing is clobbered in either direction.
- **A conflicted PR has NO checks, and that is an answer rather than a crash** (issue #801). A
  `DIRTY` PR gets no CI run at all — GitHub cannot build a merge ref for it — so
  `gh pr checks <n> --json state` exits **1** with `no checks reported on the '<branch>' branch`
  for exactly the PR this bot exists to rebase. That one exit is read as "neither in flight nor
  red"; every OTHER non-zero read is still a hard failure, and a failed read now **names the PR it
  could not judge** (`error=#<n> (<branch>): …` on stdout, quoted by the run's `::error::` line)
  instead of leaving a bare exit code with no PR attached — the shape that let a red run and the
  dead PR never meet. The drain step's `failed_prs` lists every PR it picked and did not rebase, and
  each of those carries the reason on the PR itself.
- `make rebase-bot` does the work: rebase with `rerere` **off** (a recorded resolution from an
  earlier rebase is not trustworthy), and on a conflict hand the stopped rebase to Hermes with what
  each side means plus the hard rules (preserve both sides, never weaken a test, keep a recipe's
  TAB). The agent is reached through a **snapshot of `Makefile` taken before the checkout**
  (`make -f <snapshot> rebase-bot-agent`) and the container runs Hermes directly (still through
  the one `$(nous-alias)` model pin), because a conflict
  can be *in* `Makefile` and `make` cannot parse a file that is mid-rebase (issue #460). Then it
  checks the result structurally — `make -n ci-unit` parses, `make lint`, and the
  wiring guard — every gate chained with `&&`, so ANY failure blocks the push (`;` used to report
  only the last one), and the runner provides the test image `make lint` runs in (issue #455).
  The gate mounts the checkout, not `$(REPO)`: the job exports `REPO` as the slug, and Make would
  otherwise hand docker `asimov-agent/llgenie` as a volume name and abort a rebase it had already
  resolved (run 39727049030). It pushes with **`--force-with-lease`** to the **PR's own head remote**: a fork
  PR goes to the fork, never to `origin`. It never merges, and a resolution it cannot finish is
  reported on the PR and left for a human — with its stopped rebase **aborted**, so the run's next
  decision still has a parseable `Makefile` (issues #460/#464). The step that runs it exports
  `GH_TOKEN`, because the
  outcome comment (and the `done` marker inside it) is a `gh` write: without it the push landed
  and every comment failed (issue #453).
make issue-refiner-pick   # keep the backlog implementable: spare capacity -> the oldest issue that is not decided/claimed
make issue-refiner        # step 1: Hermes REVIEWS that issue (refine-in.md) and writes its verdict to refine.md
make issue-refiner-apply ISSUE=<n>  # step 2: ONE comment + the agent:refined label (never a PR)
make issue-dedup-pick               # which two UNCLAIMED open issues look like the same defect -> dedup-in.md
make issue-dedup                    # the agent decides: DUPLICATE: #<older> + EVIDENCE, or DISTINCT: + REASON
make issue-dedup-apply COPY=<n>      # retire the copy (comment citing the canonical + agent:duplicate) and queue the canonical
**A companion bot reviews the backlog — the issues that have not been implemented yet.** It is a
separate workflow (`issue-refiner.yml`) that runs **hourly** and reviews **one issue per run**: open,
oldest first, not already reviewed (`agent:refined`), not claimed for implementation, and not already
linked to a pull request — i.e. an issue no PR answers yet. It opens **no PR at all**: its outcome is
ONE comment plus the `agent:refined` label, which is what stops it reviewing the same issue twice.

**The duplicate sweep (`issue-dedupe.yml`, issue #553) runs FOUR times a day** (`51 */6 * * *`) because
neither the refiner nor the implementer ever compares two issues: one improves an issue per run, the other
implements one, so the same defect filed twice is implemented twice — or the better specification is retired.
The host picks the most similar pair of **unclaimed** open issues deterministically (title+body token Jaccard,
older as canonical) and the agent decides `DUPLICATE: #<older>` with an `EVIDENCE:` block or `DISTINCT:` with a
`REASON:`. A duplicate close retires the **copy** only — one comment citing the canonical, the
`agent:duplicate` label, the close — and the canonical issue is queued (`agent:implement`) when it carries no
queue label, so the work is never lost. **An issue carrying any agent label is never a candidate and never a
target**: `agent:implement`, `agent:ready`, `agent:refined`, `agent:closed`, `agent:duplicate` — and a
**bot-generated tracker issue** (its body carries a `<!-- <name>-bot:` marker) is skipped too, because two
architecture-refresh issues are near-identical by construction and would pair at 0.78 with no real answer
(measured: #494/#517); the first live run then picked #411/#423, which really are the same filed-twice failure. The sweep
therefore cannot race the implementer or the refiner, and cannot re-open a decision.
The only thing it refuses to do is race the implementer: while an issue is *waiting* for it
(labelled `agent:implement`/`agent:ready` with no PR yet) the run says so and yields; once that issue
has a PR it is not waiting for anyone and the next hourly run proceeds. Hermes does the *review* —
explicit acceptance criteria, scope in/out, the surfaces it would touch, and any open decision
**named as a question** rather than decided. It never rewrites an issue body and never merges.

- **Cap**: at 3 PRs already opened today, the run logs `cap reached: N/3 today, next issue
  tomorrow`, exits 0 and changes nothing. The numerator counts the bot's own PRs by the branch
  shape the dispatcher creates (`agent/issue-<n>-<slug>`, read with `gh pr list --json
  headRefName,author,createdAt`), never by a login: the bot opens its PRs with the owner PAT, so
  they are authored `asimov-agent`, and counting `github-actions[bot]` read 0 every day (issue #409).
  Never a batch.
- **Pick**: exactly ONE issue — labelled `agent:implement` first (oldest label
  first), else the oldest open `agent:ready`. When you want a specific issue
  implemented, add the `agent:implement` label to it (or run the workflow
  dispatch with its number).
- **Claim**: a marker comment plus the branch slug, so a second concurrent run
  cannot grab the same issue.
- **The agent step** (`make implement-issue`): Hermes reads `issue.md` +
  `AGENTS.md` at the repo root and implements — Makefile-driven verification,
  no weakened or mocked tests, nothing dead (a script/test must be named by a
  make target), the issue → branch → OpenSpec → code → PR lifecycle, never
  pushes, never merges, never touches `main`. Every token (the model key, the
  owner PAT, the Nerve/JEV provider key) comes from a CI secret at run time and
  is never baked — the container's supervision is wired by #238, below.
- **Follow-ups**: once the PR is open, issue #246 keeps it rebased (one PR per
  day) and #222 repairs it when a check goes red — the implementer does not
  grow its own loop.

### The JEV decision layer in the container (issue #238)

The agent image carries the host's **Nerve plugin**, so the bots run with the same JEV decision
layer the host runs. That layer is what makes an autonomous run *cheaper and more accurate*: it
answers the cheap decisions — which step next, is this edit the right one, does this satisfy the
check, is the turn even worth starting — so the expensive model calls are spent only where they
are needed. The intended trade is **more JEV calls, fewer LLM calls**: fewer tokens, better
accuracy, and a faster run, with the context curation keeping the prompt to the part of the repo
that matters.

It is **not** a gate on the bots and not a stand-in for the review a PR gets. The bots are
autonomous: nothing in this path may stop a run.

```bash
make agent-jev-preflight   # report whether the layer is available for this run (never blocks)
make nerve-profile-check   # prove the rule the build enforces: a setting whose module the profile
                           # does not register is inert, so the build fails (issue #611)
make agent-image           # the image: Hermes CLI + the pinned nerve plugin + its settings + the profile
make agent-image-ref       # ghcr.io/<registry>/llgenie/agent:latest (publish points it at the content hash)
make issue-bot-image       # the same image, for the issue-bot (alias of agent-image)
```

- **Build** (`containers/agent/Dockerfile` → `scripts/install_nerve_ci.sh`): the plugin is
  installed at an immutable commit (the v0.3.1 release commit) in **three steps, not one** (issue
  #585): `hermes plugins install keeltrace/hermes-nerve --ref <40-char sha> --no-deps` clones and
  records provenance without resolving anything, the script then **drops the plugin's optional
  `laya` extra** from the installed `pyproject.toml`, and `hermes plugins enable nerve` resolves
  what is left. Why: `--yes-deps` makes Hermes take a **universal** `uv lock` (every marker split,
  not just this image's), and `laya==0.3.3` requires `torch>=2.0.0`, which publishes no wheels for
  `python_full_version >= '3.14'` or `sys_platform == 'android'` — so the lock had no solution, the
  plugin was never admitted, and **every agent image build failed** (which is every bot job, since
  `agent-jev-preflight` is each one's first step). The extra is dead weight here: the bots run the
  plugin's default `reflex_backend` (`jev`), never the Laya sidecar backend, and the plugin imports
  laya lazily inside a function. Adding `[tool.uv] environments` to the plugin's own pyproject does
  **not** help (measured) — Hermes generates its own workspace and does not inherit it. The removal
  is asserted, not assumed: a pin that stops declaring `laya` fails the build and names #585 instead
  of resolving extras blind. The wiring follows the plugin's own `docs/SETUP.md` and mirrors the
  host:
  - the documented **nervous-system block** under `plugins.entries.nerve.settings` (a value
    written one level up is never read): `nervous_enabled`, `nervous_turn_admission`,
    `nervous_mode: correct_next`, `nervous_challenge_confidence: 0.86`,
    `nervous_call_threshold: 0.58`;
  - the provider: `jev_provider: typesafe`, `typesafe_model: jev-latest`;
  - `context_engine_mode`/`context_curation_mode: apply` (`apply` is where prompt tokens are won;
    the schema default is `shadow`, which only measures) — and they only do anything because the
    profile below registers `context_governor`;
  - the **action gate in `advisory`**, the host's mode: the pre-tool decision is logged and steered,
    never blocked, so a run still opens its reviewable PR. It needs the `action_gate` module, which
    the profile below registers (`gate_scope: all`, `allow_tool_override: false` — the model may not
    overrule the layer);
  - `work_supervision_mode: shadow` by default, because the host's `operator` profile does **not**
    register `work_supervision`: a non-shadow mode would ask a module that is off to do something.
    `advisory`/`enforce` are available as build args, together with a profile that enables it
    (`lean`, `marie_kondo`);
  - the **profile sidecar** `${HERMES_HOME}/nerve/profile.json` = the host's profile `operator`
    (reflex, nervous, action_gate, context_governor, receipts, local_learning), written through the
    plugin's *own* `save_profile` so it is validated and atomic, and carried in the settings as
    `nerve_profile` too (the host writes both places). A named profile decides which modules
    register at all — and settings cannot switch one **on**, only off — which is why issue #611
    shipped "apply" curation and an advisory gate that were both inert under `lean`;
  - the **parity check** (`scripts/nerve_profile_check.py`, run by the build against the *installed*
    plugin's `PROFILES` table): it fails the build when a written setting's module is not enabled by
    the profile (`gate_mode` ≠ `off` → `action_gate`; `context_engine_mode`/`context_curation_mode`
    not `shadow|off` → `context_governor`; `work_supervision_mode` ≠ `shadow` → `work_supervision`;
    `nervous_enabled` → `nervous`), and prints the resolved module set. `make nerve-profile-check`
    runs the same rule on two synthetic tables, so `make test-unit` locks both directions without an
    install.
  - the dead pre-0.3.1 block `plugins.entries.hermes-nerve` is removed if a base image has it:
    Hermes never reads it, and nerve warns about it at startup.
  The build **fails** when the plugin did not land, when the ref is not an immutable SHA, when the
  profile is not one the plugin knows, or when a provider key is present in the *build*
  environment — a key in a build layer is a leak.
- **Run** (`scripts/agent_jev_preflight.sh`, reached through `make agent-jev-preflight`, and run by
  `make implement-issue` / `make fix-loop-image` before any agent work): it reports whether the
  plugin is in this `HERMES_HOME`, whether the key is available, whether the plugin is *enabled*,
  and whether the provider answers a real decision call (the plugin's own
  `scripts/live_api_smoke.py`, no stand-in). The key travels as `-e TYPESAFE_API_KEY` from the
  `TYPESAFE_API_KEY` repo secret (`issue-bot.yml`, `fix-bot.yml`) and is written into the image's
  `HERMES_HOME/.env` (mode 600), because Hermes resolves credentials per home rather than from the
  environment; the value is never printed. **When the layer is unavailable the run continues**,
  loudly: a missing key, a plugin that is not installed, a provider that does not answer — each is
  reported with what to do about it, and the bot does its work with more LLM calls and more
  mistakes for the reviewer to catch than a JEV-assisted run would make. In a workflow the run is
  **annotated** either way (`::notice` when the layer is ready, `::warning` when it is not, plus a
  line in the job summary), so "is JEV on?" is answerable from the run page instead of a log grep. `NERVE_REQUIRE=1` turns
  the report into a failure instead, and **both bot workflows arm it** (`make agent-jev-preflight
  NERVE_REQUIRE=1`): a bot run does not start with the JEV engine off — the layer is a precondition
  for an autonomous run, and an ordinary manual or local invocation keeps the report-and-continue
  behaviour.
  A bot job whose step runs the required mode does it through `make jev-preflight-required
  REPO=<owner/repo> RUN_URL=<run>` (issue #802): the exit status is unchanged (the step stays red), but
  a failure now names its failing class (`key-missing`, `plugin-missing`, `plugin-disabled`,
  `hermes-missing`, `smoke-missing`, `provider-unsupported`, `provider-no-payload`,
  `provider-unreachable`, `unknown`), the measured line and that class's fix in the run's own output,
  and files ONE issue per class — deduped by `<!-- jev-preflight: <class> -->` on the body's first line,
  labelled `agent:implement`. A later run of the same class prints the existing issue and files
  nothing, so "the bot did not run" is answerable from the issue list instead of a step name. A LOCAL
  invocation of the same target files nothing at all (`--local` whenever `GITHUB_ACTIONS` is not
  `true`): a host-local precondition is not a repository failure, and a person running the target must
  not write to the issue list (measured 2026-10-28, that mistake filed #809, now closed). The
  `issue-dedupe` job carries `TYPESAFE_API_KEY` for exactly this, and the `issue-dedup` recipe forwards
  it into the leg's container (`-e TYPESAFE_API_KEY`, as `issue-refiner` does) — until #802 neither
  did, every picked pair died in the preflight at 13:34Z on 2026-10-28, and no issue tracked it.
A bump PR publishes the images it built (`make push-engine` is a step of every
`engine-image-*` job), but those jobs run in parallel with the `install` job, so
`make ci-install` waits first: it runs `make ci-wait-engine-images ARCH=cpu` before
`make ci-install-run`. It resolves exactly the tags `make install` pulls and polls
the registry manifest until each one is published, naming and failing on a tag that never
appears (it never builds an image and never pulls a different one).

**An absent tag has two causes and the gate names which one it saw (issue #893).** The
`install` job runs in the same runner queue as the `engine-image-*` cells that publish the
tags it wants, so under queue pressure the producer is still `queued` when the wait's
budget runs out — and a 404 after 30 honest minutes reads exactly like a wrong pin.
`scripts/install_engine_launchers.py` therefore reads its producers' own job state from the
Actions API (`GET /actions/runs/<id>/jobs`, which is why the job carries `actions: read`),
joining on the cell name `engine-image-<engine>-<variant>`:

- `queued` / `in_progress` — the runner queue, not the tag. The wait keeps going, up to
  `PUBLISH_WAIT_QUEUE_MAX_S` (75 min), and then fails as **`BLOCKED — the producer cell
  <job> is still queued after N minutes with no runner: this is the runner queue, not a bad
  tag`**, telling the reader to re-run rather than touch the pin.
- `completed` with any conclusion — the producer has published its tag or never will, so the
  wait shortens to a two-minute grace (a registry manifest can lag its own push, and a verdict
  at zero would be a flake dressed as a defect) and then fails as **`NOT FOUND`**, naming the
  cell and its conclusion (`concluded success and <ref> was never published` / `concluded
  failure`). This is the real defect case.
- no state readable (a host run, or a token without `actions: read`) — the old 30-minute
  budget, and the message says the queue *cannot be ruled out* rather than pretending to know.

Both bounds are finite and the relation to the job's ceiling is pinned by
`tests/test_ci_publish_order.py`: 75 + the 20-minute reserve for the pull/install/dry-run/
uninstall stays under the job's `timeout-minutes: 120`, so a hung producer can never hold a
runner for GitHub's six-hour default. The OS branch lives in the gate target: macOS pulls
no engine image, so its run of the gate does no lookup and
`ci-install` stays the same on both OSes. Without that gate the first run of a new pin fails
`[install] FAIL llama.cpp/cpu: not published` while its own build job is still pushing
the tag (issue #169).

The same race used to red `make test-unit`, from the other side: the real-registry case in
`tests/test_ci_publish_order.py` resolved the **current checkout's** plan, so a bump PR asked GHCR
for the tag it was itself publishing, and every bump PR arrived `1 failed` (`#665`, `#663`). That
case now checks exactly the engines whose committed params this change did **not** move, and prints
the ones it defers (`[publish-order] deferred to ci-wait-engine-images: [...]`): a repinned engine's
brand-new tag is `make ci-wait-engine-images`' business, which is the gate that can wait. On `main`,
where nothing differs from the base, every engine is still checked (issue #672).

> **Why a wrapper?** `scripts/llgenie_serve.py` imports the `gguf`/`numpy` packages that live in the
> venv, so it must be launched with the venv python. The `~/bin/llgenie` wrapper does
> exactly that; the `llgenie.py` symlink keeps editors/`--list` pointing at the real file (which lives at
> `scripts/llgenie_serve.py`).

## No secret value reaches a log (#283)

Every key this repo uses travels the same way: a CI secret, `docker run -e VAR` (the **name**, never
`VAR=value`), and a guard that echoes only the variable's name when it is missing. `make
check-secret-output` (in the `ci-unit` job) keeps that true for **all** of them — `NOUS_API_KEY` /
`NOUS_PORTAL_API_TOKEN`, `GH_TOKEN` / `BUMP_TOKEN` / `GITHUB_TOKEN`, `HF_TOKEN`, `TYPESAFE_API_KEY`,
`FIRECRAWL_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`:

The list is ONE (`scripts/check_secret_output.py::SECRET_VARS`) and it is the same list the transcript
redactor reads, so a key cannot be half-covered. `tests/test_secret_output.py` compares it against both
the `secrets.<NAME>` a workflow reads **and** the Makefile's `AGENT_SHELL_KEYS` (the credentials the
agent image receives), so a newly forwarded key that is missing here reds `make test-unit` (#379):

| rule | what it fails on |
|---|---|
| `secrets-in-run-block` | `${{ secrets.X }}` — or GitHub's own `${{ github.token }}` / `${{ github['token'] }}` — interpolated **inside** a `run:` block: it becomes part of the script text and of its output; pass it through `env:` |
| `prints-secret-value` | a printing command that expands a secret's value, e.g. an echo of a token variable. Printing the variable's *name*, and redirecting a value into a `chmod 600` file, are not violations |
| `xtrace-with-secrets` | `set -x` in a file that also reads a secret: xtrace prints every expansion |
| `value-in-argv` | `-e VAR=$VAR` / `--build-arg VAR=$VAR`: the value lands in the process list, not only in the environment |
| `env-dump` | a bare `env` / `printenv` whose output reaches the log |
| `key-shaped-literal` | something that looks like a live credential, committed (a deliberate test value carries `secret-output: test value` in its file) |
| `whole-stdout-into-output-file` | a command's whole stdout redirected into `$GITHUB_OUTPUT` (`cmd | … >> "$GITHUB_OUTPUT"`, `$(cmd) >> "$GITHUB_OUTPUT"`): the file must hold `key=value` only — `make` echoes its recipe line, which is enough to fail the step with `Invalid format` after the work is done. The quoted form `echo "k=$(…)" >> "$GITHUB_OUTPUT"` is correct and stays green |
| `whole-stdout-into-log` | `… \| tee /dev/stderr`: the whole stream copied into the job log, where only *registered* values are masked, so a transformed one sails past. `tee <file>` is fine |

GitHub masks a registered secret in its own logs, and that is **not** enough: masking is a filter over
the log stream, so a transformed value (base64, a URL, a slice) sails past it, and nothing is masked in
a log a job uploads itself. `make secret-output-report` shows which files name a secret and whether any
of them prints it.

### A committed credential VALUE is scanned for too (#360)

The rules above read the *shapes a script prints*; they cannot see a key written in another provider's
shape (a PAT, a JWT, an AWS-style key, a bearer inside a URL). gitleaks runs in its own pinned image for
that, and CI runs it in the linux job before the gates:

```bash
make secret-scan            # working tree (the finding is redacted; the file and rule are named)
make secret-scan-history    # git history — refuses a worktree, where .git is a file
make secret-scan-self-test  # plants a fake credential; the scan MUST catch it (a scanner that
                            # silently does nothing is a false green)
```

A finding is removed and its key rotated — never allowlisted. `.gitleaks.toml` extends gitleaks'
default rule set (a config without `[extend] useDefault = true` scans *nothing*) and allowlists only
documented non-live fixtures, each named by path so a reviewer sees the decision. `make secret-scan`
needs a container engine, so it runs on Linux; macOS runs the rest of the loop.

`make secret-scan` reads the **committable set**, not the whole filesystem (issue #382):
`scripts/secret_scan.py` exports `git ls-files -c -o --exclude-standard` — the tracked files plus the
untracked files that are not ignored, i.e. exactly what `git add` would take — and points the same
pinned image and config at that export. gitleaks' own `dir` mode honours no `.gitignore`, so scanning
the checkout directly reported findings inside `tests/__pycache__/*.pyc` (gitignored bytecode carrying
the test suites' own sentinels) on a tree with no uncommitted change, and printed the "rotate the key"
remediation for files nobody can commit. `make secret-scan` also separates the two non-zero exits: `1`
means the scanner **found** something, anything else means the scan **could not run** and says so —
a scanner with no verdict is never reported as a clean tree or as a credential.

## The credential reaches the AGENT's shell (#358)

Every key the bots use also has to survive **Hermes's own terminal filter**. Hermes strips provider
credentials from the terminal tool on purpose (`NOUS_API_KEY`, `GH_TOKEN`, `FIRECRAWL_API_KEY`,
`HF_TOKEN` … are on its blocklist, and `env_passthrough` can never re-allow one), so a key forwarded
as `-e NOUS_API_KEY` reaches the container and the Hermes process while the **agent's own shell reads
it EMPTY** — the bot then does nothing and the run stays green. Measured on a host with the real
Hermes, with sentinel values only:

```console
$ NOUS_API_KEY=SENTINEL python3 scripts/agent_shell_keys_check.py NOUS_API_KEY
[agent-shell-keys] NOUS_API_KEY: container=set agent-shell=EMPTY (MISMATCH; _HERMES_FORCE_NOUS_API_KEY NOT forced; value never printed)
rc=1
$ NOUS_API_KEY=SENTINEL _HERMES_FORCE_NOUS_API_KEY=SENTINEL python3 scripts/agent_shell_keys_check.py NOUS_API_KEY
[agent-shell-keys] OK: 1 credential(s) visible in the agent's shell.
rc=0
```

The one sanctioned way through is the `_HERMES_FORCE_<NAME>` form. The Makefile keeps **one list** —
`AGENT_SHELL_KEYS` (`NOUS_API_KEY`, `GH_TOKEN`, `HF_TOKEN`, `TYPESAFE_API_KEY`) — exports
`_HERMES_FORCE_<NAME>` from `<NAME>` **by reference** on the host (the value is never on a command
line, in a recipe or in a log, so `ps` cannot see it), and every agent leg carries
`$(AGENT_SHELL_FORWARD)`, so the plain name and its forced twin always travel together.

```bash
make agent-shell-keys-check                                    # prove it, inside the agent image
make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS="NOUS_API_KEY TYPESAFE_API_KEY"
                                                               # narrow it to the keys this job has
```

The check drives Hermes's **real** terminal environment (`LocalEnvironment`, the code the agent's
`terminal` tool uses) inside the agent image, prints lengths only (never a value or a prefix), and
fails closed: a key that is missing from the container, or a Hermes that cannot be found, exits 2 —
`--allow-unconfigured` is the sole local opt-out and no workflow uses it. `issue-bot.yml`,
`fix-bot.yml`, `issue-refiner.yml` and `rebase-bot.yml` each run it before their agent work, so a job
whose credential cannot reach the agent stops in seconds instead of after a 120-180-minute run.

## The agent's transcript is redacted before it prints (#359)

A bot's agent stream is the job's console output, and GitHub's masking is a filter over the stream —
a transformed value (URL-encoded, base64, a slice) sails past it, and nothing is masked in a log a job
uploads itself. So every public agent leg (`issue-refiner`, `issue-bot-triage`, `implement-issue`,
`hermes-smoke`, `rebase-bot-agent`, `agent-jev-preflight`, `fix-loop-image`) runs through ONE seam:
the command's stream is captured to `hermes-run.log` (gitignored, never printed, never uploaded), the
console prints only the redactor's bounded tail, and `hermes-run.scrubbed.log` is what the bot
workflows upload as the `agent-transcript-redacted` artifact.

```bash
make scrub-log LOG=hermes-run.log OUT=hermes-run.scrubbed.log   # redact a captured stream by hand
make fix-loop-image LOG=/tmp/fix-loop.redacted.log   # LOG= now receives the REDACTED copy
```

`scripts/scrub_log.py` reads the secret values **by name** from the environment (the list lives once,
in `scripts/check_secret_output.py::SECRET_VARS`), masks every raw / URL-encoded / base64 spelling of
each, plus credential shapes (`ghp_…`, `hf_…`, `sk-…`, `Bearer …`) it never had in its environment,
and prints a redaction COUNT — never a value, never a prefix. A missing input exits 2: a stream that
cannot be read must never read as a clean run. `make scrub-log LOG=… TAIL=120` (or `HERMES_LOG_TAIL=120` for a leg) widens the printed tail.

## The agent's masked web reach (#362)

Hermes ships a bundled `browser-firecrawl` plugin keyed by `FIRECRAWL_API_KEY`, so the capability is
already in the agent image — what was missing is a sanctioned leg that uses it with the key never
printed, and a smoke that dies in seconds when the key is dead instead of returning an empty result a
run reports as success.

```bash
make agent-fetch URL=https://example.com OUT=fetched.md   # one URL -> its markdown, INSIDE the image
make search-smoke                                         # one real request, hard budget, loud on 401/402/403
make search-smoke BUDGET=4000                             # how much markdown to keep/print
```

The key travels through the #358 seam: `FIRECRAWL_API_KEY` is in the Makefile's ONE `AGENT_SHELL_KEYS`
list, forwarded by NAME plus its `_HERMES_FORCE_` twin, so `make agent-shell-keys-check` proves the
**agent's own shell** can see it (Hermes strips provider credentials from its terminal tool). The
prompt reads the value from the environment, states that it is never printed, echoed or written, and
writes only the fetched text. `scripts/fetch_smoke.py` reads the key by name, makes one request with a
bounded response, and fails with the HTTP code on 401/402/403 or on a 200 that carries no
`data.markdown` — "no results" is never healthy. A missing key is exit 2 with the variable's name.

`search-smoke` runs on the repository secret: the `search-smoke.yml` workflow (issue #381) fires daily
at 07:11 UTC (and on a hand dispatch by the owner/collaborators), where
`make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY` proves the **agent's own shell**
sees the key *before* `make search-smoke` spends it. The key travels by NAME (`docker run -e`) and never
on a command line. While the secret did not exist the target was human-run only and recorded in
`tests/fixtures/host-only-wiring.json`; that record is deleted, because `make check-wiring` fails a
recorded exception CI now reaches.

### The reach is deployed: a bot leg uses it, and the URLs are checked (issue #380)

**Issue #362** built the leg and the smoke, and **no bot leg called either** — so the capability was unreachable
from a run, and nothing said which URLs the bots depend on. That half is now wired:

```bash
make web-coverage                                    # one line per URL with its HTTP status; non-zero on a dead one
make web-coverage ISSUE_FILE=refine-in.md            # ... for the URLs a given issue names
make issue-evidence ISSUE_FILE=refine-in.md OUTDIR=fetched MAX=3   # pre-fetch them for the agent
```

`make issue-refiner` (the bot leg) runs, in order: `make agent-shell-keys-check` with
`AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY` (the key must reach the **agent's** shell first, #358), then
`make issue-evidence`, which extracts the URLs the picked issue names and pre-fetches each with the
**real** `make agent-fetch` leg (capped at 3 — each fetch is a model call), writing `fetched/index.md`.
The review prompt reads that index as evidence, and a URL it could not fetch is recorded as UNKNOWN,
never as false. `make web-coverage` is deterministic — no model call and no key: a 404 is dead for a bot
too, and a `401/403` is **reachable** (the resource exists; the bot simply has no credential), which is
a different problem from a link nobody can read. `tests/fixtures/bot-facing-urls.md` is the declared
list it checks when no issue names a URL, and `search-smoke.yml` runs it on the same daily schedule.

## A bot leg refuses to start on a missing key (#363)

A leg that forwards a key its job never set used to spend the runner first — pull the agent image,
start a container, then fail inside Hermes on a 120-180 minute-timeout job, with a log that reads like
a model problem. Every leg now runs the guard **before** the image is ensured:

```bash
make require-env KEYS="NOUS_API_KEY TYPESAFE_API_KEY"   # name-only, exit 2 when one is missing
```

`scripts/require_env.py` prints the variable's name, never a value, and exits 2 — a missing secret is
a loud failure, never a skipped check. The suite derives the roster from the Makefile (every target
that starts the agent image must run the guard before `scripts/ci_images.py ensure agent`), so a new
leg without one fails `make test-unit` instead of costing a run. That includes the web-reach legs
(`agent-fetch` keys on `NOUS_API_KEY` + `FIRECRAWL_API_KEY`, `search-smoke` on `FIRECRAWL_API_KEY`),
which landed while this change was open (#362/#369).

## The implementer's step exports `GH_TOKEN` (#364)

`make implement-issue` forwards `-e GH_TOKEN`, and the issue-bot job now exports it on the step that
runs the leg (`github.token`; the PUSH keeps the owner PAT). The suite enforces the general rule — for
every bot workflow, the step that runs a leg must export each key that leg forwards, and a sibling
step's `env:` does not count — so a leg whose token the job never sets fails `make test-unit` instead
of forwarding an empty value that looks wired.

## The code-review bot (issue #269)

A bot that reads the **tree and the pipelines** and files issues for what is actually wrong. It is
**analysis, never implementation** (AGENTS.md, #231): it never edits a file, opens a PR, merges, or
comments on anyone's PR — its entire output is one issue per finding, and every issue carries the
evidence the finding came from, so a reviewer can check the claim without re-deriving it.

```bash
make code-review-scan REPO=asimov-agent/llgenie            # the checks: tree + pipelines -> findings (writes nothing)
make code-review-scan REPO=asimov-agent/llgenie STATIC=1   # skip the two checks that read the GitHub API
make code-review-file REPO=asimov-agent/llgenie            # file ONE issue per NEW finding, capped (CAP=, default 3)
make code-review-file REPO=asimov-agent/llgenie DRY=1      # preview what it would file
```

`.github/workflows/code-review-bot.yml` runs it weekly (Monday 07:31 UTC, its own slot) and on
`workflow_dispatch` for the owner/collaborators, guard first, then scan, then file.

The checks, and the two limits they are held to:

| check | what it catches |
|---|---|
| `workflow-inline-scripts` | a workflow `run:` that invokes a repo script directly instead of a make target (a step whose whole job is gh/git orchestration is exempt, as the rule says) |
| `secrets-not-defined` | a workflow reads `secrets.X` and X is not one of the repo's secrets — GitHub substitutes an **empty string**, so the job does not fail at startup, it fails later wherever that value is used |
| `workflow-never-ran` | a workflow with its own events that has never run — never verified, only reviewed. `workflow_call`-only files are exempt: GitHub counts a reusable workflow's runs under its **caller** (`ci.yml` calls `pipeline.yml` three times and reports 892 runs while `pipeline.yml` reports 0) |
| `cron-collisions` | two workflows scheduled at the same minute+hour on overlapping days (only fixed slots are compared — an hourly cron fires many times a day by design) |
| `reusable-orphan` | a `workflow_call` pipeline that nothing calls, so nothing can run it |

**Idempotent by contract**: a filed issue carries `<!-- code-review:<key> -->`, the filer skips any
key it has already filed, and a cap (3 per run) bounds a bad run — a weekly run on an unchanged tree
files nothing and stays quiet. The two API-backed checks need a token with admin to read the secret
list; without one they warn loudly and skip rather than filing a claim they cannot support.

## Agents push to the base repository, never to the fork (issue #910)

A PR whose head lives in another repository is a **cross-repository** PR, and it costs three things this
repository has already paid for: a `pull_request` run from a fork receives **no repository secrets** (the
empty `secrets.BUMP_TOKEN` that made the old in-workflow merge job report `success` while merging nothing —
#481, which is why `auto-merge.yml` is a `workflow_run` workflow); approval follows the **fork's** own review
semantics instead of this repository's; and every sweep then needs two remote rules, "push back to the PR's
own head" and "never push a fork head to upstream", whose ambiguity has already produced near-misses.

So the rule is: **agents push branches to `asimov-agent/llgenie`.** The two remotes on a checkout are not
interchangeable, and their names have been known to move — read `git remote -v` before any push.

| remote (as configured on this host) | URL | what agents push here |
|---|---|---|
| `upstream` | `asimov-agent/llgenie` | **yes — this is the one**; a branch here makes a same-repository PR |
| `origin` | `andyholst/llgenie` (the owner's fork) | no; it is the historical path, kept so existing PRs still resolve |

On the second main repository on this host (`/home/asimov/repository/git/llgenie`) the same two URLs are
called `origin` (base) and `fork` (the owner's) — the **names** differ per clone, the **rule** does not.
Push to whichever remote's URL is `asimov-agent/llgenie`.

**What the check does about it:** `make check-pr-heads` reports every open PR grouped by head repository and
**names each cross-repository one** with the reason and the remedy. It is a **warning, never a failure** —
the fifteen existing cross-repository PRs are legitimate and merge as they are, and a check that fails on
them would teach the next person to skip it. `make pr-heads-report` prints the same view without the check's
one-line verdict. A caller that has decided cross-repository heads are unacceptable can ask for the strict
form (`python3 scripts/pr_heads.py check --strict`), which is how the policy stays a decision rather than a
default.

### The merge intent is armed when the PR is created (issue #912)

`allow_auto_merge` is on and `auto-merge.yml` can approve and merge a green PR, but a PR that nobody armed
sits `MERGEABLE/BLOCKED` with `auto=none` until a human clicks. Measured on one night: **32 of 41** open PRs
had to be armed by hand, after the fact. So arming is a producer default, not a sweep:

```bash
make arm-auto-merge AUTHOR=<login>        # arm every open PR that is not a draft and not already armed
make arm-auto-merge DRY=1 AUTHOR=<login>  # print what would be armed, call nothing
make arm-auto-merge-report                # the unarmed ones, with author and mergeable state
```

`scripts/arm_auto_merge.py` runs `gh pr merge <n> --auto --squash`. It never merges by itself — `--auto` only
arms, and GitHub (or `auto-merge.yml`) performs the merge when the required checks pass. It skips a **draft**
on purpose: arming one would queue a merge intent for something nobody can review, and drafts are banned
outright (#873). It skips a PR that is **already armed**, so running it twice is a no-op rather than churn.

A live `make arm-auto-merge-report` is the honest status line for this rule: `44 open PR(s): 11 unarmed, 33
already armed or draft`.

## A stacked PR has no CI verdict at all (issue #945)

`.github/workflows/ci.yml` triggers `pull_request` with `branches: ["main"]`, and on a
`pull_request` event **`branches` filters the BASE branch, not the head**. So a PR whose base is
another feature branch is not "waiting on CI" — it gets **no run at all**, and `gh pr checks`
prints `no checks reported`, which reads like an unfinished job rather than an absent one.
Measured on three stacked PRs (`#944`, `#929`, `#921`, all based on
`feat/agent-profile-implementer-skill`): `statusCheckRollup` had **0** entries each, `gh run list
--branch <head>` returned **0** runs, and closing/reopening the PR (the `reopened` activity) did
not change that — the filter is on the base, not on the activity type.

Two consequences that decide how a stacked PR is handled:

- **A stacked PR can never be "green",** so it must never be merged on the strength of its checks:
  merging it into its base is the only correct move, and the base's own PR carries the verdict for
  `main`.
- **The rebase-first rule is not stylistic.** Stack to keep review small, but the moment the base
  lands, retarget (`gh pr edit --base main`) or rebase onto `main`, because until then no gate in
  this repository is inspecting the head.

`AGENTS: <sha>` in a PR body is the check a reader can make by eye: if the base is not `main`, the
`AGENTS` line is quoting a tree the PR will not merge into.


## A green, conflict-free PR is merged by CI (issue #482)

Landing a PR no longer waits at a keyboard. The `auto-merge` workflow
(`.github/workflows/auto-merge.yml` — a `workflow_run` on `CI`, see #493 below) squash-merges a pull request
the moment its run is green **and** the PR is conflict-free, and deletes the branch. The shape is
`trending-local-llms`' `auto-merge` job in `qa-validate.yml`, which is the model for every bot in this repo.

**A finished PR is armed when it is done, not when it is approved (owner directive 2026-10-29, #873).** The last
push or the last green check is the trigger: the producing lane moves the PR into the merge queue itself —
`gh pr merge <n> --squash --auto` — and then **reads `autoMergeRequest` back** and states the arm time in its
comment, because that command exits 0 while arming nothing when the base is not the default branch (issue #964)
or auto-merge is disabled. A finished but unarmed PR is invisible to every sweep. One exception: a PR the owner
explicitly forbade is reported `auto=none (owner instruction)` with the line where that instruction lives.
(This paragraph is itself measured against `upstream/main` `98466eb`.) Companion: `do-not-merge` is only for a
real defect with the resolving issue named in the same comment, and never on a merged PR — a hold with no
removal condition is abandonment, and a hold on a merged PR blocks nothing.

```bash
make auto-merge PR=<n> REPO=asimov-agent/llgenie [HEAD_SHA=<sha>] [APPROVE=1] [DRY=1]  # the decision + the merge
make auto-merge-explain PR=<n> REPO=asimov-agent/llgenie     # why it was (or was not) merged — writes nothing
make auto-merge-recheck REPO=asimov-agent/llgenie [MAX=5] [DRY=1]  # retry the PRs the gate deferred at their current head
make verify-closure PR=<n> REPO=asimov-agent/llgenie         # did `closes #n` actually close?
make auto-merge-resolve REPO=<owner/repo> RUN_ID=<id> HEAD_OWNER=<owner> HEAD_BRANCH=<branch>  # run -> PR number
```

**Every number this box reports names the sha it was measured at (fleet rule 15, #873).** `auto-merge` fetches
`upstream/main` and notes the sha it branched from before it measures anything, `make` exposes it as
`HEAD_SHA=<sha>` on the merge commands, and every line that carries a count — a baseline, a decision, a
deferral — states the head sha it was taken against. A number without its sha reads like a fact about time,
not about one tree: #953's ratchet recorded `34/14` at the cut, and by the time the rebase arrived `main`
measured `107/151` — a guard asserting a board its own repo had already outgrown. The same shape as a `0`
printed while `#904` carried the label (issue #948): an instrument that does not say which tree it looked at is
believed, and believed about the wrong one. This box's own work is bookended the same way — one PR comment when
work starts (issue, branch, the main sha, what "done" means) and one when it finishes (head sha, the proof,
what is left open), and a measurement answered at a stale head replies with the sha the correction is taken at
plus the command that showed it. A gate's baseline is re-asserted against the fetched `main` before it is
trusted, never quoted from the moment it was cut.

What it will and will not touch:

| condition | result |
|---|---|
| every PR-relevant job **succeeded** + `mergeStateStatus: CLEAN` | **merged** (squash, branch deleted, head pinned by `--match-head-commit`) |
| `DIRTY` (conflicts), `BEHIND` (stale), `BLOCKED` (check/review pending) | deferred to a human, job prints the reason, exits 0 |
| draft PR, a **third-party** fork (only `andyholst/llgenie` is trusted), head branch `main` | never merged |
| head moved after the run started | deferred: the newer run decides |
| `do-not-merge` label | **held** — the human escape hatch; remove it and the next green run merges |

**It publishes what it acted on (fleet rule 14, #873).** The automation is a lane too, so every act is
written where a reader looks rather than only in a job log: a merge posts one comment naming the
**run id** (`GITHUB_RUN_ID`), the **head sha judged** and the decision, and a deferral posts the
one-line reason (`BLOCKED: review required`, `stale head`, `held`, …). The merge announcement is posted
*after* the merge call returned, so a run whose merge GitHub refused never announces one, and it is
idempotent per head — a recheck of an already-merged PR adds nothing, while a moved head announces
again because the earlier marker described a different tree.

The merge runs with the owner PAT (`secrets.BUMP_TOKEN`), never the job token: a merge made with
`GITHUB_TOKEN` starts no workflows, so the post-merge run on `main` — the one that publishes the engine
images — would never happen. Right after merging, `make verify-closure` reads the PR's own
`closingIssuesReferences` and **fails, naming the issue**, when a claimed `closes #n` did not bind, so an
unbound keyword is a red run instead of an issue left open on the board.

**The merge runs in `.github/workflows/auto-merge.yml`, a `workflow_run` workflow — not a job in `ci.yml`**
(issue #493). A `pull_request` run **from a fork** receives no repository secrets, so the job that used to live
in `ci.yml` saw `secrets.BUMP_TOKEN` as the empty string: #481's run was green and the job `succeeded` while
merging nothing. A `workflow_run` workflow executes in the base repository with the base repository's secrets,
acts only on a pull-request run that concluded `success`, checks out the **base** branch (it holds a write
token, so it never runs PR code), resolves the PR from the run, and calls the same `make auto-merge`. The
runs endpoint 404s for a fork run, so that lookup falls through and the fallback searches by
`head:<branch>` — `gh pr list --head owner:branch` matches a same-repo branch only and found nothing for
**Follow-up #502.** The fallback is `make auto-merge-resolve` (`scripts/resolve_run_pr.py`, issue #508): `gh api`
prints a 404's error *body* on stdout, so run `39735179724` read that JSON as a PR number, skipped the
fallback it was meant to trigger, and then died writing it to `$GITHUB_OUTPUT` (`Invalid format`) — the
gate never reached `make auto-merge`. Only a digits-only value is a PR number now; anything else is
"no answer" and falls through, nothing resolving is a loud failure, and the workflow runs the make
target so CI and the host run the same tested code. A missing
token is a red run (exit 2), never a silent deferral. It merges a PR only when its author is the repository
owner, a collaborator with write access, or the bot (a bot PR is authorised by who triggered the CI run) —
the same gate `ci.yml`'s `guard` job applies to a run. A stranger's green PR is deferred, even from the
trusted fork.

**The decision asks `gh pr view` only for fields `gh` actually has (issue #513).** `gh` refuses the whole
`--json` call on an unknown name, so an invented field (`authorAssociation`) killed every run before the
decision — no PR was ever auto-merged. The requested names now live in one constant
(`PR_VIEW_STATE_FIELDS` / `PR_VIEW_FIELDS` in `scripts/auto_merge.py`), the bot rule reads `author.login`
alone (an `app/github-actions` or `…[bot]` opener is allowed only when the run's ACTOR is the owner, a write
collaborator, or the bot), and `tests/fixtures/gh-pr-view-fields.json` records `gh pr view --json __probe__`'s
own allowlist — a unit test fails on any name that is not in it, so the next invented field is a red
`make test-unit` instead of a silent exit 2 in the merge workflow.

Two things make a deferral honest rather than silent (issue #491):

- **A green PR blocked only by a required review is approved by the OTHER identity, then merged**
  (issue #524). GitHub refuses a pull request approving its own author, so the job approves as the account
  that did *not* open the PR and then merges the pinned head with a plain `gh pr merge` — the path
  `trending-local-llms` gets for free because its `master` carries no review rule. `--admin` is only the
  last resort, for a PR whose author *is* the merge token's account; GitHub refuses that bypass wherever the
  review rule is enforced for admins (measured: PR #523, run 39816912388), so such a PR defers with the
  reason on itself. Setting the optional `APPROVER_TOKEN` secret to the other allowed identity's PAT lets
  those bot-authored PRs be approved and merged too. A stranger's green PR is never approved. Conflicts, a
  stale branch, a draft and `do-not-merge` are still deferred. **The job then waits, bounded, for the
  approval to take effect** (issue #531): GitHub computes `mergeStateStatus` asynchronously, so an instant
  re-read still says `BLOCKED` — the job polls for up to ~30 s and merges as soon as the PR is `CLEAN`. A PR
  that never converges defers with the state it stayed stuck in, never an empty reason.
- **Every deferral posts one comment per head SHA** with the reason and what would unblock it, so the PR
  answers "why is this not merged?" itself. `make auto-merge-explain` prints the same verdict at any time. **A deferral is retried, not parked**
(issue #545): `make auto-merge-recheck` (on every `CI` completion, and on a 30-minute cron backstop at **odd
minutes**, `3,33 * * * *` — issue #560: the `:00`/`:30` cron it replaced produced 0 runs of 66, while every
odd-minute cron in this repo fires) re-runs the same
decision for every open PR whose deferral marker names its current head, so a blocker that clears without a push — a secret added, a review
posted, `do-not-merge` removed, a pending check finished — is finished by the next sweep. A read that answers `mergeable: UNKNOWN` — GitHub computes it asynchronously right after a run — is **waited for** (`settle_mergeable`, bounded 6 × 5 s) instead of being treated as a verdict (issue #558).

The agent still never runs `gh pr merge` itself (AGENTS.md rule 7): it pushes, drives the PR green and
stops — CI lands it, or a human does when the job defers.

### Green ⇒ merged is permanent policy, and the tree half is guarded (issue #874)

**A pull request whose pipeline is green and whose state is `CLEAN` is squash-merged by CI, and this
behaviour is never removed from these pipelines** (owner instruction, 2026-10-28). #874 was filed because it
was switched off by hand and nothing in the tree failed: the file was still there, the workflow was
`disabled_manually`, and green PRs simply accumulated at `BLOCKED`. Three properties are policy now, and a
change that breaks one is a red `ci-unit` instead of a review argument:

| property | where | guarded by (`make test-unit`) |
|---|---|---|
| the workflow stays in the tree, named `auto-merge` | `.github/workflows/auto-merge.yml` | `tests/test_bot_pipeline_isolation.py::test_the_auto_merge_workflow_is_in_the_tree_and_keeps_its_name` |
| it fires **by itself** when a `CI` run on a pull request completes (`on.workflow_run`, `types: [completed]`), and its `merge` job still demands `conclusion == 'success'` | same file | `tests/test_bot_pipeline_isolation.py::test_auto_merge_fires_by_itself_when_a_pr_run_completes` |
| the decision keeps `REQUIRED_STATE = "OPEN"`, `REQUIRED_MERGEABLE = "MERGEABLE"`, `REQUIRED_MERGE_STATE = "CLEAN"` and the `do-not-merge` hold — `UNSTABLE`, `BLOCKED`, `DIRTY` and `BEHIND` all defer | `scripts/auto_merge.py` | `tests/test_auto_merge.py::test_the_merge_gate_still_requires_a_clean_pr` |

The `schedule` (`3,33 * * * *`) is the retry **backstop** for a deferral, never the trigger the guard
accepts: a workflow whose only automatic trigger is a cron merges nothing until that slot arrives, and one
reachable only by `workflow_dispatch` merges nothing until a human clicks it.

**A repo-level mute is not visible from the tree, and the guard says so.** `disabled_manually` is GitHub's
own state, readable only through the API, so a hermetic `ci-unit` cannot assert it; what the tree half can
prove is that nothing in the repository makes the workflow unreachable or inert. `allow_auto_merge` — the
repository-level switch `gh pr merge --auto` needs — is owner-only for the same reason.

### Which workflows may be paused — and which never

Pausing a bot leg is legitimate. Pausing the merge path is the defect #874 is about. Measured 2026-10-28
(`gh workflow list --all`), the paused set — the **only** workflows that may be paused — is the bot fleet:

> architecture-bot, code-review-bot, engine-build, engine-bump, engine-bump-rebase, fix-bot, issue-bot,
> issue-dedupe, issue-refiner, publish-agent-image, queued-alarm, rebase-bot, registry-sync,
> registry-sync-review, run-failure-reactor, search-smoke, security-bot, security-scan

**Never paused, in any pause: `auto-merge`** — the merge path itself. `ci.yml`, `pipeline.yml` and
`published.yml` are `active` for the same reason: each is what makes a green PR a mergeable, tested,
published one. (`bench-disk` also reads `disabled_manually` but has no file in the tree — a stale
registration, not a workflow a pause can touch.)

## The architecture bot — `docs/ARCHITECTURE.md` follows the code (issue #449)

The repository's other recurring readers (issue-bot, code-review, registry-sync, engine-bump)
each own one kind of drift; architecture had no bot and no document. `architecture-bot` runs
**every 6 hours** (`47 */6 * * *`, its own slot) and on `workflow_dispatch`, re-reads the real
tree and rewrites `docs/ARCHITECTURE.md` to match it. The refresh lands as **ONE linked issue +
ONE reviewable PR**; it never merges and never pushes to `main`.

```bash
make architecture-bot REPO=asimov-agent/llgenie          # brief -> doc -> issue + PR
make architecture-bot REPO=asimov-agent/llgenie DRY=1    # ... stopping at the preview
make architecture-bot-brief                              # real tree + git drift -> architecture-brief.md
make architecture-bot-doc                                # Hermes rewrites the doc (agent image)
make architecture-bot-publish REPO=asimov-agent/llgenie  # ONE issue + ONE PR, nothing without drift
```

- **The deterministic half decides.** `scripts/architecture_bot.py brief` derives the surface
  (tracked layout, `scripts/` modules with their docstring, public make targets, workflows and
  crons, `data/`, `skills/`, `containers/`, `tests/`) and the drift: the commit that last wrote
  the doc, the commits after it, and the paths that changed. No model call, and it writes only
  the brief. A doc with no history is a **full rebuild**.
- **The rename guard is applied to the WRITER, before anything is written** (issue #573). The
  CLI was renamed to `scripts/llgenie_serve.py` (#251) and the retired spelling may appear only in
  its deprecated shim, `agent-wiki/` and `openspec/changes/` — a doc that names it fails
  `make test-unit` and `make check-module-names` (the same rule, run as a CLI by `ci-unit`; its
  own test is the one file the CLI excludes, through `SELF_EXCLUDED`, issue #812). The rule lives
  once, in `scripts/module_name_guard.py`, imported by both
  `tests/test_rename_llgenie_serve.py` and `publish()`, which runs it on the regenerated doc and
  refuses **loudly** (no branch, no commit, no PR) instead of discovering it 25 minutes later as
  two red unit jobs (PR #572). The brief also tells the agent the rule, so the refresh should not
  trip it in the first place.
- **One agent leg, one writable file.** `make architecture-bot-doc` runs Hermes inside the
  pinned agent image with a prompt that may modify `docs/ARCHITECTURE.md` and nothing else — no
  branch, no commit, no push, no issue. Its transcript goes through the `scrubbed_run` seam and
  the workflow uploads `hermes-run.scrubbed.log`, never the raw capture.
- **A lost GitHub answer is not a failure.** `publish` retries `gh pr create` on a transient
  502/503/504 or timeout, and if the create's answer never arrives it adopts the open PR on the
  branch it pushed; only a real failure exits non-zero, naming the issue and branch it made so a
  human can finish it (issue #479).
- **Quiet unless the tree moved.** `publish` re-checks the working tree: an unchanged doc files
  nothing, a doc shorter than 200 characters is refused, and an already-open
  `agent/architecture-*` PR makes the run `action=pending` (no second issue every 6 hours).
- **What it files.** One issue (Issue / Fix / Benefit / Technical), one branch
  `agent/architecture-<UTC stamp>`, one commit carrying only the doc, authored
  `Asimov Agent <support@docondee.com>`, and one PR to `asimov-agent/llgenie:main` whose body
  ends with `closes #<issue>`.
- **The PR is opened with the owner PAT, the issue with the job token** (issue #497). A pull request
  created with `GITHUB_TOKEN` starts **no** workflows, so it would carry zero checks and could never be
  green — `gh pr checks` on such a PR answers "no checks reported". `publish` therefore reads `PR_TOKEN`
  (the workflow sets it from `secrets.BUMP_TOKEN`) for `gh pr create` only, while `gh issue create` keeps
  `github.token`, the only one of the two with Issues write (#412). Both travel in the child's
  environment, never on a command line. A PR authored by this repo's own bot is approvable by the
  auto-merge job's other identity (#529).
- **Who may run it.** The trigger guard runs first, before any secret: the repository owner, a
  collaborator with `admin`/`maintain`/`write`, or the repository's own bot when the run's head is a
  branch in this repository (a bot-opened PR is such a head, issue #510). A stranger cannot dispatch
  it.

## Holds need a remedy (issue #948)

`do-not-merge` means **a known defect with a tracked remedy** — never "this lane would rather not". The owner's
ruling: never place it unless the PR is totally wrong or conflicts with something concrete, and if you do, **file
the issue that makes the tag removable and say so where a reader can see it**. A PR a bot implemented cannot carry
it by default.

`mergeStateStatus` reads `BLOCKED` either way, so no existing check could tell a hold with a remedy from one
without. Two ways to read a hold:

```
make check-holds      # CI (holds.yml, daily + on labelled PRs): fails on any hold with no named remedy
make holds-report     # every held PR and the issue it names — exits 0, so a bad board can still be read
```

The remedy must be a **resolve-verb phrase next to an issue number** — `resolves #NNN`, `blocked by #NNN`,
`until #NNN` — in the PR body or any comment. A passing mention (`supersedes #786, see #892`) is **not** a
remedy: measured on this repo when the issue was filed, all three held PRs named issues and none named a remedy
for the *hold*, which is why an "any `#N`" rule would have passed every hold ever placed.

The lane that placed the hold removes it when its fix lands, and says so with the sha or run id that proves it.

## The run-failure reactor (issue #286)

A bot that reacts to a **failed CI run** — any run, not just a PR check — and routes it to a remedy.
It is triggered by `workflow_run: types: [completed]` over the repo's own workflows, and the route
decision lives in `scripts/run_failure_reactor.py` (stdlib only, no LLM), never in a job `if:` that
can silently skip (issue #107):

```bash
make run-failure-reactor REPO=asimov-agent/llgenie RUN_ID=<run>   # route a failed run
make run-failure-reactor REPO=asimov-agent/llgenie RUN_ID=<run> DRY=1   # preview, dispatch/file nothing
```

- **Route A** — the failed run reports a PR this bot can **push**: the reactor claims the PR
  (`scripts/bot_claims.py`, issues #279/#285) and dispatches the **existing** `fix-bot` for it,
  reusing `scripts/fix_bot_sweep.py`'s eligibility rules. Pushable means this repository **or the
  owner's fork** (`andyholst/llgenie`, where every agent PR lives): a fork `pull_request` run's REST
  `pull_requests` array is empty (measured, #277/#170), so the PR is resolved from the run's
  `head_branch` + `head_repository.owner.login` with `scripts/resolve_run_pr.py` — the resolver
  auto-merge uses (issue #555). A **fifth-party** fork is still never dispatched: no token this
  repository holds can push it. The dispatch carries the **owner** identity (`DISPATCH_TOKEN`, from
  the environment only) because the dispatched run's actor is the token's identity and every guarded
  workflow here refuses `github-actions[bot]` — a dispatch with the job token died in fix-bot's own
  guard (run `39917926028`). A missing `DISPATCH_TOKEN` is a loud failure, never a red no-op run.
- **Route B** — no pushable PR (a red `main` push, a red scheduled bot run, a red publish job):
  the reactor files **exactly ONE** issue whose title names the workflow + failing job, whose body
  carries the failing job, its step, and a tail of `gh run view --log-failed`, deduped by the
  marker `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (searched `in:body`), and labelled
  `agent:implement` so the issue-bot picks it up. An OPEN issue already carrying the marker files
  nothing.
- **Route B files only work that is still work (issue #565).** "No pushable PR" covers two very
  different states and only one of them is a work item. A `pull_request`-event run is filed only
  while an **open** PR exists for its head — a draft, or a PR whose repair attempts are spent. A
  merged/closed PR (its branch deleted) is history: nothing is left to repair. A `push` run is filed
  only when no **later run of the same workflow on the same branch concluded `success`**, because a
  later green run on that branch proves the failure was transient or already fixed. The verdict is
  printed — `[run-fixer] run <id> is SUPERSEDED: <reason> - filing nothing` — never a silent skip,
  and an unreadable answer (a failed `gh` read) is UNKNOWN, never a supersede. Measured on
  2026-10-23: **6 of 6** open `agent:implement` issues the reactor had filed were this second state,
  and with the issue-bot's `MAX_PER_DAY = 3` they were two days of agent runs spent re-deriving
  failures that were green before their issues existed. The sha-scoped marker stays: a same-job
  failure on a *different* head can be a different defect (`macos / unit` failed on the engine-image
  digest, the README dispatch table and a cron collision within six hours).

`.github/workflows/run-failure-reactor.yml` runs it on every completed run. It **never** repairs,
commits, pushes or merges in the file-issue path — it files; the issue-bot owns implementation, the
fix-bot owns PR repair. A run it cannot diagnose is reported loudly, never silently dropped.

Its `workflows:` roster is TRUE, not a list someone remembered (issue #349): GitHub matches it against
each workflow's top-level `name:` verbatim and takes no wildcard, so `make check-workflows` fails
`ci-unit` when a name in it is no workflow's `name:` (a rename stops matching silently — measured on
`rebase-bot.yml` after #463, whose failures then routed nowhere for a week), when a workflow's completion
is routed nowhere, when the list names the reactor itself (a self-trigger loop), or when an entry in
`tests/fixtures/workflow-run-exemptions.json` has no `reason` or names no workflow (a stale exemption).
Two workflows are exempted there, each with its reason written down: `security-scan`, whose red is
already a work item `make security-issues` and `security-bot` own, and the reactor itself.

### A scheduled sweep must not queue behind itself (issue #917)

A `schedule:` workflow fires again on its slot whether or not the previous run finished. Two different
failures follow, and the second one is the one that bit here:

1. with `cancel-in-progress: false` a new run **waits** for the old one, so a slow sweep becomes a queue of
   identical sweeps — measured on `auto-merge`: **nine sweeps stacked in 36 minutes**;
2. and the flag does **not** protect a *pending* run at all. GitHub keeps one running plus one pending per
   group, and a newly queued run replaces the pending one whatever the flag says — the flag only protects the
   run already executing. With a per-branch group the scheduled sweeps (which carry no `head_branch`) all
   collapsed into one empty-name group and cancelled each other's pending slot: **16 of the last 25 runs were
   cancelled with no job rows**, so nothing drained and churn looked like backlog.

So `auto-merge` uses **one repo-wide group with `cancel-in-progress: true`** — only one sweep decides at a
time, absolutely. That is safe here specifically: a sweep holds no state between runs (it re-reads every PR),
each merge is one atomic `gh pr merge` call so a cancellation lands before or after a merge and never inside
one, and a PR whose sweep is preempted is picked up by the next sweep, including the scheduled recheck.

`make sweep-concurrency-report` lists every other scheduled workflow whose runs stack, split into *"stack with
no stated decision"* and *"stack on purpose"*:

- **reads fresh state, then acts** → `cancel-in-progress: true` under a group that cannot preempt a different
  unit of work;
- **mutates shared state** (a registry sync, an image build, a branch force-push) → serialising is right: keep
  `false` **and state it in the file** as `# concurrency: stacking is intended — <reason>`, so the next reader
  knows it was decided rather than copied. `tests/test_ci_concurrency.py` refuses an unexplained
  `cancel-in-progress: true`; the marker is the escape, and it is reviewed in the same diff as the setting.

## Dispatching a bot by hand (issue #276)
Every workflow a human can start by hand states **what work the run will do** — in its name, in its
dispatch form, and in the header block at the top of the file (`Trigger surface` / `Flow` / `Never`).
A bot you cannot dispatch without reading its YAML is a bot only its author can operate.
`make check-dispatch-forms` enforces it (in the `ci-unit` job): every dispatchable workflow must
- have a `name:` that states the work, not the file name — `issue-bot — implements ONE issue per run
  as a reviewable PR (never merges)`, so the Actions list reads as a list of jobs;
- give every `workflow_dispatch` input a `description:` (written as the instruction a user needs) and
  a `default:` or `required: true` — a bare `workflow_dispatch:` is allowed only with an explicit
  `# dispatch: no inputs — <reason>` line, so "it takes no input" is a decision, not an oversight;
- carry the header block, where `Flow` names the make target behind each stage and `Never` states the
  invariants (never merges, never pushes to `main`, never edits code).
The table below is generated from the workflows by `make dispatch-forms-report` and verified against
them by `make check-dispatch-forms`, so the documentation you read before dispatching cannot drift
from the pipeline that will run.
<!-- dispatch-forms:begin -->
| workflow | what the run does | dispatch inputs |
|---|---|---|
| `architecture-bot.yml` | rewrites docs/ARCHITECTURE.md from the tree and opens a linked issue + PR (never merges) | `dry` (optional, default `false`) — Preview the issue and PR bodies this run would file, filing nothing<br>`doc` (optional, default `docs/ARCHITECTURE.md`) — Repository-relative markdown document to refresh |
| `ci-hf-live.yml` | the merge-to-main real-Hub test pipeline (HF live tests + the committed-link liveness gate), never a PR check | none — the pipeline runs exactly the @pytest.mark.network ownership set, gated first |
| `ci-requeue.yml` | re-runs only the cancelled runs no later run superseded, every 30 minutes | none — the healer takes no target: it re-runs every cancelled run in the window that |
| `code-review-bot.yml` | reviews the tree and the pipelines and files one issue per finding (never edits code) | `dry` (optional, default `false`) — Preview the issues it would file (owner only) |
| `engine-build.yml` | builds and verifies EVERY engine at its committed pin, in parallel (never merges) | `engine` (optional) — Engine id to sweep (e.g. llama.cpp); empty = every engine in the committed params<br>`arch` (optional) — One backend to sweep (cpu|cuda|rocm|vulkan); empty = every variant of each engine<br>`push` (optional, default `false`) — Publish the built images to GHCR (true) or build and verify only (false)<br>`force` (optional, default `false`) — Rebuild from scratch, ignoring the layer cache (true) or reuse a cached/available image (false) |
| `engine-bump-rebase.yml` | rebases every open engine-bump PR onto the latest main | `dry` (optional, default `false`) — print the PRs it would rebase and push nothing (no branch is touched) |
| `engine-bump.yml` | bumps pinned engines to their newest upstream release and opens the PR | `engine` (optional) — Only bump this engine (id); empty = all |
| `fix-bot.yml` | repairs a failing PR branch until its checks pass (never merges) | `pr_number` (optional) — PR number whose branch should be repaired<br>`branch` (optional) — PR head branch (used when pr_number is empty)<br>`check` (optional, default `make ci-unit`) — the deterministic check to drive the loop<br>`rounds` (optional, default `5`) — repair attempts (default 5)<br>`report_file` (optional) — path to the failed run's captured log (repair context; empty = run the check locally) |
| `holds.yml` | fails when a do-not-merge label names no resolving issue | none — it reads every held PR and fails on any hold with no named remedy, so a hand run just |
| `issue-bot.yml` | implements ONE issue per run as a reviewable PR (never merges) | `issue_number` (optional) — Issue to implement (owner only). Leave BLANK and the bot picks the oldest agent:implement issue itself - one issue per run, exactly like the schedule |
| `issue-dedupe.yml` | retires a duplicate of an issue, FOUR times a day, never a claimed one | none — the bot decides by itself which ONE pair to compare (scripts/issue_dedup.py). |
| `issue-refiner.yml` | reviews ONE not-yet-implemented issue, never opens a PR | none — the bot decides by itself which ONE issue to review (scripts/issue_refiner.py); |
| `publish-agent-image.yml` | builds + pushes the Hermes agent image when its hash is not on GHCR yet | `force` (optional, default `false`) — Rebuild + push even if the hash tag is already on GHCR |
| `queued-alarm.yml` | reports CI jobs queued far too long, once per affected run | `minutes` (optional, default `30`) — report jobs queued longer than this many minutes |
| `rebase-bot.yml` | keeps every open PR current with main, every eligible PR per run (never merges) | `max_prs` (optional, default `10`) — Most PRs this run may rebase (the sweep's daily cap still applies on top) |
| `registry-sync-review.yml` | a GREEN registry-sync PR is reviewed into ONE agent:implement issue | `dry` (optional, default `false`) — Preview the brief and the issue body this run would file, filing nothing |
| `registry-sync.yml` | syncs the vendored registry and regenerates the derived tables, then opens the PR | none — the sync has no modes: it always fetches the upstream registry, regenerates |
| `search-smoke.yml` | one real Firecrawl request proves the masked web reach | none — the smoke takes no target: it always proves the same leg with one request. |
| `security-bot.yml` | turns ONE auto-fixable vulnerability issue into a green PR (never merges) | `dry` (optional, default `false`) — Preview the issue it would take and the edit it would make, pushing nothing |
| `security-scan.yml` | the daily vulnerability pipeline (Trivy + Syft + Grype + Semgrep), never a PR or push check | `tools` (optional, default `all`) — Which scanners to run: all, or one of syft / trivy / grype / semgrep<br>`enforce` (optional, default `full`) — Failure policy for THIS dispatch: full = the daily policy, report = never gate |
<!-- dispatch-forms:end -->

## Verification, loop & CI (containerized — same everywhere)

Every verification stage runs **inside the test container** so behaviour is
byte-identical on your local host (docker; on macOS through Colima) and on GitHub
Actions CI. Stages are driven **only through `make`** — the container is never
started directly.

```bash
make loop              # == make loop-harness: run ALL stages in order, GREEN gate
make test-image        # the test image (python+pytest+deps + hf + docker CLI; no inference server): pulls the
                       # published ghcr.io/asimov-agent/llgenie/test:<hash of its Dockerfile + lockfiles>,
                       # builds it here only when that hash is not published yet (an edited Dockerfile/lockfile)
make openspec-image    # the OpenSpec CLI image, the same way (hash of openspec/Dockerfile)
make ci-image-refs     # print both GHCR refs for the current files
make ci-<job>          # one CI pipeline job (ci-lint, ci-unit,
                       # ci-agents-read, ci-openspec, ci-cpu-health, ci-top-tier, ci-install): what CI runs
                       # ci-install chains, in this order: test-env -> ci-install-run (make install)
                       # -> ci-install-dry (the installed launcher, bare --dry) -> ci-install-dry-args
                       # (the INSTALLED launcher's argument surface over the mocked arch x vram x ram
                       # grid, issue #236) -> ci-install-uninstall
make lint              # linefeed/editorconfig lint (fail-closed)
make test              # the loop's fast stage: the hermetic files in ONE named group the roster records
                       # (`groups.fast` in tests/fixtures/unit-suite.json, issue #403), run through
                       # scripts/unit_tests.py — the recipe names no test file; then the install
                       # assertions run on the host where ~/bin/llgenie + ~/models live
make test-unit         # hermetic unit tests — the suite is DISCOVERED by scripts/unit_tests.py (every
                       # tests/test_*.py minus the dated exclusions in tests/fixtures/unit-suite.json),
                       # never a hand-written list in the recipe (issue #393)
make openspec-tasks-check  # every ACTIVE OpenSpec change has no unchecked `- [ ]` task box — the
                       # completion half of the openspec gate (the loop's last stage, and ci-openspec)
make test-agents-read  # AGENTS.md threat-pattern guard + its tests, in a make-built Python 3.12
                       # venv (~/.cache/llgenie/agents-read-venv: hermes-agent==0.19.0 + pytest;
                       # needs python3.12)
make test-install      # install tests (run in-container; host-artifact asserts — no skips via test-install-ci)
make test-install-ci   # REAL install tests, NO SKIPS: make install + model + assert in ONE container
make test-uninstalled  # after make uninstall: no launcher/shim/llgenie-engine-* left, no engine container
make test-install-host # verify the REAL host install: ~/bin/llgenie + symlinks + ~/models (runs on host)
make engine-launchers  # pull this host's published engine images (default llama.cpp + Prism; ENGINES=all|id,id;
                       # BUILD=1 builds unpublished ones) and write ~/bin/llgenie-engine-<id> + the
                       # llama-server / prism-server shims
make test-install-trend # after make install: ~/bin/llgenie with NO model in a pty -> recommended list from
                       # data/models.json -> pick 1/1 -> REAL GGUF download -> the engine container answers
                       # "hi" (issue #105)
make test-published-engine ENGINE=<id> ARCH=<arch>  # issue #102: pull ENGINE's :ARCH image AS PUBLISHED
                       # (no build, digest == the :ARCH tag), then the binary reports its version and the
                       # container serves the tiny model and answers "hi" on /v1/chat/completions.
                       # The binary-flag check runs in the TEST IMAGE like every other test stage
                       # (issue #621): the runner's own python3 has no pytest
make ci-engines BACKEND=metal  # the engine stage (issue #120): cpu|cuda|rocm|vulkan -> container engines, metal -> every native engine
make test-native-engines       # Apple Silicon: make install path for EACH native-Metal engine, tiny model on Metal + "hi"
make test-native-engine        # Apple Silicon: REAL TensorFold install / update / reuse through the llgenie pick
make test-native-engine-serve  # + llgenie --select 1 --engine tensorfold downloads Qwen3.8-27B, serves on Metal (context 65536), "hi"
make test-native-engine-light  # lightest TensorFold model (Qwen3.5-9B MLX 4-bit) via the start script: Metal "hi", or the budget refusal on a 7 GB runner
make test-interactive-tensorfold                          # plain interactive llgenie: pick Qwen3.8-27B, then TensorFold -> installs, serves on Metal, "hi"
make test-interactive-tensorfold TEST_LAUNCHER=~/bin/llgenie  # the same through the launcher `make install` wrote
make test-interactive-tensorfold-ci                       # macOS CI runner variant: same picks (--dry, 48 GB emulated) + real install
# The native targets above are Metal-only: on Linux (any backend) they print that the host
# has no native engine and exit 0; Linux engines are tested in their images (make test-engine).
make test-health       # Linux: 0.5B answers "hi" through the llama.cpp image. macOS: refuses --arch cpu, no image
make test-health-host  # after make install: the same through ~/bin/llama-server (on the host, no container)
make test-top-tier     # REAL acceptance (no mocks): live HF trending + fit gate + real download
make test-top-tier-serve  # Linux: lightweight model through the llama.cpp image, "hi". macOS: no engine image
make test-top-tier-ci        # REAL top-tier acceptance inside the test container (CI/CPU; hf + gguf are bundled)
make test-top-tier-serve-ci  # Linux: serve the lightweight model through the llama.cpp image. macOS: no engine image
make test-top-tier-cli-ci # REAL CLI dry-run in the CI container: llgenie --download-top-tier --dry --count 2
make test-variant-image      # CUDA toolkit + python variant-build image, built locally (the matrix job is retired)
make download-test-model  # fetch Qwen2.5-0.5B into ~/models/Qwen/8GB (via `hf` CLI)
make lint-fix          # append a missing trailing newline to tracked text files (containerized)
make check-registry-keys     # fail when the vendored registry dropped a key, model or measurement vs the committed copy
make check-strata-models     # fail when data/strata_models.json differs from Strata's setup.py at the pinned commit
                             # A FAMILIES entry with no Hub URL (e.g. the vendor-hosted `nvfp4`) is vendored as
                             # "hub": false with no repo — it is not downloadable here, and it no longer breaks the
                             # vendor step (a family with a URL keeps the committed shape byte for byte; issue #416)
                             # A map that breaks the family SHAPE — a family is Hub-hosted (repo + revision +
                             # subdir, no `hub` key) or explicitly not-Hub (`hub: false`, no repo), never both,
                             # never neither — is now reported by family and defect, not just as a diff
make queued-alarm      # report CI jobs stuck in `queued` too long (a runner that never picks them up, issue #254);
                       # COMMENT=1 delivers it to the run's pull request (else ONE deduped issue per stuck runner
                       # label, for runs no PR tracks) and a delivery that fails is exit 3, never silent; DRY=1 previews
make ci-requeue-cancelled  # re-run the CI runs a bulk cancel killed, ONLY where the head sha has no other run
                           # (a superseded run already has its verdict): WINDOW=2h, DRY=1 previews; issue #843

Scheduled: `.github/workflows/ci-requeue.yml` runs that same target every 30 minutes (`23,53 * * * *`,
off the hour and off the other bots' minutes) with `concurrency: cancel-in-progress: false`, so one
round can never be cancelled by the next — the exact bug the healer exists to undo. It holds only
`contents: read` / `actions: write` / `pull-requests: read` (what `gh run rerun` needs) and it is named
in `run-failure-reactor.yml`'s roster, so its own red is routed like every other workflow's.

make run-failure-reactor  # route a failed CI run to a remedy (REPO=; RUN_ID=; DRY=1 previews): a PR this bot can push
                       # (this repo or the owner's fork) -> dispatch the fix-bot as the OWNER (DISPATCH_TOKEN); else file
                       # ONE deduped issue labelled agent:implement (issue #286, fork routing #555)
make openspec-validate NAME=<change>   # validate ONE OpenSpec change (fail-closed)
make openspec-validate-all             # validate the structure of EVERY active change — what ci-openspec runs (issue #156)
make openspec-new NAME=<change>        # create a change dir (the OpenSpec CLI, containerized)
make openspec-status                   # list the changes and their task state
make openspec-shell                    # interactive shell with the openspec CLI in a container
make engine-detect ENGINE=<id>         # is ENGINE installed? runs that skill's detect
make engine-smoke ENGINE=<id>          # HOST entry: install the engine via its skill, serve a tiny model, assert llm-local answers
make generate-build-engine-params      # alias of generate-engine-params
make run-engine-<engine>-<arch> MODEL=…  # run one engine x arch image (e.g. run-engine-vllm-cuda PORT=11434)
make fix-bot-sweep | fix-loop | fix-loop-image | fix-bot-report  # the PR fix-bot (issues #222, #238): sweep, loop, loop-in-the-agent-image, report
make agent-image | agent-image-pull | agent-image-ref | publish-agent-image  # the Hermes agent image: pull, CI pull, ref, publish
make check-docs        # fail when a user-facing make target is not documented here, or a work record names no issue (issue #257)
make docs-report       # show every user-facing target: documented, missing, or a recorded exception
make check-pr-hygiene  # fail when a producer's commit message or PR body is empty, a placeholder, a subject with no body, or when AGENTS.md lost the mandate (issue #313)
make pr-hygiene-report # show every producer the PR/commit-message guard reads, and its verdict
make check-pr-authors  # fail when a PR commit is authored through an allowlisted email address, when a Co-authored-by trailer names anyone else, or when a producer commits off the allowlist (issue #345)
make pr-authors-report # show every commit in the range with its author verdict, and the identity each producer assigns
make check-workflows   # fail when a YAML file's GitHub expression does not parse, a YAML file lacks a trailing newline, a workflow has no top-level name, a `workflow_run` trigger names no workflows (issue #330), or a `workflow_run` roster names a workflow that does not exist / leaves one unwatched (issue #349)
make check-module-names   # fail when a LIVE file spells the retired CLI module name instead of
                          # `scripts/llgenie_serve.py`; the one excluded file is the guard's own test, through the
                          # module-level `SELF_EXCLUDED` constant (issues #251, #573, #812)
make issue-cleaner-scan   # which OPEN issue a merged PR already implemented: GitHub closes an issue at merge
                          # only when the body carries a closing keyword bound to it, so a PR that merged and
                          # left its issue open is a stale-open (issue #325). Prints each finding with its
                          # evidence and closes nothing; REPO= picks the repo
make issue-cleaner-apply  # the same decision, then: an evidence comment on the issue and a close as
                          # completed. An issue the PR's own `Not covered` section names is a tracked
                          # remainder and is left open; REPO= picks the repo
make workflows-report  # show every YAML file the workflow gate reads, how many expressions it validated, and its verdict
make worktree-report   # measure the bench before a bot starts, and mutate NOTHING (issue #794): one row per
                       # `git worktree list --porcelain` entry with its path, branch (`detached` when it holds
                       # none), merged-into-main (a real `git merge-base --is-ancestor <head> <base>`), open-pr
                       # (a real `gh pr list`) and dirty (a real `git status --porcelain` in that directory),
                       # then a summary counting total, stale (merged, no open PR), off-main-no-pr and dirty.
                       # Exit 0 even when nothing is stale; exit 2 naming the step when a measurement fails,
                       # because an unreadable state is not a clean state. SLUG= and BASE= override the repo and
                       # the base. A host bot runs this INSTEAD of the prune: the prune deletes directories and
                       # cannot see uncommitted work, so a mid-flight tree whose tip is already an ancestor of
                       # `main` looks exactly like a finished one (it destroyed the #791 run's worktree).
make worktree-prune    # remove the worktrees and local branches whose PR already merged, so the checkout stops
                       # accumulating debris (issue #431). Eligibility is the PR, never a name pattern or an
                       # ancestry guess: this repo squash-merges, so a merged branch's tip is NEVER an ancestor
                       # of main and `git branch --merged` calls landed work unmerged forever. A branch is
                       # pruned only when it is a MERGED PR's head AND that PR's merge commit is on the base
                       # (origin/main; BASE= overrides). Kept, with its reason printed: an OPEN/CLOSED PR, no
                       # PR at all, a merge commit off the base, a dirty worktree, and the main checkout. A
                       # worktree git reports as DETACHED carries no branch name, so it is matched by HEAD: one
                       # detached worktree parked on the pruned branch's own tip IS that branch's checkout and is
                       # removed before the branch, while a detached worktree on any other commit is left alone
                       # (issue #570 — the plan used to promise "prune 1 branches, 0 worktrees" for a branch that
                       # had one, and `git branch -D` then failed the whole sweep forever). When git still refuses
                       # the delete because a worktree holds the branch, the refusal is split two ways (issue #593):
                       # a worktree that is detached, branch-less and clean is debris and is removed before a
                       # single retry, while one with a branch checked out or uncommitted/unmerged work makes the
                       # branch a KEEP with that reason printed — never an `Error 2` that reds the whole sweep.
                       # DRY=1 prints the plan and mutates nothing; SLUG= picks the owner/name
                       # gh reads (default asimov-agent/llgenie — REPO is the checkout path, which gh rejects).
                       # A BOT RUN IS REFUSED (issue #794): `scripts/worktree_prune_guard.py` runs first and,
                       # when the run is unattended and CONFIRM=1 is absent, exits 3 naming the marker that
                       # said so, `make worktree-report`, and the re-run spelling. "Unattended" covers every
                       # lane a bot takes: `CI` (a GitHub step sets it), `BOT` (the Makefile's
                       # AGENT_BOT_MARKER, forwarded as `-e BOT=1` on every agent-image run — docker does not
                       # inherit the host env) and the dispatcher's `HERMES_KANBAN_TASK`,
                       # `HERMES_KANBAN_WORKSPACE`, `HERMES_KANBAN_BRANCH`, `HERMES_KANBAN_WORKSPACES_ROOT`
                       # (a lane spawned on the host). The owner's own run (no marker set) is unchanged, and
                       # CONFIRM=1 lets a bot proceed once a human has read the report.
make test-clean        # prune stopped orphaned test containers (always)
```

The `make loop` harness runs these stages in order (each in its own `--rm`
container), then **always** prunes orphaned containers:

```
image → download → lint → unit → install → health → top-tier → top-tier-serve → test → openspec → clean
```

- The **`health` stage** on Linux is a real end-to-end check: it downloads the
  lightweight `Qwen2.5-0.5B` model and asserts `/health` + a chat "hi" reply
  from the **llama.cpp engine image**, started from the test container through the host docker socket (the test image holds no inference server).
  On macOS the same `make test-health` does not start an image: `--arch cpu` is refused and the native Metal serve stays `make ci-engines BACKEND=metal`.
- **Python 3.11 on both OSes:** on Linux the test stages run in `llgenie/test` (`python:3.11-slim`); on macOS the SAME make targets run natively with the 3.11 gguf venv (`~/llama-gguf-tools/.venv`), never in a container. `make test-env` prepares it (Linux: pulls the test image; macOS: `make -C tools venv-dev-install`, then `brew install uv` when `uv` is not already on PATH). LiteRT, MLX and TensorFold install as `uv` tools; a missing `uv` fails `make install` loudly.
- **`RUNTIME`** is `docker`, on Linux and on macOS (Colima with `--runtime docker`).
  `make install` reports a docker that does not answer as such, not as an unpublished image.
  `RUNTIME=<path to a docker CLI>` overrides it.
- **A slow test is shown, not hidden:** `pytest.ini` sets `faulthandler_timeout = 300`, so a
  test running over 5 minutes prints every thread's stack into the log and keeps running.
- **CI is Linux-only (issue #870).** `ci.yml` has **no `macos` group**: the seven macOS rows
  (`lint`, `install`, `openspec`, `agents-read`, `cpu-health`, `unit`, `top-tier`) are gone from the
  pull-request matrix, not conditionally skipped, so no macOS runner is ever requested. The trigger
  is conservative on purpose — an absent row cannot starve.
  **Why, measured:** the hosted macOS pool on this account is not reliably issued. Probe run
  `40741670180` queued all three hosted macOS labels for 14 minutes each with `runner=NONE`, while
  the repository holds 10 successful macOS jobs in the same `GitHub Actions` runner group and 54
  macOS jobs were cancelled with **no runner ever assigned**. The recourse is not a label: it is not
  depending on a macOS row in the PR path. Measured cost of depending on it: #767, a one-file
  documentation PR, sat with 26 green jobs and **zero failures**, waiting two hours on one macOS row.
  **The trade, stated so it is not discovered later:** a macOS-path change now needs **hand review**.
  `pipeline.yml` is unchanged and still runs on a macOS runner when a caller passes that label, so
  the coverage can be restored by adding a caller back; until then nothing in CI exercises macOS, and
  the native-engine targets (`make ci-engines BACKEND=metal`) are verified on an Apple-Silicon host
  by hand.
- **`linux / top-tier` is not a pull-request gate (issue #859).** It downloads and serves a real
  model on every PR; what it proves is a property of `main` and of the weekly engine/registry data,
  not of a diff, and it was one of the long poles of every matrix (measured: #767's run
  `40694228407`, a one-file documentation PR, sat with 26 green jobs and zero failures waiting on
  one heavy row alone). It **does** run on every non-PR event — the `push` to `main`, so one run per
  merge still catches a model/engine regression — and on a pull request that carries the
  **`ci:slow`** label (add the label, then a new run of that PR — close/reopen, or a push —
  schedules it). It is the heaviest row when requested. Everything else is unchanged:
  `linux / unit` remains the PR gate for the whole suite (`ci-unit` included), and
  `linux / cpu-health` still serves the 0.5B model through the engine image on a PR. The macOS rows
  this issue also named (`macos / unit`, `macos / top-tier`) are gone by **deletion** (#870), not by
  a condition. The decision is `scripts/ci_slow_rows.py` behind `make ci-slow-rows`, published by
  `ci.yml`'s `guard` job and consumed as the ONE matrix axis of `pipeline.yml`'s `top-tier` job, so
  there is no job-level `if:` and no silent skip: a run that does not schedule the row has the
  `["none"]` placeholder, which runs no make target and whose first step prints
  `[slow-rows] … = NOT SCHEDULED` with the reason. `tests/test_ci_slow_rows.py` pins the decision and
  the wiring.
- **Required for merging into `main`** (branch protection): the Linux jobs that remain. A failure
  fails the run. That is `linux / *` and the four `linux-published / install-published-*` installs.
  They have no published-image stage of their own and no native-engine job: `linux / cpu-health` and
  `linux / top-tier` run a real model in a container, which is what a GPU-less runner can prove.
- **One CI run per change, not per push:** `ci.yml` triggers on `pull_request` against
  `main` and on `push` to `main` (a merge, which additionally builds and publishes the
  engine images) — never on a bare feature-branch push. So a branch is vetted by its PR's
  run, and the merge commit's run is the publish path. A fork PR is vetted by the upstream
  run and its checks report on the PR (issue #155).
- **A fork PR's publish is a loud skip, not a red job (issue #155):** `make push-engine` is a step of
  every `engine-image-*` job, and GitHub scopes a fork PR's token to the base repository's packages
  **read-only**, so the registry answers `denied: installation not allowed to Write organization
  package` on a branch whose build and test passed. `scripts/engine_image.py::push` turns exactly that
  refusal, and only inside a `pull_request` run, into a skip: a `::warning::` annotation plus
  `[engine-image] SKIP publish <ref>: pull_request token cannot write … (issue #155)`. The image is
  still built and post-build tested, and the run that lands the change on `main` publishes it. A push
  run's denial — or any other push failure — still fails loudly. The policy is in the script, not in a
  scenario-scoped workflow `if:`; locked by `tests/test_ci_publish_scope.py`.
- **Only collaborators, the `github-actions[bot]`, and the owner may trigger the
  workflows:** `ci.yml`, `registry-sync.yml`, `engine-bump.yml` and `engine-bump-rebase.yml` gate every run behind an actor guard that
  fails unless the triggering actor is the repo owner, the `github-actions[bot]`, or a
  collaborator (checked via the GitHub API collaborators endpoint). This is defense-in-depth
  on top of the fact that a push to a fork already runs the workflow in the fork (its own
  GHCR), never upstream — so a non-collaborator can never drive the upstream's GHCR publish
  jobs (`ci-images`, `engine-base`, `engine-matrix` in ci.yml; `sync` in registry-sync.yml; `plan`/`bump` in engine-bump.yml).
- **CI images are pulled, never rebuilt per job (issue #117):** the first job, `ci-images`,
  tags `llgenie/test` and `llgenie/openspec` with a hash of the files they are built from
  (`scripts/ci_images.py`) and runs `make publish-ci-images`: a hash already on GHCR is one
  manifest lookup, a new one is built once for linux/amd64 + linux/arm64 (registry layer
  cache) and pushed to `ghcr.io/<owner>/llgenie/{test,openspec}:<hash>`. Every other job
  (Linux, macOS, `engine-image`, `test-published-*`, `install-published-*`) runs
  `make test-image-pull` / `make openspec-image-pull`, which fail instead of building when the
  tag is missing.
- **The same CI pipeline on Linux and macOS:** `.github/workflows/ci.yml` calls ONE file,
  `pipeline.yml`, twice: `linux` (ubuntu-latest) and `macos` (macos-15-intel). Linux sets
  up Docker; macOS runs the same `make ci-<job>` targets in the Python 3.11 gguf venv
  and never starts Colima. No macOS job calls the Docker action. Engine images are the
  Linux published stage. OpenSpec on macOS installs the pinned CLI.
  The early `install` job runs `make ci-install` on both OSes. That target only prepares
  the environment, then runs `make install`, `$HOME/bin/llgenie --dry` and `make uninstall`
  as separate make targets. macOS runs them in the Python 3.11 venv and never starts a
  container. The `macos` job is `macos-15-intel` (`x86_64`): `make install` there installs
  no Metal engine and pulls no image, because LiteRT, MLX and TensorFold publish arm64
  wheels only — and because nothing was written, the `test-built-engine` and `uninstall`
  steps that follow are a no-op that exits 0 (nothing to version-test, nothing to remove).
  Apple Silicon still installs every native Metal engine. Linux runs
  `make install`, the dry run and `make uninstall` inside the test container, so the dry
  run sees the launcher `make install` just wrote.
  Native-Metal engines are not tested in CI (no Metal on the runners); run
  `make ci-engines BACKEND=metal` on an Apple-Silicon host. Every job is one `make ci-<job>` target (lint, unit,
  install, agents-read, openspec, cpu-health, top-tier), the same job on both
  OSes, same asserts, no combined jobs (issue #120). Docker is set up only on Linux
  (`.github/actions/docker`); macOS never runs it. `tests/test_ci_images.py` locks that both OSes call the one file.
- **Native Metal engines, on an Apple-Silicon host (issue #120):** `make ci-engines BACKEND=metal`
  (no CI job: GitHub's macOS runners have no Metal GPU):
  every servable engine with a Metal backend (`model_engine_pick.metal_engines()`: litert,
  llama.cpp, llama.cpp-prism, mlx, ollama, tensorfold) is installed natively by its skill —
  llama.cpp and the Prism fork are BUILT from source with `-DGGML_METAL=ON` — prints its
  version and serves a tiny model on Metal answering "hi".
- **One pipeline, per-OS engine set (issue #120):** the macOS pipeline is literally the
  same pipeline as Linux — the same `make ci-<job>` targets, in the same order, with the
  same asserts. The only divergence is the **engine matrix**: Linux builds/tests the
  container engine images it supports; macOS installs/tests the native-Metal engines it
  supports (issue #114 — Metal cannot run in a container). At the end each OS runs
  `make install` **for each engine it supports, in that engine's own environment** and
  proves it works (Linux in CI: the container engine answers "hi"; macOS on an
  Apple-Silicon host: the native engine serves on Metal and answers "hi"). No engine is built or tested on the wrong platform,
  and no supported engine is skipped.
- **Every make command runs its corresponding Python script (issue #120):** each top-level
  `make` target is a thin shell entrypoint that runs a Python script in `scripts/` (install,
  engine skills, launch/tune/health, CI). The same script runs on both OSes — inside the
  docker test image on Linux, inside the 3.11 venv (and natively for Metal) on macOS. There
  is no hidden `_install` internal command API.
- **bash 5 is the recipe shell on both OSes (issue #120):** the Makefile resolves `SHELL`
  to brew's bash on macOS (bash 5) and `/bin/bash` on Linux (also bash 5). `make bash-check`
  — a prerequisite of `install`, every `ci-*` target, `loop` and `chained` — installs bash
  via `brew install bash` on macOS when it is missing and fails closed if the recipe shell
  is not bash 5, so no stage ever runs under macOS's system bash 3.2. The Makefile exports
  that shell as `LLGENIE_BASH`, and `engine_runner` / `engine_smoke` run their `bash -c`
  under it — a bare `bash` on the macOS CI runner is `/bin/bash` 3.2, invoked as a login
  shell, which drops the 3.11 venv from PATH. The readiness fixture is
  `scripts/loopback_server.py`, not `python3 -m http.server`: on the macOS 15 runner
  that module calls `socket.getfqdn()` between bind and listen, and the lookup stalls
  ~35s, so a 30s probe reports the server dead while it is still alive. The check
  lives in `scripts/check_bash.py` (single source of truth).
- **No CI job or step is skipped:** each OS has its own pipeline file, and nothing carries a
  `runner.os` / matrix / event condition. OS- and matrix-specific work is decided in make:
  `make ci-free-disk` frees disk on a Linux runner and only reports on macOS, and
  `make test-engine-stage TEST=serve|detect` is the one post-build test step of every engine
  image (serve: `make test-engine-image` first, so the binary must answer its flags, then
  `make test-engine`; detect: `make test-engine-image` only). Every cell therefore has its
  binary executed and probed, whether it serves a model on the runner or not. The engine images are
  built once (Linux containers), then `published.yml` (`make ci-engines BACKEND=<b>` ->
  `make test-install-published` per backend) installs them on Linux in every **push** run (macOS
  never runs an engine container, so it has no published-image stage).
  The four `install-published-{cpu,cuda,rocm,vulkan}` rows run only when that run actually **pushed an
  image** (issue #844): `scripts/engine_matrix_pushed.py` answers one question — push event AND at
  least one real (non-`none`) engine row — `engine-matrix` publishes it as the `pushed` output, and
  `linux-published` passes it to `published.yml`, whose matrix resolves to the single `none`
  placeholder row instead of the four. A `pull_request` never publishes, so on a PR these rows are
  skipped **by the row, not by the job**: every check name still reports, and the row's first step says
  `install-published-none: SKIPPED - no image pushed in this run`. That is why a green
  `install-published-*` means "this run's image installs" rather than "the registry still works".
- **One engine stage, the only per-OS row (issue #120):** `make ci-engines BACKEND=<b>`
  (`scripts/ci_engines.py`). `BACKEND=cpu|cuda|rocm|vulkan` runs `make test-install-published`
  (container engines, CI `linux-published`); `BACKEND=metal` (Apple-Silicon host only, no CI job) runs
  `make test-native-engines` — `make install`'s path for EACH native-Metal engine (litert, mlx,
  ollama, tensorfold): skill install at the pin, start-script version, a tiny model served on
  Metal answering "hi" — plus `test-native-engine`, `test-interactive-tensorfold-ci` and
  `test-native-engine-light`. Every stage runs; any failure fails it.
- **Python 3.11 everywhere (issue #120):** the test image and the lockfile image are
  `python:3.11-slim`; the gguf venv is created with Python 3.11 (`scripts/check_python.py`,
  which `brew install`s python@3.11 on macOS when missing, and on Linux auto-provisions
  it via `uv python install 3.11` when `uv` is on PATH — or finds a uv-managed 3.11 even
  when it is not on PATH; a non-3.11 venv is recreated).
  `make test-install-ci` ends with `make test-uninstalled` (no installed file, no engine
  container left). make install picks this host's images by itself: on a Mac the cpu
  images (linux/amd64, run through Rosetta), and llgenie offers only trending models whose
  engine has an image for this host.
- **CI** (`.github/workflows/ci.yml`) triggers on a `pull_request` against `main` and on a
  `push` to `main`; it is the hub, and calls the reusable `pipeline.yml` once per OS
  (`linux`, `macos-15-intel`), which runs each stage as its own **parallel** job: `lint`,
  `unit`, `install`, `openspec`, `cpu-health`, ... Every job is a `make ci-<job>` command, so
  CI == your local loop.

### PR fix-bot & the agent (Hermes) image (issues #222, #238)

The Hermes agent image is what repairs a red PR in CI, so it gets its own publish path
instead of riding the test/openspec images:

```
make agent-image        # pull ghcr.io/<registry>/llgenie/agent:latest, else build it here
make agent-image-pull   # CI: pull that :latest tag as llgenie/agent:latest; fails when missing, never builds
make agent-image-ref    # print the GHCR :latest ref every agent pull uses
make publish-agent-image  # build + push the agent image (linux/amd64) when its hash is not there yet, and point :latest at that hash either way
```

`publish-agent-image.yml` is `workflow_dispatch`-only, re-checks that the actor is the
owner/a collaborator with write before any secret is read, and pushes with `secrets.GITHUB_TOKEN`
plus `packages: write` — the same credential, account and shape `.github/workflows/ci.yml`'s
`ci-images` job publishes `llgenie/test` and `llgenie/openspec` with (issue #413: the owner PAT it
used before carries no `write:packages`, so its own `agent-image-push-check` refused it with
`403 DENIED … does not match expected scopes`). It is `linux/amd64` only: building Hermes under arm64
emulation times out. The content hash stays the immutable tag. A re-run does not rebuild when that hash is already on GHCR, and it still points `:latest` at the hash. Pulls use `:latest`.

The fix-bot (`fix-bot.yml`: hourly `schedule` + `workflow_dispatch`) repairs the branch,
re-checks and stops — it **never merges**; a human reviews the result:

```
make fix-bot-sweep      # which red PR deserves the bot, then dispatch it (DRY=1 previews; needs gh)
make fix-bot-resolve    # a failed run -> its PR for the sweep; an EMPTY `number=` means nothing to repair
                        # (a PR that already merged), never a red run — the merge gate's auto-merge-resolve
                        # keeps failing loudly on the same answer (issue #629)
make fix-loop           # run the loop locally against the failing check (scripts/fix_loop.sh; needs an agent on PATH)
make fix-loop-image     # the same loop inside the agent image (AGENT_IMAGE= overrides the ref, LOG=path tees)
make fix-bot-report     # render the loop's failure report (REPORT=<path>) — the comment the workflow posts
```

The loop runs the failing check, hands the failure to Hermes and re-checks, up to
`FIX_ROUNDS` (default 3). The loop itself never commits or pushes; the workflow pushes
the repaired tree as ONE commit with the owner PAT (so CI re-runs) only when the loop
ends green.

### Documentation is part of the change (issue #257)

A change is not done until the docs the user reads describe it. Two rules, both
enforced in `ci-unit` by `make check-docs` (`scripts/check_docs.py`):

1. **Every user-facing make target is documented here, in the same change.** A target
   that `make help` prints (its recipe carries a `##`) must be named in this README —
   whole-token, so `docs-report` does not document `docs`, and a pattern target
   (`run-engine-%`) is documented by its stem. A target that deliberately stays out of
   the README is recorded in `tests/fixtures/docs-exceptions.json` with a reason, a
   date and the issue; `make check-docs` fails when that record goes STALE (the README
   documents it after all) so the file cannot rot.
2. **Every `agent-wiki/` work record references the issue or PR it implements** (`#<n>`).
   A work record that names no issue is unfalsifiable, and `make check-docs` fails it.

The same applies to a workflow, feature, stage or behaviour change: mirror it in the
README's matching section and update the `agent-wiki/` entry in the same commit, before
the PR is ready. `make check-docs` catches a target the README never learned about;
the reviewer reads the rest. `make docs-report` shows the whole picture (documented,
missing, recorded exceptions, and each work record's references).

### Every PR and commit message states the issue, the fix and the benefit (issue #313)

A commit and a PR are read on their own — by a reviewer, by `git log`, by a `git bisect`. They must
therefore carry, in their own text, **what the issue was**, **how the change solves it** and **what
the benefit is**, plus a **technical** extension (the files, targets, tests and gates the change
touches, and any measured number that proves it). A subject-only commit or an empty PR body fails a
reviewer exactly as an empty one does, so neither is allowed.

- The **subject** is a typed Conventional Commit (`type(scope): summary`); it indexes the change, it
  does not explain it.
- The **body** carries the three labelled parts — `Issue:` (with `#N`), `Fix:`, `Benefit:` — then
  `Technical:`. A PR body ends with `closes #<issue id>`.
- Never `-m "update"` / `-m "fix"` / `-m ""`, and never a PR opened with no `--body`, `--body ""` or
  `--body "-"`.

`make check-pr-hygiene` (`scripts/check_pr_hygiene.py`, in the `ci-unit` job) is the gate: it reads
every producer the repository owns — the `.github/workflows/*.yml` steps, the `Makefile`, and
`scripts/**` (both shell invocations and the argv list the `_gh` helper builds) — and fails on a
commit that has no message, a placeholder message, a subject that is not a typed Conventional Commit
or no body; on a PR opened with no body or a placeholder body; and on an `AGENTS.md` that no longer
carries the mandate section. `make pr-hygiene-report` prints every producer it reads and the verdict,
so the guard's scope is visible rather than assumed.

The in-repo producers follow the same rule: `engine-bump.yml`, `issue-bot.yml` and `registry-sync.yml`
build their commit message (and PR body) as a subject plus the `Issue:`/`Fix:`/`Benefit:`/`Technical:`
body, so a bot's commit reads like a human's.

### Every issue body carries the goal, then the technical solution (issue #745)

An issue is the root of the pipeline — issue → branch → OpenSpec change → code → PR → `closes #n` —
so its body is read by someone who was not in the run that filed it. Every issue this repository
files carries six sections, in this order: `## Problem`, `## Why it matters`, `## How we fix it`,
`## Benefit`, `## Acceptance criteria` (each a `- [ ]` item), then `## Technical` last. `## Not
covered` is optional and sits between the acceptance criteria and `Technical`.

One renderer spells them: `scripts/issue_body.py::render`. Every producer that files an issue renders
through it — `security_issues`, `code_review`, `run_failure_reactor`, `engine_skill_gap`,
`registry_change_issue`, `architecture_bot`, `queued_run_alarm` — and each keeps its own dedupe marker
as the body's first line, so a re-run updates the issue instead of filing a duplicate. The
`issue-triage` and `issue-refiner` legs restate a human-written issue in the same six sections.

`make check-issue-bodies` (`scripts/check_issue_body.py`, in the `ci-unit` job and classified in
`scripts/issue_bot_gates.py`) is the gate: it fails on a producer that hand-builds a body, on a rendered body
missing a section / out of order / with `## Technical` anywhere but last, on `## Acceptance criteria`
with no `- [ ]` item, on an `AGENTS.md` that lost the section, and on an issue skill that no longer
states the shape. `make issue-bodies-report` prints every producer, whether it renders through the
seam, and the verdict.

### A PR's commits are authored through an allowed email — no one else (issue #345)

A commit's author is the attribution every reader trusts — `git log`, `git blame` and `git bisect`
all answer "who wrote this" from it. Only two identity **addresses** may author a PR's commits:

```
andy.holst@protonmail.com
support@docondee.com
```

The **email is the gate**, and the display name is informational: GitHub's squash of a PR commit writes the
name from the account **profile**, not the committer, so `Andy <andy.holst@protonmail.com>`,
`andyholst <andy.holst@protonmail.com>` and `Mr. Asimov <support@docondee.com>` are the same two people and
all pass (issue #840 — rewriting history to satisfy a field the committer cannot set is the wrong fix). A
commit authored at a **foreign address** fails whatever the name says — `Andy Holst <someone@else.example>` —
and `github-actions[bot]`, `Hermes Agent` and `llgenie fix-bot` fail because their addresses are outside the
allowlist. A `Co-authored-by:` trailer naming an off-allowlist address fails too. The repository's own
**producers** are held to the stricter name-and-address pair, because a workflow author types `user.name` by
hand and so can control it.

`make check-pr-authors` (`scripts/check_pr_authors.py`, in the `ci-unit` job) is the gate. It reads
the commits a PR **adds** (`git rev-list --no-merges <base>..<head>`, default `origin/main..HEAD`):

- a **merge commit** is skipped — its author is the merge machinery, not the PR's — which is why the
  merge commit GitHub writes on `main` (authored `GitHub <noreply@github.com>`) never trips it;
- a commit already **reachable from the base branch** is someone else's landed work, so history on
  `main` is out of scope;
- every `Co-authored-by:` trailer in every commit is read, under its own finding key;
- the repository's own **producers** are read too — a workflow that stamps a literal off-allowlist
  identity fails, which is why `fix-bot.yml`, `issue-bot.yml`, `rebase-bot.yml`, `engine-bump.yml`,
  `engine-bump-rebase.yml` and `registry-sync.yml` commit as `Asimov Agent` (their push/PR still use
  `BUMP_TOKEN`, so the PR is opened by a real account and CI starts — issue #136);
- `AGENTS.md` must still carry the rule, so deleting it is a red gate rather than a silent edit.

`make pr-authors-report` prints every commit in the range with its verdict and the identity each
producer assigns. `PR_BASE` / `PR_HEAD` bound the range (`ci-unit` runs it with no range on a push to
`main`, where the static half still applies). A branch that is already off the allowlist is fixed with
`git config user.name "Andy Holst"` / `git config user.email andy.holst@protonmail.com`, then
`git rebase --reset-author` and a `--force-with-lease` push to its own PR branch.

### Which token makes which write (issue #412)

A bot step writes with the credential that can actually make the write:

| the step does | the token | why |
|---|---|---|
| comments on / labels an **issue** (refiner claim + verdict, issue-bot verdict, reactor, alarm) | `${{ github.token }}` | the job already declares `issues: write`; the owner PAT carries no Issues write, which is why `issue-refiner` was red on **every** run (`Resource not accessible by personal access token (addComment)`) |
| **dispatches** another workflow (fix-bot sweep, reactor) | `${{ github.token }}` | the job declares `actions: write`; the PAT is refused `403 … /dispatches` |
| **pushes** a branch / opens a PR | `secrets.BUMP_TOKEN` | a `github.token` push does not re-trigger CI (issue #136) |

`tests/test_bot_write_tokens.py` locks the split: it reads each workflow's writing steps, asserts the
step's `GH_TOKEN`, and that the job declares the permission the write needs. A push is checked against
the PAT wherever the job carries it (step env, job env, or the `actions/checkout` token that `git push`
actually uses).

### Every workflow file is validated before it can merge (issue #330)

GitHub **refuses a whole workflow file** whose `${{ ... }}` expression it cannot parse, and the refusal
is silent: the run arrives `status=completed`, `conclusion=failure`, with **zero jobs**, a `name` equal
to the file path, and no log at all. `engine-bump-rebase.yml` shipped exactly that for four pushes on
`main`, because of one comment inside the `rebase` job's `run: |` block:

```yaml
        run: |
          # folded into one `${{ ... }}` so the mode this run took is readable in the log.
```

A `#` line inside a `run:` block scalar is **script text, not a YAML comment**, so GitHub evaluated the
expression in it, could not parse `...`, and refused the file. `yaml.safe_load` accepts it — PyYAML has
no notion of `${{ }}` — which is why nothing caught it.

`make check-workflows` (`scripts/check_workflows.py`, in the `ci-unit` job) is the gate, and it reads
**every YAML file in the repository**, not only the workflows:

1. every `${{ ... }}` in a file must parse (a real recursive-descent parser over GitHub's expression
   grammar, so the expressions this repo already uses are not false positives);
2. every YAML file must end with a newline (the repository's linefeed lint spec);
3. every `.github/workflows/*.yml` must declare a top-level `name:` — a missing name is what makes a run
   present itself as a file path, indistinguishable from a startup failure in `gh run list`;
4. an `on.workflow_run` trigger must carry a `workflows:` list. GitHub **requires** it and refuses the
   whole file without it (`Invalid workflow file: on.workflow_run does not reference any workflows`),
   just as silent: a 0-job run whose `name` is the file path and with no log. Measured on
   `run-failure-reactor.yml`, whose first two push runs were refused that way while this gate passed;
5. the roster must be TRUE (issue #349). GitHub matches `workflow_run.workflows` against a workflow's
   top-level `name:` **verbatim** and takes no wildcard, so the list is a hand-kept roster that rots
   silently: a workflow added later is never watched, and one whose `name:` is edited stops matching.
   So a listed name that is no workflow's `name:` is a violation, a workflow no roster names is a
   violation unless `tests/fixtures/workflow-run-exemptions.json` records **why** (a `reason` is
   required, and an entry naming no workflow is reported STALE), and a workflow may not name itself —
   that would re-fire on its own completion. Measured on `rebase-bot.yml`: renamed by #463
   (`…ONE PR per run…` -> `…every eligible PR per run…`), after which every rebase-bot failure routed
   nowhere while the roster still looked complete.

`make workflows-report` prints the file count, how many expressions were validated and the verdict, so
the gate's scope is visible rather than assumed. `tests/test_workflows_valid.py` (in `make test-unit`, so
it runs under `ci.yml`) pins each rule and adds the check only a YAML library can make — a strict parse
with **no duplicate keys**, which GitHub also refuses and PyYAML hides (last key wins).

### No-fallback rule

The repo has **one** code path per resource, running through the same container
on CI and locally. In particular the model download always uses the official
`hf`(huggingface_hub) CLI (bundled in the test image) — never a `requests`/
`urllib` fallback.

### Local GPU (Metal) verification is mandatory

CI exercises only the **CPU** path (bare runners, no GPU). Before reporting a
change that touches the launcher/health/serving as done, you must also run the
health check against the **host GPU (Metal)** via `~/bin/llgenie` with the
`Qwen/8GB` model and record the reply.

---

## Who may start a bot or publish (the trigger guard)

Every workflow a human can dispatch with `Run workflow` — the four bots, the engine bump + rebase, the
registry sync, the code review, the queued-run alarm and the agent-image publish — starts with the **same
`guard`** job: it refuses anyone who is not the repo owner, the repository's **own bot**, or a collaborator
with **write** access, and it checks **both** `github.actor` and `github.triggering_actor` (the actor who
started it, so a re-run by someone else is re-checked too). `github-actions[bot]` is an App login and never
a collaborator — the permission read answers `none` — so it is admitted **only** when the run's
`HEAD_REPO` (`github.event.pull_request.head.repo.full_name`) is this repository: a same-repo head can only
be produced by a token with write access, while the bot as the actor of a **foreign** head (a bot comment on
a stranger's fork PR) is still refused, as is a bot actor on a non-PR event with no head at all (issue #510
— the architecture bot's own PR #495 was refused by this, run `39650944430`). The refusal is the step's non-zero exit, and every job that touches a
secret, a branch or GHCR needs the guard, directly or transitively. GitHub itself already refuses
`workflow_dispatch` from a user without write access; the guard is the second line, and it is what covers
the paths that are not a dispatch (`issues: [labeled]`, a fork-side run). `ci.yml` carries the guard for the
publish jobs that run on `pull_request`/`push`. `tests/test_workflow_guards.py` holds all of it to one
shape: an any-collaborator `curl` check, an actor-only check, a guard nothing depends on, or a declared
guard output nobody reads (issue #295) all fail `make test-unit` — and it **runs** the real guard script
under bash against a real fake `gh`, so the bot allowance (same-repo head yes, foreign or missing head no)
is executed rather than read off the YAML (issue #510). The guard is the same step — name, `env`
and script — byte-for-byte in all eleven places, so a fix to the rule cannot miss a copy of it. The
accepted **permission set** is read from the guard's own `case` arm, not matched as substrings, so an arm
that also accepts `read`/`triage` (or a bare `*`) fails the suite and names the workflow (issue #306).

## How the bots stay out of each other's way

Four bots (`issue-bot`, `issue-refiner`, `fix-bot`, `rebase-bot`) write to the same issues and PR
branches, so each one announces what it is doing **on the subject itself** and reads the thread
before it picks anything:

    <!-- bot-claim: refiner 2026-10-14T22:10:03Z refine ttl=180m run=123456 -->
    <!-- bot-done:  refiner 2026-10-14T22:41:55Z refined -->

- A bot claims the issue/PR first — one comment, **before** its first mutation, so a sibling can see
  it in time.
- **A recent comment that has not been concluded by a `done` comment means someone is on the
  subject**, so the run *skips it and takes the next one in the list* — it never stands down for the
  whole run. That is why the schedules are not the race protection.
- **The marker carries the terms the reader applies** (issue #292): `ttl=<minutes>m` is the writer's
  own window (the same number the human sentence names it with), and `run=<id>` is the run holding
  it. A reader honours the announced `ttl` — its own default is only the fallback for a marker
  written before that field existed — so a 30-minute rebase no longer blocks a 4-hour repair.
- **A run that is over releases its claim immediately** (issue #291): the reader asks GitHub about
  `run=<id>` and, when that run is finished or cancelled, takes the subject and prints why. An
  unreadable run state is *unknown*, which never releases a claim.
- A `done` marker releases it, and **it says which kind of done**: `refined`, `closed`, `merged`,
  `cancelled` and `repaired` release the subject, while **`pr-open` keeps occupying it** — implemented
  but not yet approved must not be implemented a second time.
- `make test-unit` runs the rule (`tests/test_bot_claims.py`, `tests/test_issue_refiner.py`,
  `tests/test_issue_implementer.py`, `tests/test_fix_bot_sweep.py`, `tests/test_rebase_bot_sweep.py`);
  `scripts/bot_claims.py` is shared **byte-identically** by all four bots, so whoever merges first
  makes the other three no-ops.

## The dry-run retry bound (`--dry` in the PR-blocking `top-tier` job)

The `--dry` acceptance cases (`make test-top-tier-cli-ci`, run by `make ci-top-tier`
from the `top-tier` job in `.github/workflows/pipeline.yml`) talk to the **live** Hub,
so a slow read used to decide a PR's `macos / top-tier` and `linux / top-tier` result
(run 39381961586: the same tree failed `TimeoutError: The read operation timed out`,
then passed on an unchanged re-run). Those cases now shell out through
`tests/top_tier_dry_run.py::run_dry_run`, which retries the whole dry run **once**
(`TOP_TIER_DRY_RUN_ATTEMPTS = 2`, the run plus one retry) when it failed on the Hub's
transport — the CLI's `[ERROR] HF API still failing after N attempts` line,
`TimeoutError`, `URLError`, connection resets/errors, `SSLError`, resolution failures,
or a transient 429/502/503/504. Inside the process, `_hf_get` already retries a
read-phase timeout on `HF_GET_MAX_ATTEMPTS` (issue #549), so the job's conclusion rests
on a stated number of attempts instead of on one read at one minute.

A failure that is **not** the Hub's transport (a bad argument, a bug in the discovery
code) is returned on the first attempt — a regression is never retried into a green. A
Hub that stays unreachable spends the bound and still exits non-zero with the CLI's
named cause: the case fails loudly, it is never skipped and never softened. The seam is
locked by `tests/test_top_tier_dry_run_retry.py` (real child processes, no mocked
subprocess) inside `make test-unit` (issue #399).

**A slow child is a transport failure too (issue #676).** The `subprocess.run(timeout=…)`
used to sit outside that seam, so a dry run that outlived its deadline raised
`TimeoutExpired` straight out of `run_dry_run`: no retry, and the caller saw a traceback
instead of a cause — measured twice in PR #661's `macos / top-tier` job (`timed out after
780 seconds`, on changes that never touch the dry run; the same case takes 237 s on a
developer host). A timeout is now converted to exit 124 with `timed out after <n> seconds`
in stderr, retried within the same bound, and named at the bound instead of escaping. The
`top-tier` job's ceiling went 60 → 90 minutes so one full retry fits above the measured
38-minute macOS stage.

---

### Preflight

`make bot-preflight` fetches `origin/main`, fast-forwards a clean behind checkout and writes `preflight.txt` — the `origin/main` commit, `AGENTS.md`'s bytes, lines and heading digest, and the `AGENTS: <sha> <bytes>b <lines>l` line a bot PR body must carry (issue #792). A dirty or diverged checkout is refused with its paths; the target never rebases. `CHECK=1` re-derives the record and fails when the file on disk disagrees with the tree.
