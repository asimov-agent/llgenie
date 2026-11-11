#!/usr/bin/env python3
"""Scan downloaded GitHub Actions run logs + artifacts for leaked secrets.

Usage:
    python3 scan-ci-secrets.py LOGDIR [ARTDIR]

LOGDIR holds the unzipped run logs (one file per run). ARTDIR (optional) holds
artifact files; a file that is gzip (dockerbuild records) is decompressed on
the fly, a zip is read through zipfile. Scans for:
  * credential SHAPES (ghp_/gho_/ghu_/ghs_/ghr_, github_pat_, fc-, hf_, sk-,
    ev_, Bearer <token>, JWT, user:pass@ URL, private key) — catches a token
    that never entered this process's environment;
  * the literal VALUE of every secret present in the local env, in raw,
    base64, URL-encoded and prefix spellings.

Prints a per-file hit list with surrounding context (so a false positive like a
signed blob URL or a variable NAME in a fixture can be ruled out) and a summary
of which secret values were checked literally vs by shape only.

Exit 0 always (it is a report, not a gate).
"""
from __future__ import annotations

import base64
import gzip
import os
import re
import sys
import urllib.parse
import zipfile
from pathlib import Path

SHAPES = (
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bfc-[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(rb"\bev_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(rb"[A-Za-z0-9._%+-]+:[^@\s]{8,}@[A-Za-z0-9.-]+"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

#: Secret env vars to check literally. Only those present in THIS shell are
#: actually searched; the rest are shape-only. Extend per repo.
SECRET_VARS = (
    "NOUS_API_KEY", "NOUS_PORTAL_API_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
    "FIXBOT_DISPATCH_TOKEN", "HF_TOKEN", "TYPESAFE_API_KEY", "FIRECRAWL_API_KEY",
)


def iter_bytes(path: Path):
    """Yield the raw bytes of a log/artifact file, decompressing as needed."""
    head = path.read_bytes()[:2]
    if head == b"\x1f\x8b":  # gzip (dockerbuild records are gzip, not zip)
        with gzip.open(path, "rb") as f:
            yield f.read()
    elif head == b"PK":  # zip of logs
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                yield z.read(n)
    else:
        yield path.read_bytes()


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    logdir = Path(sys.argv[1])
    artdir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    literal = {v: os.environ.get(v) for v in SECRET_VARS if os.environ.get(v)}
    spellings = {}
    for name, val in literal.items():
        b = val.encode()
        spellings[name] = [b, base64.b64encode(b), urllib.parse.quote_plus(val).encode(), b[:16]]

    files = sorted(logdir.rglob("*")) if logdir.is_dir() else []
    if artdir and artdir.is_dir():
        files += sorted(artdir.rglob("*"))

    total_lines = 0
    hits = 0
    for f in files:
        if not f.is_file():
            continue
        for blob in iter_bytes(f):
            total_lines += blob.count(b"\n")
            for m in re.finditer(rb"[^\n]*\n", blob):
                line = m.group(0)
                for pat in SHAPES:
                    for sm in pat.finditer(line):
                        ctx = line[max(0, sm.start() - 120):sm.end() + 40].decode("latin1")
                        print(f"SHAPE {pat.pattern[:20]!r} {f} :: {ctx!r}")
                        hits += 1
                for name, forms in spellings.items():
                    for form in forms:
                        if form in line:
                            print(f"VALUE {name} {f} :: {line[:200]!r}")
                            hits += 1

    print(f"\nlines {total_lines}  hits {hits}")
    print("literal-checked:", ", ".join(sorted(literal)) or "(none in env)")
    print("shape-only:", ", ".join(v for v in SECRET_VARS if v not in literal) or "(none)")


if __name__ == "__main__":
    main()
