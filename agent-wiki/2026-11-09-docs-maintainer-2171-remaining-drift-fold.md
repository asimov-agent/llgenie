# Documentation lane: fold remaining live→tree drift for 3 skill files (#2171)

## What changed

The `llgenie-documentation-maintainer` lane's live profile had grown ahead of the committed tree on
three files since the last fold (#2147 / issue #2132) went in. This fold copies those three files from
the LIVE profile into the tree byte-identically, in the live → tree direction that the comparator
requires — a write-mode `sync-agent-profile` in the other direction would have **truncated** 4,034 b
of live behaviour.

| file | tree before | tree after (=`live`) | delta |
|---|---|---|---|
| `skills/llgenie-docs-maintainer/SKILL.md` | 100,428 b | 100,539 b | +111 b |
| `skills/llgenie-docs-maintainer/references/acceptance-writeback.md` | 8,720 b | 10,886 b | +2,166 b |
| `skills/llgenie-docs-maintainer/references/authoring-and-delivery.md` | 4,140 b | 5,897 b | +1,757 b |

## Measured

At `origin/main` `54ff1145`:

```
make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1
  before: 3 of 28 file(s) differ, all three tree-truncated
  after : 0 of 28 file(s) differ
```

`cmp` proven byte-identity of the folded copy against the live file at the fold head (`cmp -s <tree>
<live>` per file). The three diffs were all pure supersets (live added sections; 0 tree-only lines on
the two references, and the SKILL.md single tree-only-line is a rewritten sentence, superseded not
lost — the "tree is often the truncated side" paragraph replaced the older one-line form the live no
longer has).

## Why this matters

The tree is this lane's reviewable, diffable source of truth; the live profile is what the lane runs.
A truncated tree means a rebuild materialises *less* behaviour than the lane now has, with no error —
a shorter `SOUL.md`/skill is not a failure, it just behaves differently. Folding the remaining drift
makes `agents/llgenie-documentation-maintainer/` identical to the running agent, so a review of the
tree is a review of the agent and a rebuild is a no-op.

## Class

Standing #791 live-vs-tree drift class, umbrella #2090. Successor of #2132 (closed by #2147) for this
lane. Fold is doc/behaviour-only: no `scripts/`, `tests/`, workflow or Makefile change.
