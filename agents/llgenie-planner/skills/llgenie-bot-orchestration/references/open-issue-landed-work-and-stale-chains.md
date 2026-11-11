# Open issue with landed work — completion debt, and stale dispatch chains

## An OPEN issue whose work already landed is a close-with-evidence obligation
An issue still OPEN whose PR/commit already landed on main (the sha is an ancestor of
`origin/main`) and which has NO open vehicle is a COMPLETION DEBT, not a no-op:
- The owning lane must post a **close comment citing the sha + AC evidence** and close the issue.
- It is NOT a "not a next vehicle" drop — that leaves resumable-looking OPEN work forever, and the next pass
  re-derives it as free.
- It is NOT a fresh duplicate PR — a new branch for landed work violates one-vehicle-per-issue.
- When a lane argues "OPEN ≠ unlanded, so not a vehicle", the correct reply is: the work landed, so the
  close comment is the *remaining* task — no new branch. Confirm `git merge-base --is-ancestor <sha> origin/main`
  AND "no open PR for head" from the API before agreeing either way.

## Re-pull the board before dispatching a chain
Dispatch chains go stale within minutes. Before dispatching or re-dispatching a lane's queue:
- Re-read each named item's live state from the API: merged sha + ancestor-of-main, issue `state`/`stateReason`,
  open PR by head.
- A lane's numerical pushback is usually against a **stale snapshot** that crossed with your correction — the
  fix is a fresh API read, not a re-argument. Verify, then agree; do not re-litigate a position you already moved off.
- Accept the drops the API proves (merged/closed), AND independently catch the OPEN-with-landed-work completion
  gap a lane may have misparsed as a no-op.

## Lane boundaries are fixed — route out-of-lane findings, never re-offer
Workflow/gate changes belong to `ci-pipelines-maintainer`; security-scan findings belong to `security`. When an
implementer correctly flags a finding as outside its SOUL boundary, route it to the owning lane (post the id + the
one-line ask) rather than re-offering it to the implementer.
