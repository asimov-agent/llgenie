# 2026-11-02 — issue #1590: the planner's failure monitor now covers its own main-branch gate reds

## What changed

One bullet added to the planner's `pr-failure-monitor` reference (a behavior-versioning
surface under `agents/llgenie-planner/`, the #791 contract). The failure sweep now extends
beyond open-PR reds to main/default-branch workflow runs with **no PR attached** — `CI`,
`ci-verdict`, `ci-scope`, `engine-build` at `head_sha == origin/main` — because a red there
is a main-red, not a PR-red, and has no open PR for `gh pr view` to surface. It also teaches
cross-wired verdict-check tracing: a `ci-verdict`/`CI` red on main that evaluates a *different*
run's head is that PR's red projected onto main, not a main-red — quote the real main-head
verdict and trace the false two.

## Why it matters

The owner standing rule (2026-10-30) says to monitor ALL llgenie agents and ALL open PRs, but
the monitor language only covered open PRs. A main-branch red with no PR attached passed
unseen, and a cross-wired verdict check was misattributed as a main red instead of traced to
the PR whose guard actually redded.

## Proof

- The bullet is present verbatim at line 15 of
  `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/pr-failure-monitor.md`
  (after the `Distinguish in_progress from FAILURE` bullet, before the `A red at an open PR is
  a delegation trigger` bullet); no other behavior text changed (+1 line).
- `make bot-preflight` OK; `make check-docs` green with this note + fragment.

Issue: #1590
