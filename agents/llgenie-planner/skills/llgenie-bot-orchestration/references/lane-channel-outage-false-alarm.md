# Lane reports a dead channel (exit 126): a deleted workdir, not an outage

A lane reporting "every shell dropped output / exited 126, so I could NOT wire-confirm X" is usually not
describing a real outage: its **persistent shell workdir was deleted** (a pruned `wt*` / `/tmp` worktree),
so every command dies `cd: No such file or directory` -> exit 126 before doing anything. The lane then
honestly reports "unconfirmed" for an artifact that DID land.

Do not accept the outage claim as evidence either way, and do not ask the lane to re-post. Verify the
artifact yourself by ID and close the loop:

```bash
gh api repos/<o>/<r>/pulls/<n>/reviews \
  --jq '[.[]|select(.user.login!="<self>")|{id,state,at:.submitted_at[0:16],body:(.body//"")[0:40]}]'
```

A review with `state=COMMENTED` and a body headed `Review @ <head>` is posted — tell the lane it landed
and name the false alarm as a workdir, not a channel.

When YOUR OWN shells start failing this way mid-pass, pass an explicit `workdir=` on every call instead of
trusting the persisted cwd.

## Base-gate corollary: a green, verdict-ticked PR can go red on `check-pr-base` alone when `main` advanced

After a merge advances `main`, a previously-green PR re-runs its guard and can fail **only** `check-pr-base`:
its merge-base is the old base, so it carries "foreign commits" (#845). The AC verdict/ticks stay valid (they
pin a verdict at a sha, not a branch) — the sole unblock is rebasing onto the new live base and force-pushing.
Route that to the vehicle's owning lane; never rebase another lane's branch yourself, and never read the base
red as "the change is wrong".
