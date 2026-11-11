# Binding board work to a lane: the `assignees` field is dead, the claim pair is authoritative

## The trap
For llgenie lanes, GitHub's issue `assignees` field **cannot** hold a lane. The lanes are Hermes profiles, not GitHub users — `users/<lane-handle>` returns 404, and a `POST /issues/{n}/assignees {"assignees":[lane]}` returns HTTP 201 with an `assignees:[]` body, silently no-oping. A control `POST` naming a real GitHub user persists while the lane handle does not — the 201 response is identical either way, so the body is the only signal. So never treat "assign the issue" as the board binding, and never read `assignees` back to assert a lane owns an issue — you will see `[]` and wrongly conclude nobody took it.

## What is authoritative instead — the claim pair
- **Planner side:** a claim-comment on the issue (`Planner assignment — #N bound to <lane>`), naming scope, the `closes #N` adjacency requirement for the eventual vehicle, and "one vehicle, one window base, never draft".
- **Lane side:** the lane's start bookend on the same issue (`BOT <lane> · working on #N · branch <ref> · ...`) — its claim and its "done" definition.
The two together, on the issue thread, are the sole binding.

## If a board tool/status-keeper thinks an issue is "unassigned"
It is referenced from the claim pair, not `assignees`. A comment mentioning the lane + a start bookend = owned. A wildcard claim is only "claimed" once the lane posts its own bookend (a planner claim alone is a reservation, not possession).

## Cleanup discipline when the field was touched
If a control/diagnostic POST polluted `assignees` (e.g. assigned `andyholst`), remove it: `DELETE /issues/{n}/assignees {"assignees":[who]}` then read back (empty). If relay flakiness duplicates a posted comment, delete the extras by comment id and verify the surviving set — never leave duplicate claims that look like two owners.
