# acceptance-criterion-heading-canary

## ADDED Requirements

### Requirement: red a closed issue whose unticked criteria sit under a non-canonical heading

When `check_pr_acceptance` evaluates a CLOSED issue and the canonical `## Acceptance criteria` section
is empty but the body still contains acceptance-like `- [ ]` checkboxes, the gate MUST NOT report green
(`OK`). It MUST exit 1 and name the heading(s) that hold those boxes, so an issue that merges `- [ ]`
is seen to be unmarked. The canonical path is unchanged.

[comment]: # (AC / how to verify: the new test_check_pr_acceptance test reds on the pre-fix script and passes on the fixed one.)

#### Scenario: a closed issue with criterion boxes under `## Fix (acceptance criteria)` is reported

- **Given** a closed issue whose body has `- [ ]` boxes under a non-canonical heading
  (e.g. `## Fix (acceptance criteria)`) and NO canonical `## Acceptance criteria` section
- **When** `check_pr_acceptance` evaluates that closed issue
- **Then** the gate exits 1 and names the heading(s) that hold the unticked boxes

#### Scenario: a canonical issue is unaffected

- **Given** a closed issue with a canonical `## Acceptance criteria` section
- **When** `check_pr_acceptance` evaluates it
- **Then** behavior is exactly as today (ticked green, unticked red on `claim-unchecked`),
  and the canary never fires

#### Scenario: the exact-match section reader is unchanged

- **Given** `issue_body.section_body`
- **When** the canary is active
- **Then** `section_body`'s exact-match behavior is unchanged (the canary is added beside it,
  via `issue_body.HEADING_RE`), and `check-pr-acceptance` / `openspec-validate-all` are not weakened
