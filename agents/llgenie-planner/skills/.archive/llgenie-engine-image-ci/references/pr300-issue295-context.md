# PR #300 / Issue #295 — the trigger-guard change (metadata + linkage)

Reference for the work this skill's "Trigger guards drift" and "Changing a workflow's guard/token shape"
sections came from. SKILL.md is at its 100k character ceiling and cannot hold this, so it lives here.

## The linkage

| artifact | value |
|---|---|
| Issue | **#295** — "ci(bots): every dispatchable workflow must carry the same trigger guard (queued-alarm has none, four guards accept any collaborator)" |
| Issue origin | #122 (the guard's original rule) |
| PR | **#300** — "ci(bots): one write-level trigger guard for every dispatchable workflow (#295)" |
| PR base | `main@29080c7` |
| Branch | `fix/workflow-guards` (pushed to `fork`, PR to `origin` — this clone's remotes are inverted) |
| Final head | `20150b6` |
| Merge commit | **`08f585f`** — `ci(bots): one write-level trigger guard for every dispatchable workflow (#295) (#300)` |
| Merged at | 2026-10-16T00:13:55Z |
| Issue outcome | #295 CLOSED / COMPLETED at 2026-10-16T00:13:56Z (closed by the merge) |
| Filed during review | **#306** — the write-level test passes a guard that accepts `read`/`triage` (still OPEN) |
| Explicitly out of scope | **#254** (the `macos-15-intel` queue) — repo-settings/hosted-runner decision |
| OpenSpec change | `openspec/changes/workflow-guards/` (proposal + `specs/workflow-guards/spec.md` + `tasks.md`) |
| Wiki entry | `agent-wiki/2026-10-15-workflow-guards.md` |

Both directions were linked: the PR body carried `Closes #295`, and #295's body was updated with a dated
"Status 2026-10-16 — implemented in #300" block (the original audit kept below it as history). #306 was
cross-linked from the PR's "Not covered" section.

## What #300 changed (20 files)

One guard step — `name:`, `env:`, `run:` — byte-identical across **11** guard sites: the ten
`workflow_dispatch` workflows (in fix-bot the guard is a step inside its dispatch-only `fix` job) plus
`ci.yml`. `.permission` for `github.actor` **and** `github.triggering_actor`, accepting exactly
`admin|maintain|write`, refusal = the step's non-zero exit. Each guard uses the run's own `github.token`
(never the job-level `BUMP_TOKEN` PAT). `queued-alarm.yml` gained the `guard` job (`alarm` needs it);
`ci.yml`'s dead `outputs.allowed` was removed. `tests/test_workflow_guards.py` pins all six rules, wired
into `make test-unit`.

## Verification that was reported

- `tests/test_workflow_guards.py`: **6 passed** on the branch; **5 failed, 1 passed** against the pre-fix
  workflows (`git show origin/main:…`) — a test that passes on both trees would prove nothing.
- 198 passed across the guard + dispatch-form + bot-isolation + time-budget + reviewer + wiring + claims +
  concurrency suites.
- `make lint` / `check-docs` (145 targets, 58 wiki entries) / `check-wiring` (122 documents) /
  `check-dispatch-forms` (10 workflows) / `openspec-validate NAME=workflow-guards` all exit 0.

## The first-run red (why the PR needed a second push)

`linux / unit` + `macos / unit` failed on two tests that pinned the OLD guard mechanism —
`test_engine_bump_rebase.py::TestWorkflowYaml::test_guard_sends_the_default_token_variable` and
`test_engine_bump.py::test_guard_keeps_default_token`. Both now assert the `gh api` + default-token shape.
See the SKILL.md section "Changing a workflow's guard/token shape turns MAIN's tests red".

## Post-merge note

`engine-bump-rebase.yml` runs with `event=push`, zero jobs, and the workflow's FILE PATH as the run name on
every push to `main` — including the #300 merge commit itself. That is **not** caused by #300: the file
carries only `schedule` + `workflow_dispatch` and is valid. It is tracked as **#318**, and it predates the
merge (first seen on `a6ec098`). Do not attribute it to the guard change.

## Related reference files

- `references/bot-container-supervision.md` — the bot container's nerve/JEV supervision, moved out of
  SKILL.md when this change pushed it against the size ceiling.
- `references/bot-fleet-mutual-exclusion.md` — the two-axis mutual-exclusion audit for a bot fleet,
  likewise moved out of SKILL.md.
- `references/workflow-trigger-guards.md` — the guard audit procedure these findings came from.
- `references/worktree-cleanup-root-owned.md` — the root-owned `__pycache__` trap hit when removing
  this PR's worktree after the merge.
