#!/usr/bin/env python3
"""One immutable image per scanner (issue #714, parent #713).

A scanner installed at scan time is a mutable tool on a mutable base, with network access during
the scan. Each scanner therefore ships as its own image, built only by this repository from
`containers/scanners/<id>/Dockerfile`, whose base is pinned by DIGEST and whose scanner is pinned to
EXACT versions. The published tag is a hash of the Dockerfile, so `<registry>/llgenie/<id>:<hash>`
names one build of one file — the same convention `scripts/ci_images.py` uses for `llgenie/test`.

Commands (driven by make, never by hand):

    digest <id>     print the Dockerfile's content hash (the immutable tag)   make scanner-digests
    ref <id>        print the published ref                                   make scanner-ref
    build <id>      build the image from its Dockerfile                       make scanner-image
    test <id>       build + run the image's version command and compare it with the pin
                                                                              make test-scanner-image
    publish <id>    build linux/amd64 + linux/arm64 and push the hash tag     make publish-scanner-images
    write           rewrite containers/scanners/digests.json from the files   make scanner-digests
    check <id>|all  fail when a Dockerfile floats, or when digests.json is stale
                                                                              make check-scanner-images
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:  # the subprocess policy seam (issue #797)
    from .proc import run_ok  # type: ignore
except ImportError:  # pragma: no cover - script mode
    from proc import run_ok  # type: ignore

REPO = Path(__file__).resolve().parent.parent
RUNTIME = os.environ.get("RUNTIME") or "docker"
DEFAULT_REGISTRY = "ghcr.io/asimov-agent"
PLATFORMS = "linux/amd64,linux/arm64"
SCANNER_DIR = "containers/scanners"
DIGESTS = f"{SCANNER_DIR}/digests.json"
#: id -> the ARG that pins the scanner, and the command whose output carries the version.
SCANNERS: dict[str, dict[str, str]] = {
    "trivy": {"arg": "TRIVY_VERSION", "cmd": "version"},
    "grype": {"arg": "GRYPE_VERSION", "cmd": "version"},
    "semgrep": {"arg": "SEMGREP_VERSION", "cmd": "--version"},
}
#: A base image must be pinned by digest: `FROM image@sha256:<64 hex>`.
FROM_DIGEST = re.compile(r"^FROM\s+(\S+)@sha256:([0-9a-f]{64})\s*$", re.M)
#: A floating base: a `FROM` with a tag but no digest (the digest form is matched above, so a
#: lazy `\S+?` plus the negative lookahead keeps `image@sha256:<hex>` out of this rule).
FROM_FLOAT = re.compile(r"^FROM\s+(?!\S*@sha256:)(\S+?):(\w[\w.-]*)\s*$", re.M)


def registry() -> str:
    return os.environ.get("LLGENIE_REGISTRY", DEFAULT_REGISTRY).rstrip("/").lower()


def dockerfile(scanner: str) -> Path:
    path = REPO / SCANNER_DIR / scanner / "Dockerfile"
    if not path.is_file():
        raise SystemExit(f"[scanner-image] no Dockerfile for scanner `{scanner}` ({path})")
    return path


def pinned_version(scanner: str) -> str:
    """The exact version the Dockerfile pins (no range, no `latest`)."""
    arg = SCANNERS[scanner]["arg"]
    text = dockerfile(scanner).read_text(encoding="utf-8")
    m = re.search(rf"^ARG\s+{arg}=(\S+)\s*$", text, re.M)
    if not m:
        raise SystemExit(f"[scanner-image] {scanner}: no `ARG {arg}=<version>` pin")
    return m.group(1)


def content_hash(scanner: str) -> str:
    """A tag that names one build of one Dockerfile — the immutability the scans rely on."""
    return hashlib.sha256(dockerfile(scanner).read_bytes()).hexdigest()[:12]


def ref(scanner: str) -> str:
    return f"{registry()}/llgenie/{scanner}:{content_hash(scanner)}"


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"[scanner-image] $ {' '.join(cmd)}")
    # policy: run_ok — the caller inspects rc (issue #797, scripts/proc.py is the one seam).
    return run_ok(cmd, **kw)


def build(scanner: str, tag: str | None = None) -> str:
    tag = tag or f"llgenie/scanner-{scanner}:{content_hash(scanner)}"
    res = _run([RUNTIME, "build", "-t", tag, str(dockerfile(scanner).parent)])
    if res.returncode != 0:
        raise SystemExit(f"[scanner-image] build failed: {scanner}")
    return tag


def version_line(scanner: str, image: str) -> str:
    """Run the image's version command and return everything it printed."""
    res = subprocess.run([RUNTIME, "run", "--rm", image, SCANNERS[scanner]["cmd"]],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                         capture_output=True, text=True)
    out = (res.stdout + res.stderr).strip()
    if res.returncode != 0:
        raise SystemExit(f"[scanner-image] {scanner}: version command failed: {out}")
    return out


