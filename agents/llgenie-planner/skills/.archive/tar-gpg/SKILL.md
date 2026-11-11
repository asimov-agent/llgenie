---
name: tar-gpg
description: >
  Encrypt and decrypt files/folders using tar + GPG symmetric encryption.
  Covers creating .tar.gpg archives with passphrase prompt, decrypting back
  to original paths, and safety guards (set -euo pipefail) to prevent data
  loss. Triggers: encrypt folder, gpg encrypt, tar gpg, secure archive,
  decrypt tar.gpg, symmetric encryption, protect files, archive encrypt.
---

# Tar + GPG: Symmetric Encryption for Files and Folders

Encrypt files or folders into a `.tar.gpg` archive protected by a GPG
passphrase, and reverse the operation. Useful for secure backups, sensitive
data at rest, or transferring files to cold storage.

## When to use

- User wants to encrypt a folder or file with a passphrase
- User wants to securely archive something (optionally removing the original)
- User has a `.tar.gpg` file and wants to extract it

## Encrypt

```bash
tar-gpg.sh /path/to/folder [output_name]
```

- Archives the folder with **relative paths** (uses `tar -C dirname basename`)
- Pipes to `gpg --symmetric --cipher-algo AES256` (prompts for passphrase)
- Removes the original folder after success (only on success — see Safety)
- Default output name is `<folder>.tar.gpg` if not specified

## Decrypt

```bash
untar-gpg.sh file.tar.gpg
```

- Decrypts with GPG (prompts for passphrase)
- Extracts with `tar xf -` to the original folder name
- Removes the `.tar.gpg` after success

## Safety

Both scripts use `set -euo pipefail`. This means:
- If `tar` or `gpg` fails, the script exits immediately
- The `rm -rf` only runs after both commands succeed
- No accidental source deletion on encryption/decryption failure

**Always verify the archive before relying on source removal:**
```bash
gpg --decrypt file.tar.gpg | tar tf -   # list contents without extracting
```

## Notes

- No explicit compression: `tar cf` is archive-only. GPG applies zlib
  compression internally, but it's less efficient than gzip/zstd.
- For better compression, pipe through `zstd` or `gzip` before gpg:
  `tar cf - folder | zstd | gpg --symmetric -o folder.tar.zst.gpg`
- For decrypting compressed variants: `gpg --decrypt file | zstd -d | tar xf -`

## User preferences

- Remove the original folder/file after successful encryption
- Restore to the same folder name on decrypt
- No compression by default (can be added if requested)

## References

- `references/compression-variants.md` — notes on adding zstd/gzip compression
- `scripts/tar-gpg.sh` — encrypt script (tar + gpg symmetric, removes source on success)
- `scripts/untar-gpg.sh` — decrypt script (gpg + tar, removes .tar.gpg on success)
