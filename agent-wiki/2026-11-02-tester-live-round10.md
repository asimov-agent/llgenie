# agents(llgenie-tester): round-10 live fold — issue #1327

## What was folded live→tree

Round 10 of the versioned live→tree fold for the llgenie-tester lane. Measured at branch time
off fresh `origin/main`, then copied via the wired `make tester-fold-live PROFILE=llgenie-tester COPY=1`:

| file | live sha | size | note |
|------|----------|------|------|
| SKILL.md | `770d355` | 97,752 B | +1,901 B vs main `b2a81fb3` — two in-review lesson-blocks folded live this session |
| references/agent-profile-versioning.md | `d939d6f1` | 25,603 B | +723 B vs main `ba2a4a8f` — the `tester-fold-live` `COPY=1` forwarding / exit-code-signal block |

The fold tool itself is unchanged vs main (`scripts/fold-live-profile.py` `05f829`), so this fold
touches only live-ahead content, not the tool.

## #1273 standard — byte-identical proof

After the copy, both blobs were re-read from the worktree and compared byte-for-byte against live:

- `SKILL.md`: tree `770d3555605b` == live `770d3555605b` (same, 97,752 B)
- `agent-profile-versioning.md`: tree `d939d6f1d6dd` == live `d939d6f1d6dd` (same, 25,603 B)

Fold report: `5 same, 2 drifted, 0 live-missing, 0 live-only, 0 mid-write` (rc 0). Mid-write guard
clean — no live file moved between the two reads.

## Purpose

This is the planner-dispatched round-10 vehicle (#1327) — the +1,901 B / +723 B residual that
postdated the round-9 fold (#1324). Live is the authority; live-ahead drift is folded live→tree,
never trimmed. This is the fold itself; the #1326 engine branch merged ahead of it in the same
window is a different lane and untouched here.
