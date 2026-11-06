# Fix: land the #1791-AC3 read-the-failing-job-log pointer in the engine-improver lane skill

## Why

#1791-AC3 requires each affected lane (implementer, engine-improver, security, pr-reviever,
pr-merge-conflict, ci-pipelines) to carry a copy or a pointer to the read-the-failing-job-log-first
procedure **in its own skill**, versioned per #791 (issue→PR under `agents/<lane>/`). The
implementer's vehicle (#1840) ships the canonical reference and the implementer's pointer only; the
engine-improver lane must land its own pointer so the sequence is loadable from this lane's skill
surface at the moment the lane reports — `closes #1791` keeps `check-pr-acceptance` red by design
until the remaining lanes' vehicles land.

## What changes

Adds a skill-surface pointer to the engine-improver lane's skill:
`agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/read-the-failing-job-log-pointer.md`,
naming the canonical #1791 procedure reference
(`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`,
merged via #1840) and pointing there for the full mandatory sequence alongside this lane's own
`engine-build-proof-dispatch.md`/`publish-run-adjudication.md` for the build-engine-specific failing-leg
loop. A SKILL.md pointer row makes the pointer part of the skill surface.

This lane's SOUL already carries the read-the-failing-job-log-first discipline verbatim (#1726 fleet
block); the vehicle is a pointer addition, not a rewrite — the SOUL line and the existing build-engine
references are untouched.

## Who

llgenie-engine-improver (this lane owns the skill; the fleet ships each affected lane's
copy/pointer as its own #791 vehicle).
