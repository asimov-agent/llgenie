# Session: Large git-crypt repo maintenance (2026-09-14)

**Repo**: singularity (personal Obsidian vault, git-crypt with wildcard .gitattributes)
**Size**: 5.0 GB working tree, 2.87 GiB packed, 157,599 objects

## Problem

User reported git operations timing out on a large git-crypt repo.

## Diagnosis

1. `git count-objects -vH` showed 92 loose objects + 2 packfiles totaling 2.87 GiB
2. `.git/objects/11/` was owned by root (from a prior `sudo git` operation)
3. `git gc` failed with `Permission denied`

## Fix

```bash
# Fix root-owned objects
sudo chown -R asimov:asimov .git/objects/11/
sudo chown -R asimov:asimov .git/

# Compact packfiles
git gc --prune=now --aggressive
```

Result: 2 packs → 1 pack, 2.87 GiB → 2.82 GiB, zero loose objects.

## Config Applied

```bash
git config http.postBuffer 524288000
git config http.lowSpeedLimit 1000
git config http.lowSpeedTime 60
git config core.bigFileThreshold 512m
git config core.packedGitLimit 512m
git config core.packedGitWindowSize 512m
git config pack.windowMemory 512m
git config pack.threads 2
```

## Lesson

- Large git-crypt repos need aggressive gc to keep packfiles compact
- Root-owned objects are a common cause of gc failure — check ownership first
- Config tuning prevents push/pull timeouts on multi-GB repos
