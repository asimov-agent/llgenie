# Reviewer lane: the review verdict is load-bearing, not narrative

Issue: #1193.

The reviewer lane's verdict did not move the board. `mergeStateStatus` read `REVIEW_REQUIRED` for every open PR regardless of whether a defect was found, so an owner scanning "which PRs are ready" could not distinguish a pass from a "has real defects" review. The fix is to make the reviewer's own verdict state load-bearing through the GitHub review API, not just a comment:

- When the code at the head **fails** an acceptance criterion (or a security/architecture advisory is unanswered): `gh pr review -r` (REQUEST_CHANGES) naming the failing criterion, the head sha and the run id.
- When **every** acceptance criterion is met with evidence: `gh pr review -a` (APPROVE) with the same anchor (head sha + run id or exact test command).
- A neutral body-only comment **never** substitutes for the `-a` / `-r` state — the board must see the verdict.

The `-a` this lane raises is a statement that the issue's acceptance criteria were met at the measured head and sha; it is **not** a merge authorization. The lane still never merges, never approves on the owner's behalf, and never squash/auto-merge. `agents/manifest.json` continues to declare `never-merge` and `never-implement`, and both gate regexes (`check_agent_profiles.py`) still match the edited SOUL.

Versioned in `agents/llgenie-pr-reviever/SOUL.md` and the `llgenie-pr-review` skill (issue + PR, #791/#919 — never a private edit).
