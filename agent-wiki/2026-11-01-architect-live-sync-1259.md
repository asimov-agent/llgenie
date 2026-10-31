# Versioned the architect lane's live SOUL + skill into the tree (v1.3.0)

PR #1259 — the tree's `agents/llgenie-architect/` catches up to the authoritative
live Hermes profile (the live copy is newest; the direction is live→tree, never
tree-over-live). Versioned via the #791/#1062 path under `agents/llgenie-architect/`,
tracked by the recurring live↔tree drift issue (#1156).

## What changed (live→tree, byte-for-byte)

1. **`SOUL.md`** — the mission and "This lane's rules" now carry the live text the
   lane actually runs under: "You own the architecture of … a structural design
   change is your ready-for-review pull request … You never merge."
2. **`agents/manifest.json`** — the `llgenie-architect` row drops `never-implement`
   (the live SOUL itself states "the tree PR has to drop `never-implement` or the
   gate will reject this soul": the architect lane opens structural-design PRs);
   `never-merge` is kept, so the gate's REQUIRED_RULE survives.
3. **`skills/…/llgenie-architecture-issue-pass/SKILL.md`** — v1.2.0 → v1.3.0: adds
   the refine/restate-targets-BODY lesson, the satisfiable-AC rescope lesson, the
   sequencing-landing lesson, the inline-body-backtick rule, the read-only-dispatch
   guard-is-unsatisfiable guidance, and the sibling-issue-vs-widening section.
4. **`…/references/landscape-sweep.md`** — referenced by the live SKILL.md but was
   never synced into the tree; added so the tree and live skill agree.

## Verified

Tree copies byte-identical to the live profile (SOUL, SKILL, landscape-sweep);
`HERMES_PROFILES_HOME=/nonexistent python3 scripts/check_agent_profiles.py check`
clears the architect lane at the head; this note + its `changes.d` row clear
`make check-docs`.

Does not close #1060 (its other lanes' rows remain); references #1156 for the
drift class. PR #1259 is NOT armed — released only by owner approval (#1088).
