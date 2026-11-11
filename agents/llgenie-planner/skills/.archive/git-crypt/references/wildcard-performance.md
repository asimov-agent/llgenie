# Wildcard .gitattributes Performance Impact

The pattern `* filter=git-crypt diff=git-crypt` in `.gitattributes` encrypts
every tracked file in the repository. This causes significant slowdowns
on large repos.

## Symptoms

- `git-crypt unlock` takes minutes (rewrites index + working tree)
- `git status`, `git diff`, `git add` are slow
- All files must be decrypted/encrypted on every operation

## Example

Repo with 19,000+ files totaling 352MB:
- `git-crypt unlock` → several minutes
- Every git operation → decryption/encryption overhead

## Recommendation

Replace wildcard with specific paths:

```
# Instead of:
* filter=git-crypt diff=git-crypt

# Use:
.env filter=git-crypt diff=git-crypt
*.pem filter=git-crypt diff=git-crypt
secrets/** filter=git-crypt diff=git-crypt
```

Encrypt only files that actually contain secrets. Keep `.gitattributes`,
`.gitignore`, and other non-sensitive files unencrypted.

## Fixing an existing repo

1. Edit `.gitattributes` to list specific files instead of `*`
2. Commit the change
3. Re-export the key (files already encrypted stay encrypted)
4. Collaborators must pull and re-unlock
