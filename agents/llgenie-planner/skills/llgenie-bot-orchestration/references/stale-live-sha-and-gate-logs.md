# A lane's "live main" is the stalest fact in its report

Rebase and engine lanes sample `origin/main` when they start, then keep quoting that sha for the
rest of the turn — after one or more merges have landed. Never propagate a lane's live cite.

## Check

- Re-fetch yourself and compare by count, not by eye:
  `git rev-list --count <their-base>..origin/main`. A ladder of shas eyeballed as "3 merges
  behind" was actually `1` (only the security-pins merge was missing). Compute before naming it.
- A lane calling a local artifact "current-main, gate-green" while its parent is even one merge
  behind live is a real defect, not pedantry: releasing it as-is reds `check-pr-base`
  (`base_sha != live`). Ask for a one-commit re-cut onto true live, then re-verify
  `git merge-base <head> origin/main` == `origin/main` and `git rev-list --count <head>..origin/main` == 0.
- Owner-held / local-only staging (no push) makes this informational: post the corrected live
  sha and the re-cut ask on the vehicle issue, do not demand an immediate rewrite.

## Claimed full-suite gates: read the log, not the pass count

"N passed, RC=0" is credible only when the log exists on disk and ends in its own sentinel
(e.g. `TU_FINAL_RC=0 … GATE_V2_DONE rc=0`) with no truncation. A count that grew between bases
(N vs N-18) is usually the live-base delta — check which merges the base gained before calling
it a regression. A lane that discards an earlier truncated/failed attempt and cites the complete
one is behaving correctly; say so.
