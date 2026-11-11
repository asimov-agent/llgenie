# Self-approval (approver==merger) audit methodology

Lesson: when auditing approve-then-merge ratio (the #491/#1088 class), the GitHub list-view pulls endpoint returns `merged_by: null` on EVERY row even though the PR WAS merged — a field-exposure quirk, NOT absence of a merger. If you read the list and see all-null merged_by, you have NOT verified anything.

Correct audit:
1. `gh api "pulls?state=closed&sort=updated&direction=desc&per_page=100"` → filter `.merged_at != null` → take the newest 30. Note PR numbers only.
2. For each sampled PR: `gh api pulls/<n>` → `.merged_by.login` resolves properly per-PR (list view lies).
3. `gh api pulls/<n>/reviews` → collect `.state == "APPROVED"` users + submitted_at.
4. Verify: is approval user == merged_by user? (the self-approval class). Also cross-check instance-level sub-minute gap: approval submitted_at .. merged_at.
5. A `COMMENTED` review is NOT an approval; count only APPROVED. A lane reviewer (andyholst) COMMENTED verdicts never satisfy the REQUIRED review approval.

Rule: never assert a ratio on the list-view merged_by field; per-PR GET is the ground truth. Report the sample PRs you actually checked, not the roster as a claim.

Known-good outcome (2026): last 30 merged showed 30/30 `asimov-agent` merged_by==approver, 0 independent approvals. The self-approval path was the ONLY approval+merge route on the board for that window.
