# CI fresh instance is the ground truth on a shared host

Rule: verdicts come from CI's **fresh instance**, never from a lane's local read on the shared host. When llgenie bots run on the same machine, local gate checks are advisory only — the authoritative verdict is the GitHub runner CI run.

## Why (the failure each pass)
- A lane reports green or red from a *local* run (`make ci-lint`, `make check-*`, worktree runs). Its env is shared with other lanes: shared `/tmp` tmpfs, docker/container caches, other worktrees, degraded tool/terminal delivery. Those mask or forge the verdict.
- **#1584**: the doc lane ran `make check-docs` locally in a `/tmp/wt-1580` worktree and mislabeled the scope failure as "infra/starvation" — from degraded local reads — when the CI run's log had a **deterministic** product error: `[change->note] ... adds no agent-wiki note; see issue #1123`. The rerun re-redded byte-identical. Local read ≠ evidence.

## What to do
1. **A verdict is a CI run id + sha**, measured fresh via `gh api`/`gh run view`, from the **`pull_request`** run bound to the current head — not a local command's exit code, not the lane's word, not a `mergeStateStatus` read alone.
2. When a lane reports a red, read the **actual failing job's log line** (`gh run view <id> --log --job <n>`, strip escape codes) *before* accepting any conclusion (product-defect vs infra). A rerun that re-reds on the identical gate is a deterministic product red, not infra — rerunning to "clear the queue" changes nothing (attempt n+1 re-fails).
3. A lane that cannot read its own output (terminal/read relay degraded) must still dispatch the fix; CI's fresh run is what proves it.
4. Document the lane's run bid directionally: "CI will prove it" when called into doubt, and hold bookend until the fresh-instance run lands green at the head.

Local runs stay useful for **targeted** checks (did my edit pass the exact step that redded) but never override or substitute the CI verdict.

## Some pipelines are merge-to-main-only — do not demand a verdict at a PR head

Before dispatching for a pipeline as "the owed verdict", read its trigger surface at the head tree (`git show <head>:.github/workflows/<wf>.yml`). A workflow that names no `pull_request` trigger (`branches: [main]` + schedule + workflow_dispatch, header "never in a pull request") CANNOT run on a PR by design — ci-hf-live (#1002) is exactly this. Demanding its run id or job id at a PR head is an invalid premise that blocks a ready PR (#1642/2026-11-03). Instead: accept the PR-only CI verdict at the head (all `pull_request` runs bound to the head sha), record the deterministic local acceptance evidence (`_acc2.json`-style), and note the main-only pipeline will fire on merge — watch it there, since the live-data gate is often the class that originally redded the issue.
