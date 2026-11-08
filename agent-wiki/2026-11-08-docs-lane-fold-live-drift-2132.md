# Documentation lane: fold live→tree drift for 10 skill files (#2132)

## What changed

Folded the documentation lane's live profile ahead-of-tree content into the repository, in the
**live → tree** direction that `live-longer` requires. Ten files under
`agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/`:

| file | tree before | tree after |
|---|---|---|
| `SKILL.md` | 99,414 b | 100,053 b |
| `references/acceptance-writeback.md` | 3,983 b | 6,838 b |
| `references/agents-soul-doc-changes.md` | 16,018 b | 19,955 b |
| `references/change-note-gate.md` | 5,438 b | 5,842 b |
| `references/landed-change-verification.md` | 2,988 b | 5,870 b |
| `references/live-vs-tree-drift.md` | 8,774 b | 11,136 b |
| `references/own-domain-audit.md` | 10,901 b | 13,196 b |
| `references/gate-red-triage.md` | *(absent)* | 5,385 b (new file) |
| `references/authoring-and-delivery.md` | *(absent)* | 3,371 b (new file — the live profile grew a second time mid-fold) |

## Measured

At `origin/main` `2e04c9c27548fca16920fea64ab8cd887dd3a0fc`:

```
HERMES_PROFILES_HOME="$HOME/.hermes/profiles" python3 scripts/check_agent_profiles.py check
  before: 12 findings for llgenie-documentation-maintainer
  after :  0 findings for llgenie-documentation-maintainer
```

The **fleet-wide** total is not a stable number and this note does not claim one: the other twelve lanes'
live profiles keep growing while this PR sits, so a fleet figure measured at authoring time is wrong by
the time a reader sees it. Measured repeatedly during this work it read 600, then 592, then 605 — all
correct at their moment, none of them a property of this branch. What this PR asserts is only the one
lane it touches: **12 → 0**.

## Safety: no instruction was lost

`diff <(sort tree) <(sort live)` gives **0 tree-only lines** for every file folded — each was a pure
superset, so folding only added. `change-note-gate.md` was the single file with 2 tree-only lines, and
they are **superseded, not dropped**: the tree said "one row in the form `| … |`" while live says
"**exactly one line**: one row in the form `| … |`. A markdown TABLE header, a blank line, or a trailing
summary line all red it: `[changes-index] ERROR: <fragment>: holds 4 line(s)`". The live text states the
same rule with the failure mode it prevents.

## Why this matters

These live-only lines are procedure this lane already learned and wrote down on the host but never
versioned — the `## Not covered` single-line-bare-`#<n>` exemption mechanics for `check-pr-acceptance`,
the "exactly one row" fragment rule, the landed-change verification protocol, the idle-audit contract
(#1245) and the gate-red triage sequence. Until folded they were unreviewable by any PR.

## Note on the `$HOME` form

Commands in this change are written `HERMES_PROFILES_HOME="$HOME/.hermes/profiles"`, never with a
hardcoded absolute home path: the measurement must be reproducible on a host whose profile home is not
this one. Both forms were verified to produce the same counts (4 vs 4 on a mid-fold measurement), so the
`$HOME` form is not a weaker check.

## Class

This is the standing #791 live-vs-tree drift class, umbrella **#2090**. Successor vehicle to **#2019**
(closed) for this lane. No `scripts/`, `tests/`, workflow or Makefile change.
