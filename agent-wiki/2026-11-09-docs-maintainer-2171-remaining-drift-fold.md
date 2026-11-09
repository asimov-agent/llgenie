# Documentation lane: fold remaining live→tree drift for 4 skill files (#2171)

## What changed

The `llgenie-documentation-maintainer` lane's live profile had grown ahead of the committed tree on
three files since the last fold (#2147 / issue #2132) went in. This fold copies those files from
the LIVE profile into the tree byte-identically, in the live → tree direction that the comparator
requires — a write-mode `sync-agent-profile` in the other direction would have **truncated** live
behaviour.

The fold covers **four** files: the original three (`SKILL.md`, `acceptance-writeback.md`,
`authoring-and-delivery.md`) plus `ci-triage-for-docs-prs.md`, which the 2026-11-09T04:37Z reviewer
verdict measured as still tree-truncated at the fold head (`tree 16,057 b < live 17,532 b`, +15 lines)
and required folded before the acceptance gate could pass.

| file | tree before | tree after (=`live`) | delta |
|---|---|---|---|
| `skills/llgenie-docs-maintainer/SKILL.md` | 100,428 b | 100,539 b | +111 b |
| `skills/llgenie-docs-maintainer/references/acceptance-writeback.md` | 8,720 b | 10,886 b | +2,166 b |
| `skills/llgenie-docs-maintainer/references/authoring-and-delivery.md` | 4,140 b | 5,897 b | +1,757 b |
| `skills/llgenie-docs-maintainer/references/ci-triage-for-docs-prs.md` | 16,057 b | 17,532 b | +1,475 b |

## Measured

At `origin/main` `54ff1145` `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1`
reported the three original files as the lane's entire live-vs-tree delta (3 of 28, all tree-truncated);
after this fold they read **no live-longer / 0 absent-from-tree** for the lane at the fold head. Each
folded file proved byte-identical to live via `cmp -s <tree> <live>`. The diffs were all pure supersets
(live added sections; 0 tree-only lines on the references, and the SKILL.md single tree-only-line is a
rewritten sentence, superseded not lost).

Two **tree-longer** residuals remain at the head — `SOUL.md` (tree 20,931 b / live 20,044 b) and
`scripts/docs_audit.py` (tree 6,870 b / live 6,768 b). Both are the "the tree is newer there" case
(issue step 4: keep the tree and say so), named under the PR's `## Not covered` and tracked by #2165
(provisioning); they are not channel-truncations of live behaviour.

## Why this matters

The tree is this lane's reviewable, diffable source of truth; the live profile is what the lane runs.
A truncated tree means a rebuild materialises *less* behaviour than the lane now has, with no error —
a shorter `SOUL.md`/skill is not a failure, it just behaves differently. Folding the remaining drift
makes `agents/llgenie-documentation-maintainer/` identical to the running agent, so a review of the
tree is a review of the agent and a rebuild is a no-op.

## Class

Standing #791 live-vs-tree drift class, umbrella #2090. Successor of #2132 (closed by #2147) for this
lane. Fold is doc/behaviour-only: no `scripts/`, `tests/`, workflow or Makefile change.
