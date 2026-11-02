# Arm read-back must read both REST and GraphQL (#1600)

## What changed

The lane's own read-back rule in `security-scan-ops/SKILL.md` (*"Arm auto-merge only on a `main`-based
PR, and read `state` before `autoMergeRequest`"*) now requires reading **both** signals before claiming
`armed` or `auto=none`:

- `gh api repos/<o>/<r>/pulls/<n> --jq '.auto_merge.enabled_at'` (REST) **and**
- `gh pr view <n> --json autoMergeRequest --jq '.autoMergeRequest.enabledAt // "NULL"'` (GraphQL identity).

`auto=armed` if **either** is non-null; `auto=none` only when **both** are null. On a true disagreement
(REST null, GraphQL non-null — the review-blocked case) **default to armed and dis-arm**
(`gh pr merge <n> --cancel`), read both back null, then report `auto=none`. Never report `auto=none` on a
lone REST null. Scope note: the shared fleet block in `SOUL.md` is canonical verbatim from
`agents/standing-rules.md` and must NOT carry per-lane read-back detail; the correction lives in the
lane's own skill only.

## Why

REST `pulls/{n}.auto_merge` **omits** `enabled_at` while a PR is blocked on a required review, even though
auto-merge is genuinely armed. Measured on #1599: `gh pr merge 1599 --squash --auto` exit 0 at 14:27:27Z,
REST `enabled_at` NULL the same second, GraphQL `autoMergeRequest.enabledAt=2026-11-02T14:27:27Z` — a lone
REST null read a genuinely-armed, review-gated PR as "not armed", and it merged at 14:29:30Z. This is the
#964/#1247 read-back trap.

## Record

- Issue: #1600 (security, tagged).
- Fix PR: #1601 (targets `agents/llgenie-security/`, closes #1600).
- Measured at the fix head: guard/scope/holds/ci-images/scanner-images/lint/openspec/agents-read/
  cpu-health/install pass. A first version of the fix wrongly edited the canonical SOUL fleet block
  (SOUL.md rule 16 must stay verbatim — red `fleet-block-drift` in `test_agent_profiles`), so it was
  reverted to verbatim; the detail now lives in the lane-owned skill only.
