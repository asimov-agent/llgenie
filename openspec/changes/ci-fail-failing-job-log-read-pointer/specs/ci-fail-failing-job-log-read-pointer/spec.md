# CI-fail failing-job-log pointer

## ADDED Requirements

### Requirement: the engine-improver lane's skill carries a pointer to the failing-job-log-first procedure

The engine-improver lane's versioned skill carries
(`agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/read-the-failing-job-log-pointer.md`)
a pointer to the canonical #1791 procedure reference
(`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`,
merged via #1840) so the read-the-failing-job-log-first sequence is loadable from this lane's skill
surface, alongside this lane's own build-engine references.

#### Scenario: the pointer is loadable from the engine-improver skill surface

- **Given** a red bot-gate on an engine-improver change
- **When** the lane prepares to dispatch a fix or report green/red/reviewable
- **Then** its skill surface exposes `references/read-the-failing-job-log-pointer.md`
- **And** that pointer names the canonical #1840 reference and directs the lane to read the failing
  step's OWN log (run id + job id + head sha) and quote the error line before any claim
- **Test:** `check_pr_hygiene.py openspec-change` + the pointer file present in the lane skill

#### Scenario: the pointer does not rewrite the SOUL or the build-engine references

- **Given** this lane's SOUL carries the read-the-failing-job-log-first discipline verbatim
- **When** the pointer vehicle lands
- **Then** the SOUL line and the existing `engine-build-proof-dispatch.md`/`publish-run-adjudication.md`
  references are unchanged, and no cross-lane file is edited (#791)
- **And** the PR body carries `AGENTS:`/`BASE:`/`SYNC:` (#792/#845/#1724) ready for review
