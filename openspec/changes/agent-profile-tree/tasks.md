# Tasks — agent-profile-tree

- [x] 1. `agents/manifest.json` lists `llgenie-planner` (rules `never-implement`, `never-merge`) and `llgenie-issse-implementer`; each listed profile has a directory with a `SOUL.md`.
- [x] 2. `agents/llgenie-planner/SOUL.md` carries the orchestrator text, `agents/llgenie-planner/skills/llgenie-bot-orchestration/` carries the skill and the `references/proving-bot-claims.md` it names, `agents/llgenie-issse-implementer/SOUL.md` carries the implementer's.
- [x] 3. `scripts/agent_profile_sync.py` + `make sync-agent-profile PROFILE=<p> [CHECK=1]` (`HERMES_PROFILE_HOME`, exit 2 on an unknown profile, write-then-read-back, no delete path).
- [x] 4. `scripts/check_agent_profiles.py` + `make check-agent-profiles` + `make agent-profiles-report`, with one rejection per gate rule and the whole gate wired into `ci-unit` beside `check-agent-skills`.
- [x] 5. `tests/test_agent_profiles.py` drives the real scripts: the committed tree, one fixture per rejection, and the sync + `CHECK=1` against a temporary `HERMES_PROFILE_HOME` (`# Given / # When / # Then` markers).
- [x] 6. `.hermes/skills/README.md` states the two-tree split; `docs/BOTS.md` documents the tree, both targets and every gate rule; both new `##` targets carry a `## help` line and a `.PHONY` entry.
- [x] 7. `agent-wiki/2026-10-28-agent-profiles-tree.md` records the change (issue #791, the PR), is indexed in `CHANGES.md`, and carries the host-only proof `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` against the live profile.
- [x] 8. The planner's live behaviour is folded in verbatim (issue #851): `agents/llgenie-planner/SOUL.md` (7,509 b) and `skills/llgenie-bot-orchestration/` (`SKILL.md` 100,343 b + all 12 `references/*.md`) are byte-identical to `~/.hermes/profiles/llgenie-planner/`, on this branch and PR (#903) — no second vehicle.
- [x] 9. Gates green: `make check-agent-profiles`, `make check-agent-skills`, `make check-docs`, `make check-wiring`, `make test-unit` and `make openspec-validate NAME=agent-profile-tree`.
