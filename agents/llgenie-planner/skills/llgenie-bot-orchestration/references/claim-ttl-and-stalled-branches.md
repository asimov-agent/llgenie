# Claim-TTL: a branch with no PR is stalled, not in flight

A branch is not progress. Measure three axes before you describe an issue as being worked on, and
re-measure them on every pass — the answer changes without anyone telling you:

```bash
gh api "repos/<owner>/<repo>/pulls?state=all&head=<fork>:<branch>" --jq 'length'   # PRs for that head
gh api repos/<owner>/<repo>/issues/<n>/comments --jq '.[-1] | "\(.created_at) \(.user.login)"'
git ls-remote --heads <remote> <branch>                                            # head sha, vs your last reading
```

**A claim is live only if the head moves, a PR exists, or the lane answers.** Head sha unchanged since
the last pass + zero PRs for that head + no reply to the dispatch or the open-PR reminder = the claim
has expired, even though commits exist and the branch looks substantial. The tell that separates
"stalled" from "blocked": the lane is answering *other* threads in the same window. A lane that talks
elsewhere and not here is stalled on itself, not on a gate.

When it has expired, **record it as expired on the issue** with the branch head sha, the commit
window, the dispatch and reminder comment ids, and three ordered unblock conditions:

1. open the PR (ready-for-review, never draft, with the preflight/`closes` gates);
2. or post the standing state line (`BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> ·
   blocked on <x|none> · next <y>`) naming the specific blocker — "a stalled branch with no PR" is
   not a blocker report;
3. or hand the issue back, at which point it is re-dispatched.

**Never dispatch a second implementer behind a live claim** — that is the two-lanes-one-issue race, and
two abandoned branches instead of one. **Never force-push a branch a lane owns**, even to "fix" it.
The board, not a DM, is where "expired" has to be legible: an unmeasured branch and an abandoned one
look identical to the next reader.

## Post an acceptance-criteria disposition on the issue that owns the criterion

When a criterion cannot be ticked, the note belongs on **the issue whose AC it is**, not only on the
PR or on the child issues that explain the red. The issue thread is what the owner and the review gate
read; a disposition that exists only on the blocker issues leaves the criterion looking simply
unanswered. State the failing jobs and ids, whether the deliverable is nonetheless proven, the two
honest exits (wait for the blockers, or scope the criterion into a not-covered section), and the one
thing that must not happen (ticking the box on partial evidence, or merging a `closes #n` while the box
is unticked).

## When read-only tools are gated mid-pass

A mutation-first guard that pauses reads makes "measure then decide" impossible for one turn. Land the
mutation whose facts you already measured earlier in the session (the AC disposition, the claim-TTL
record, the routed finding), verify it by reading the created object back by id, then resume measuring.
Never invent a measurement to satisfy the guard, and never write a scratch file to satisfy it — that is
the one move the guard is designed to refuse.
