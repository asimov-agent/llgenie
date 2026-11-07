# llgenie-pr-merge-conflict-vehicle-hygiene

## ADDED Requirements

### Requirement: cite a PR as green only from its live `check-runs` conclusions

When any dispatch, audit, or report cites a PR as a passing contrast witness, it MUST read that PR's
conclusions from the API at the measured head (`gh api repos/<r>/commits/<sha>/check-runs` with
`.conclusion`), never a `mergeable` status and never a relayed "passed". A `MERGEABLE` PR is not CI-green; a
`cancelled` run (superseded by a newer push) is *not yet*, not a pass; a `failure` conclusion is the wire
fact. A green is proven by `.conclusion == "success"` rows at the current head sha.

[comment]: # (AC / how to verify: the #1850 case — the audit's dispatch cited its own vehicle as passed while its live guard/scope runs at head were red — is named as the defect class; a new vehicle may neither call a MERGEABLE PR green nor treat cancelled as pass.)

#### Scenario: a report cites a MERGEABLE PR as green

- **Given** a PR that is `MERGEABLE` and "ready-for-review"
- **When** any dispatch/audit/report cites it as green
- **Then** the citer first reads its live `check-runs` conclusions from the API at the head; a red
  (`failure` / `cancelled`) conclusion is recorded as the wire fact, never overwritten by a `mergeable` true

### Requirement: a profile-editing lane vehicle carries its `SYNC:` line in the same push

Any PR that edits `agents/<profile>/SOUL.md` or a lane skill under `agents/<profile>/` MUST include
`SYNC: <profile> make sync-agent-profile PROFILE=<profile>` in its body in the same commit/push that adds
the skill edit. `check-pr-sync-line` (#1724) reds a live-again vehicle whose body omits it; the edit and its
SYNC line land together, never deferred to a re-push.

[comment]: # (AC / how to verify: this PR itself touches agents/llgenie-pr-merge-conflict/ and carries a SYNC: llgenie-pr-merge-conflict … line in its body — AC-3 of finding #1854 exercised by the vehicle.)

#### Scenario: a vehicle edits a lane profile without a SYNC line

- **Given** a PR diff touching `agents/<lane>/` files
- **When** its body carries no `SYNC:` line for that profile
- **Then** `check-pr-sync-line` reds it (the gate is real), and the fix is to add the line in the same push,
  not to defer it to a later re-push

#### Scenario: the vehicle carries its own SYNC line

- **Given** a vehicle whose diff touches `agents/<profile>/`
- **When** the PR body names `SYNC: <profile> make sync-agent-profile PROFILE=<profile>`
- **Then** `check-pr-sync-line` returns 0 at its head, and the live profile is re-synced from the tree
