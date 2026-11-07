# llgenie-pr-merge-conflict-own-domain-audit

## ADDED Requirements

### Requirement: the own-domain audit re-measures at read-time, never reuses a stale record

When the lane's bounded own-domain audit runs (empty reactive queue, #1245), every claimed PR head and base
MUST be re-read from the API (`gh pr view <n> --json headRefOid,baseRefName`) at the moment of the claim —
never copied from a prior record. Every base used in the last N rebases MUST be an ancestor of the *current*
`origin/main` (`git merge-base --is-ancestor <base> origin/main`); a base that is not an ancestor is a
stale-base defect. Each measured item records the sha it was measured at.

[comment]: # (AC / how to verify: the #1852 defect class — a head cited as live without re-measurement ~20 min after a sweep landed — is stated as the defect to guard, with the #1816 near-miss documented.)

#### Scenario: a record cites a head as live without re-measuring it

- **Given** the lane's audit has a prior record citing a PR head as "live"
- **When** the audit runs again
- **Then** it re-reads the head from the API at read-time, checks ancestor-or-not vs the *current*
  `origin/main`, and records the sha it measured — it does not repeat the prior record as current truth

#### Scenario: every base in the last N rebases is checked as an ancestor

- **Given** the audit reviewing the lane's last rebases
- **When** it checks each base
- **Then** `git merge-base --is-ancestor <base> origin/main` is run against the *current* `origin/main`
  and a non-ancestor base is recorded as a stale-base defect

### Requirement: a finding's own witness is read from live `check-runs`, not a relayed claim

When the audit cites a PR as "passed" (the contrast that proves a mechanical gate), it MUST read that PR's
live `check-runs` conclusions at its head (`gh api repos/<r>/commits/<sha>/check-runs`), never a `mergeable`
status and never a relayed "green". A `MERGEABLE` PR is not CI-green; a `cancelled` run is not a pass. The
defect class is codified so a finding filed on a witness never measured is recognised as the same stale-read
failure.

[comment]: # (AC / how to verify: the #1850 case — the audit's dispatch cited its own vehicle as passed while its live guard/scope runs at head were red — is named as the defect class.)

#### Scenario: an audit cites a "passed" witness it never measured

- **Given** the audit about to cite a PR as a passing contrast witness
- **When** it cites it
- **Then** it first reads the PR's `check-runs` conclusions from the API at the measured head, and a red
  (`failure` / `cancelled`) conclusion is recorded as the wire fact, never overwritten by a `mergeable` true

### Requirement: findings file as refined issues; the audit never fixes in-pass

Every finding the audit produces is a refined six-section issue tagged `agent:implement` routed through the
normal implementer queue; a clean audit is recorded as `re-audited at <sha>, no findings`. The audit lane
files, never fixes, in-pass; one pass, no infinite loop, never overrides reactive work.

[comment]: # (AC / how to verify: the own-domain-audit.cs reference states the routing and scale.)

#### Scenario: the audit finds a defect

- **Given** the audit discovering a stale-base/stale-head or openspec-trio defect
- **When** it completes
- **Then** it files one refined six-section `agent:implement` issue naming the measured shas, and does not
  fix the defect in the audit pass itself
