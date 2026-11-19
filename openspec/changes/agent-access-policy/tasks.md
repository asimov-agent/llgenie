# Tasks — agent-access-policy

- [x] Write `scripts/check_agent_access.py`: AGENTS.md identity/access section check (section
      (heading, identity name, scope roster with operation mapping), host-agent-skill check
      (`agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md` present with the
      audit, stamp, and `gh auth status` rule phrases), and a secret scan refusing
      `gh[pousr]_…`/`github_pat_…` strings in the section or the skill (prints kind + location,
      never the value). Stdlib only.
- [x] Wire it: `make check-agent-access` + `make agent-access-report` in `mk/gates.mk`, added to
      the Makefile target roster, and `make check-agent-access` added to the `scripts/ci_unit.py`
      step list next to `make check-issue-bodies`; `make check-wiring` stays green.
- [x] Add the AGENTS.md section `## The agent's GitHub identity and required access (mandatory,
      durable)` (identity `asimov-agent`, the six-scope roster each tied to its unblocked step,
      audit/stamp rules, no-secrets rule) and list the new targets in AGENTS.md's Makefile-targets
      section.
- [x] Author `agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md` (frontmatter +
      scope→operation map + audit rules + procedure + precedents) and sync it into the live profile
      with `make sync-agent-profile PROFILE=llgenie-issse-implementer`.
- [x] Test the gate in `tests/test_check_agent_access.py`: happy tree green; removed section red;
      missing scope mapping red; removed skill red; stripped rule phrase red; planted `gho_` token
      red with no value echoed; `ci_unit.py` step-list assertion.
- [x] Change note: `agent-wiki/2026-11-19-agent-access-policy-2923.md` + matching
      `docs/changes.d/` index row naming #2923 and #2914.
- [x] Validate: `make check-agent-access`, `make test-unit`, `make openspec-validate
      NAME=agent-access-policy`, `make openspec-tasks-check`, `make check-docs`, `make lint`,
      `make lane-preflight`.
- [x] PR body mirrors the issue's `## Acceptance criteria` with `(proven: …)` tokens, names the
      `Not covered` items as their own issues (#2914, #2837, #2254/#880), and carries
      `closes #2923` outside any code fence.
