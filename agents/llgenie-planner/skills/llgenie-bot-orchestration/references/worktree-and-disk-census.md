# Worktree + disk census: measure and report, never prune

Owner-domain work when the queue is thin. `make worktree-prune`, `git worktree prune` and
`git worktree remove` are **forbidden to every bot** unless the owner says otherwise: the prune's
"already merged" test reads the branch ref only, so it cannot see uncommitted work and will destroy
a run that is mid-flight. The sanctioned form is measurement (`make worktree-report`) plus a report.

## The measurement

```bash
df -i /tmp; df -h /tmp                       # inode + space pressure, as of NOW
git worktree list --porcelain | grep '^worktree '
git worktree list | awk '{print $1}' > /tmp/wtlist.txt
echo "total: $(wc -l < /tmp/wtlist.txt)"
grep -c '^/tmp/' /tmp/wtlist.txt              # split by location
# registered-but-gone check (a consistent registry reports 0)
while read -r d; do [ -d "$d" ] || echo "GONE: $d"; done < /tmp/wtlist.txt
# orphan detection: dirs matching worktree patterns that the registry does NOT know
ls -d /tmp/wt* /tmp/pl_* 2>/dev/null | wc -l   # compare against the registered count
```

## Reading the numbers

- **Report the present figure; do not inherit the issue's premise.** A pressure tracker written at
  85% may sit at 22% today — say "not currently binding, which is not evidence the habit was
  fixed", never "resolved" (that closes a class on a snapshot) and never repeat "still 85%".
- **`git worktree list` count is the durable accumulation number.** Hundreds of entries each carry a
  full checkout; the split by location matters because the bulk usually sits under the normal repo
  parent (real disk), not the tmpfs the issue is about. A tmpfs cleanup cannot touch that.
- **Zero registered-but-missing dirs = the registry is consistent.** Say it explicitly so a reader
  does not assume corruption.
- **The recoverable thing is often ORPHAN DIRECTORIES, not inodes.** Directories matching worktree
  naming patterns that exceed the registered count are leftovers no `git worktree list` knows about;
  only a directory listing finds them. Give the approximate count, not a deletion plan.
- **Measure means measure.** Do not delete, do not re-point a ref, do not "tidy" one obviously stale
  directory: a worktree that looks merged can hold the only copy of an uncommitted fix.

## Report shape (post on the tracker issue)

1. The raw numbers: inode %, space %, total worktrees, per-location split, missing-dir count,
   pattern-matching dirs vs registered.
2. An honest reading: which figure is a snapshot, which is structural.
3. An explicit "what I will not do" line naming the forbidden commands and why.
4. A **proposal for owner decision**, each item owner-gated: adopt the report target as periodic
   measurement instead of the destructive prune; decide a retention rule for the real-disk
   accumulation; state that orphan tmpfs dirs need an explicit owner sweep.
5. Close with "no cleanup performed, no worktree removed" — the absence of action is the point, and a
   body that leaves it ambiguous reads as an undocumented deletion.