def test(scanner: str) -> int:
    """Build, then prove the binary answers with the pinned version."""
    image = build(scanner)
    pin = pinned_version(scanner)
    out = version_line(scanner, image)
    numeric = pin.split("-")[0]  # apk revision suffix (-r5) is not part of the upstream version
    if numeric not in out:
        raise SystemExit(f"[scanner-image] {scanner}: expected version {numeric}, got: {out}")
    print(f"[scanner-image] OK {scanner} {numeric} ({image})")
    return 0


def publish(scanner: str) -> int:
    """Build both platforms and push the content-hash tag."""
    target = ref(scanner)
    res = _run([RUNTIME, "buildx", "build", "--platform", PLATFORMS, "--push",
                "-t", target, str(dockerfile(scanner).parent)])
    if res.returncode != 0:
        raise SystemExit(f"[scanner-image] publish failed: {scanner}")
    print(f"[scanner-image] published {target}")
    return 0


def write() -> int:
    """Rewrite digests.json: the version pin and the immutable tag per scanner."""
    data = {
        scanner: {
            "version": pinned_version(scanner),
            "tag": content_hash(scanner),
            "ref": ref(scanner),
            "dockerfile": f"{SCANNER_DIR}/{scanner}/Dockerfile",
        }
        for scanner in SCANNERS
    }
    path = REPO / DIGESTS
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[scanner-image] wrote {DIGESTS} ({len(data)} scanners)")
    return 0


def check(scanner: str = "all") -> int:
    """Fail when a Dockerfile floats or digests.json disagrees with the files."""
    problems: list[str] = []
    ids = list(SCANNERS) if scanner == "all" else [scanner]
    for sid in ids:
        text = dockerfile(sid).read_text(encoding="utf-8")
        if not FROM_DIGEST.search(text):
            problems.append(f"{sid}: base image is not pinned by digest (`FROM image@sha256:<64 hex>`)")
        for image, tag in FROM_FLOAT.findall(text):
            problems.append(f"{sid}: floating base `{image}:{tag}` — pin it by digest")
        if "latest" in re.sub(r"#.*", "", text):
            problems.append(f"{sid}: the Dockerfile names `latest`")
    path = REPO / DIGESTS
    if not path.is_file():
        problems.append(f"{DIGESTS} is missing — run `make scanner-digests`")
    else:
        recorded = json.loads(path.read_text(encoding="utf-8"))
        for sid in SCANNERS:
            entry = recorded.get(sid)
            if not entry:
                problems.append(f"{DIGESTS} does not name `{sid}`")
                continue
            if entry.get("version") != pinned_version(sid):
                problems.append(f"{sid}: digests.json records version {entry.get('version')!r}, "
                                f"the Dockerfile pins {pinned_version(sid)!r}")
            if entry.get("tag") != content_hash(sid):
                problems.append(f"{sid}: digests.json records tag {entry.get('tag')!r}, "
                                f"the Dockerfile hashes to {content_hash(sid)!r}")
            if not (entry.get("ref") or "").endswith(f"/{sid}:{content_hash(sid)}"):
                problems.append(f"{sid}: digests.json ref does not end with the content-hash tag")
    if problems:
        print(f"[scanner-image] {len(problems)} problem(s):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[scanner-image] OK: {len(ids)} scanner image(s) pinned by digest, exact version, and "
          "matching digests.json")
    return 0


def ci() -> int:
    """Every scanner: build + prove its version. Publish only on a push (never a PR run).

    The policy lives here, not in a workflow `if:` — a scenario-scoped condition in YAML is how a
    publish silently stops happening (AGENTS.md).
    """
    published = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch") != "pull_request"
    for sid in SCANNERS:
        test(sid)
        if published:
            publish(sid)
        else:
            print(f"[scanner-image] build+test only for {sid} (a pull_request run does not publish)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("digest", "ref", "build", "test", "publish", "write", "check", "ci"))
    ap.add_argument("scanner", nargs="?", default="all")
    args = ap.parse_args(argv)
    sid = args.scanner
    if args.command in ("digest", "ref", "build", "test", "publish") and sid not in SCANNERS:
        raise SystemExit(f"[scanner-image] unknown scanner `{sid}`; known: {', '.join(SCANNERS)}")
    if args.command == "digest":
        print(content_hash(sid))
        return 0
    if args.command == "ref":
        print(ref(sid))
        return 0
    return {"build": lambda: 0 if build(sid) else 0, "test": lambda: test(sid),
            "publish": lambda: publish(sid), "write": write,
            "check": lambda: check(sid), "ci": ci}[args.command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
