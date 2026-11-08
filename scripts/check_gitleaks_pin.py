#!/usr/bin/env python3
"""Fail when the secret-scan admission gate addresses gitleaks by a mutable tag (issue #2235).

Every other scanner in this pipeline is content-addressed — the daily gate runs trivy/grype/semgrep
from `containers/scanners/digests.json` refs (content-hash tags of Dockerfiles this repo builds) and
`make check-scanner-images` guards those Dockerfiles — yet the **admission** scanner, the one that holds
the "no committed credential VALUE may reach the repo" property on every Linux CI build, was addressed by
a bare upstream tag (`ghcr.io/gitleaks/gitleaks:v8.30.1`) that anyone with `packages:write` on that
package could re-push.

This guard closes that gap in the same style `check-scanner-images` guards the daily-gate Dockerfiles. It
reads every site that references the gitleaks image and fails when:

- any reference is a bare `:v` semver tag (mutable under a re-push — the #810 trust-boundary class),
- the sites disagree (a scan that moved away from what was reviewed — the #1252/#1262
  silently-unsatisfiable-pin class: an edit that names a digest in one place and a different one in
  another is a pin that can never have been reviewed),
- the pinned reference is not `@sha256:<64 hex>` (a malformed pin is silently-unsatisfiable).

The source of truth is `scripts/secret_scan.py:GITLEAKS_IMAGE`; the Makefile `GITLEAKS_IMAGE` and the
self-test's literal must equal it exactly. Satisfiability (that the pinned digest actually resolves and
runs) is proven at scan time: `make secret-scan-self-test` runs the pinned image against a planted
credential and fails if the image cannot run or does not catch it.

Usage:
    python3 scripts/check_gitleaks_pin.py check
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SECRET_SCAN = REPO / "scripts" / "secret_scan.py"
SELF_TEST = REPO / "scripts" / "secret_scan_self_test.py"
MAKEFILE = REPO / "Makefile"

#: A content-pinned reference: `name@sha256:<64 hex>`.
REF = re.compile(r"(ghcr\.io/gitleaks/gitleaks)@(sha256:[0-9a-f]{64})")
#: A bare mutable tag reference — the defect this issue exists to make impossible.
TAG_REF = re.compile(r"ghcr\.io/gitleaks/gitleaks:[\w][\w.\-]*")


def _ref_sites() -> list[tuple[str, Path, str]]:
    """(site_name, file, extract) for every place the gitleaks image is addressed."""
    def make(site: str, path: Path, pat: re.Pattern) -> list[tuple[str, Path, str]]:
        text = path.read_text(encoding="utf-8")
        return [(site, path, m.group(1)) for m in pat.finditer(text)]

    sites = []
    # source of truth: the constant value (not the name) in secret_scan.py
    sites += make("secret_scan.py", SECRET_SCAN,
                  re.compile(r"GITLEAKS_IMAGE\s*=\s*\"([^\"]+)\""))
    sites += make("secret_scan_self_test.py", SELF_TEST,
                  re.compile(r"\"(ghcr\.io/gitleaks/gitleaks@[^\"]+)\""))
    sites += make("Makefile", MAKEFILE,
                  re.compile(r"GITLEAKS_IMAGE\s*:?=\s*(\S+)"))
    return sites


def check() -> int:
    problems: list[str] = []

    # 0. The source-of-truth reference is a proper digest pin.
    try:
        truth_text = SECRET_SCAN.read_text(encoding="utf-8")
        m = re.search(r"GITLEAKS_IMAGE\s*=\s*\"([^\"]+)\"", truth_text)
    except FileNotFoundError:
        problems.append(f"{SECRET_SCAN} is missing — the pinned gitleaks image is undefined")
        m = None
    if m:
        truth = m.group(1)
        tm = REF.match(truth)
        if not tm:
            problems.append(f"{SECRET_SCAN}.GITLEAKS_IMAGE names {truth!r} — not a digest pin "
                            "(`ghcr.io/gitleaks/gitleaks@sha256:<64 hex>`); the admission gate must "
                            "not address gitleaks by a mutable tag (issue #2235)")
    else:
        truth = None

    # 1. No site names a bare mutable tag.
    for name, path, _cfg in (("Makefile", MAKEFILE, None), (str(SELF_TEST), SELF_TEST, None),
                             (str(SECRET_SCAN), SECRET_SCAN, None)):
        text = path.read_text(encoding="utf-8")
        for t in TAG_REF.finditer(text):
            problems.append(f"{name}: gitleaks addressed by a mutable tag {t.group(0)!r} — "
                            "pin it by digest (issue #2235)")

    # 2. Every site carries exactly the source-of-truth reference (no divergence, no stale digest).
    if truth:
        for site, path, found in _ref_sites():
            if found != truth:
                problems.append(f"{site}: gitleaks reference {found!r} does not match the pinned "
                                f"{truth!r} — rerun `make scanner-digests`-style review so every "
                                "site names the SAME reviewed digest")

    if problems:
        print(f"[check-gitleaks-pin] {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    digest = truth.split("@", 1)[1] if truth and "@" in truth else "?"
    print(f"[check-gitleaks-pin] OK: gitleaks pinned by digest {digest} identically in "
          "secret_scan.py, the Makefile and the self-test; no bare tag reference")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("check",))
    args = ap.parse_args(argv)
    return check()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
