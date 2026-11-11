# Re-verifying a lane's "re-anchored" citation

A lane that reports *"re-anchored the `(proven:)` / `verdict-ref` citation to head X"* has fixed drift
once; it has not proven it cannot drift again. The PR is frequently rebased again in the minutes
between the lane's measurement and your pass, so the sha it moved **to** is often already stale.
Verify the fix with the same check that produced it.

## Procedure

1. Resolve the live head from the API, not from the lane's report:

```bash
gh api repos/<owner>/<repo>/pulls/<n> --jq '{head: .head.sha, base: .base.sha, ms: .mergeable_state, upd: .updated_at}'
```

2. Test the cited sha against the live head in two independent steps:

```bash
git merge-base --is-ancestor <cited> <live>                # ancestry
git diff --quiet <cited> <live> -- <graded files>          # graded-file identity (rc=0 = identical)
```

3. Read the outcome off both facts, never off ancestry alone:

| ancestry | `git diff` | Meaning | Action |
|---|---|---|---|
| false | rc=0 | content-move rebase: files identical, only the sha moved | **no re-judge owed**; one-line citation fix to the live head |
| false | rc≠0 | graded content genuinely changed under the pin | the lane must re-judge; prior ticks are unproven |
| true | any | pin still valid, string merely behind | nothing owed |

4. Dispatch the correction naming the live sha and the commands run, and state explicitly that **no
   re-judge is owed** when the files are byte-identical — otherwise the lane burns a run re-grading
   identical content, or reads a citation complaint as a verdict complaint.

## Why this shape

The failure repeats because "re-anchored" is a claim about a moment, exactly like the stale head it
replaced. Byte-identity is the fact separating *the citation is ugly* (cosmetic — fix the string) from
*the verdict is void* (re-judge). Quote the measured live sha and the command output behind the ruling.

## Bookkeeping the result in your own ledger

When patching a markdown ledger whose `old_string` is a section header you are inserting **above**,
repeat that header in `new_string`. A bare replace silently consumes the header and folds every bullet
under it into the previous section. After the write, confirm the heading count moved by exactly the
number of sections added:

```bash
grep -c '^## ' <ledger>.md
```
