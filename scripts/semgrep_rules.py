#!/usr/bin/env python3
"""Refresh the committed semgrep rules pack from upstream `p/default` (issue #2283 criterion 2).

`containers/scanners/semgrep/rules/default.yml` is the SAST surface a scan runs: it is baked into
the pinned scanner image and content-addressed into `containers/scanners/digests.json`. The
recency floor (criterion 1) forces a re-capture within `RULES_BASELINE_DAYS`, and this is the
other half -- HOW the pack is re-resolved, re-escaped and re-pinned.

Flow (driven by `make semgrep-rules-refresh`, wired into the scheduled
`.github/workflows/semgrep-rules-refresh.yml`):

1. resolve  run the PINNED scanner image's semgrep against upstream `p/default`
            (`semgrep --config p/default --validate`), so the live rule set is
            resolved through the exact engine that will bake it -- the same
            guarantee criterion 1 measures (`--config p/default --validate`
            prints the live rule count).
2. fetch    download the pack YAML the pinned engine resolves (`https://semgrep.dev/c/p/default`,
            the URL the image's own downloader hits -- confirmed by `--debug`).
3. escape   apply `neutralise()`: re-write the pack's own credential-shaped rule bodies
            (`-----BEGIN … PRIVATE KEY-----` headers, the Slack webhook URL) with the
            `\x59` / `\x2e` / `\x2f` escapes so the committed bytes are not themselves a
            gitleaks / push-protection finding (issue #1284/#2105; a raw fetch would red
            `make secret-scan`). The loaded patterns are unchanged -- YAML/regex resolves
            the escapes before semgrep matches.
4. write    replace `containers/scanners/semgrep/rules/default.yml` and run
            `make scanner-digests` (`scripts/scanner_image.py::write`), which recomputes
            `rules_sha = sha256(file)`, stamps `rules_captured_at = today` and counts
            `rules_count = n(- id:)` -- the parity the freshness gate reads.
5. re-pin   the workflow commits the changed pack + digests and opens the re-pin PR (only
            when something changed). `rules_sha == sha256(rewritten default.yml)` is the
            property the test locks.

Commands: `resolve`, `fetch`, `escape`, `refresh` (resolve+fetch+escape+write), `write`.
`neutralise()` and `write()` are pure enough to test hermetically; `resolve`/`fetch`/`refresh`
need the pinned image and network (exercised by the workflow, and by `make semgrep-rules-refresh`).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

try:  # the subprocess policy seam (issue #797)
    from . import scanner_image as _si  # type: ignore
    from .proc import run_ok  # type: ignore
except ImportError:  # pragma: no cover - script mode
    import scanner_image as _si  # type: ignore
    from proc import run_ok  # type: ignore

REPO = _si.REPO
SCANNER_DIR = _si.SCANNER_DIR
RUNTIME = _si.RUNTIME

RULES_FILE = f"{SCANNER_DIR}/semgrep/rules/default.yml"
DIGESTS = f"{SCANNER_DIR}/digests.json"
#: The live registry pack the pinned semgrep resolves `p/default` to (confirmed by its `--debug`).
LIVE_URL = "https://semgrep.dev/c/p/default"

#: Live credential-shaped rule bodies -> the escaped forms the committed pack carries. Refusing a
#: no-op: if an upstream spelling is not found the refresh FAILS LOUDLY instead of silently
#: committing a credential shape (an upstream rule edit must be handled deliberately, #2283).
LIVE_TO_NEUTRAL = [
    ("  pattern-regex: '-----BEGIN PGP PRIVATE KE\x59 BLOCK-----'\n",
     '  pattern-regex: "-----BEGIN PGP PRIVATE KE\\x59 BLOCK-----"\n'),
    ("      - pattern: '-----BEGIN $TYPE PRIVATE KEY----- $KEY'\n",
     '      - pattern: "-----BEGIN $TYPE PRIVATE KE\\x59----- $KEY"\n'),
    ("      - pattern: |\n          -----BEGIN PRIVATE KEY-----\n          $KEY\n",
     '      - pattern: "-----BEGIN PRIVATE KE\\x59-----\\n$KEY\\n"\n'),
    ("  - pattern-regex: https://hooks\\.slack\\.com/services/",
     "  - pattern-regex: https://hooks\\x2eslack\\x2ecom\\x2fservices\\x2f"),
    ("  - pattern-not: https://hooks\x2eslack\x2ecom\x2fservices\x2fT00000000\x2fB00000000\x2fXXXXXXXXXXXXXXXXXXXXXXXX",
     "  - pattern-not: https://hooks\\x2eslack\\x2ecom\\x2fservices\\x2fT00000000\\x2fB00000000\\x2fXXXXXXXXXXXXXXXXXXXXXXXX"),
]


def neutralise(pack_text: str) -> str:
    """Re-escape the pack's own credential-shaped rule bodies (see module docstring)."""
    out = pack_text
    for live, escaped in LIVE_TO_NEUTRAL:
        if live not in out:
            raise SystemExit(
                "[semgrep-rules] refusing a no-op neutralization: the upstream pack no longer "
                f"contains the credential shape {live[:64]!r} -- an upstream rule edit broke the "
                "escape transform. Update LIVE_TO_NEUTRAL in scripts/semgrep_rules.py and re-run "
                "the refresh gate before committing (issue #2283)."
            )
        out = out.replace(live, escaped)
    return out


