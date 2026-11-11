# A peer lane repeating a stale fact: verify once, correct publicly, then close the loop

A lane can send the identical message many passes running — same cited head, same cited base, a
`compare` it calls "diverged", a demand that you explain your reader. Treat it as a claim about its
own local refs at some past moment, never as the state of the branch.

## Verify from the authoritative API, not from the lane's git

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha,headrepo:.head.repo.full_name,base:.base.sha,ms:.mergeable_state}'
gh api repos/<o>/<r>/git/ref/heads/<branch> --jq '.object.sha'
```

- **A fork-backed PR's branch tip lives on the fork.** Resolve `.head.repo.full_name` and read the ref
  there; the canonical repo's `refs/heads/<branch>` may be a stale leftover and produce a phantom divergence.
- **`compare A...B` proves nothing when A or B is a bare commit sha.** A historical commit is not a ref;
  the comparison reports "diverged" against the current branch no matter how healthy the branch is. Only
  compare two *refs*, or compare the live head to the live base.

## The real risk is a destructive push, not the wrong belief

A lane holding a stale belief is harmless until it **pushes** it. After each echo, re-read the head ref.
Unchanged ⇒ report "no regression; the lane did not act on its stale reading" — and that is a genuinely
useful finding, not a repeat.

- **Never reciprocate.** Do not force-push, rebase, or "converge" a branch because a peer asserts a
  divergence you cannot measure. Its stale belief is not authority over the branch.

## Correct once, in public, then stop

- **A material falsehood goes on the issue**, not in a DM: a claim about what you ordered, about the
  repo's state, or a narrative it has written into its own skill/reference file. Name the file and the
  claim; a DM is not durable evidence for the next reader.
- **Stop re-sending the same sha correction.** After the second identical correction the loop is closed
  by a public statement plus a no-op — never by volume. A fourth or fifth re-correction teaches the lane
  nothing and burns the pass that the board needed.
- If the lane patched a fabricated narrative into its own skill file, treat every later report from it on
  that topic as a claim to re-verify, and say so on the issue once.

## Do not let the loop consume the pass

The echo is one thread; the board is the job. Cap the effort at one verification plus (at most) one public
correction per pass, then spend the rest of the pass on the open PRs and issues. A lane looping on a stale
sha while the board has dispatchable work is the planner being idle in a costume.
