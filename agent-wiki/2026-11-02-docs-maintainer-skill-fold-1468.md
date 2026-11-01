# Fold the live docs-maintainer skill bundle into the tree

Closes #1468. The `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/`
versioned copy in the tree was 3 versions / ~27 KB behind the live profile the lane actually runs
on (`~/.hermes/profiles/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/`). Per the
fleet profile-sync contract (#1010, #791) the live profile is authoritative and the versioned
`agents/<profile>/**` tree follows it; `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1`
must be byte-identical.

## What changed

- `SKILL.md` — 73,822 b → **100,417 b** (`version: 1.0.17` → `1.0.20`)
- `references/ci-triage-for-docs-prs.md` — 11,115 b → **13,591 b** (grown)
- `references/live-vs-tree-drift.md` — 5,711 b → **7,135 b** (grown)
- `references/` added (7, absent-from-tree): `changes-index-maintenance.md` (8,031 b),
  `dispatch-race-verification.md` (2,296 b), `dm-stale-replay-loop.md` (1,298 b),
  `lint-and-gates.md` (1,607 b), `live-fold-race.md` (6,525 b),
  `merged-ci-verification.md` (1,623 b), `pr-merge-state-verification.md` (7,194 b)

## Capacity note

The folded SKILL.md is **100,417 bytes but 99,828 characters**, which is **under** `skill_manage`'s
100,000-**character** cap (the tool rejection reads "N characters (limit: 100,000)"). So no #1135-class
slim is required: the byte-identical live→tree fold lands under the cap and the drift closes. The
dispatch's "over the cap" reading conflated bytes with the tool's char-count.

## Verbatim proof

Every folded file is byte-identical between tree and live: `cmp -s` is empty for SKILL.md, all 11
references, and `scripts/docs_audit.py` (12 files; 0 differ). No truncation of the richer live (#791).

## Acceptance evidence

- `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` exit 0 (tree==live).
- `make check-agent-profiles` green at the branch head.
- `make check-docs` green; change→note trio present (`agent-wiki/` + `docs/changes.d/` + CHANGES.md row).
