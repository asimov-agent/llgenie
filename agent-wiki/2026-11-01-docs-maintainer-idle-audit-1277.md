# docs-maintainer idle audit (issue #1277)

The documentation-maintainer lane gains the owner-approved **empty-queue → own-domain-audit**
continuous-improvement clause (issue #1245; per-lane spec comment 6551533999), versioned live→tree
(byte-identical) in this lane's #791 PR.

## Behaviour

When this lane's reactive queue is empty for **N=2 consecutive passes** (no dispatched work, no
in-flight gate it owns), run **one bounded own-domain audit**:

- **main-versus-docs alignment** — README / skill sections stale vs current `main`;
- **skill-freshness** — a skill 2+ releases old (read the `version:` frontmatter against the release
  ledger in `CHANGES.md`);
- **change-note coverage** — a behavioural surface with no `agent-wiki/` note + `docs/changes.d/` row
  (the #1123 change→note gate).

Every finding is filed as a refined **six-section issue tagged `agent:implement`**, routed through the
normal queue — **never implemented by the same pass**. If there are none, record
`re-audited at <sha>, no findings`. One-pass scope, no infinite loop; it never overrides real reactive
work.

## Files

- `agents/llgenie-documentation-maintainer/SOUL.md` — new `## Idle / empty-queue audit (continuous improvement, #1245)` section.
- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` — new `## Idle / empty-queue audit` section.
- Both byte-identical to the live `~/.hermes/profiles/llgenie-documentation-maintainer/` copies.

Refs: #1277 (this issue), #1245 (contract), #791 (live→tree versioning), #1123 (change→note gate).
