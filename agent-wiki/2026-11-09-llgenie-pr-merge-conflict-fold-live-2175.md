# LLGenie llgenie-pr-merge-conflict — fold live profile into the tree (issue #2175)

Per the #791 self-versioning flow, this lane's versioned source of truth under
`agents/llgenie-pr-merge-conflict/` must match what the lane runs in
`~/.hermes/profiles/llgenie-pr-merge-conflict/`. Measured at `origin/main` `e141cc9b68` with the
repository's own comparator: `make sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1`
reports **10 of 29 file(s) differ** (the issue's own 7/28 table was stale — re-measured fresh).

| file | tree b | live b | direction | action |
|---|---|---|---|---|
| `skills/llgenie-pr-rebase/references/fork-pr-mechanical-rebase.md` | 3,488 | 4,545 | tree TRUNCATED | fold live→tree |
| `skills/llgenie-pr-rebase/references/hard-rules.md` | 30,961 | 31,177 | tree TRUNCATED | fold live→tree |
| `skills/llgenie-pr-rebase/references/measurement-and-readback.md` | 5,455 | 10,714 | tree TRUNCATED | fold live→tree |
| `skills/llgenie-pr-rebase/references/skill-script-hygiene.md` | 23,361 | 29,009 | tree TRUNCATED | fold live→tree |
| `skills/llgenie-pr-rebase/references/sweep-mechanics.md` | 18,364 | 22,656 | tree TRUNCATED | fold live→tree |
| `skills/llgenie-pr-rebase/SKILL.md` | 105,313 | 80,836 | tree LONGER | keep tree — do not downgrade |
| `skills/llgenie-pr-rebase/scripts/post-rebase-verify.sh` | 13,656 | 11,933 | tree LONGER | keep tree |
| `skills/llgenie-pr-rebase/scripts/salvage-audit.sh` | 9,050 | 9,047 | tree LONGER | keep tree |
| `skills/llgenie-pr-rebase/scripts/stack-replay.sh` | 6,462 | 6,457 | tree LONGER | keep tree |
| `skills/llgenie-pr-rebase/scripts/test-revert-detector.sh` | 9,343 | 6,027 | tree LONGER | keep tree |

## What was done

1. **Folded the 5 tree-truncated references live→tree byte-identical FIRST** (byte-copy live into the
   tree, `git show :<path>` == live verified) — never a tree→live sync while the tree is the shorter
   side. Each of the 5 now matches live byte-for-byte.
2. **The 5 tree-longer files were left as the committed tree** — the exact trap the prior botched
   push `b97ac6a0` fell into (it shaved `salvage-audit.sh`/`stack-replay.sh` DOWN to live size and
   grew `SKILL.md`/`hard-rules.md`/`sweep-mechanics.md` instead of byte-copying live or keeping the
   tree). These carry pre-existing tree behaviour and were NOT shaved to live.
3. **#1123 change-note trio** — this note + `docs/changes.d/2026-11-09-llgenie-pr-merge-conflict-fold-live-2175.md`
   + `CHANGES.md` row (regenerated via the change generator).
4. **OpenSpec presence** — content-sync fold change with `skip_specs: true`, matching the
   status-keeper fold (#2179) so the #1807 openspec-presence gate is satisfied.

## Verification at the pushed head

- `make sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1` → **0 of 29 file(s) differ**.
- `make check-agent-profiles` clean for this lane at the head.

Text-only change under `agents/llgenie-pr-merge-conflict/`. No behaviour change — this is a content
sync of rules that already run live, plus the keep-tree files retain the pre-existing tree
behaviour. Never merged/armed by this lane (#1088).
