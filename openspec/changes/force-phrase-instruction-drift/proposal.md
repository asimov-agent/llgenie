# Force-phrase instruction drift — adjudicate every stale `--force-if-includes` teaching and gate the surface

## Why

Issue #2502. Issues #2451 and #2498 established the canonical push rule (recorded in
`agents/standing-rules.md`): a **rebased, squashed, or otherwise rewritten head does NOT contain the
old remote tip, so `--force-if-includes` justifiably REJECTS it — such pushes go through a plain
`--force-with-lease` after a fresh fetch**; `--force-if-includes` is only for amend/integrate pushes
where the remote tip IS an ancestor of the new head. But the agent instruction surface (lane
`SKILL.md`s, `references/`, `prompts/`) still teaches the stale tuple
`--force-with-lease --force-if-includes` as the general rebase/squash vehicle in
**55 hits across 47 files** (re-measured at `8a4bc26df`, the tip after #2498 merged; the
issue-side counts 39 drift + 11 correct-keep were measured at `b2e3b1ec4`, and #2498's own edits
already corrected 4 listed sites on the way in). An agent following the stale text gets a spurious
`(stale info)` rejection mid-PR and then either widens to a bare force or churns a corrupt rerun —
the failure class #2451/#1960/#2498 exist to stop.

## What Changes

