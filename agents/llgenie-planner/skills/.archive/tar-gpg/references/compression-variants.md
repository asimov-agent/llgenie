# Compression Variants

## Default (no explicit compression)

```bash
tar cf - folder | gpg --symmetric --cipher-algo AES256 -o folder.tar.gpg
```

GPG applies zlib compression automatically but it's not optimal.

## With zstd (recommended)

```bash
tar cf - folder | zstd -19 | gpg --symmetric -o folder.tar.zst.gpg
```

Decrypt:
```bash
gpg --decrypt folder.tar.zst.gpg | zstd -d | tar xf -
```

## With gzip

```bash
tar cf - folder | gzip -9 | gpg --symmetric -o folder.tar.gz.gpg
```

Decrypt:
```bash
gpg --decrypt folder.tar.gz.gpg | gzip -d | tar xf -
```

## With xz (best compression, slowest)

```bash
tar cf - folder | xz -9 | gpg --symmetric -o folder.tar.xz.gpg
```

Decrypt:
```bash
gpg --decrypt folder.tar.xz.gpg | xz -d | tar xf -
```

## Recommendation

- **zstd** for most cases — fast, good ratio, widely available
- **xz** for archival where size matters more than speed
- **gzip** for maximum compatibility
