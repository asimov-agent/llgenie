# Autonomy over a human gate; auditing the no-cron lanes

## Never park a fixable red on "a human gate" — split CI-green work from the approval

Standing owner rule: **work autonomously until the CI pipelines are green; never wait on a human gate for work a bot or the planner can do.** Classify every red on an open PR into two piles before you report:

- **(a) CI-green work** — body stamps, rebases, dispatch, re-runs, closing/hygiene lines — bot/planner-actionable NOW.
- **(b) the #1088 approval/merge** — the one genuine human gate you can never fabricate (bot-authored PRs cannot self-approve).

Do every item in (a) first. The only thing you may say you are "waiting on" is (b). `mergeStateStatus: BLOCKED` / `REVIEW_REQUIRED` is **not** a reason to leave a PR red on `guard`/`check-pr-agents-line` or on a stale base — clear the fixable gates, then name the approval as the sole remaining gate so it is a single click for the owner. A pass that ends "all PRs blocked on owner" while a body-stamp or a stale base is unaddressed is idleness wearing a gate's clothes — a defect in the planner, not a fact about the board.

Mode this against the SOUL's "never merge" constraint: the approval is genuinely un-clearable by any bot, so do not fabricate or bypass it — but you MUST still drive everything below it to green and reviewed so the human gate is the last mile, not the first blocker.

## A bot-quiescence audit by cron slot misses the no-cron dispatch-only host lanes

"Which bot is idle" answered with `gh run list` per scheduled workflow only measures **scheduled** lanes. A dispatch-only host lane (e.g. the reviewer / `@llgenie-pr-reviever`) has **no cron**, so it never appears as 'idle' and never self-triggers — it acts only when you dispatch it. An empty review queue across every open PR is therefore a **planner defect**, not a quiet fact, and the fix is to force the lane, not to report "nothing idle."

On every audit, after the scheduled-workflow sweep, enumerate the dispatch-only host lanes separately and ask for each: *is there open, un-gated work in its domain right now?* (For the reviewer: any open PR with `reviews=[]`.) If yes → dispatch it with the choreography the lane needs (ids, expected evidence). Do not classify a no-cron host lane as 'nothing to do' because its nonexistent cron slot is clear — a cron-slot audit cannot see a lane that has no slot.

```bash
# the review-gap probe: which open PRs carry ZERO reviews (the reviewer's idle-capable queue)
for n in $(gh pr list --repo <o>/<r> --state open --json number --jq '.[].number'); do
  c=$(gh pr view $n --repo <o>/<r> --json reviews --jq '.reviews|length')
  echo "#$n reviews=$c"
done
```
