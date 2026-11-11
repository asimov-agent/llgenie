# Git Maintenance — Large Repo Checklist

## Full Tuning Reference for Repos >5GB

When a repo exceeds 5GB or commands consistently timeout, apply these in order:

### 1. Current State Assessment

```bash
du -sh .git/
du -sh .git/objects/pack/
git count-objects -vH
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | sed -n 's/^blob //p' | sort -rn | head -20
```

### 2. Config Settings

Apply to `.git/config` (or `~/.gitconfig` for global):

```ini
[core]
    bigFileThreshold = 512m
    packedGitLimit = 512m
    packedGitWindowSize = 512m
    preloadIndex = true
    fscache = true
[http]
    postBuffer = 524288000
    lowSpeedLimit = 1000
    lowSpeedTime = 60
[pack]
    windowMemory = 512m
    threads = 2
    deltaCacheSize = 256m
[repack]
    usedeltabaseoffset = 1
[fetch]
    writeCommitGraph = true
[feature]
    manyFiles = true
```

### 3. GC Strategy

| Scenario | Command |
|---|---|
| Quick cleanup | `git gc` |
| Full compaction | `git gc --prune=now --aggressive` |
| Repack only | `git repack -a -d --window=256 --depth=50` |
| Remove unreachable | `git prune --expire now` |
| Full verify | `git fsck --full --strict` |

### 4. If GC Keeps Failing

```bash
# Check for permission issues
find .git -not -user $USER -ls

# Fix ownership
sudo chown -R $(whoami):$(whoami) .git/

# Check for corrupted objects
git fsck --full

# If objects are corrupted, try recovering from remote
git fetch --all
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 5. Disk Space Recovery

After gc, compare:
```bash
du -sh .git/        # Before
git gc --prune=now --aggressive
du -sh .git/        # After
```

For multi-GB repos, expect 40-60% reduction after aggressive gc.

### 6. Common Timeout Fixes

| Symptom | Fix |
|---|---|
| `git push` times out | Increase `http.postBuffer` and `lowSpeedTime` |
| `git status` slow | Enable `core.fscache` and `core.preloadIndex` |
| `git log` slow | Disable `log.decorate`, enable `commitGraph` |
| `git add` slow on large files | Increase `core.bigFileThreshold` |
| `git diff` slow on binaries | Enable `core.bigFileThreshold` |
| Clone fails mid-way | Use `--depth 1` for shallow clone first |
