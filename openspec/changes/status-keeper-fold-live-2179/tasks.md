# Tasks

Issue: [#2179](https://github.com/asimov-agent/llgenie/issues/2179)

## Fold the live profile into the tree

- [x] Copy `skills/llgenie-status-keeper/SKILL.md` live→tree byte-identically (sha256 `09d2982b…` on both sides).
- [x] Verify the tree SOUL.md is already in parity (10,421 b both) — no fold needed there.
- [x] Confirm the `host-bot-tools` marker blocks (live and committed tree) are byte-identical pinned form — no re-stamp.
- [x] Record the change (agent-wiki note + docs/changes.d fragment + CHANGES.md row, closes #2179).
- [x] Gate through `make check-docs`, `make lint`, and `make sync-agent-profile PROFILE=llgenie-status-keeper CHECK=1` → `0 of 2 file(s) differ` at the pushed head.
