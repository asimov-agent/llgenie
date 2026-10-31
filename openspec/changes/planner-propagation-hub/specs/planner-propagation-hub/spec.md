# planner-propagation-hub

## ADDED Requirements

### Requirement: the planner is the propagation hub

The planner MUST, the moment a lane finish lands or a PR reaches a fresh head or a merge lands, route the
dependent lanes (tester, security, architect, reviewer) onto that same PR in the same pass, on-record, instead
of leaving them to discover the new head by polling.

#### Scenario: a lane finish routes the dependent lanes in the same pass

- **Given** a lane reports a finished PR at a fresh head
- **When** the planner processes that finish in the same pass
- **Then** the planner reads the finish from evidence (branch, head sha, run id), posts a routing comment on
  the PR naming which dependent lanes look now and why, and dispatches each named lane — or says in the
  comment why it was not dispatched (it already holds a vehicle, or is gate-blocked)
- **And** the routing and disposition are recorded so the next pass does not re-dispatch a lane already on
  the vehicle
- **Test:** a reviewer reading `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` finds the
  section "The planner is the propagation hub" stating this behaviour

#### Scenario: the propagation rule is versioned, not claimed live

- **Given** the versioned planner profile
- **When** `make check-agent-profiles` runs
- **Then** it is green, and the section above is present in the tree's
  `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
- **Test:** `make check-agent-profiles` and the section present in the working tree
