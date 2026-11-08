# Documentation lane: fold live→tree drift for 6 skill files (#2132)

## What changed

Folded the documentation lane's live profile ahead-of-tree content into the repository, in the
**live → tree** direction that `live-longer` requires. Six files under
`agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/`:

| file | tree before | live/tree after |
|---|---|---|
| `SKILL.md` | 99,414 b | 99,717 b |
| `references/acceptance-writeback.md` | 3,983 b | 6,838 b |
| `references/agents-soul-doc-changes.md` | 16,018 b | 19,955 b |
| `references/change-note-gate.md` | 5,438 b | 5,842 b |
| `references/landed-change-verification.md` | 2,988 b | 5,870 b |
| `references/live-vs-tree-drift.md` | 8,774 b | 11,136 b |

## Measured

At `origin/main` `2e04c9c27548fca16920fea64ab8cd887dd3a0fc`:

```
HERMES_PROFILES_HOME="$HOME/.hermes/profiles" python3 scripts/check_agent_profiles.py check
  before: 600 findings fleet-wide, 12 for llgenie-documentation-maintainer
  after : 592 findings fleet-wide,  0 for llgenie-documentation-maintainer
```

## Safety: no instruction was lost

`diff <(sort tree) <(sort live)` gives **0 tree-only lines for 5 of the 6 files** — a pure superset in
each case. `change-note-gate.md` had 2 tree-only lines, and they are **superseded, not dropped**: the
tree said "one row in the form `| … |`" while live says "**exactly one line**: one row in the form
`| … |`. A markdown TABLE header, a blank line, or a trailing summary line all red it: `[changes-index]
ERROR: <fragment>: holds 4 line(s)`". The live text states the same rule with the failure mode it
prevents.

## Why this matters

These live-only lines are procedure this lane already learned and wrote down on the host but never
versioned — the `## Not covered` single-line-bare-`#<n>` exemption mechanics for `check-pr-acceptance`,
the "exactly one row" fragment rule, and the landed-change verification protocol. Until folded they were
unreviewable by any PR.

## Class

This is the standing #791 live-vs-tree drift class, umbrella **#2090**. Successor vehicle to **#2019**
(closed) for this lane. No `scripts/`, `tests/`, workflow or Makefile change.
