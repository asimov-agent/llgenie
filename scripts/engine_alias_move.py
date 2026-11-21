#!/usr/bin/env python3
"""Move an engine's :<variant> GHCR alias to a committed pin digest (issue #2996).

The registry-liveness gate (scripts/check_engine_pins_published.py, alias knob,
issue #2987) classifies gaps by gap class. A cell whose committed pin tag RESOLVES
but whose `:<variant>` alias points at an older digest needs NO build: the image is
already in the registry under its exact tag, only the alias is stale. The repair is
a registry-side manifest re-point — `docker buildx imagetools create` — which
copies the manifest reference to a new tag without building or running anything.
That matters exactly for the cells a build can never heal: DEFAULT_CPU_ONLY engines
(vllm) have their GPU variants structurally absent from every build matrix and
dispatch sweep, so the #2996 fire-loop dispatched green-but-useless sweeps against
the lag. The gate emits

    [aliasmove] <engine> <variant> <tag-suffix> <pin-digest>

for such a cell; the liveness heal step feeds those fields here, one move per cell.

The move is verified: after the registry accepted it, the alias ref is re-resolved
through engine_image._digest_http — the SAME manifest authority the gate reads
(issue #2892's one-registry-read-path rule) — and the MOVED line prints only when
the resolved digest equals the pin digest. A mismatch FAILs loudly.

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
import re
import subprocess
import sys
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


def move_alias(engine: str, variant: str, suffix: str, digest: str,
               registry: str | None = None,
               run: Callable[..., subprocess.CompletedProcess[str]] = proc.run_live,
               probe: Callable[[str], tuple[str, str]] | None = None) -> int:
    """Move `<repo>/<engine>:<variant>` to `digest` by manifest re-point; verify after.

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

    repo = ref.rpartition(":")[0]
    target = f"{repo}:{variant}"
    source = f"{repo}@{digest}"
    cmd = ["docker", "buildx", "imagetools", "create", "-t", target, source]
    print(f"[alias-move] manifest move {source} -> {target} (no build)")
    r = run(cmd)
    if r.returncode != 0:
        print(f"[alias-move] FAIL {target}: imagetools create exited "
              f"{r.returncode}; the alias stays where it was")
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
