# security-pipeline-skill-790 — proposal

Issue: [#790](https://github.com/asimov-agent/llgenie/issues/790) · [#349](https://github.com/asimov-agent/llgenie/issues/349) · [#780](https://github.com/asimov-agent/llgenie/issues/780)

## Why

Under #790, the security legs have no contract an agent can be handed: `docs/SECURITY.md` documented
only the pin gate and `.hermes/skills/` had no security entry among its 15 legs. The issue body says
"the docs half is in review as #780; the skill half is this issue" — AC#1 (the routing-invariant
page) is already satisfied on `main` via #780 (`a25650938a`), so this change carries the skill half
(AC#2 + AC#3). An agent asked to work a vulnerability leg currently starts by re-deriving the four
owners, the `enforce_events`-as-data rule, the floor rule and "green or nothing" from source; a
versioned HOST skill states them once, where the next agent looks.

## What Changes

- `.hermes/skills/security-pipeline/SKILL.md` (new): a HOST-agent skill (no CI leg preloads it;
  admitted by name in `HOST_SKILLS`) with frontmatter `name: security-pipeline` (matching the
  directory), exact `## Inputs`/`## Output`/`## Rules` headings, and the contract: the four owners
  (daily scan, floor, tagged issues, remediation bot), `enforce_events` is data (never a literal;
  `push`/`pull_request` forbidden, `pr_fail_on` empty = report-only), the floor is the maximum of the
  minimums (only a finding with a fixed version becomes a floor), a compiled `requirements*.txt` is
  never an edit target, green-or-nothing, never add an `automerge` key to `renovate.json` (#718),
  the routing invariant (#780/#349: a gate nobody watches is not a gate; the one deliberate exemption
  is `security-scan`), a merged PR's bare `closes #N` never clears a scan-evidence box (#1693), and
  refuse-what-the-lane-cannot-place.
- `.hermes/skills/README.md`: lists the new `security-pipeline` leg row and names it in the HOST-skills
  paragraph.
- `scripts/check_agent_skills.py`: `security-pipeline` added to `HOST_SKILLS` (one line) — required by
  the gate's `skill-unused` finding, the only script change (dispatch pre-authorized it).
- The #1123 change-note trio (`agent-wiki/2026-11-06-security-pipeline-skill-790.md` +
  `docs/changes.d/2026-11-06-security-pipeline-skill-790.md` + `CHANGES.md` regen via
  `scripts/changes_index.py write`).

## What Doesn't Change

- No gate code logic, no renderer, no merge/arm rule. `issue_body.py`, `acceptance_writeback`, and
  `auto-merge.yml` are untouched (#1644/#1088/#491 intact). The one `check_agent_skills.py` line is a
  HOST_SKILLS admission (data), not a gate change. No edit to `docs/SECURITY.md` (AC#1 already landed
  via #780).