def rules_count(pack_text: str) -> int:
    """The `n(- id:)` rule count the freshness gate compares against `rules_count`."""
    return sum(1 for line in pack_text.splitlines() if line.startswith("- id: "))


def _validate_command(image: str) -> list[str]:
    return [RUNTIME, "run", "--rm", "-e", "HOME=/tmp", image, "scan",
            "--config", "p/default", "--validate", "--metrics", "off", "/tmp"]


def resolve(image: str | None = None) -> str:
    """Run the pinned image's semgrep against upstream `p/default` and return its stdout."""
    image = image or _si.ref("semgrep")
    print(f"[semgrep-rules] $ {' '.join(_validate_command(image))}")
    res = run_ok(_validate_command(image))
    out = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0:
        raise SystemExit(f"[semgrep-rules] pinned image semgrep could not resolve p/default: {out[-400:]}")
    print(out)
    return out


def fetch(url: str = LIVE_URL) -> str:
    """Download the pack YAML the pinned engine resolves `p/default` to."""
    with urllib.request.urlopen(url) as respone:  # noqa: S310 - the pinned engine's own registry URL
        data = respone.read().decode("utf-8")
    print(f"[semgrep-rules] fetched {len(data)} bytes from {url}")
    return data


def write(pack_text: str, repo: Path = REPO) -> tuple[Path, str, str, int]:
    """Write the neutralised pack and re-stamp digests.json via `scanner_image.write()`.

    Returns (pack_path, rules_sha, captured_at, count). `rules_sha` is the sha256 of the file
    just written -- the property a re-pin PR must carry (`rules_sha == sha256(default.yml)`).
    """
    pack = repo / RULES_FILE
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text(pack_text, encoding="utf-8")
    # Re-stamp digests.json through the ONE discipline: scanner_image.write() recomputes
    # rules_sha, rules_captured_at (= today) and rules_count from the file on disk.
    si = _si
    if repo is not REPO:
        si.REPO = repo
    si.write()
    sha = hashlib.sha256(pack.read_bytes()).hexdigest()
    captured = _dt.date.today().isoformat()
    count = rules_count(pack_text)
    print(f"[semgrep-rules] wrote {RULES_FILE} ({len(pack_text)} bytes, {count} rules, "
          f"sha {sha[:12]}, rules_captured_at {captured})")
    return pack, sha, captured, count


def refresh(url: str = LIVE_URL) -> int:
    """resolve + fetch + neutralise + write; returns 0 (the workflow decides re-pin on git diff)."""
    resolve()
    raw = fetch(url)
    escaped = neutralise(raw)
    _pack, sha, captured, count = write(escaped)
    print(f"[semgrep-rules] refreshed: rules_sha={sha} rules_captured_at={captured} rules_count={count}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("resolve", "fetch", "escape", "refresh", "write"))
    ap.add_argument("--url", default=LIVE_URL)
    ap.add_argument("--image", default=None)
    args = ap.parse_args(argv)
    if args.command == "resolve":
        resolve(args.image)
        return 0
    if args.command == "fetch":
        sys.stdout.write(fetch(args.url))
        return 0
    if args.command == "escape":
        sys.stdout.write(neutralise(sys.stdin.read()))
        return 0
    if args.command == "refresh":
        return refresh(args.url)
    if args.command == "write":
        write(sys.stdin.read())
        return 0
    raise SystemExit("unknown command")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
