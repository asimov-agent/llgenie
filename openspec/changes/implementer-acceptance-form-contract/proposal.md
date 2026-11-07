# The implementer lane files and opens every PR body with a tickable acceptance-criteria contract

## Why

The universal form rule (#1796 #1) is only as universal as the fleet that authors issue/PR bodies.
`scripts/issue_body.py` enforces the six-section shape (incl. `## Acceptance criteria` with `- [ ]`) on the
producer-rendered issue path (#745), and the #1804/#1810 gates surface a missing PR-body checklist — but a
lane actually *behaves* by the contract its own versioned skill states. Before this change the implementer
SOUL (`agents/llgenie-issse-implementer/SOUL.md`) named the #791 versioning path but carried **no** form
contract — nothing told the lane's own authoring step what an issue or a PR body it files must include. The
reviewer's #1804 verdict (comment 6669030076, #1796 = 5/6) left #1 honestly UNTICKED for exactly this gap,
blocking #1804 from 6/6 and #1796 from closing.

## What changes

`agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/SKILL.md` (the lane's
active implementing skill, folded live→tree via #1060 so it is versioned and reviewable) gains the
acceptance-criteria form contract, verbatim from #1796 #1, as a dedicated section: every issue this
lane files AND every PR body it opens has a `## Acceptance criteria` section with each criterion a
`- [ ] ` markdown checkbox — one per provable outcome; a criterion a reviewer cannot tick is not one
(#745). The checklist must be the canonical `## ` heading (never a bare `**Acceptance criteria:**` bold
line — that defeats `issue_body.missing()` and the verdict-gated ticking in `acceptance_writeback`,
#1644). The changed skill is text-only under `agents/llgenie-issse-implementer/`, versioned via #791,
and re-synced with `make sync-agent-profile PROFILE=llgenie-issse-implementer` (SYNC per #1724).

No gate code changes (`issue_body.py`, `acceptance_writeback`, `auto-merge.yml`, #1804/#1810 stays intact).
This change adds only implementer-lane skill behaviour.
