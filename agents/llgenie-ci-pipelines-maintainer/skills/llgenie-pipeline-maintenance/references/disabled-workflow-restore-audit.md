# Auditing `disabled_manually` workflows and the #902 bot-restore

An "empty queue" own-domain audit often lands on workflows reported `disabled_manually`.
`disabled_manually` is API-only — `gh workflow list` sees it, the tree does not — so the
audit is a wire measurement cross-checked against the recorded decision, never a tree read.

## Procedure

1. **Read the recorded decision first.** `bots/pause.toml` is the source of truth for WHY a
   workflow is paused and WHAT restores it (`paused` list + `paused_utc`, `never_pause`,
   `restore_first`/`restore_after`, and the `[restore]` health condition N/K/L). Its own rule:
   *a workflow the API reports `disabled_manually` that is NOT in `paused` is a silent break,
   not a decision.* Also read the `docs/changes.d/*bots-pause*` note — the pause being
   "recorded" usually invalidates any "un-tracked quiet period" premise on the issue.
2. **Measure live state per workflow** (do not trust a count from a stale scan):
   ```
   for wf in $(list from pause.toml paused); do
     gh api repos/<owner>/<repo>/actions/workflows/$wf.yml --jq '.state'
   done
   ```
   Classify each `active` vs `disabled_manually`. Any disabled-and-not-in-`paused` → silent break.
3. **Check the restore ORDER, not just the count.** `bots/pause.toml` encodes
   `restore_first` (cheap common bots, wake the board early) BEFORE `restore_after` (heaviest,
   last so they cannot re-saturate a just-drained queue). A partial restore that has
   `restore_after` members `active` while `restore_first` members are still `disabled_manually`
   is **out of order** = a stale/partial restore finding, even though every individual state is
   "documented". This is the failure mode a bare disabled-count audit misses.
4. **Measure the restore GATE before calling a pause stale.** The #902 condition is queue health:
   queued `pull_request` runs reaching `in_progress` within L minutes, N readings K apart. Cheap
   proxy on the wire — for the most recent PR runs, compare a job's `created_at` to `started_at`:
   ```
   gh api "repos/<o>/<r>/actions/runs?event=pull_request&per_page=5" --jq '.workflow_runs[].id'
   gh api repos/<o>/<r>/actions/runs/$rid/jobs \
     --jq '.jobs[]|select(.status=="in_progress")|"\(.created_at[11:19]) -> \(.started_at[11:19])"'
   ```
   Jobs starting ~seconds after creation and runs completing in <2 min = healthy = the restore
   gate is MET, so remaining disables are stale. A real backlog (queued > L min) = pause still valid.
5. **Before declaring "clean re-audit", quantify the uncovered queue.** Count open
   `agent:implement` issues (`gh api .../issues?state=open&labels=agent:implement`): if the
   disabled bots (issue-bot, issue-refiner, fix-bot, run-failure-reactor, …) are the ones that
   dispatch/refine/repair that queue, a healthy gate + still-disabled bots + a large open queue
   is a finding, not a clean record.

## Deliverable shapes

- **Intended & fully restored** → a one-line "re-audited at <sha>, no findings" record.
- **Intended but stale/partial/out-of-order restore** → a six-section `agent:implement` finding
  issue: Problem, Why it matters, How we fix it (name every still-disabled workflow and the
  exact re-enable order), Benefit, Acceptance criteria (each workflow reaches `active` on the
  wire; `make bots-restore-health CMD=measure` passes with the fleet back on; a
  `docs/changes.d/` row), Not covered (implementation routes through the normal queue — this
  lane files the finding, it does not fix it).

## Tooling pitfalls

- **`cd <path> && …` in a persisted shell can silently no-op the real command.** A pinned cwd
  that points at a removed worktree makes every `cd` fail and short-circuits the `&&` chain, so
  the probe you meant to run never ran. Pass the terminal tool's `workdir=` parameter instead of
  relying on a persisted `cd`, and re-`pwd`/`git rev-parse --short HEAD` before trusting output.
- **Do not run `make <target>` in a stale worktree.** A target added by a recent change
  (`make bots-restore-health` from #902) is absent in an old checkout and reports
  `No rule to make target`. Measure the wire directly, or run from a worktree at the live head.
- **jq: keep field access inside the object, not the array constructor.** `.[]|[.id,.head_sha|.[0:7]]`
  parses `.[0:7]` against the whole array and dies `expected an array but got: number`;.
  Slice inside parens per field: `.[]|"\(.id) \(.head_sha[0:7])"`.
