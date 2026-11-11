# Classifying a named branch: awaiting / just-branched / stalled-claim / vehicle

When you list an issue as "in flight", or retract your own earlier on-issue claim that "no work
started", prove the branch's state — a name is a claim. Measure, then classify into exactly one bin:

```bash
B=fix/<n>-...
git ls-remote origin "refs/heads/$B"                              # empty = not pushed
git rev-parse "refs/heads/$B" 2>/dev/null                         # local tip (empty = no local ref)
git rev-list --count "origin/main..$B" 2>/dev/null                # commits ahead of main
gh pr list -R <o>/<r> --head "$B" --json number,state             # empty = no PR
```

- **awaiting branch** — no local ref, not pushed, no PR. Holds no vehicle; blocks no fresh dispatch;
  never count as a lane's load. `gh pr merge --auto` on this phantom arms nothing yet reports success.
- **just-branched (work commencing)** — local ref tip **== `origin/main`**, ahead-count **0**, not
  pushed. This is the lane ACTING on your dispatch, not a deliverable and not a correction target.
  Do not retract your dispatch premise and do not route a second item on it.
- **stalled-claim (publishing debt)** — local ref with **ahead-count > 0** (real commits) but
  `git ls-remote` empty and no PR. Work is stranded where a prune/cleanup destroys it; the dispatch is
  binary — rebase onto fresh `origin/main`, push, open the PR ready-for-review (`Closes #<n>`,
  `AGENTS:` line, base sha) and report PR#/head/run-id — OR release the claim with the owning-lane
  reason. Never count it as "the lane is busy".
- **vehicle** — pushed ref and/or an open PR exists. Only this counts as in flight.

The ahead-count is what separates just-branched from stalled-claim — always check it before
classifying.

## Retracting your OWN earlier claim: was it stale when posted, or overtaken after?

Before you "correct" your own on-issue statement (e.g. "no work started"), settle the timing with the
branch reflog against your post's `created_at`:

```bash
git reflog show --date=iso refs/heads/$B | tail -1   # 'branch: Created from origin/main' @ <local time>
```

The reflog stamps the **host clock offset** (e.g. `+0100`); API `created_at` is **`Z` (UTC)**. Convert
before comparing: a `+0100` reflog timestamp minus one hour is its UTC value. If the branch was created
**after** your post, your claim was accurate when made — record the lane's pickup (branch, `main` sha,
ahead-count) and do **not** retract. A branch created a minute after a dispatch is the lane
responding, not proof your dispatch falsely preceded the work.
