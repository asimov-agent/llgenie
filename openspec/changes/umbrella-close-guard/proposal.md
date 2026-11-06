# Proposal — guard a squash-merge closing keyword against premature umbrella auto-close (#1815)

GitHub auto-closes an issue from a merged PR's close keyword — and it reads the SQUASH COMMIT
TEXT as well as the PR body. `check_pr_acceptance.py` (the merge-time issue-state gate, #1792)
derives its linked-issue set ONLY from the PR body (`closing_references(body)`), so a lane whose
squash commit message carries an adjacent `(closes #N)` on a multi-lane rollout umbrella is never
held to that umbrella's `## Acceptance criteria`: the gate does not know #N is being closed, and
GitHub's native close COMPLETEs the umbrella while it measures 0/5 ticked and 1/3 lanes merged
(measured 2026-11-05: #1813's squash `(closes #1812)` auto-closed #1812; planner reopened
21:17:59Z, comment 6669797855).

This change extends the acceptance gate to read the squash-text closes too (union with the body
closes), makes the close-keyword parse negation-aware (`does not close #N` is not a close), and
wires the workflow steps to pass the commit range so a lane that would prematurely close a rollout
umbrella is RED — the merge is blocked until the umbrella is genuinely done or the close keyword is
moved off the squash text.
