# post-#1161 live->tree sync threads the tester skill

Issue #961 (row), carrying the remaining llgenie-tester live→tree delta that #1161 left behind. This sync CLEARS the llgenie-tester rows; it does not close #961 or #1060.

## What was measured

After #1161 merged (as `3dfca701`), the live profile kept moving while the queue was open: `SKILL.md` grew 61,659→62,629 b and `references/agent-profile-versioning.md` grew 13,353→14,461 b. `sync-agent-profile --check` reported `live-longer`/`live-edited-not-tree` on both — the exact drift class #1161's lesson describes. A rebase can surface drift that was NOT there when you started, because **live is edited by other lanes while your PR sits open**; the remedy is to re-take the whole drifted set in ONE amended head, never ship the older tree.

## What changed

Three lessons from this cycle, live→tree byte-for-byte (CHECK 7/7, guard findings naming llgenie-tester = 0, lint rc=0):

1. **Never pad a short sha into a `head_sha=` filter** — the API matches the exact 40-hex string, so a fabricated full sha returns `[]`, which reads as "no run was scheduled" when CI did trigger.
2. **A re-run inherits the run's DISPATCH-time config** — a ceiling raise merged to `main` does not reach a run already dispatched, so re-running before rebasing buys a second, identical cancel.
3. **A rebase can surface live→tree drift** on files outside your change; re-sync live→tree before push.

## Verified

`sync-agent-profile --profile llgenie-tester --check` → `OK: 7 file(s) ... match ... byte for byte`; `check_agent_profiles.py` report → findings naming `llgenie-tester` = 0; `lint_linefeeds.py` rc=0; `make check-docs` + `make changes-index` green (after adding this note + fragment per #1123).