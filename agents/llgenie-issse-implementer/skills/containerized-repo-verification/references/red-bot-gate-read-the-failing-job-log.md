# A red bot-gate reads the failing job's log before anything else

## The rule

On a red bot-gate, **read the failing job's log first**, root-cause THAT gate, then fix
and re-push. Never report "green", "red", "reviewable" or "mergeable" off a CI conclusion you
have not read; a `conclusion` is a verdict, not a cause, and a fix without the actual log is a
guess (owner standing rule, versioned in the implementer SOUL).

## The mandatory sequence on a red

1. **Name the run and head.** `gh run view <run-id> --json status,conclusion,headSha` — record
   `headSha` (the run's `head_sha`) beside the verdict. A claim about a branch without the sha it
   was measured at is a claim about time, not about the branch.
2. **Find the failing job.** `gh api repos/<owner>/<repo>/actions/runs/<run-id>/jobs --jq '.jobs[] | {id,name,status,conclusion}'` — the row whose `conclusion == "failure"` (or `cancelled`, which is a
   non-verdict, not a pass).
3. **Read that job's OWN log.** `gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences`
   (iterate pages with `?per_page=100` / `Link`; the unit leg is large). Quote the exact failing line:
   the step name, the `[step] FAILED` line, and the Makefile target or script the step runs.
4. **Attribute the root cause to THAT gate.** Use the gate→defect map (below) so the red is
   attributed to the right defect once, then fix it in this vehicle or route it to the lane that
   owns it — never forward it as "another lane's drift" until you have read the log.
5. **Report a fresh conclusion after the fix** with the new run id + head sha. A green report cites
   the completed run id + head sha of the CONCLUDING run; it is not green while any `linux/*` or
   guard/scope row is `in_progress` or `cancelled`.

## The gate→defect map (attribute once)

- **`check-pr-authors` / `AGENTS: <sha> <bytes>b <lines>l` missing or mis-cited** → the PR body's
  `AGENTS:` line is wrong/missing (#792).
- **`BASE≠AGENTS` / stale branch-cut** → the PR body's `BASE:` line, or the branch was cut from a
  base that is not `origin/main`'s current merge-base (#845 / `check-pr-base`).
- **`check-pr-sync-line` missing `SYNC:`** → the PR body omits the required `SYNC:` line (#1724) —
  the classic one-line body omission that looks like "another lane's drift".
- **closing / `check-pr-close`** → the body's `closes #n` line issue matches (#1329).
- **`cancelled` runs** → non-verdicts: diagnose the concurrency/queue, never read as pass or fail
  (#858 / #843).

## Log-read commands verbatim

```
gh run view <run-id> --json status,conclusion,headSha
gh api repos/<owner>/<repo>/actions/runs/<run-id>/jobs --jq '.jobs[] | {id,name,status,conclusion}'
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences
```

## When the log is unretrievable

If the run is still `in_progress` and the endpoint answers "run is still in progress" /
BlobNotFound, say exactly **"error line not yet retrievable — unlocks at run completion"** and
never invent a cause. Never pronounce a PR reviewable or mergeable while a heavy row is unread;
never read a stale `ci-verdict` (attempt-1 artifact) as current truth — wait for a fresh verdict
at the CURRENT head.
