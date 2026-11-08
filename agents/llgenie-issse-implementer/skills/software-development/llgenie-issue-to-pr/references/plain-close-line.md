# Plain literal `closes #N` — body (gate `check-pr-closing`) and squash-commit messages

**Rule (planner directive):** every PR you open must carry the PLAIN literal `closes #N` (no bold, no code wrap, no colon/space between keyword and `#N`) in BOTH:
1. the PR **body**, and
2. the **joined branch commit messages** (this repo squash-merges with `COMMIT_MESSAGES`, so the commit landing on main is the concatenation of branch messages).

**The gate regex (`scripts/check_pr_closing.py`), exact:**
```python
CLOSING = re.compile(
    r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)(?![#\w])",
    re.IGNORECASE,
)
```
It requires a single literal space between the keyword and `#N`. It MISSES (all verified against the real gate, rc=1):
- `closes **#N**` — markdown bold between keyword and ref;
- `closes: #N` — colon separator;
- a bare `#N` in prose with no (adjacent) keyword.

Only a `closes #N` body with keyword directly before the space-separated ref (lower/upper case both fine) is green (rc=0).

**Why both sets must match:** the body-close set must equal the commit-close set.
- A body that closes **none** while commits close `#N` is its own violation.
- A body-only edit does NOT re-trigger CI — so never let a body rewrite drop or bold-wrap the close line (it silently reds the gate on a stale head with no fresh run to clear it, #1303-class).

**Scope note:** this gate guards only an `agent/*` head branch (the implementing-lane surface). A non-`agent/*` head is out of scope.

**Verified on:** #1328 (body `Addresses and closes **#1327**` — the `**` broke adjacency, #1327 stayed OPEN); #1326 (`Fixes #1322` first-line — correct).

**#1693-class trap: a historical `closes #N` inside prose quotes ALSO reds the gate.** When the body narrates a past event, do not write the exact keyword plus a real issue number (`closes #1646`) even inside backticks — the gate regex is substring-based, so `...by #1655's \`closes #1646\`` on the body is parsed as a close of `#1646` and sets the body close-set to {1646, 1693} ≠ commits {1693}. Write the historical case as the fixer PR number or the defect name instead (`merge-closed by #1655`, or `the #1646 defect`), keeping `#1646` on its own as prose, and keep the ONE close line `closes #1693` flush-left.

**Do:**
- In the body: line `closes #N` plain, one space, no asterisks, no colon.
- In every branch commit message (or at least one) that should close the issue: same plain `closes #N`.
- After any body/commit edit, re-check the gate line is still PLAIN: run
  `python3 scripts/check_pr_closing.py check --body-file <body> --head agent/issue-N` and expect rc=0.
- When a PR carries multiple closes, keep every one plain (`closes #A`, `closes #B`).

**Probing tip (measured):** `python3 scripts/check_pr_closing.py check --body-file /tmp/p.md --head agent/x` runs standalone on the host (host python3 has the argparse/re stdlib it needs).

## A bare trailing `(#N)` in a commit subject or PR title is a CLAIM — distinct from a close keyword

The `check-pr-closing` gate builds the required body close-set from TWO sources: the branch
commit messages (and PR title) AND the body. A **close keyword** (`closes #N` / `fix #N` /
`resolve #N`) on either side adds to the close-set. **Separately, a CLAIM**: any commit subject
or PR title whose LAST token is a bare parenthetical issue ref — `... (#N)` — even with NO close
keyword, registers that issue as claimed and requires the body to adjacently close it, or the
gate reds `squash-commit: the body must adjacently close #N`.

- Consequence: you cannot silently DROP an issue from the body close-set while any branch
  commit subject still ends `(#N)`. Dropping it turns a passing gate into a red — the claim
  survives in the commit text. Either keep the body `closes #N`, or rewrite the commit subject to
  remove the trailing `(#N)`.
- A parenthetical that is NOT the trailing token is NOT a claim: `(issue #N)` mid-subject, or
  `#N` in prose, forces no body close. Measure instead of eyeballing: `git log --format=%s` and
  look for any subject whose final token is `(#N)`; that is the claim set.

**Verify every re-dispatch against the LIVE state, never the first-run log.** A queue re-dispatch quoting a guard job number (`"diagnosed from job 127202129880"`) is stale the moment it is written — the run it cites may have been superseded by a body fix and the PR merged. Before ANY edit, read `gh pr view <n> --json state,mergedAt,mergeCommit` and `gh issue view <n> --json state`: if `MERGED` + issue `CLOSED`, the cited red no longer exists; re-run the gate on the LIVE merged body (`gh pr view <n> --json body`) and report parity (closing references == squash closes == the one claim), refuse-with-evidence on-issue, and NEVER force-push a body edit to a merged/closed PR branch (issue #824: read-only forever; a body push to a closed vehicle is fabrication).
