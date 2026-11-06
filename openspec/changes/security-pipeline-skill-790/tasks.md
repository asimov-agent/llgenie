# security-pipeline-skill-790 — Tasks

Issue: [#790](https://github.com/asimov-agent/llgenie/issues/790)

- [x] 1. `.hermes/skills/security-pipeline/SKILL.md` created with frontmatter `name: security-pipeline` (matching the directory) and exact `## Inputs`/`## Output`/`## Rules` headings stating the contract: the four owners, `enforce_events` is data (never a literal), `pr_fail_on` empty = report-only, floor is the maximum of the minimums, compiled `requirements*.txt` never an edit target, green-or-nothing, never add an `automerge` key to `renovate.json` (#718), the routing invariant (#780/#349), merged PR's bare `closes #N` never clears a scan-evidence box (#1693), refuse-what-the-lane-cannot-place.
- [x] 2. `.hermes/skills/README.md` lists the new `security-pipeline` leg row and names it in the HOST-skills paragraph.
- [x] 3. `scripts/check_agent_skills.py`: `security-pipeline` added to `HOST_SKILLS` (one line) so the `skill-unused` finding is satisfied — the only script change, gate-driven (no leg preloads a security skill).
- [x] 4. Change-note trio (#1123) shipped: `agent-wiki/2026-11-06-security-pipeline-skill-790.md` + `docs/changes.d/2026-11-06-security-pipeline-skill-790.md` + `CHANGES.md` regen via `scripts/changes_index.py write`.
- [x] 5. `make check-docs`, `make check-agent-skills`, `make check-workflows`, `make lint` (and `make check-wiring`) green in a clean worktree; openspec presence change (this dir) present so the #1807/#1810 presence gate is satisfied.
- [x] 6. No edit to `docs/SECURITY.md` (AC#1 via #780), `issue_body.py`, `acceptance_writeback`, or `auto-merge.yml` (#1644/#1088/#491 intact).
