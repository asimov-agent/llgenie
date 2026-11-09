# LLGenie status-keeper — fold live profile into the tree (issue #2179)

Per the #791 self-versioning flow, this lane's versioned source of truth under
`agents/llgenie-status-keeper/` must match what the lane runs in
`~/.hermes/profiles/llgenie-status-keeper/`. Measured at `origin/main` `eb08416f34` with the
repository's own comparator: `make sync-agent-profile PROFILE=llgenie-status-keeper CHECK=1`
reports **1 of 2 file(s) differ**, and the differing file is tree-truncated:

| file | tree b | live b | direction | action |
|---|---|---|---|---|
| `skills/llgenie-status-keeper/SKILL.md` | 13,857 | 28,919 | tree TRUNCATED | fold live→tree |
| `SOUL.md` | 10,421 | 10,421 | parity | no change |

## What was done

1. **Folded live→tree byte-identical FIRST** (`cp` the live 28,919-b v1.3.1 skill into the tree,
   sha256 `09d2982b…` verified on both sides) — never a tree→live sync while the tree is the
   shorter side, which would destroy 15,062 b of live behaviour (#1724/#2084-class).
2. **No marker re-stamp needed**: both `host-bot-tools` blocks (live and committed tree) are the
   pinned form and byte-identical, so the #1582 rendered-block gate stays green.
3. **SOUL.md left in parity** — no edit.
4. **#1123 change-note trio** — this note + `docs/changes.d/2026-11-09-status-keeper-fold-live-2179.md`
   + `CHANGES.md` row (regenerated via `make gen-changes`).

## Verification at the pushed head

- `make sync-agent-profile PROFILE=llgenie-status-keeper CHECK=1` → **0 of 2 file(s) differ**.
- `make check-docs`, `make lint`, `make check-agent-profiles` green.

Text-only change under `agents/llgenie-status-keeper/`. No behaviour change — this is a content
sync of rules that already run live. Never merged/armed by this lane (#1088).
