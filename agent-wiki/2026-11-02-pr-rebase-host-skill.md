# 2026-11-02 — the PR-rebase procedure is a gated host skill, not a profile file

**Issue:** [#818](https://github.com/asimov-agent/llgenie/issues/818)

## What was wrong

The procedure that cleared PR #789's `CHANGES.md` conflict lived only on one host, in
`~/.hermes/profiles/llgenie-pr-merge-conflict/skills/development/llgenie-pr-rebase/SKILL.md` (94
lines, 7369 bytes, written 2026-10-28). The tree had its inner half —
`.hermes/skills/rebase-conflict/SKILL.md`, the CI leg that resolves the conflicted files, stages
them (`git add`), and stops — but not the outer half that decides which PR is conflicting,
hands off to the owning bot, cuts the worktree, runs the gates, forces the push with a leading
lease, and reads the result back. Three readers were exposed: a CI implementer handed a `DIRTY` PR
re-derived the resolution from scratch, a reviewer could not diff what the rebase was told between
two conflicting PRs, and a reinstall or a second machine lost the specific cheap facts the rebase
depends on (a conflicting PR reports zero checks because GitHub builds no merge ref; agent PR
branches live in the base repo so the lease names the fetched `origin` ref; a long-`pending`
`guard` beside queued runs is capacity, not a defect).

## What changed

- **`.hermes/skills/llgenie-pr-rebase/SKILL.md`** — the outer procedure admitted as a HOST skill:
  frontmatter plus `## Inputs` / `## Output` / `## Rules`, carrying the keep-both `CHANGES.md` rule,
  the leading-tuple `--force-with-lease="refs/heads/$BR:origin/$BR"` form, the
  zero-checks-on-a-conflicting-PR fact, and the capacity-vs-defect distinction. It names
  `.hermes/skills/rebase-conflict` as the resolve-and-stage dependency and must not restate it, and
  states which half runs where: the leg contract ends at `git add` in the CI image; this outer half
  runs on the host and owns survey, worktree, gates, lease and report.
- **`HOST_SKILLS`** (`scripts/check_agent_skills.py`) — `llgenie-pr-rebase` admitted by name as the
  third entry (`llgenie-engine-improver`, `llgenie-architecture-pass`, `llgenie-pr-rebase`).
- **`.hermes/skills/README.md`** — one new table row plus the existing HOST paragraph extended
  (not duplicated) to name all three.
- **`tests/test_agent_skills.py`** — two admission tests in the #793/#811 pair shape: removing the
  name from `HOST_SKILLS` turns the gate red with `skill-unused`, and deleting the skill's `## Rules`
  section is a finding.

## Verified

- `make check-agent-skills` green; `agent-skills-report` prints `llgenie-pr-rebase: host-skill`
  with its description.
- `make check-docs` and `make check-wiring` green; docs trio (note + `docs/changes.d/` fragment)
  per #1123.

No workflow YAML touched; **no gate weakened** — the admission is the same reviewed-by-name
mechanism #793/#811 used, and the skill still owes Inputs/Output/Rules. Nothing merged; stop at the
reviewable PR (owner #1088).
