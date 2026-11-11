# Armed auto-merge that never fires: finding the real gate

`autoMergeRequest` non-null + `mergeStateStatus: BLOCKED` is the normal, correct state while some gate is still
red. Do not call it misconfigured, and do not re-arm it. Name the gate, then name who can clear it.

## Procedure

1. **Read the PR's full gate picture in one call.** `--json` belongs to `gh pr view`, not `gh api`:

   ```bash
   gh pr view <n> --json autoMergeRequest,reviewRequests,reviewDecision,mergeStateStatus,mergeable,latestReviews \
     --jq '{autoMerge:(.autoMergeRequest // "NULL"),requested:[.reviewRequests[].login],reviewDecision,mergeStateStatus}'
   ```

2. **`reviewDecision: REVIEW_REQUIRED` needs a rule to exist somewhere.** Enumerate every ruleset, then open each
   one — the list endpoint gives id/name/target only, not rule types:

   ```bash
   gh api repos/{owner}/{repo}/rulesets --jq 'map({id,name,target,enforcement})'
   gh api repos/{owner}/{repo}/rulesets/<id> --jq '{name,enforcement,target,types:[.rules[].type]}'
   ```

   Then check legacy protection: `gh api repos/{owner}/{repo}/branches/main/protection` — a 404 means none.
   `/orgs/<org>/rulesets` 404s on a user-owned repo; that says nothing about repo-level rulesets.

3. **If no ruleset carries a `pull_request` rule, the required review resolves to the PR itself** — an approving
   review must be submitted and auto-merge fires the instant it lands. Say that plainly; it is not a stuck queue.

4. **Identify the approver, then request it explicitly instead of announcing that "an approval is needed".** The
   PR author cannot approve its own PR, and in this fleet every lane authors with one shared token, so no lane may
   self-approve. The approver is the account with write/admin on the repo:

   ```bash
   gh pr view <n> --json author,headRepositoryOwner --jq '{author:.author.login,fork_owner:.headRepositoryOwner.login}'
   gh api repos/{owner}/{repo} --jq '.owner.login'
   ```

   A fork-authored PR (`fork_owner` != repo owner) means the repo owner account is the approver.

   ```bash
   gh api -X POST repos/{owner}/{repo}/pulls/<n>/requested_reviewers -f 'reviewers[]=<account>'
   gh api repos/{owner}/{repo}/pulls/<n>/requested_reviewers --jq '[.users[].login]'
   ```

   The POST response need not echo `users` (jq'ing `.users[]` on the POST body can error `cannot iterate over:
   null`) — a response-shape artifact, not a failed request. Verify with the separate GET.

5. **Never approve or merge.** Request the review, post the measured state, and report the single unblock
   condition: "owner approval on #<n>; auto-merge is armed and fires on its own".

## Pitfalls

- `gh api` rejects `--json` and `--raw` — those are `gh pr view` / `gh run view` flags. Repeating the call with the
  flag does not help; use `--jq` / `--template`.
- Verify a reviewer request or a posted comment with a follow-up GET by exact id/login. A successful POST is not
  proof the board changed.
- A `requested_reviewers` hit with an older `reviewRequests: []` read means one of the two reads is stale — re-read
  before reporting either state.
