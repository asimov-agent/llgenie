# The PR-count assignment gate (owner standing rule, 2026-10-30)

Owner directive: **always be monitoring the bots**, and **keep assigning lanes related gate-free issues whenever the open-PR count is below 25**.

- **Monitor continuously regardless of the threshold.** A turn ends in a dispatch, a close with evidence, or the measured count that says the trigger is above threshold — never on "waiting".
- **Arm the gate dynamically.** When `gh pr list --state open --limit 100 --json number --jq length` < 25, assign idle-capable lanes gate-free issues from the `agent:implement` backlog: host lanes via `message_agent`, in-repo bots via label + a claim-free comment naming the issue. One lane, one issue, one PR.
- **At/above 25, hold the trigger.** Adding a new PR above the cap inflates the exact queue the #919→stacked-melt drain exists to clear; a new PR counts against the 25. Re-measure each pass; the trigger fires the instant the count drops to 24.
- **The count is necessary, not sufficient: there must be an idle-capable lane.** When the gate is armed (count < 25) but every lane is claim-bound (stacked on an un-merged base awaiting the owner, mid-rebase, or on a live product/CI thread), end the pass with that measured reason — "armed, no fit lane yet" — and DO NOT force a new issue onto a claim-bound lane. Putting new work on a lane that cannot act on it is queue-inflation, indistinguishable from a no-op dispatch, and burns the claim the base-merge would have cleared. The gate fires on the next genuine frees-up (a base landing that melts the stack), and the monitor watches for exactly that.
- **Re-verify, don't relay.** Every new PR the gate produces is counted and its head verified before it is reported as a task landing.
- This gates new PR-producing assignment; it does NOT pause in-flight rebase/CI/queue work, which continues independently.
