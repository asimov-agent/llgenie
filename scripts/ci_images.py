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
import json
import base64
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
# The agent image installs the Hermes CLI by BUILDING it. Under arm64 emulation that step alone
# runs for many minutes and the multi-arch publish job times out mid-install (measured: the
# installer was still on "Installing Python dependencies" past 900s). The bots run on
# GitHub-hosted ubuntu runners, which are amd64, so this image publishes amd64 only — no arm64
# consumer exists to justify paying that, and no other image is affected.
PLATFORMS_FOR = {"agent": "linux/amd64"}


def platforms(name: str) -> str:
    """The `--platform` list an image publishes for."""
    return PLATFORMS_FOR.get(name, PLATFORMS)
SOURCE = "https://github.com/" + (os.environ.get("GITHUB_REPOSITORY") or "asimov-agent/llgenie")

# name -> (Dockerfile, the files COPYed into the build context next to it)
IMAGES: dict[str, tuple[str, tuple[str, ...]]] = {
    "test": ("containers/test/Dockerfile", ("tools/requirements.txt", "tools/requirements-dev.txt")),
    "openspec": ("openspec/Dockerfile", ()),
    # the bots' agent image (issues #222/#238/#248): the test image plus the Hermes CLI and the
    # git/gh/docker tooling a bot job needs. Its inputs include the install script it COPYs.
    # every file the Dockerfile COPYs belongs here: the hash tag is what makes "the image a job
    # uses" the image of THIS commit, so a changed install script must move the tag.
    "agent": ("containers/agent/Dockerfile", ("scripts/install_hermes_ci.sh",
                                              "scripts/install_nerve_ci.sh",
                                              "scripts/agent_jev_preflight.sh")),
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
    if name == "agent":
        # The agent image is built FROM the test image's published tag, so a rebuilt base must
        # produce a new agent tag — otherwise the agent would keep an old base and its Hermes
        # toolchain would silently drift from the gates it has to run.
        h.update(b"base\0" + tag("test", root).encode() + b"\0")
    return h.hexdigest()[:12]


def build_args(name: str, root: Path = REPO) -> list[str]:
    """Extra `--build-arg` flags: the agent image pins the exact test image it builds FROM."""
    if name == "agent":
        return ["--build-arg", f"TEST_IMAGE={ref('test', root)}"]
    return []


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


def _docker_auth(host: str = "ghcr.io") -> tuple[str, str] | None:
    """The credential `docker login` stored, as (user, secret). None when absent."""
    d = os.environ.get("DOCKER_CONFIG") or str(Path.home() / ".docker")
    cfg = Path(d) / "config.json"
    if not cfg.exists():
        return None
    entry = (json.loads(cfg.read_text()).get("auths") or {}).get(host) or {}
    if not entry.get("auth"):
        return None
    user, _, secret = base64.b64decode(entry["auth"]).decode().partition(":")
    return user, secret


def check_push(name: str, root: Path = REPO) -> int:
    """Prove the ambient credential can actually PUSH this image, before the build.

    A publish that is going to be DENIED (a token that cannot create the package, a PAT that
    is not the account that owns the key, a repository-scoped token for an org package) fails
    after a ten-minute build otherwise, and says only "denied". So: ask for a push-scoped GHCR
    token, initiate the cheapest real write there is (a blob upload with no data), and report
    the registry's own message. Nothing is uploaded; an aborted upload leaves no layer.
    """
    r = ref(name, root)
    path = r.split("/", 1)[1].split(":")[0]          # asimov-agent/llgenie/<name>
    host = r.split("/")[0]
    cred = _docker_auth(host)
    if not cred:
        print(f"[ci-images] not logged into {host}: `docker login {host}` first", flush=True)
        return 1
    scope = f"repository:{path}:push,pull"
    basic = base64.b64encode(f"{cred[0]}:{cred[1]}".encode()).decode()
    try:
        token = json.loads(_http(f"https://{host}/token?scope={scope}&service={host}",
                                 {"Authorization": f"Basic {basic}"}))["token"]
        code, body = _http_status(f"https://{host}/v2/{path}/blobs/uploads/",
                                  {"Authorization": f"Bearer {token}", "Content-Length": "0"},
                                  method="POST")
    except Exception as e:                                            # noqa: BLE001
        print(f"[ci-images] cannot reach {host}: {e}", flush=True)
        return 1
    if code in (201, 202):
        print(f"[ci-images] push OK: {cred[0]} may publish {r}", flush=True)
        return 0
    try:
        msg = json.loads(body)["errors"][0]["message"]
    except Exception:                                                 # noqa: BLE001
        msg = body.strip()[:200]
    print(f"[ci-images] push DENIED for {r}: {msg}", flush=True)
    return 1


def _http(url: str, headers: dict) -> str:
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as fh:
        return fh.read().decode()


def _http_status(url: str, headers: dict, method: str = "GET") -> tuple[int, str]:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as fh:
            return fh.status, fh.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


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
        # A registry cache ref that does not exist yet makes buildx fail to configure the
        # importer (the first publish of a NEW image), so only read a cache that is published.
        cache_flags = (["--cache-from", f"type=registry,ref={cache_ref(name)}"]
                       if published(cache_ref(name)) else [])
        rc = _sh([RUNTIME, "buildx", "build", "--platform", platforms(name), "-t", r,
                  *build_args(name, root),
                  # links the GHCR package to the repo, so it gets the repo's visibility
                  "--label", f"org.opencontainers.image.source={SOURCE}",
                  *cache_flags,
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
        return _sh([RUNTIME, "build", "-t", local_name(name), *build_args(name, root), str(ctx)]).returncode
    finally:
        shutil.rmtree(ctx, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CI images on GHCR: publish once per hash, pull everywhere")
    ap.add_argument("cmd", choices=("publish", "pull", "ensure", "ref", "tag", "check-push"))
    ap.add_argument("names", nargs="*", default=list(IMAGES), help=f"default: {' '.join(IMAGES)}")
    a = ap.parse_args(argv)
    for n in a.names:
        if n not in IMAGES:
            ap.error(f"unknown image {n!r} (have {', '.join(IMAGES)})")
    if a.cmd in ("ref", "tag"):
        for n in a.names:
            print(ref(n) if a.cmd == "ref" else tag(n))
        return 0
    run = {"publish": publish, "pull": pull, "ensure": ensure, "check-push": check_push}[a.cmd]
    rc = 0
    for n in a.names:
        rc = run(n) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
