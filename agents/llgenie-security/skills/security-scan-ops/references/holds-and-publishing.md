# Publishing findings and holding PRs (this lane's form)

## A scan result nobody can see is not a finding

A finding's value is that another person can go and check it. So:

- The finding goes **on the issue/PR**, with the sha it was measured at, the run id and the scanner digests.
  A report against a tree that has moved is false on arrival, and "critical in <package>" without a run id is
  a claim about a database snapshot, not about this tree.
- Genuinely sensitive detail goes to the private channel first, but the **existence and the reference stay
  traceable** — a private note with no public pointer is an exposure nobody owns.
- Claim before you start: a comment on the issue/PR naming the branch and what "done" means. Re-read the
  thread before the first edit; an existing claim or a note from the lane that touched the files last
  outranks your plan.
- When the work overlaps another lane (`scripts/`, `.github/workflows/`, anything the scan reads),
  **message that lane with the scanned sha and what you need**, then post the conclusion in the issue.
  Silence between two lanes on one set of files is how a green gets discarded twice.

## A security hold must carry its remedy

A security defect **is** grounds for `do-not-merge` — which is exactly why an untracked hold is itself a
finding: nobody else can judge whether the exposure still applies, and `mergeStateStatus` reads `BLOCKED`
for a live hold and an abandoned one alike.

Every hold, in one PR comment:

1. **the exposure** — what is reachable, and how it was measured;
2. **the issue** that closes it, by number;
3. **the removal condition** — a patch, a policy change, or a scan showing absence, at a named sha.

The lane then removes the tag itself once that evidence exists, quoting the sha or run id in the removal
comment. Never hold to say "I am not confident": that is a review comment, not a label.

## Clearing a hold, end to end

```bash
git fetch origin && git log --oneline origin/main -1          # base the condition is judged against
git rebase origin/main                                        # continue an interrupted one
git push --force-with-lease=<branch>:<old-sha> --force-if-includes origin HEAD:<branch>

# prove closure with the real scanner, not the checks summary
make sbom && make security-scan TOOL=trivy
python3 scripts/security_scan.py verdict --event schedule      # expect: 0 finding(s)

# name issue + sha + that output in a PR comment, then lift it yourself
gh pr edit <n> --remove-label do-not-merge
```

After lifting, re-read the PR and say which `BLOCKED` reason remains: *pending checks*, *review required*, or still a hold.
