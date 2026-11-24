# Spec Delta: umbrella-cite-renderer

## ADDED Requirements

### Requirement: A `## Not covered` pointer shall be a full issue URL

Every `## Not covered` bullet produced through the one issue-body seam (`scripts/issue_body.py::render`)
SHALL name its side issue as a full issue URL
(`https://github.com/asimov-agent/llgenie/issues/<n>`). A bare `#<n>` cite SHALL NOT survive the render:
it is the token `scripts/check_pr_acceptance.py::rollout_lane_findings` derives a rollout lane from, so a
bare pointer holds the umbrella's own `closes #<umbrella>`. Line anchors (`#L12`), already-linked issue
URLs and fenced code SHALL be left exactly as written, and the dedupe marker SHALL remain the body's
first line.

#### Scenario: a bare pointer renders as a URL

- **Given** a producer that passes `not_covered=["the ranking rule is its own decision (#669)"]`
- **When** `issue_body.render` builds the body
- **Then** the `## Not covered` bullet carries `https://github.com/asimov-agent/llgenie/issues/669`
- **And** the rendered body carries no bare `#669` cite

#### Scenario: an already-linked pointer is not rewritten twice

- **Given** `not_covered=["tracked as https://github.com/asimov-agent/llgenie/issues/3056"]`
- **When** `issue_body.render` builds the body
- **Then** the bullet is unchanged and no nested URL appears

#### Scenario: a line anchor is not an issue cite

- **Given** a bullet that cites `scripts/issue_body.py#L105`
- **When** `issue_body.render` builds the body
- **Then** the anchor is unchanged

### Requirement: `make check-issue-bodies` shall gate the bare-cite pointer form

For every registered producer, `scripts/check_issue_body.py` SHALL re-render that producer's
`not_covered` bullets through the one seam and report a finding naming the producer file when the
rendered `## Not covered` section still carries a bare `#<n>` cite. The renderer self-probe SHALL carry
the same assertion, so removing the normalizer reddens the gate even when no producer spells a literal
cite.

#### Scenario: producer pointer renders clean

- **Given** `scripts/registry_change_issue.py`, whose `not_covered` region contains `(#669)`
- **When** `make check-issue-bodies` re-renders that region through `issue_body.render`
- **Then** no cite-shape finding is reported for that producer

#### Scenario: a renderer that stops normalizing is named

- **Given** `issue_body.render` whose `Not covered` bullets bypass `link_issue_cites`
- **When** `make check-issue-bodies` runs its self-probe and its producer probes
- **Then** at least one finding names the producer file and states the URL remedy

### Requirement: a rollout hold shall name the pointer-form remedy

`scripts/check_pr_acceptance.py`'s blocking `rollout-lane-open` finding SHALL state, in its evidence,
that the umbrella body's bare `#<n>` pointers in `## Not covered` are converted to full issue URLs to
release the hold on the closes keyword, and that the side issue stays open either way.

#### Scenario: hold carries the remedy

- **Given** an umbrella body that cites an OPEN issue which cites the umbrella back
- **When** `rollout_lane_findings` reports `rollout-lane-open`
- **Then** the evidence names the bare-`#<n>` pointer form and the full-issue-URL remedy
