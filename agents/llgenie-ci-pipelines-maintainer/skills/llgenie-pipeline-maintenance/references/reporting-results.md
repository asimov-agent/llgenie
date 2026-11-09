# Reporting a result: read it back, never guess

A lane's report is only as good as the numbers in it. A wrong PR number, a guessed sha, or a stale
run id makes the planner act on a premise that does not exist. The rule: **every identifier in a
report is read from the live record in the same turn you report it.**

## Getting the PR number

`gh pr create` prints the PR URL (`.../pull/<n>`) on success — capture that number. If you did not
keep it, or you want to confirm, use exactly one command:

```bash
gh pr list --repo asimov-agent/llgenie --head <branch> --state all --json number --jq '.[0].number'
```

- `--head <branch>` matches the branch as pushed (`gh pr list --head andyholst:<branch>` also works
  for a fork head).
- `--state all` finds it whether open, merged, or closed.
- The scalar `.[0].number` is the answer. If it prints nothing, no PR exists for that head — that is
  a fact, not an error, and the next step is to create one, not to guess a number.

Re-running `gh pr create` on an existing head is a valid existence probe: it exits non-zero with
`a pull request for branch "..." into branch "..." already exists: <URL>`. The URL carries the
number. Do this at most once — it is a probe, not a loop.

## When `gh pr create` refuses the head

`gh pr create -R asimov-agent/llgenie --base main --head <branch>` fails with
`Head sha can't be blank, Base sha can't be blank, No commits between main and <branch>` when the
branch exists only in a fork — an unqualified `--head` resolves branches in the BASE repository only.
The message never says "fork" and it arrives as a GraphQL error, so it reads like a transient glitch;
re-running the identical command fails identically. Read the branch's location first
(`git ls-remote origin <branch>` plus
`gh api repos/asimov-agent/llgenie/branches/<branch> --jq .commit.sha` → 404 means fork-only), then
choose ONE remedy and state which: push the branch to the base repo, or qualify the head in the same
call — `--head <forkowner>:<branch>`. Verify the create landed by reading `headRefOid` and
`isDraft` back; a fork head does not change either.

## When a result will not render

If a tool result looks empty or truncated (a file you wrote reads back blank, a JSON body looks
cut off), the fix is one re-run printed as a bare scalar, not a fan of probes:

```bash
P=$(gh pr list --repo asimov-agent/llgenie --head <branch> --json number --jq '.[0].number')
echo "PR=$P"
```

A short scalar `echo` renders reliably where a multi-KB JSON dump or a write-file→read-file round-trip
may not. Do not: write a marker file in N different places, try five `gh api`/`graphql` shapes, or
scan `/tmp` for a previously-written answer file. Those spread the same uncertain read across many
calls and still leave you guessing.

## What a result report must carry

Bookend every fix with two comments (start = branch + base sha + what "done" means; finish = head
sha + what changed + the run id or command that proves it). No PR number, sha, or run id goes into a
report until it has been read back this turn.

## Post the finish bookend on the thread that CARRIES the finding, not a tangential vehicle's PR

A routing conclusion ("gate is working, no fix owed" / "this red is X") belongs on the thread where
the FINDING lives — the merge-verification record on the merge vehicle's PR/issue, the issue the red
was filed against — never on a side PR that happens to be your own open vehicle. A conclusion posted
only on a tangential PR is invisible to the reader who owns the finding, so it reads as unanswered.
When a dispatch says "planner route posted on the merge thread context," find that exact thread
(`gh api repos/<o>/<r>/issues/<merge-pr-or-issue>/comments`, read the newest planner MERGED-/
verification record) and post the finish bookend there; a same-content comment on your own PR does
NOT satisfy it, and DMing the planner does not substitute for the on-thread record. Verify the post
by DIRECT id read-back (`gh api repos/<o>/<r>/issues/comments/<new-id>`), because the comments LIST
endpoint on this host can return a stale last item even after a successful POST.
