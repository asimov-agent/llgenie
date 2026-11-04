# The profile-propagation `SYNC:` gate (issue #1724)

**Owner directive 2026-11-04:** rule/SOUL/skills changes land as issues + PRs committing text under
`agents/<profile>/` (#791), and `make sync-agent-profile PROFILE=<p>` is the write path that copies the
tree INTO a live Hermes profile's home. But no gate forced that re-sync to be run **and reported** — so a
rule could sit in the tree while the live profile that acts under it still runs the old one. #1707's
SOUL fleet-block drifted from the canonical `fleet_block()` in the gate, and #1719's lane re-reported its
own already-merged PR: the propagation step itself was the hole.

## What this adds

`scripts/check_pr_hygiene.py` now has a `sync-line` gate (wired as `make check-pr-sync-line`): a **bot PR
whose diff changes a directory under `agents/<profile>/`** must carry a `SYNC:` line naming each touched
profile and the command —

```
SYNC: <profile> make sync-agent-profile PROFILE=<profile>
```

Missing it reds the PR before it can land silently. It is mounted in CI beside `check-pr-closing` and
`check-pr-agents-line` (both `ci.yml`'s `guard` job and `scope.yml`'s docs gate), reading the LIVE PR body
via `gh api` (issue #1589) so a body-only fix clears on rerun.

## The shape of the report

One profile per `SYNC:` line; a diff touching several profiles needs several lines. A human-only range is
skipped (not failed) — the rule lands on the lane that owns the profile. A top-level `agents/` file
(`AGENTS.md`, `agents/standing-rules.md`) is not a profile dir and does not trigger the gate.

## Why "reported" and not just "run"

A reviewer must be able to verify propagation happened, not just that a commit landed. The `SYNC:` line
names the profile and the exact command, so checking green answers "did the live profile get re-synced?"
with a yes that the body itself documents — the same reason the `AGENTS:`/`BASE:` lines exist for the
rulebook (#792, #845).

## Tested

`tests/test_pr_hygiene_sync_line.py` builds real commits touching `agents/` and proves: the matching
`SYNC:` line passes, a missing or wrong-profile line refuses naming the profile, two profiles need two
lines, a top-level `agents/` file does not trigger the gate, a human-only range is skipped, and removing
the CI step reds the wiring test.
