# Open-issue/PR landscape sweep (gap analysis)

A read-only pass that finds: issues whose premise `main` has invalidated, several issues for one root, and
structural gaps no open vehicle owns. It ends in a findings list to the inbox — **no issue filed, no branch,
no merge** unless the dispatch says otherwise.

## 1. Fix the baseline first

```bash
gh api repos/asimov-agent/llgenie/commits/main --jq .sha   # the sha every finding is measured at
```

Quote that sha in the report. A finding without a head is a claim about time, not about the branch.

## 2. The open landscape, in one command per surface

The reliable jq form wraps the stream in an ARRAY LITERAL and joins — a bare `.[] | "..."` piped into
`sort -n` interleaves and can read empty, which looks like "no PRs" rather than a formatting miss:

```bash
# PRs: state + review + arm
gh pr list --repo asimov-agent/llgenie --state open --limit 50 \
  --json number,mergeStateStatus,reviewDecision,autoMergeRequest,baseRefName,headRefOid,isDraft \
  --jq '[.[] | "#\(.number) ms=\(.mergeStateStatus) rv=\(.reviewDecision // "none") auto=\(.autoMergeRequest != null) base=\(.baseRefName)"] | sort | join("\n")'

# issues, for closed-by / open-but-fixed detection
gh issue list --repo asimov-agent/llgenie --state all --limit 900 --json number,title,state,labels
```

Field-name gotchas that error rather than default:
- `draft` is not a PR field — it is `isDraft`.
- `reviewDecision` is null on an unrequired PR; `// "none"` normalises it instead of printing `null`.
- `autoMergeRequest` present == armed; read `enabledAt` to report the arm time, never the `gh pr merge` exit code.
- For ONE PR's full state, `gh pr view <n> --json state,mergedAt,mergeCommit,headRefOid` is cheaper than a list.

All `BLOCKED` + `REVIEW_REQUIRED` + `auto=null` on every open PR is one signal: the owner-approval wall, not
conflict or missing CI. Say that, and do not read `BLOCKED` as "a check failed" (a `REVIEW_REQUIRED` also
reads `BLOCKED`).

## 3. Premise-invalidation checks (the payload of a sweep)

- **Open-but-fixed via `Refs` not `Closes`.** A fix PR whose body said `Refs #N` leaves
  `closingIssuesReferences` empty, so the issue stays OPEN and keeps being force-delegated. Confirm the fix is
  on `main` (`git log origin/main --oneline | grep -i '<scope>'`, or the merge commit sha) before proposing a
  close-with-citation; do not close on the PR title alone.
- **Superseded premise.** An issue whose named "first step" (e.g. "depends on #X") has already merged is no
  longer pending on that step — re-scope it onto what actually remains, or fold its orbit into the issue that
  now owns the residue. Read `main` for the merged commit, not the issue text, to confirm.
- **Closed-by.** `gh issue view <n> --json state,stateReason` plus the merging PR's `mergeCommit`: a sweep
  list that still shows a closed issue as active is stale and must be corrected in the report.

## 4. Redundancy detection

Group open issues by ROOT CAUSE, not by title wording. Three symptoms of one 60-minute-cap ceiling are one
vehicle; a symptom issue, a "measure first" issue and a "hits the cap" report all fix the same thing. When
they collapse, name the ONE implementable issue to keep and the others to fold into it by cross-reference.
Conversely, two issues on the SAME policy but DIFFERENT mechanisms (an entry-point omission vs a helper
indirection) are defensibly two — state the differing mechanism in one line or they are the same issue.

## 5. What "done" is

A findings list the planner can vet and route: per line an issue/PR number, the sha measured at, and the
one-line verdict (invalidated / redundant / survives). Ends with no issue opened and no branch unless the
dispatch authorised it. Report back to the inbox in the same message.
