# A bot PR's `AGENTS:`/`BASE:` pair is written by the seam that opens it (issue #2050)

## Why

The `check-pr-agents-line` gate (#792/#845) reads two body lines — `AGENTS: <sha> <bytes>b <lines>l` and
`BASE: <sha> (== origin/main at open)` — and reds a bot PR that lacks them before any substantive CI runs.
The pair was written by a leg that *remembered* `make bot-preflight`; no producer wrote it. Measured
2026-11-07 at `origin/main@cb6c56a9`: five open bot PRs (#1696, #1982, #2039, #2043, #2049) were red on that
gate alone, and a fix-bot repair pass left the body unchanged while its comment claimed
"Pushed as one commit" on #2051 whose head never moved. The stamp is a **control that is not enforced where
it is needed**: at the moment the PR body is composed.

## What changes

- `scripts/bot_preflight.py` gains the write side of the same contract: `stamp_body(text, record)` inserts or
  replaces the pair (flush-left, adjacent, idempotent) and `resolve_record(root, base, refs)` measures the
  rulebook from the first ref that resolves (`origin/main`, then a producer's own `main`) — refusing, never
  guessing, when none does.
- `make bot-stamp-body BODY=<file> [OUT=] [BASE=] [REFS=]` is the ONE seam every producer calls before
  `gh pr create` / `gh pr edit`.
- The producers that compose a bot PR body now stamp at OPEN: `issue_implementer.render_pr_body` /
  `open_pr` (the issue-bot), `engine-bump.yml`, `registry-sync.yml`, `security_bot.py`,
  `security_bumps.py`.
- `fix-bot.yml` re-stamps a repaired PR's body when its branch was synced onto the latest main, and its
  outcome comment only claims a push when the push step actually produced a sha.
- `docs/BOTS.md` records the target and the finding.

## What does not change

`make check-pr-agents-line` is untouched — the gate still holds a bot PR body to a rulebook that is an
ancestor of both head and base. `make bot-preflight` keeps its read side (fetch, fast-forward, warn/refuse
pre-push). No producer is given a weaker path: a checkout that cannot name `main` refuses to open the PR
rather than opening one the gate will red.
