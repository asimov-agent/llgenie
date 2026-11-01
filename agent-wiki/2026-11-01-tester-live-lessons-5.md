# tester lane live→tree fold, round 5 (2026-11-01)

Versioning the tester lane's live→tree drift at `8a9f0e41` (#1272's merge). Live accreted a fresh
organizing lesson in **two** files while the tree was frozen at the #1272 fold. Pure accretion in each
(+/−0): byte-copied live→tree, re-hashed the destination.

## New in `SKILL.md` (992 lines)

- The recurring never-quite-finished feel traceable to **live carrying every skill while the tree
  carries only the versioned ones** — so a lane's live text can cite tools that exist nowhere else.
  Folding is the way the text reaches the tree.

## New in `references/agent-profile-versioning.md` (277 lines, §11)

- **Derive the lane's file set from the TREE (`git ls-files agents/<profile>`), never an assumed
  layout.** The live home holds all skills; the tree only the versioned ones — a hand-guessed path
  (e.g. `references/` one level off) matches nothing and still reads "in sync", so a zero-file fold
  and a nothing-to-do fold look identical. Re-enumerate at the start of every round — the live half
  moves while the PR sits open.

## Proof at the committed head

`SKILL.md` `a3b1e0536383 == live`; `agent-profile-versioning.md` `4509c08f8978 == live`; 4 other
reference files + SOUL unchanged byte-for-byte; `make changes-index` regenerates `CHANGES.md` (345
fragments).
