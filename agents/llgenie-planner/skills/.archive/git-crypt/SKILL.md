---
name: git-crypt
description: >
  Transparent file encryption in Git repositories using git-crypt.
  Covers installation, initialization, key management, and the critical
  pitfall of wildcard .gitattributes on large repos. Triggers: git-crypt,
  encrypt files in git, transparent encryption, git secrets, secret files
  in repo, .gitattributes encryption.
---

# Git-Crypt: Transparent File Encryption in Git

Use git-crypt to encrypt sensitive files in a git repository while keeping
the rest transparently version-controlled.

## When to use

When the user wants to store secrets, credentials, or sensitive files in a
git repo without exposing them in the remote history.

## Installation

```bash
sudo pacman -S --noconfirm git-crypt
```

## Initialization

```bash
cd /path/to/repo
git-crypt init
git-crypt export-key ~/git-crypt-key   # back this up securely
```

## Key Management

```bash
git-crypt export-key ~/path/to/key     # export current key
git-crypt unlock ~/path/to/key         # decrypt files with key
git-crypt lock                         # re-encrypt all files
git-crypt status                       # show encrypted files
git-crypt add-gpg-user <email>         # grant access via GPG
```

## Designating Files to Encrypt

Create or edit `.gitattributes` in the repo root:

```
secret.txt filter=git-crypt diff=git-crypt
*.key filter=git-crypt diff=git-crypt
config/secrets/* filter=git-crypt diff=git-crypt
```

**Commit `.gitattributes`** — it must be tracked for encryption to apply
on clone.

## Pitfall: Wildcard .gitattributes on large repos

The pattern `* filter=git-crypt diff=git-crypt` encrypts **every file**
in the repo. This is simple but has consequences:

- **Unlock speed**: On large repos, `git-crypt unlock` must rewrite the
  index and update the working tree for every tracked file. With 19,000+
  files and hundreds of MB, this can take several minutes.
- **git operations**: Every `git status`, `git diff`, `git add` must
  decrypt/encrypt files, adding overhead.
- **Collaborators**: Everyone with the key sees decrypted files; those
  without see encrypted blobs.

**Recommendation**: Encrypt only the specific files or directories that
need it, not `*`. Example:

```
.env filter=git-crypt diff=git-crypt
*.pem filter=git-crypt diff=git-crypt
secrets/** filter=git-crypt diff=git-crypt
```

## Large Repo Maintenance

Large git-crypt repos (hundreds of MB to GB+) need periodic maintenance to keep `git status`, `diff`, `push`, and `pull` responsive.

### Root-owned objects blocking `git gc`

A previous `sudo git` operation can leave objects owned by root, causing
`git gc` to fail with `Permission denied`:

```bash
cd /path/to/repo

# Find root-owned objects
find .git -not -user $(whoami) -ls

# Fix ownership
sudo chown -R $(whoami):$(whoami) .git/objects/<hash-prefix>/
sudo chown -R $(whoami):$(whoami) .git/
```

Then re-run gc.

### Aggressive gc to compact packfiles

Multiple small packfiles and loose objects slow down every git operation.
Compact into one packfile:

```bash
cd /path/to/repo
git gc --prune=now --aggressive
```

This rewrites packfiles into a single compact pack, significantly reducing
latency on encrypted repos.

## Git Config Tuning for Large Repos

On large repos with git-crypt, tune these to prevent timeouts during
push/pull/status:

```bash
git config http.postBuffer 524288000       # 500MB buffer for pushes
git config http.lowSpeedLimit 1000         # bytes/sec before timeout
git config http.lowSpeedTime 60             # seconds before timeout
git config core.bigFileThreshold 512m      # don't delta-compress files >512MB
git config core.packedGitLimit 512m         # memory limit for pack access
git config core.packedGitWindowSize 512m    # sliding window for pack access
git config pack.windowMemory 512m          # memory for pack compression
git config pack.threads 2                   # limit CPU during pack operations
```

## Pitfall: User prefers terse responses

- Don't explain what git-crypt is unless asked
- Run the command, report result, stop
- If unlock takes time on a large repo, state: "Large repo, decrypting
  N files — this takes a minute" rather than narrating progress

## Verification

After unlock, verify files are decrypted:

```bash
git-crypt status
# Should show: "not encrypted" for .gitattributes, "encrypted" for secrets
```

## References

- `references/wildcard-performance.md` — notes on wildcard .gitattributes performance impact
- `references/large-repo-maintenance.md` — session transcript: root-owned objects blocking gc, config tuning for large repos
