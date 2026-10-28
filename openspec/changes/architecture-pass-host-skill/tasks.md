# Tasks — architecture-pass-host-skill

- [x] 1. `.hermes/skills/llgenie-architecture-pass/SKILL.md`: the architecture-pass contract in the repo's shape — frontmatter, `## Inputs`, `## Output`, `## Rules`, the audit-check table and the correction discipline.
- [x] 2. `scripts/check_agent_skills.py`: `HOST_SKILLS` frozenset (by name), the unused-skill rule exempts a member, `report()` marks it ` host-skill`, and the docstring states the admission rule.
- [x] 3. `scripts/check_agent_skills.py`: the required sections match an EXACT heading line (`^## Rules$`), not a substring — all twelve committed skills already comply.
- [x] 4. `tests/test_agent_skills.py`: four cases — an admitted host skill is not `skill-unused`; an admitted host skill missing `## Rules` is still refused; a decorated heading is a missing section; and this tree reports `llgenie-architecture-pass: host-skill` with the sha rule inside it.
- [x] 5. `.hermes/skills/README.md`: the HOST-skill row plus the paragraph that defines it; `docs/ARCHITECTURE.md`: the `.hermes/skills/` row names the host skill.
- [x] 6. Proven against the base: with `HOST_SKILLS` emptied the gate fails `skill-unused` for the new skill, and with `## Rules` decorated it fails `skill-section` — both restored afterwards.
- [x] 7. `make check-agent-skills`, `make check-wiring`, `make check-docs`, `python3 scripts/lint_linefeeds.py` exit 0; `pytest tests/test_agent_skills.py` -> 24 passed.
- [x] 8. `AGENTS.md`: the `(MANDATORY, durable)` measurement section (owner-approved) — sha from the API, detached worktree, counting method, correct-the-body discipline.
- [x] 9. `.hermes/skills/llgenie-architecture-pass/references/host-skill-merge.md` — the 3-path merge recipe for two host skills (measure with `merge-tree`, the README keep-both trap, the `HOST_SKILLS` union, prove on the merged tree), routed from the skill body.
- [x] 10. `agent-wiki/2026-10-28-architecture-pass-host-skill.md` records the change and names #805 / the PR; `CHANGES.md` indexes it.
- [x] 9. `make openspec-validate NAME=architecture-pass-host-skill` exits 0.
