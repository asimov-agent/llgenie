# llgenie-pr-reviever failing-job-log-read pointer (#1791-AC3 / #1849)

## ADDED Requirements

### Requirement: pr-reviever skill carries the failing-job-log-read pointer

The `llgenie-pr-reviever` lane's skill surface carries a pointer to the canonical
failing-job-log-read procedure, so the read-the-log-first sequence loads where this lane reads
instructions.

#### Scenario: a red bot-gate in the pr-reviever lane

Given the `llgenie-pr-reviever` lane is facing a red bot-gate (guard/scope/ci run)
When the lane applies its review procedure
Then it first reads the failing job's own log
And it names the run id and head sha before any verdict, write-back, hold, or routing decision
And the source of the mandatory sequence is the implementer-lane canonical
`red-bot-gate-read-the-failing-job-log.md` reference (merged via #1840)
And the pointer references it from this lane's skill surface per #791 versioning

#### Scenario: pointer-only, no cross-lane edits

Given this lane's #1849 vehicle is being prepared
When the diff is composed
Then it touches only `agents/llgenie-pr-reviever/` plus the change-note machinery and this
openspec change
And no other lane's files are edited (#791)
And no product code, script, or workflow is altered
