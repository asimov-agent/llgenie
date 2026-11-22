#!/usr/bin/env python3
"""Move an engine's :<variant> GHCR alias to a committed pin digest (issue #2996).

The registry-liveness gate (scripts/check_engine_pins_published.py, alias knob,
issue #2987) classifies gaps by gap class. A cell whose committed pin tag RESOLVES
but whose `:<variant>` alias points at an older digest needs NO build: the image is
already in the registry under its exact tag, only the alias is stale. The repair is
a registry-side manifest move that copies the manifest to the alias tag without
building or running anything.
That matters exactly for the cells a build can never heal: DEFAULT_CPU_ONLY engines
(vllm) have their GPU variants structurally absent from every build matrix and
dispatch sweep, so the #2996 fire-loop dispatched green-but-useless sweeps against
the lag. The gate emits

    [aliasmove] <engine> <variant> <tag-suffix> <pin-digest>

for such a cell; the liveness heal step feeds those fields here, one move per cell.

The move is byte-preserving (issue #3006): `docker buildx imagetools create`
re-publishes its input as a manifest LIST, so the new tag can never equal the pin
digest — measured on run 45019438459, where both #2996 heals published
manifest.list.v2+json under new digests. The mover instead FETCHES the pin
manifest verbatim (`docker buildx imagetools inspect --raw <repo>@<digest>`; the
fetched bytes hash back to the pin — checked locally before ANY write) and re-
publishes those EXACT bytes through the registry manifest PUT
(`PUT /v2/<name>/manifests/<variant>`, Content-Type from the manifest's own
mediaType, token exchanged from GHCR_LOGIN_TOKEN/GHCR_LOGIN_USER in the
environment — #361). Same bytes ⇒ the registry stores the identical blob ⇒ the
tag resolves to the identical digest.

The move is then verified: after the registry accepted it, the alias ref is
re-resolved through engine_image._digest_http — the SAME manifest authority the
gate reads (issue #2892's one-registry-read-path rule) — and the MOVED line
prints only when the resolved digest equals the pin digest. A mismatch FAILs
loudly.

Contract refusal: all four fields are required and the digest must be
`sha256:<64 hex>`; the tag suffix must equal the committed exact-tag formula's
suffix for this (engine, variant) (scripts/engine_image.resolve), so a line that
contradicts the params is rejected before any registry write.

Usage:
    python3 scripts/engine_alias_move.py --engine vllm --variant cuda \
        --suffix 3a4d82f5-4c1f3eee-cuda --digest sha256:b62be545…
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import engine_image as ei  # noqa: E402
import proc  # noqa: E402

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _ref(engine: str, variant: str, registry: str) -> str:
    """The committed exact-tag ref for this cell, spelled the way the gate spells it."""
    return f"{registry}/{ei.resolve(engine, None, variant)['tag']}"


def _name_path(ref: str) -> str:
    """`ghcr.io/asimov-agent/vllm:tag` -> `asimov-agent/vllm` (the registry API name)."""
    return ref.partition("/")[2].rpartition(":")[0]


def _ghcr_push_token(host: str, name_path: str) -> str | None:
    """Exchange the env login credential for a push-capable repo token (#361).

    GHCR_LOGIN_TOKEN / GHCR_LOGIN_USER arrive through the environment (the
    registry-liveness heal step exports them via `env:` next to the same
    `docker login` that already uses them); nothing here prints the secret.
    """
    user = os.environ.get("GHCR_LOGIN_USER", "")
    token = os.environ.get("GHCR_LOGIN_TOKEN", "")
    if not token:
        print("[alias-move] FAIL credential: GHCR_LOGIN_TOKEN is unset — the "
              "manifest PUT needs a push-capable token")
        return None
    query = urllib.parse.urlencode(
        {"service": host, "scope": f"repository:{name_path}:pull,push"})
    req = urllib.request.Request(
        f"https://{host}/token?{query}",
        headers={"Authorization": "Basic " + base64.b64encode(
            f"{user}:{token}".encode()).decode()})
    try:
        payload = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as exc:  # noqa: BLE001 — a refused exchange is a loud FAIL
        print(f"[alias-move] FAIL credential: GHCR token exchange refused: "
              f"{type(exc).__name__} {str(exc)[-120:]}")
        return None
    exchanged = payload.get("token") or ""
    if not exchanged:
        print("[alias-move] FAIL credential: GHCR token exchange returned no token")
        return None
    return exchanged


def _put_manifest(name_path: str, tag: str, body: bytes, media_type: str,
                  host: str) -> tuple[int, str]:
    """PUT the EXACT manifest bytes; returns (status, digest-or-reason)."""
    token = _ghcr_push_token(host, name_path)
    if token is None:
        return -1, "no push-capable GHCR token"
    req = urllib.request.Request(
        f"https://{host}/v2/{name_path}/manifests/{tag}", data=body, method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": media_type})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.headers.get("Docker-Content-Digest", "")
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read() or b"")[:200].decode(errors="replace")
    except Exception as exc:  # noqa: BLE001 — transport failure is a loud FAIL
        return -1, f"{type(exc).__name__} {str(exc)[-160:]}"


def move_alias(engine: str, variant: str, suffix: str, digest: str,
               registry: str | None = None,
               run: Callable[..., subprocess.CompletedProcess[str]] = proc.run_live,
               probe: Callable[[str], tuple[str, str]] | None = None,
               put: Callable[[str, str, bytes, str, str], tuple[int, str]]
               = _put_manifest) -> int:
    """Move `<repo>/<engine>:<variant>` to `digest` byte-for-byte; verify after.

    Exit 0 + `[alias-move] MOVED` only when the post-move alias digest equals the
    pin digest. A malformed contract is refused (exit 2) before any registry call.
    """
    registry = registry if registry is not None else ei.REGISTRY
    probe = probe if probe is not None else ei._digest_http

    for name, value in (("ENGINE", engine), ("VARIANT", variant),
                        ("SUFFIX", suffix), ("DIGEST", digest)):
        if not value:
            print(f"[alias-move] FAIL contract: {name} is missing")
            return 2
    if not DIGEST_RE.match(digest):
        print(f"[alias-move] FAIL contract: DIGEST {digest!r} is not "
              "sha256:<64 hex> — refusing to move any tag")
        return 2
    ref = _ref(engine, variant, registry)
    committed_suffix = ref.rpartition(":")[2]
    if committed_suffix != suffix:
        print(f"[alias-move] FAIL contract: SUFFIX {suffix!r} contradicts the "
              f"committed exact-tag formula {committed_suffix!r} for "
              f"{engine}/{variant} — refusing to move any tag")
        return 2

    host = ref.partition("/")[0]
    repo = ref.rpartition(":")[0]
    name_path = _name_path(ref)
    target = f"{repo}:{variant}"
    source = f"{repo}@{digest}"

    fetch_cmd = ["docker", "buildx", "imagetools", "inspect", "--raw", source]
    print(f"[alias-move] byte-preserving move {source} -> {target} (no build): "
          "fetching the pin manifest verbatim")
    r = run(fetch_cmd)
    if r.returncode != 0:
        print(f"[alias-move] FAIL {source}: imagetools inspect --raw exited "
              f"{r.returncode}; nothing was fetched and nothing was written")
        return 1
    body = (r.stdout or "").encode()
    got = "sha256:" + hashlib.sha256(body).hexdigest()
    if got != digest:
        print(f"[alias-move] FAIL {source}: the fetched bytes hash to {got}, "
              f"not the committed {digest} — refusing to publish them anywhere")
        return 1
    try:
        media_type = json.loads(body).get("mediaType") or ""
    except json.JSONDecodeError:
        media_type = ""
    if not media_type:
        print(f"[alias-move] FAIL {source}: the fetched manifest names no "
              "mediaType — a PUT without the exact Content-Type would let the "
              "registry re-serialize it")
        return 1
    status, detail = put(name_path, variant, body, media_type, host)
    if status not in (200, 201):
        print(f"[alias-move] FAIL {target}: manifest PUT refused (status "
              f"{status}, {detail}) — the alias stays where it was")
        return 1
    ad, aerr = probe(target)
    if ad == digest:
        print(f"[alias-move] MOVED {target} -> {digest}")
        return 0
    print(f"[alias-move] FAIL {target}: post-move digest is {ad or aerr}, "
          f"not the committed {digest}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--engine", default="", help="committed engine id (dots intact)")
    ap.add_argument("--variant", default="", help="backend variant the alias names")
    ap.add_argument("--suffix", default="", help="committed exact-tag suffix")
    ap.add_argument("--digest", default="", help="pin digest, sha256:<64 hex>")
    a = ap.parse_args(argv)
    return move_alias(a.engine, a.variant, a.suffix, a.digest)


if __name__ == "__main__":
    sys.exit(main())
