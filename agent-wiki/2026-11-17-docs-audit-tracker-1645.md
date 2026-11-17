# 2026-11-17 — the docs lane's audit records get a named durable home (issue #1645)

## What was verified

- The audit playbook (`agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/own-domain-audit.md`)
  previously made the record home **conditional** ("IF an open docs-lane tracking issue exists … else DM
  the planner"), so every future audit re-discovered the missing-tracker problem. It now names **#1645**
  as the durable recording home: every audit outcome posts there as a comment (bare measured sha, each
  check's gate rc, finding routing); findings route as their own six-section `agent:implement` issues
  naming #1645; umbrella-named drift (live-vs-tree family #791/#2090) is cited, never refiled; the DM
  fallback fires only if #1645 itself is closed.
- Live proof audit executed at tip `2513b954a8854492060da8c7cc9cce7c80b26307` in a detached worktree:
  check 1 — the fleet-memory pointer claim (docs commit `05741c350`, #2861) reads true against the tip
  tree (1 anchor occurrence in the ci-pipelines-maintainer `agent-profiles.md`, `docs/BOTS.md` heading at
  line 3016, rc=0); check 2 — `check-agent-profiles` rc=2, 5 findings (live-longer x3, live-lines-missing,
  absent-from-tree), all already named under #791/#2090 → cited, not refiled; check 3 — `make -s check-docs`
  rc=0 (355 targets documented, 882 wiki entries indexed, census OK).
- Record comment posted on #1645 (`#issuecomment-6940700409`) and read back: first line carries the bare
  measured sha. (Pitfall hit: `gh api -f body=@path` posts the literal `@path` token — file content must
  go through `--input` JSON.)

## Decision

- #1645 stays OPEN forever as the tracker (its lifecycle is the planner's); the precedent is the sweeper
  lanes' never-closing tracker #2652 (`b0347c6be`).

## Current status

- OpenSpec change `docs-audit-tracker-1645`; playbook + SKILL.md 1.0.24 landed on the branch; record on
  the tracker; shipped via a PR whose text references the tracker as prose only — #1645 itself stays
  open forever as the recording home (precedent: never-closing rolling tracker #2652, `b0347c6be`).
- The 1.0.24 pointer pushed `llgenie-docs-maintainer/SKILL.md` to 100,163 chars — over the 100,000
  skill-writer cap the unit gate enforces (main sat at 99,938). The stale-snapshot/repeat-DM rule was
  moved VERBATIM into `references/merged-ci-verification.md` (zero loss, gate-prescribed fix: move a
  section into `references/`, never raise the cap); SKILL.md keeps a 3-line pointer and sits at 99,944
  chars. `tests/test_agent_profiles.py` 150 passed at this head.
