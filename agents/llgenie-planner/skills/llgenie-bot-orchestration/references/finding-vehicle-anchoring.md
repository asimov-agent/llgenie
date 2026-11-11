# Anchoring a lane's finding to the right issue vehicle

A lane's follow-up often *amends* its own earlier report: it concedes the original claim was wrong
and produces a genuinely new, real finding in its place. That new finding needs a **new issue** —
the old one is not a vehicle for it.

## Rules

- **A PR body's `closes #<n>` against a CLOSED issue is a no-op and a falsified trail.** GitHub does
  nothing (the issue is already closed) and the merge graph later reads as if the PR delivered the
  old claim, which it did not. Check the anchor before accepting the report:
  `gh issue view <n> --json state,stateReason,closedAt,title`.
- **Never reopen a COMPLETED issue to host a new finding.** A close made on refuted evidence stays
  closed; the corrected finding is a different problem with different acceptance criteria. Reopening
  teaches the next reader that closes are provisional, so nobody trusts a close again.
- **The planner files the issue when the lane jumped straight to a PR.** Issue creation is triage,
  not implementation. Write it in the six-section shape with explicit acceptance criteria, name the
  PR as the implementation vehicle, and put an explicit `do NOT reopen #<old>` line in the body so
  nobody "helpfully" revives the completed one.
- **Then correct on two channels:** a board comment on the PR naming the new issue and asking the
  lane to retitle the body to `closes #<new>`, plus a DM with the number already created — so the
  lane does not race you and open a duplicate. Quote the comment id in your ledger.
- **Verify a hardening/test PR by diff, not by description.** `gh pr diff <n>`: the assertion should
  be a containment/subset check on the object it pins (e.g. the make target's body still composes a
  named sub-target), never exact-list equality or line-number pinning — those red on the next
  legitimate edit and teach the next person to edit the test instead of the code.
- **Accept the lane's own red-on-removal proof for test-only hardening.** Asking for a full matrix
  re-run on a test-only `+n` file wastes a run; the guard-proofed both-directions argument is the
  evidence.

## CI API pitfall while verifying a head

`/actions/runs?head_sha=<short-sha>` returns **empty** — the runs query needs the full 40-char sha.
Resolve it first:

```bash
gh pr view <n> --json headRefOid --jq '.headRefOid'
gh api "repos/<owner>/<repo>/actions/runs?head_sha=<full-sha>&per_page=8" \
  --jq '.workflow_runs[]?|"\(.created_at) \(.status)/\(.conclusion // "-") run=\(.id) \(.name)"'
```

An empty result from a short sha is *not* evidence that CI never started. Same for `gh pr checks`
after a lane pushes: a new head means a brand-new run with no jobs registered yet, which reads as a
blank jobs query, not a skipped workflow.
