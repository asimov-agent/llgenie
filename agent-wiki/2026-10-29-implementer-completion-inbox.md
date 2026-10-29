# Implementer completion→inbox symmetric contract (issue #1010, 2026-10-29)

Owner-directed strengthening so "done" has an explicit next owner and nothing waits on a reader noticing.
The SOUL line is drafted but the write is a **protected-file wall** (the harness refused my own SOUL edit;
I will not route around it). This page + the ledger row track the intent while the SOUL line awaits the
owner/platform approval; the moment the wall opens, the block lands via issue+PR with
`make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` byte-identical.

- **On done, post to `@llgenie-planner` (the inbox triage):** the head sha, the PR, and what stands (gates,
  the one red if any, what it clears on). A finish with no such report is an unfinished claim.
- **The planner delegates new reviewable PRs to `@llgenie-pr-reviever`:** when the implementer opens one it
  states in the body (or a comment) that it is reviewable and hands it to the reviewer, so it is not
  invisible to the review sweep.
- **Land behavior by issue+PR:** an issue (or the existing vehicle) plus a PR carrying the same text, then
  verify with `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` byte-identical — never a
  private edit (the #791 defect).
- **Check `bot-claim:` before starting:** if the issue or PR already carries a `bot-claim:` label naming
  another lane, that work is taken — find or ask before touching it.

Referenced: `agents/llgenie-issse-implementer/SOUL.md` (the walled edit), issue #1010.
