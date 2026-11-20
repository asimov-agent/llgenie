# Proposal: agents-md-task-pacing

## Why

Two owner-mandated behaviors are missing from `AGENTS.md`, the instruction file every agent session reads first. (a) The host-side pacing mandate (restated 2026-11-20, issue #2956) — work one issue/PR at a time, never foreground-wait on a CI pipeline, set the wait as a background watching task, move to the next issue while CI runs — lives only in private agent notes. (b) The #2526 start-surface gate rule (owner/collaborator/bot trigger rules machine-checked by `make check-workflows`, R1/R2/R3) is enforced by CI and documented in `docs/BOTS.md`, but its AGENTS.md bullet was the approval-blocked half of #2526, filed as #2527. The owner approved both protected-file edits (2026-11-20); this lane carries them as one documentation-only change.

## What Changes

- `AGENTS.md` gains a new section "Host-side task pacing (MANDATORY, durable)", placed immediately after the "Git workflow — feature branch + PR (MANDATORY)" section, stating the four behaviors: one issue/PR at a time; a pushed lane's CI run is never awaited in the foreground; the wait is a background watching task with a completion notification; the agent starts the next issue immediately and re-polls the board until every PR is green and armed. (closes #2956)
- `AGENTS.md` §"Every workflow file is validated before it can merge" gains the #2526 gate bullet: start-surface classification per file; R1 explicit top-level `permissions:` (`write-all` refused); R2 `pull_request_target` ban; R3 the `github.triggering_actor` guard outside `run:` script text on every outsider-reachable trigger, or a fixed-point transitive derivation through a `workflow_run` roster (cycles are not trust); internal-only triggers platform-restricted, no guard; zero-exemption fleet state named. Wording matches the `docs/BOTS.md` #2526 paragraph. (closes #2527)
- Documentation mirrors: dated `agent-wiki/` entry + `docs/changes.d/` fragment + `make changes-index` row, referencing #2956, #2527 and the PR.
- No code, no workflow changes.

## Impact

- Affected specs: `host-task-pacing` (new capability)
- Affected code: `AGENTS.md` (protected agent-instruction file; owner chat approvals of 2026-11-20 are the consent for both additions)
- Affected docs: `agent-wiki/`, `docs/changes.d/`, `docs/CHANGES.md` (generated)
