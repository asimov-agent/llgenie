# Fold the 4 live-richer doc-maintainer skill references into the tree (#1724, live-parity)

`make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` reported 6 of 16
differing files at `origin/main` `a9f05258`; four of them were **live-richer** — a write-mode sync
would have truncated live behaviour with no gate noticing (#791). The contract is one-way tree→live
and says fix the TREE: a live-only edit is a finding in `check_agent_profiles.py`, commit it via an
issue+PR under `agents/llgenie-documentation-maintainer/`, then re-sync (#1724).

## The fold (live authoritative, tree follows)

Four files under `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/`
copied byte-identical from the live profile (`~/.hermes/profiles/llgenie-documentation-maintainer/…`):

- `agents-soul-doc-changes.md` — 3,677 b → 8,794 b (the tree copy had been truncated by 5,117 b);
- `dispatch-race-verification.md` — 2,296 b → 5,637 b (+3,341 b);
- `changes-index-maintenance.md` — 8,031 b → 9,430 b (+1,399 b);
- `merged-ci-verification.md` — 1,623 b → 2,455 b (+832 b).

Verified after the fold: `sync-agent-profile … CHECK=1` reports only **SOUL.md** (tree 16,918 b vs live
16,175 b) and **SKILL.md** (tree 101,247 b vs live 100,578 b) differing — both **tree-ahead** (they
carry the merged rule-15 fleet block and the #1725 owned-process statement), the correct
non-truncating direction for a later tree→live sync. No remaining file would shrink the live
profile.

## Prove-the-gate

This PR is itself a `skills/**` surface change, so it ships this `agent-wiki/` note + its
`docs/changes.d/` row + the regenerated `CHANGES.md` row in the same branch (the #1123/#1725
discipline). Implements the #1724 live-parity fold for the documentation-maintainer lane.

