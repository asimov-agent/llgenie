# `make bot-preflight` now surfaces the #1724 SYNC-line obligation before a lane pushes (issue #1782)

The owner's propagation rule (#1724) says behaviour-versioned changes (SOUL/skills/rule) landing
under `agents/<profile>/` must be re-synced INTO the live profile (`make sync-agent-profile
PROFILE=<p>`) *and reported* in the PR body as a `SYNC: <p> make sync-agent-profile PROFILE=<p>`
line — so a reviewer can verify propagation happened, not just that a commit did. The only
producer of that rule was the CI gate `make check-pr-sync-line`, which reads the LIVE PR body —
unreachable from a hermetic preflight. So a profile-touching PR opened **green-preflight but
red-CI**: the lane heard nothing at `make bot-preflight` about the SYNC line its body would need.

Measured on three consecutive profile PRs (#1778 / #1779 / #1780 — the engine, security and
pr-reviever lanes): each passed `make bot-preflight` yet failed `check-pr-sync-line` in CI
because the body lacked the `SYNC:` line, burning one `linux/unit` matrix per miss before the
error was visible.

## What changed

- `scripts/bot_preflight.py`: a new `sync_line_verdict()` reuses the CI gate's **own**
  `check_pr_hygiene.pr_sync_line_findings` (imported, never restated) over the would-be range and
  a prospective body. `make bot-preflight [BODY=/tmp/body.md]` now:
  - refuses (`exit 1`) when `--body-file` is supplied and a touched agent profile's `SYNC:` line
    is missing or mis-cited — the lane cannot open a PR its own preflight proves will red;
  - warns loudly (`WARN`, still `exit 0`) when no body is supplied yet on a profile-touching
    branch — the lane hears the obligation before pushing even with no draft;
  - stays silent for a non-profile PR (a derived change) and for a human-only range, mirroring
    the gate's `is_bot_pr` gating exactly — never flagging what CI would not flag.
  - every verdict names issue #1724 and the contract location `scripts/check_pr_hygiene.py:499`.

The CI gate's own contract is unchanged; this surface only *surfaces* its verdict earlier.
