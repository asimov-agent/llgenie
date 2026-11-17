## Why

The issue-implementer lane's close verdict closes the cited issue with
`gh issue close --reason "not planned"` no matter what the close was for. The run that closed
#2048 at 2026-11-16T20:28Z did exactly that while PR #2863 — which already implements #2048 and was
OPEN, landing through CI — carried the closing reference. The issue ended `state_reason=not_planned`
with `by: github-actions[bot]`, a completed piece of work filed under the rejected-work reason.
The lane playbook `.hermes/skills/issue-triage/SKILL.md` and the planner playbook
`agents/llgenie-planner/skills/github-issue-triage/SKILL.md` teach one close shape with no reason
split, so the lane has no shape for "an OPEN PR already implements this — leave it open".

## What Changes

- `scripts/issue_implementer.py`: add the fourth verdict `hold` and a deterministic guard on the
  close path. A close verdict whose evidence cites an OPEN pull request whose title/body names this
  issue (a closing keyword adjacent to `#<num>`, a `(#<num>)` title, or an `Issue: #<num>` line) is
  converted to `hold`: the issue stays OPEN, the lane posts a hold comment naming the PR, posts its
  `bot-done` release marker, and removes the queue labels. `close` keeps `--reason "not planned"`
  for duplicate / superseded / not-a-change closes (its current meaning).
- The `issue.md` decision block (`DECISION_BLOCK`) prints the `TRIAGE: hold` shape with
  `EVIDENCE:` naming the open PR, so the agent is told the leave-open shape instead of guessing.
- The three lane playbooks state the close reasons and the leave-open rule explicitly:
  `.hermes/skills/issue-triage/SKILL.md`,
  `agents/llgenie-planner/skills/github-issue-triage/SKILL.md`, and
  `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/references/planner-stale-state.md`.
- New `scripts/bot_close_reasons.py` + `make bot-close-reasons-report`: a read of closed issues that
  a MERGED PR's closing reference targets AND that the bot closed (it carries `agent:closed` or
  closed the issue as a Bot), printing each issue's current `state_reason`. A `not_planned` reason
  on an issue a merged PR implements is flagged as contradicting its own close evidence.

#2048 was corrected to `state_reason=completed` on 2026-11-16 by a GitHub staff action; the report
names it with that corrected reason.

## Impact

- Affected specs: `bot-issue-close-discipline` (new capability)
- Affected code: `scripts/issue_implementer.py`, `scripts/bot_close_reasons.py` (new),
  `mk/bots.mk`, `scripts/package-layers.json`, the three playbook files,
  `tests/test_issue_implementer.py`, `tests/test_bot_close_reasons.py` (new)

## Out of Scope (tracked separately)

- Correcting other flagged issues' `state_reason` by API PATCH: the report names them; each
  correction is filed as its own issue after the first live read.
