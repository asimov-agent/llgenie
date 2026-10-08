#!/usr/bin/env python3
"""CI images (issue #117): the test image and the OpenSpec CLI image, published to GHCR once
per content change and PULLED by every CI job instead of being rebuilt in each one.

Each image is tagged with a hash of exactly the files it is built from:

    llgenie/test      containers/test/Dockerfile + tools/requirements.txt + tools/requirements-dev.txt
    llgenie/openspec  openspec/Dockerfile

    <LLGENIE_REGISTRY>/llgenie/<name>:<hash>     e.g. ghcr.io/asimov-agent/llgenie/test:3f2a9c0d1b7e

Commands (driven by make, never by hand):

    publish <name>  CI job `ci-images`: look the hash tag up; build linux/amd64 + linux/arm64 and
                    push it ONLY when it is missing (registry layer cache)   make publish-ci-images
    pull <name>     every CI job: pull the hash tag, tag it llgenie/<name>:latest; a missing tag
                    fails loudly, nothing is built                           make test-image-pull
    ensure <name>   a dev host: pull the published hash, else build it here from the same
                    Dockerfile (an edited Dockerfile/lockfile is not published yet)  make test-image
    ref <name>      print the published ref                                  make ci-image-refs
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNTIME = os.environ.get("RUNTIME") or "docker"  # docker only (issue #112)
DEFAULT_REGISTRY = "ghcr.io/asimov-agent"  # the same default as engine_image.py and the Makefile
PLATFORMS = "linux/amd64,linux/arm64"  # Linux + Intel-macOS runners, Apple-Silicon dev hosts
SOURCE = "https://github.com/" + (os.environ.get("GITHUB_REPOSITORY") or "asimov-agent/llgenie")

# name -> (Dockerfile, the files COPYed into the build context next to it)
IMAGES: dict[str, tuple[str, tuple[str, ...]]] = {
    "test": ("containers/test/Dockerfile", ("tools/requirements.txt", "tools/requirements-dev.txt")),
    "openspec": ("openspec/Dockerfile", ()),
}


def registry() -> str:
    """OCI refs must be lowercase (a fork owner like Asimov-Agent)."""
    return os.environ.get("LLGENIE_REGISTRY", DEFAULT_REGISTRY).rstrip("/").lower()


def inputs(name: str, root: Path = REPO) -> list[Path]:
    dockerfile, extra = IMAGES[name]
    return [root / dockerfile, *(root / f for f in extra)]


def tag(name: str, root: Path = REPO) -> str:
    """12 hex of sha256 over each input's repo path and bytes: same inputs, same tag."""
    h = hashlib.sha256()
    for p in inputs(name, root):
        h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:12]


def local_name(name: str) -> str:
    """The name every make target already runs (TEST_IMG / OS_IMG)."""
    return f"llgenie/{name}:latest"


def ref(name: str, root: Path = REPO) -> str:
    return f"{registry()}/llgenie/{name}:{tag(name, root)}"


def cache_ref(name: str) -> str:
    return f"{registry()}/llgenie/{name}:buildcache"


def _sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("[ci-images] $", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def published(r: str) -> bool:
    """One manifest lookup on the registry; no pull, no build."""
    return _sh([RUNTIME, "buildx", "imagetools", "inspect", r], capture_output=True).returncode == 0


def context(name: str, root: Path = REPO) -> Path:
    """A temp build context holding exactly the hashed inputs (Dockerfile + lockfiles)."""
    ctx = Path(tempfile.mkdtemp(prefix=f"ci-image-{name}-"))
    for p in inputs(name, root):
        shutil.copy2(p, ctx / p.name)
    return ctx


def _pull_and_tag(name: str, r: str) -> int:
    rc = _sh([RUNTIME, "pull", r]).returncode
    if rc == 0:
        rc = _sh([RUNTIME, "tag", r, local_name(name)]).returncode
    return rc


def publish(name: str, root: Path = REPO) -> int:
    """CI only: build both arches and push, unless this hash is already on the registry."""
    r = ref(name, root)
    if published(r):
        print(f"[ci-images] {r} already published (inputs unchanged): nothing to build", flush=True)
        return 0
    ctx = context(name, root)
    try:
        rc = _sh([RUNTIME, "buildx", "build", "--platform", PLATFORMS, "-t", r,
                  # links the GHCR package to the repo, so it gets the repo's visibility
                  "--label", f"org.opencontainers.image.source={SOURCE}",
                  "--cache-from", f"type=registry,ref={cache_ref(name)}",
                  "--cache-to", f"type=registry,ref={cache_ref(name)},mode=max",
                  "--push", str(ctx)]).returncode
    finally:
        shutil.rmtree(ctx, ignore_errors=True)
    if rc == 0:
        print(f"[ci-images] published {r} ({PLATFORMS})", flush=True)
    return rc


def pull(name: str, root: Path = REPO) -> int:
    """CI jobs: pull the published hash tag, never build. A missing tag fails the job."""
    r = ref(name, root)
    if _pull_and_tag(name, r) != 0:
        print(f"[ci-images] {r} is not published: the ci-images job publishes it "
              f"(make publish-ci-images); CI jobs never build a CI image", file=sys.stderr, flush=True)
        return 1
    print(f"[ci-images] {local_name(name)} = {r}", flush=True)
    return 0


def ensure(name: str, root: Path = REPO) -> int:
    """Dev host: the published image of these inputs, else a local build of the same Dockerfile."""
    r = ref(name, root)
    if registry() and _pull_and_tag(name, r) == 0:
        print(f"[ci-images] {local_name(name)} = {r} (pulled, not built)", flush=True)
        return 0
    print(f"[ci-images] {r} is not published (an edited Dockerfile or lockfile): "
          f"building {local_name(name)} here", flush=True)
    ctx = context(name, root)
    try:
        return _sh([RUNTIME, "build", "-t", local_name(name), str(ctx)]).returncode
    finally:
        shutil.rmtree(ctx, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CI images on GHCR: publish once per hash, pull everywhere")
    ap.add_argument("cmd", choices=("publish", "pull", "ensure", "ref", "tag"))
    ap.add_argument("names", nargs="*", default=list(IMAGES), help=f"default: {' '.join(IMAGES)}")
    a = ap.parse_args(argv)
    for n in a.names:
        if n not in IMAGES:
            ap.error(f"unknown image {n!r} (have {', '.join(IMAGES)})")
    if a.cmd in ("ref", "tag"):
        for n in a.names:
            print(ref(n) if a.cmd == "ref" else tag(n))
        return 0
    run = {"publish": publish, "pull": pull, "ensure": ensure}[a.cmd]
    rc = 0
    for n in a.names:
        rc = run(n) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
