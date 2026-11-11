# Verifying a lane's "the fix is already staged in PR <X> — a new PR would be a #824 duplicate" decline

A lane declining a dispatch on ownership grounds often rests on: *"the fix is already staged in the owner-held PR <X>, so a fresh PR from me would be a duplicate vehicle."* That is a claim about X's **current** payload, and it is frequently **false** — the lane has confused a *planned*, *remembered*, or *superseded* commit with one actually committed to X. Two one-call checks settle it:

```bash
# 1. is the claimed fix-commit ACTUALLY an ancestor of X's real head?
git merge-base --is-ancestor <fix-sha> <PR-head-sha> && echo "in head" || echo "NOT in head"
# 2. does X's diff even TOUCH the file/seam the fix belongs to?
gh pr diff <X> --name-only | grep -E '<file-or-dir>'
gh pr diff <X> | grep -A6 -B6 '<file>'   # read the actual hunks, not only the filename list
```

`merge-base --is-ancestor` returning non-zero (**NOT in head**), plus a diff that touches only an unrelated two-line change in that file, together **refute** the decline: the seam is staged nowhere and the fix is not in X. The stacked/superset nuance is real — an un-committed superset commit (the `ff5e19e1` class) is kept rebased on top of a merge and never appears in X's head — so a "not in head" result is *consistent* with a pending staged payload, but it is NOT a reason to accept the decline as fact or to open a parallel vehicle blindly.

**Resolve on the durable on-issue thread, not a DM** (loop-prone lanes reject planner DMs on a full queue). Name the two measures — ancestor false, diff does not touch the seam — and let the declining lane either take the issue or name the lane that should. Do not open the parallel vehicle yourself on an unverified decline; do not accept the decline as fact either. The check is the arbiter and resolves in one call each way.

Measured instance: a lane declined the FROM-local-load engine-build red citing "#1696 carries the `_buildx()` superset fix (`ff5e19e1`)"; `merge-base --is-ancestor ff5e19e1 <#1696-head>` → false, and #1696's diff to `scripts/engine_image.py` was a two-line report-format change touching no builder seam. The red was genuinely unowned; the correction went on the issue thread.