- **Adjudicate every hit** (table below — the record required by #2502 AC1): 36 FIX sites get the
  canonical phrasing (flag removed from rebase/squash/general teaching), 10 KEEP-QUALIFIED sites keep
  the flag but carry an explicit ancestor/amend-integrate qualification, 9 KEEP sites already teach
  the rejection correctly and are untouched. The `llgenie-pr-merge-conflict` lane carries the
  canonical #1960 wording and is out of the finding surface by design.
- **Add a repo hygiene test** `tests/test_force_phrase_instruction_surface.py` (discovered by
  `scripts/unit_tests.py`, so `make test-unit` runs it — the issue #393 model): it greps the
  instruction surface (`agents/**/SKILL.md`, `agents/**/references/**`, `agents/**/prompts/**`,
  excluding the `llgenie-pr-merge-conflict` lane) for `--force-if-includes`; every occurrence must
  carry an ancestor/amend/integrate/rejection qualification in-line or within ±2 lines; a documented
  allow-list (`tests/fixtures/force_phrase_allowlist.json`) names exceptions; a planted stale-tuple
  fixture under `tests/fixtures/force_phrase_instruction_surface/` MUST be reported (red proof).
- Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry.

## Adjudication (measured at `8a4bc26df`, 55 hits, 47 files)

| file (under `agents/`) | verdict | hits |
|---|---|---|

| `llgenie-architect › software-development/llgenie-architecture-issue-pass/SKILL.md` | KEEP | kept: :377, :379 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/SKILL.md` | FIX | corrected: :274 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/ci-lint-trailing-newline.md` | KEEP-QUALIFIED | kept, qualified: :40 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/ci-red-triage.md` | KEEP-QUALIFIED | kept, qualified: :50 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/gate-and-own-hygiene-same-vehicle.md` | FIX | corrected: :30 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/issue-1463-change-record-trio.md` | FIX | corrected: :24 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/new-workflow-admission.md` | FIX | corrected: :75; kept, qualified: :71 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/pr-body-gates.md` | KEEP-QUALIFIED | kept, qualified: :32 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/pr-issue-linking-and-force-push.md` | FIX | corrected: :26 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/rebase-directive-lessons.md` | FIX | corrected: :64 |
| `llgenie-ci-pipelines-maintainer › llgenie-pipeline-maintenance/references/stale-head-and-import-root-lessons.md` | FIX | corrected: :13 |
| `llgenie-documentation-maintainer › llgenie-docs-maintainer/references/authoring-and-delivery.md` | KEEP-QUALIFIED | kept, qualified: :91 |
| `llgenie-documentation-maintainer › llgenie-docs-maintainer/references/base-race-rebase-and-metadata.md` | FIX | corrected: :21, :28 |
| `llgenie-documentation-maintainer › llgenie-docs-maintainer/references/live-to-tree-fold-prs.md` | FIX | corrected: :34 |
| `llgenie-engine-improver › llgenie-engine-improver/references/engine-build-proof-dispatch.md` | KEEP | kept: :381 |
| `llgenie-engine-improver › llgenie-engine-improver/references/pr-gate-and-rebase-recovery.md` | FIX | corrected: :158 |
| `llgenie-engine-improver › llgenie-engine-improver/references/pr-hygiene-gates-fix-engines.md` | KEEP-QUALIFIED | kept, qualified: :11 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/SKILL.md` | KEEP | kept: :651 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/agent-profile-pr-body-gates.md` | KEEP-QUALIFIED | kept, qualified: :5 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/commit-author-and-local-gates.md` | KEEP-QUALIFIED | kept, qualified: :23 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/gate-red-triage.md` | FIX | corrected: :95 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/gate-rerun-and-verify.md` | FIX | corrected: :44, :72 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/multi-pr-batch-repair.md` | FIX | corrected: :32 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/open-pr-measurement.md` | KEEP-QUALIFIED | kept, qualified: :253 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/pr-close-mismatch-recovery.md` | FIX | corrected: :171 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/pr-closing-commit-title-and-remotes.md` | FIX | corrected: :17 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/rebase-while-run-in-flight.md` | FIX | corrected: :30 |
| `llgenie-issse-implementer › software-development/llgenie-issue-to-pr/references/squash-to-one-commit.md` | FIX | corrected: :23 |
| `llgenie-planner › prompts/llgenie-orchestrator-tick.md` | FIX | corrected: :249 |
| `llgenie-planner › llgenie-bot-orchestration/SKILL.md` | FIX | corrected: :788 |
| `llgenie-planner › llgenie-bot-orchestration/references/actions-run-attempt-reconciliation.md` | FIX | corrected: :111 |
| `llgenie-planner › llgenie-bot-orchestration/references/auto-merge-approve-and-handle-throttle.md` | FIX | corrected: :112, :128 |
| `llgenie-planner › llgenie-bot-orchestration/references/check-pr-acceptance-writeback-dispatch.md` | FIX | corrected: :37 |
| `llgenie-planner › llgenie-bot-orchestration/references/pipeline-verify-matrix.md` | FIX | corrected: :110 |
| `llgenie-planner › llgenie-bot-orchestration/references/pr-closing-gate.md` | KEEP | kept: :695, :723 |
| `llgenie-planner › llgenie-bot-orchestration/references/rebase-and-merge-mechanics.md` | FIX | corrected: :48 |
| `llgenie-planner › llgenie-bot-orchestration/references/red-triage-lint-in-unit.md` | FIX | corrected: :42 |
| `llgenie-planner › llgenie-bot-orchestration/references/second-gate-stale-base-and-stuck-run.md` | FIX | corrected: :403 |
| `llgenie-planner › llgenie-bot-orchestration/references/verifying-lane-claims.md` | KEEP-QUALIFIED | kept, qualified: :541 |
| `llgenie-planner › llgenie-bot-orchestration/references/worktree-and-push-hygiene.md` | FIX | corrected: :55 |
| `llgenie-pr-reviever › software-development/llgenie-pr-review/references/branch-base-and-rebase.md` | FIX | corrected: :12 |
| `llgenie-security › security-scan-ops/SKILL.md` | FIX | corrected: :320 |
| `llgenie-security › security-scan-ops/references/branch-and-push-hygiene.md` | FIX | corrected: :44 |
| `llgenie-security › security-scan-ops/references/ci-red-read-the-job-log.md` | FIX | corrected: :29 |
| `llgenie-security › security-scan-ops/references/holds-and-publishing.md` | FIX | corrected: :39 |
| `llgenie-tester › llgenie-pr-testing/SKILL.md` | FIX | corrected: :692; kept: :740 |
| `llgenie-tester › llgenie-pr-testing/references/agent-profile-versioning.md` | KEEP | kept: :344, :358 |

## Impact

- Affected lanes (the closing PR carries one `SYNC:` line each): llgenie-ci-pipelines-maintainer,
  llgenie-documentation-maintainer, llgenie-engine-improver, llgenie-issse-implementer, llgenie-planner,
  llgenie-pr-reviever, llgenie-security, llgenie-tester.
- No gate/script changes; the new check is a test (unit-lane discovery).
- Provenance: #2451 (canonical phrase), #2498 (standing-rules wording live), #1960 (measured
  rejection), #393 (discovered unit suite), issue #2502 (this sweep).
