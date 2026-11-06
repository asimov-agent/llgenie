# security-pipeline-skill-790

## ADDED Requirements

### Requirement: the security pipeline skill exists as a HOST agent skill
`.hermes/skills/security-pipeline/SKILL.md` MUST exist with frontmatter `name: security-pipeline`
(matching its directory), non-empty `description:`, and exact `## Inputs` / `## Output` / `## Rules`
headings, stated in the same contract shape as the other 15 skills under `.hermes/skills/`.

WHEN an agent is asked to work a security leg,
THEN it reads `.hermes/skills/security-pipeline/SKILL.md` for the contract instead of re-deriving the
pipeline from source.

#### Scenario: the skill states the four owners and the data rules
- **Given** `.hermes/skills/security-pipeline/SKILL.md`
- **Then** it names the four owners (daily scan, floor, tagged issues, remediation bot)
- **And** it states `enforce_events` is data (never a literal; `push`/`pull_request` forbidden,
  `pr_fail_on` empty = report-only), the floor is the maximum of the minimums (only a finding with a
  fixed version becomes a floor), a compiled `requirements*.txt` is never an edit target,
  green-or-nothing, never add an `automerge` key to `renovate.json` (#718), the routing invariant
  (#780/#349), a merged PR's bare `closes #N` never clears a scan-evidence box (#1693), and
  refuse-what-the-lane-cannot-place

### Requirement: the skill is admitted in HOST_SKILLS so make check-agent-skills is green
`security-pipeline` MUST be in the `HOST_SKILLS` frozenset in `scripts/check_agent_skills.py`, because
no workflow/leg preloads a security skill and the gate's `skill-unused` finding fails any skill no leg
preloads that is not admitted by name.

WHEN `make check-agent-skills` runs,
THEN `security-pipeline` is not reported as unused (it is admitted by name).

#### Scenario: the one-line admission satisfies the unused-skill rule
- **Given** `.hermes/skills/security-pipeline/` exists with `SKILL.md`
- **When** `make check-agent-skills` runs
- **Then** no `skill-unused` finding names `security-pipeline`
- **And** the admission is a single HOST_SKILLS line (data), not a gate-logic change

### Requirement: the skill is listed in the README leg ledger
`.hermes/skills/README.md` MUST list `security-pipeline` as a **no leg — host skill** row and name it
in the HOST-skills paragraph.

WHEN a reader opens `.hermes/skills/README.md`,
THEN the security-pipeline leg is discoverable and its HOST-skill status is unambiguous.

#### Scenario: the ledger has the security row
- **Given** `.hermes/skills/README.md`
- **Then** it contains a `| security-pipeline | **no leg** — host skill | … |` row
- **And** the HOST-skills paragraph names it among the admitted HOST skills
