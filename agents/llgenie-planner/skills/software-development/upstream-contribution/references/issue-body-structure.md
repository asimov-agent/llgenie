# Detailed feature-issue body structure

Sections a detailed feature issue carries, in order. Each impl issue gets its own
acceptance criteria and scope so it can ship independently.

## Feature Description
What the feature does, concretely, in numbered steps. Name the real entry point
(e.g. `llgenie --suggest`) and the real data source. Include the actual data shape
as a JSON/markdown block when the feature consumes an external contract.

## Motivation
Why it matters — the problem it solves, in the user's own framing when that framing
is the clearest statement of intent. Tie it to what the tool does today and what it
should do instead.

## Proposed Solution
How it could work: new CLI flags, new module/function names, which existing code it
reuses (name the real functions), and the flow. Keep it concrete enough that a
maintainer can scope it.

## Acceptance Criteria
A checkbox list of verifiable outcomes. Each must be testable (a command output, a
behavior, a test that exists). This is what a PR must satisfy.

## Scope / Effort Estimate
Small / Medium / Large + what areas of the codebase it touches and what it depends on.

## Additional Context
Links to the source index/contract, related existing issues, and the repo's own
contribution rules (e.g. "per AGENTS.md: OpenSpec change + feature branch + PR").

## Parent/impl split
A large feature becomes one parent (overview + motivation + the impl list) plus one
impl per independently-shippable piece. The parent is created first; impl titles
carry the parent's real number (`impl(#92): ...`).
