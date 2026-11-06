# The close-set gate is now completeness-aware (issues #1629, #1273)

## Background

`check_pr_closing.py` (the `check-pr-closing` gate) validated the *adjacency* of the keywords a
PR body chose — `closes #N` with nothing between keyword and ref. It had no guard for the reverse
failure: a PR whose diff materially fixes issue X while the body names X only in resolving prose and
grants a different issue the closing keyword. #1628 is the concrete casualty: the merged PR
`52b21a42` fixed the #1582 truncation defect (its diff added the paginated `branch_runs` walk the
issue asks for) and closed the descoped symptom #1617, but the body's resolving references to #1582
won it no `closes #1582` — so the root-cause issue stayed OPEN (`agent:implement`) with its fix
already on `main`, invisible to anyone scanning for outstanding work.

## The answer

The gate is now completeness-aware. `check_completeness` scans the PR body and the squash commit
text for **resolving references** — a `#N` governed by a fixing/resolving verb (`resolves #1582`,
`the fix for #9`, `completes #N`) — and REDs when such an issue is neither adjacent-closed nor
on-record justified-open:

- **closes #N** (the adjacency grammar, unchanged — #1273/#1556/#1619 stay) satisfies the issue.
- an explicit `does not close #N because <reason>` note on-record satisfies it (a scoped-out or
  separately-tracked item leaves the issue open with a reason the next reader can find).
- a bare reference (`see #9`, a `## Not covered` remainder) is **not** a resolving reference and is
  not a finding — prose stays prose.

So a merged change can no longer silently leave intact the root-cause issue it set out to fix:
every issue the change resolvingly claims is either closed or justified-open on-record. No gate or
severity is weakened; the new check only *adds* a RED when the completeness set is violated.

## Linked

Implements #1629; supersedes the orphaned-OPEN state that #1628's `closes #1617` created for #1582.
The #1582 close was routed as NOT_PLANNED on 2026-11-03; this issue is the durable guard.
