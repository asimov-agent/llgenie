#!/usr/bin/env python3
"""Engine install-string dependency pins, inventoried for the scan (issue #1282).

The security pipeline's contract is "is anything in this tree known-vulnerable", but the tree's
most security-sensitive artifacts — the engine cells whose install strings pin the runtime
(`torch==2.14.0`, `litert-lm==0.19.0`, `ziglang==0.17.0`, `--index-url <whl index>`) — are JSON
strings, which no scanner parses as a dependency declaration. A vulnerable or silently-unsatisfiable
engine pin never touches trivy/syft, so the daily "0 findings" is true only of `tools/`.

This module closes that gap: at `make sbom` / `make engine-pins` time it walks
`containers/engines/params/*.json`, extracts the Exact-version pins a cell actually installs (from
its committed `variants[*].install` lines, never a rationalised "all of unpinned install" blob),
and writes a requirements-shaped artifact the SAME Trivy/Syft pass runs over. A known-bad engine
pin then reports with the same verdict/issue path as a `tools/` finding.

Commands (driven by make, never by hand):

    inventory    write security-reports/engine-pins/requirements.txt + manifest.json   make engine-pins
    check        fail when no pins are inventoried, or an engine install pin is dropped,
                 or (when the SBOM exists) an inventoried pin is absent from sbom.cdx.json
                                                                            make check-security-scan
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
#: `python3 scripts/engine_pins.py` puts scripts/ on sys.path, not the repo root — so a sibling
#: `scripts.proc` import needs the repo root inserted (same bootstrap as check_pr_acceptance.py).
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: The ONE subprocess seam (issue #797): the `git rev-parse HEAD` probe goes through scripts.proc,
#: never a bare direct call site (check-proc-gate reds one in scripts/).
from scripts.proc import run_ok  # noqa: E402

PARAMS = REPO / "containers" / "engines" / "params"
REPORTS = REPO / "security-reports"
#: A pip/uv install of a pinned package: `name==version` where name is a sane distribution token.
PIN = re.compile(r"(?P<pin>(?<![\w-])[A-Za-z0-9_.-]+==[A-Za-z0-9_.\-*]+)")
#: Every `--index-url <url>` a cell pins its install to.
INDEX_URL = re.compile(r"--index-url\s+(\S+)")
#: An "install" line is one that actually installs a pinned python package (not a git clone,
#: not a `pip list` introspection, not `cmake`): pip/uv with an explicit `==` pin.
_INSTALLER = re.compile(r"(?:\bpip\b|\buv\b).*?(?:install|--index-url|--no-deps)")
#: Lines that are not a wheel install of a pinned package, even when they carry a `==`.
_EBUILD_SKIP = ("git clone", "cd /opt", "-e '", "-c /tmp", "cmake ", "ln -sf", "rm -f",
                "pip list", "[ -d", "test -d", "cp pyproject", "setup_rocm")


def _install_lines(params: dict) -> list[tuple[str, str, str]]:
    """(variant_id, pin, install_line) for every pinned install line in a params file."""
    out: list[tuple[str, str, str]] = []
    for variant_id, variant in (params.get("variants") or {}).items():
        if not isinstance(variant, dict):
            continue
        for line in variant.get("install") or []:
            if not isinstance(line, str):
                continue
            if any(k in line for k in _EBUILD_SKIP):
                continue
            if not _INSTALLER.search(line):
                continue
            m = PIN.search(line)
            if m:
                out.append((variant_id, m.group("pin"), line))
    return out


def inventory_params(path: Path) -> list[dict]:
    """The Exact-version engine pins a params file names, as inventoried records."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for variant_id, pin, line in _install_lines(data):
        im = INDEX_URL.search(line)
        idx = im.group(1) if im else ""
        name, _, version = pin.partition("==")
        try:
            source = str(path.relative_to(REPO))
        except ValueError:
            source = str(path)
        rows.append({
            "package": name,
            "version": version,
            "pin": pin,
            "index_url": idx,
            "source": source,
            "variant": variant_id,
        })
    return rows


def head_sha() -> str:
    try:
        res = run_ok(["git", "rev-parse", "HEAD"], cwd=str(REPO), timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "(local)"


def inventory() -> list[dict]:
    """Walk every committed params file and return all inventoried pins, sorted."""
    rows: list[dict] = []
    if PARAMS.is_dir():
        for p in sorted(PARAMS.glob("*.json")):
            rows.extend(inventory_params(p))
    rows.sort(key=lambda r: (r["source"], r["variant"], r["package"], r["version"]))
    return rows


def write_inventory(reports: Path = REPORTS) -> int:
    """Write the requirements-shaped artifact and the sha-bound manifest."""
    rows = inventory()
    manifest = {"head_sha": head_sha(), "count": len(rows), "pins": rows}
    (reports / "engine-pins").mkdir(parents=True, exist_ok=True)
    req = []
    for r in rows:
        idx = f" --index-url {r['index_url']}" if r["index_url"] else ""
        req.append(f"{r['pin']}  # {r['source']}/{r['variant']}{idx}")
    (reports / "engine-pins" / "requirements.txt").write_text(
        "\n".join(req) + ("\n" if req else ""), encoding="utf-8")
    (reports / "engine-pins" / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[engine-pins] {len(rows)} pinned engine dep(s) inventoried "
          f"(@ {manifest['head_sha']}) -> security-reports/engine-pins/")
    return 0


def check() -> int:
    """Fail when the scan's engine-pin coverage is silent or dropped, and (when the SBOM exists)
    when an inventoried pin is absent from it — so the engine runtime deps cannot be a blind spot."""
    problems: list[str] = []
    rows = inventory()
    if not rows:
        problems.append("no engine install-string pins inventoried — the engine runtime deps are "
                        "a scan blind spot; a params install line carries no `name==version` pin")
    # The SBOM is the artifact trivy/grype match: when it exists, every inventoried package must be in it.
    sbom = REPORTS / "sbom.cdx.json"
    if sbom.is_file():
        try:
            doc = json.loads(sbom.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
        comps = set()
        for c in doc.get("components") or []:
            purl = c.get("purl") or ""
            m = re.match(r"pkg:pypi/([^@]+)", purl) if purl.startswith("pkg:pypi/") else None
            if m:
                comps.add(m.group(1))
        if not comps:
            problems.append(f"{sbom.name} has no pkg:pypi components — the engine-pin coverage "
                            "cannot be verified")
        for r in rows:
            if r["package"] not in comps:
                problems.append(f"engine pin {r['package']}=={r['version']} "
                                f"({r['source']}/{r['variant']}) is absent from {sbom.name} — the "
                                "SBOM does not cover the engine runtime deps")
    # The committed artifact (if present) must match what the tree would inventory.
    manifest = REPORTS / "engine-pins" / "manifest.json"
    if manifest.is_file():
        try:
            rec = json.loads(manifest.read_text(encoding="utf-8"))
            if {r["pin"] for r in rec.get("pins") or []} != {r["pin"] for r in rows}:
                problems.append("security-reports/engine-pins/manifest.json is stale — run "
                                "`make engine-pins`")
        except json.JSONDecodeError:
            problems.append("security-reports/engine-pins/manifest.json does not parse")
    if problems:
        print(f"[engine-pins] {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"[engine-pins] OK: {len(rows)} engine pin(s) inventoried and (where scanned) in the SBOM")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("inventory", "check"))
    args = ap.parse_args(argv)
    return write_inventory() if args.command == "inventory" else check()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
