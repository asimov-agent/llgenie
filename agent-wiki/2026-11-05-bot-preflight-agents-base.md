# `make bot-preflight` now surfaces the `AGENTS:`/`BASE:` body obligation before a lane pushes (issue #1790)

Every bot PR body must carry the `AGENTS: <sha> <bytes>b <lines>l` line (issue #792) that names the
rulebook its work is measured against, and — since issue #845 — the `BASE: <sha> (== origin/main at
open)` line beside it, recording the main commit the branch was cut from. The only producer of that
pair requirement was the CI gate `make check-pr-agents-line`, which reads the LIVE PR body —
unreachable from a hermetic preflight. So a bot PR could open **green-preflight but red-CI**,
exactly the gap `#1788` measured: it opened with **zero** hygiene lines in its body, passed
`make bot-preflight`, then red'd `check-pr-agents-line` in CI.

## What changed

- `scripts/bot_preflight.py`: a new `agents_base_verdict()` reuses the CI gate's **own**
  `check_pr_hygiene.pr_agents_line_findings` (imported, never restated) over the would-be range and
  a prospective body. `make bot-preflight [BODY=/tmp/body.md]` now:
  - refuses (`exit 1`) when `--body-file` is supplied and the body is missing or mis-citing the
    `AGENTS:`/`BASE:` pair — the lane cannot open a PR its own preflight proves will red; the
    #845 `BASE: == AGENTS:` equality is enforced by the gate itself
    (`check_pr_hygiene.py:564`), so the verdict inherits it;
  - warns loudly (`WARN`, still `exit 0`) when no body is supplied yet on a bot branch — the lane
    hears the obligation before pushing even with no draft;
  - stays silent for a human-only range, mirroring the gate's `is_bot_pr` gating exactly — never
    flagging what CI would not flag.
  - every verdict names issues #792/#845 and the contract location
    `scripts/check_pr_hygiene.py:518`.

The CI gate's own contract is unchanged; this surface only *surfaces* its verdict earlier — the
sibling pattern to the #1782 `Sync:`-line verdict (`sync_line_verdict`).
