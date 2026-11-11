## ADDED Requirements

### Requirement: base-vs-main staleness is measured independent of short-sha truncation

The orchestrator tick's PR section SHALL decide staleness by comparing each PR's `baseRefOid` to the
fetched main sha as sha prefixes: the two names denote the SAME commit when either contains the
other (8-char base vs 9-char main, full-length base vs 7-char short-form main). It SHALL report
STALE only when the prefixes genuinely differ, and SHALL still print the true base on every PR line.

#### Scenario: a PR based on the current main at a 9-char main sha reads fresh
- **Given** main read at 9 chars (e.g. `23faf9550`) and a PR whose `baseRefOid` is the full 40-char
  sha of that same commit
- **When** the tick's PR section runs
- **Then** the PR is counted fresh, never STALE, and its base is printed

#### Scenario: a genuinely stale base is still STALE with its true base
- **Given** a PR whose `baseRefOid` is the full sha of an older main commit
- **When** the same section runs
- **Then** the PR is counted STALE and its true (truncated) base is printed

#### Scenario: short-form main of any length matches a full-length base
- **Given** `MAIN_OVERRIDE` at 8 chars and PR fixtures carrying that exact 8-char base (the existing
  #2159 fixtures)
- **When** the same section runs
- **Then** the fresh/stale counts are unchanged (12 stale of 14 at the #2159 fixture board)

### Requirement: the CI tip tag matches the main tip at any truncation length

The tick's CI section SHALL tag a run as `TIP` when its `headSha` and the fetched main sha denote
the same commit by the same prefix rule, instead of an exact `[:8]`-against-`main` string equality.

#### Scenario: a run at the main tip reads TIP despite differing name lengths
- **Given** a CI run whose `headSha` is the full 40-char sha of current main and main read at its
  short form (7–9 chars)
- **When** the tick's CI section runs
- **Then** that row is tagged `TIP`, not `other`
