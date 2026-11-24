# Proposal: umbrella-cite-renderer

## Why

AGENTS.md requires every issue/PR body to close its scope with a `## Not covered` section whose every
item names its own side issue. Those pointers are spelled today as bare `#<n>` cites
(`registry_change_issue.py` writes `the ranking rule … is its own decision (#669)`,
`trend_staleness_issue.py` writes `(issue #2901)`). A bare cite is the exact token the acceptance
rollout path reads as a lane: `scripts/check_pr_acceptance.py::rollout_lane_findings` enumerates
`CITE = re.compile(r"#(\d+)")` over the umbrella's own body, probes each referenced issue live, and
holds the umbrella's close (`rollout-lane-open`, blocking) whenever a referenced issue is still OPEN
and cites the umbrella back. So an umbrella that defers side work as prose-cites is blocked by its own
deferral list: the umbrella's PR cannot carry its `closes #<umbrella>` while a pointer that already
lands as its own issue sits OPEN (#3053's PR was held exactly this way in 2026-11-24:
`scope: fail — "Not covered" cites #3050 which is still OPEN and references #3053 back`, while the
lane's own `closes #3050` passed and merged). A full `https://…/issues/<n>` link renders the same
pointer and does not trigger the cite regex. GitHub: #3055.

## What Changes

- `scripts/issue_body.py` gains `ISSUE_URL_BASE`, `issue_url(n)` and `link_issue_cites(text)`: every
  bare `#<n>` in a `## Not covered` bullet is rendered as its full issue URL, while `#L12`-style line
  anchors, already-linked URLs and fenced code keep their text. Producers need no edit: they keep
  writing the pointer, and the one seam spells the link — additive, never removing behaviour.
- `scripts/check_issue_body.py` gains the cite-shape rule: for each registered producer it extracts the
  `not_covered=` argument region and re-renders those bullets through `issue_body.render`; a rendered
  `## Not covered` that still carries a bare `#<n>` is a finding that names the producer file. The
  renderer self-probe grows the same assertion, so a regression in the normalizer reddens
  `make check-issue-bodies` even when no producer spells a literal cite.
- `scripts/check_pr_acceptance.py`'s `rollout-lane-open` finding names the fix that unblocks the close:
  convert the umbrella body's bare `#<n>` pointers in `## Not covered` to full issue URLs (the side
  issue stays open either way; only the hold on the closes keyword changes).
- `tests/test_issue_body.py` and `tests/test_check_issue_body.py` prove the render states (bare cite →
  URL, URL pointer untouched, `#L12` anchor untouched, marker still first line) and the gate states
  (producer with a bare-cite pointer renders clean today; a renderer whose normalizer is removed names
  the producer). `tests/test_check_pr_acceptance.py` proves the new remedy text appears in the blocking
  finding.

## Impact

- Affected specs: none previously required URL-shaped `Not covered` pointers; this change adds the
  requirement.
- Affected code: `scripts/issue_body.py`, `scripts/check_issue_body.py`, `scripts/check_pr_acceptance.py`,
  `tests/test_issue_body.py`, `tests/test_check_issue_body.py`, `tests/test_check_pr_acceptance.py`.
- Affected GitHub state: issue #3055 body synced to this proposal; the #3053 lane's
  `Not covered` pointer is re-rendered as a URL when that lane ships.
