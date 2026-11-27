# Spec delta: fleet-architecture (issue #3106)

## ADDED Requirements

### Requirement: the fleet roster gate is a subset of the documented profiles

`scripts/check_fleet_roster.py check` MUST read `agents/manifest.json` from the tree and require
every `profiles[].name` to appear as a standalone token in the `## Host lane fleet` subsection of
`docs/ARCHITECTURE.md`. It MUST exit 1 and print each missing profile name when any is absent, exit
1 with a clear "no subsection" finding when the subsection does not exist, and exit 0 when all
manifest profiles appear. It MUST use a subset check (`manifest <= documented`): a documented name
that is not in the manifest MUST NOT fail the gate, because rosters are meant to grow.

#### Scenario: a manifest profile is absent from the fleet subsection

- **Given** a fleet doc whose `## Host lane fleet` section lists 12 of the 13 manifest profiles
- **When** `python3 scripts/check_fleet_roster.py check --doc <fixture>` runs
- **Then** it exits 1 and names the missing profile (`llgenie-tester`) in its output

#### Scenario: the subsection has an extra lane

- **Given** a fleet doc listing every manifest profile plus one future lane
- **When** the gate runs
- **Then** it exits 0 (subset, not equality)

### Requirement: the gate is judged by check-docs

`make check-docs` MUST chain `python3 scripts/check_fleet_roster.py check`, and a
`make check-fleet-roster` public target with a `## help` line MUST exist. CI has no live profiles
(#928), so both MUST read only the tree copy.

#### Scenario: check-docs judges the fleet subsection

- **Given** a branch whose `docs/ARCHITECTURE.md` drops one manifest profile from the fleet subsection
- **When** `make check-docs` runs
- **Then** the chained fleet-roster step exits 1 and names the dropped profile

### Requirement: the weekly review has one clock, one guard and one output

`.github/workflows/fleet-architecture-review.yml` MUST declare `on.schedule` with a `43` minute,
a `workflow_dispatch` input, an explicit `timeout-minutes` on every job (#2317), an
owner/collaborator guard before any secret is read, and one static concurrency group with
`cancel-in-progress: false`. Its agent leg MUST be a single Hermes call that reads the brief and
writes only a suggestions file. The deterministic publish step MUST file at most one refined issue,
MUST dedupe on this producer's marker across open issues, and MUST file nothing when the
suggestions file is empty. It MUST NOT edit code, workflows, gates or `SOUL.md`, and MUST NOT push,
commit or merge.

#### Scenario: no new suggestion

- **Given** an empty suggestions file
- **When** `scripts/fleet_architecture.py publish` runs
- **Then** it prints `action=none` and no `gh issue create` is called

#### Scenario: an open issue already carries the marker

- **Given** a non-empty suggestions file and an open issue whose body carries
  `<!-- fleet-architecture-review:`
- **When** publish runs
- **Then** it prints `action=skip` with that issue URL and files nothing
