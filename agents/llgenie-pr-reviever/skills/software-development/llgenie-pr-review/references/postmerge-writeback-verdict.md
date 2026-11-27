# Post-merge verdict + write-back shape (verified #3088/#3080)

Use when a PR is already MERGED at first check but its closing issue still has unticked boxes.

- #1799 first check can find `state=closed, merged=true` — that is the normal post-merge
  #1644 write-back shape, NOT an open-PR review. Do not merge, approve, or arm.
- The merge may already carry an APPROVED review from `github-actions[bot]`. That is the
  auto-merge mechanism, not this lane's verdict. The writer still owes a COMMENTED verdict.
- A trusted bot-verdict APPROVE cannot come from `asimov-agent` when it is PR author and a
  `MERGER_LOGIN`: `verdict_for_head` returns untrusted and `gh pr review -a` self-approval is
  refused. It is also NOT required — the #1644 seam runs on a COMMENTED review + `rc=0` ref.
  Do not switch to the owner's credential to manufacture an approve (SOUL line 21).
- Verify each provable box locally at the exact head BEFORE the verdict, then
  `acceptance_writeback.py writeback --issue N --proven K --verdict-ref '...'` and `check`.
  Ref: `reviewer <login> review <id> command <cmd> rc=0 head <40hex>` — no bare `#N`, no parens.
- Leave genuinely post-merge boxes (live GHCR re-probe, registry-liveness conclusion on main)
  open and record their unblock conditions; do not tick them from a pre-merge head.
- Record the final on-wire state (head, review ids, tick counts, check rc) in an evidence file
  and READ IT BACK — external gh writes alone are not session-observable to the Nerve guard.
