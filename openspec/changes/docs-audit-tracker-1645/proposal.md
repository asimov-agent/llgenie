# docs-audit-tracker-1645

<!-- OpenSpec change for issue #1645 -->

## Why

The docs lane's continuous-improvement audits have no durable, open place to land their records:
prior trackers (#1393, #1580, #1245) are closed, and `references/own-domain-audit.md` today makes the
record home conditional ("IF an open docs-lane tracking issue exists … else DM the planner") — which
lets every future audit re-discover the same missing-tracker problem and leave a clean pass recorded
only in a DM. Issue #1645 IS the canonical open tracker; the playbook must NAME it so the record home
stops being a lookup and the fleet has one stable thread to read.

## What Changes

- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/own-domain-audit.md`
  replaces the conditional "missing tracker" paragraph with a pinned contract: #1645 is the durable
  recording home; every clean-audit record posts there as a comment (measured-at sha, each check's
  gate rc, the four-AC-box read, bare greppable sha); findings route as their own six-section
  `agent:implement` issues naming #1645 and the measured sha; findings already named under a standing
  umbrella (e.g. the #791/#2090 live-vs-tree drift family) cite that umbrella instead of filing a
  one-off; the DM fallback applies ONLY when #1645 itself is closed.
- `SKILL.md` gains the one-line pointer to that contract and bumps `version:`.
- The lane then proves the contract live: one bounded audit at the current tip (the playbook's three
  checks) with its record posted on #1645 and verified by read-back.

## Impact

- Affected specs: `docs-audit-record` (ADDED: pinned recording home; routed findings; live proof)
- Affected docs: `agents/llgenie-documentation-maintainer/` (playbook + skill pointer — SYNC line
  obligation via `make bot-preflight`), agent-wiki note + changes.d fragment + CHANGES.md row
- No code, gate or workflow changes.
