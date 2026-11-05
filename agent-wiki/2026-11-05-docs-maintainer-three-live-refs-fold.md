# Docs-maintainer: fold three live-only ref files into the committed tree

The docs-maintainer own-domain audit at `e083b30b` (tracked #1645) surfaced live→tree profile drift
on three files under `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/`:

- `dispatch-race-verification.md` was live **+400 b** (a new "If the red is a stale base, not a
  stale dispatch" section cross-referencing `base-race-rebase-and-metadata.md`); tree held the
  truncated 5637 b copy. `make sync-agent-profile … CHECK=1` reds (Error 1) and the sync tool warns
  "do not sync it until it is re-copied".
- `base-race-rebase-and-metadata.md` (2871 b) and `live-to-tree-fold-prs.md` (5258 b) existed live
  only — `git log --all` confirmed they were **never committed**.

Per #791/#1060 a live→tree fold is a change under `agents/<profile>/`, and lands as the owning
lane's issue+PR (finding #1800 → this PR). The fix folds all three byte-identically and never runs a
write-mode `sync-agent-profile`, which would truncate live (#791 trap). After merge:
`make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` must report
`OK: N file(s) match byte for byte, rc=0`.
