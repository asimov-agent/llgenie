#!/usr/bin/env python3
"""Is every engine this change repinned actually published in the registry?

A pin bump used to publish its image in the same CI run: `ci.yml`'s parallel
`engine-image-*` jobs built and pushed the new tag, and
`tests/test_ci_publish_order.py::test_every_image_install_pulls_is_published`
DEFERRED the repinned engine because the producing cell was this very run. Since
issue #1027 no engine is built or published by the PR pipeline at all — the
engine-build PRODUCER owns building and publishing, and publishing happens only
when it is dispatched with `push=true`. So a bump PR could merge with its new
pin's tag never appearing on GHCR, and nothing redded until a later scheduled
run tripped on the manifest 404 (issue #1622; the #1365/#1587 recurring class).

This gate closes that hole AT THE PR: an engine whose committed params differ
from the base is repinned by THIS change, so its exact image tag — computed by
the ONE tag formula `engine_image.resolve().tag` — must resolve a registry
manifest before the PR may merge. Red on a 404 / absent manifest, green only
when every repinned engine's tag resolves. An engine this change does NOT
re-pin is never queried, so a normal PR stays hermetic and fast; the network is
touched only for engines a bump actually moved.

No container is started, nothing is pulled or built — a registry manifest digest
lookup per repinned tag (`engine_image._digest_http`), the same hermetic-testable
probe `wait_published` uses (issue #169). LLGENIE_REGISTRY overrides the registry
(a fork's GHCR), matching every other engine path.

Usage:
    python3 scripts/check_engine_pins_published.py check [--base REF]   # exit 1 on an unavailable repinned tag
    python3 scripts/check_engine_pins_published.py report [--base REF]  # print the repinned set and the lookups

`--base` is resolved by scripts/base_ref (issue #925) when not given, so it
compares against the same tree CI does.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import engine_image as ei  # noqa: E402
import base_ref  # noqa: E402


def repinned_engine_ids(base: str, root: Path | None = None) -> list[str]:
    """Engine ids whose committed params differ from `base` (or are new there).

    The comparison is the params FILE, the thing a bump writes, never a skill
    (mirrors `install_engine_launchers.PARAMS`). An engine with no params copy on
    the base is repinned too: it is a first import, and nothing has published it.
    """
    root = root or REPO
    params_dir = root / "containers" / "engines" / "params"
    ids: list[str] = []
    for path in sorted(params_dir.glob("*.json")):
        rel = f"containers/engines/params/{path.name}"
        shown = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=root,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                               capture_output=True, text=True)
        if shown.returncode != 0 or shown.stdout != path.read_text():
            with path.open() as fh:
                ids.append(json.load(fh)["id"])
    return ids


def exact_tags(engine: str, variant: str) -> str:
    """The exact published tag install/CI pulls for this engine x variant."""
    return ei.resolve(engine, None, variant)["tag"]


def check(base: str, root: Path | None = None,
          digest: Callable[[str], tuple[str, str]] | None = None,
          registry: str | None = None) -> int:
    """Exit 0 only when every repinned engine's exact tag resolves a manifest."""
    registry = registry if registry is not None else ei.REGISTRY
    probe = digest if digest is not None else ei._digest_http
    ids = repinned_engine_ids(base, root)
    if not ids:
        print("[pins] no engine this change repins; nothing to check")
        return 0
    missing: list[str] = []
    checked = 0
    for engine in ids:
        params = json.loads((REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
        for variant in sorted(params["variants"]):
            if ei.disabled(engine, variant):
                continue
            tag = exact_tags(engine, variant)
            ref = f"{registry}/{tag}"
            d, err = probe(ref)
            checked += 1
            if d:
                print(f"[pins] PUBLISHED {ref}")
            else:
                missing.append(ref)
                print(f"[pins] NOT PUBLISHED {ref} ({err})")
    if missing:
        print(f"[pins] FAIL {len(missing)} repinned image(s) are not published "
              f"(of {checked} checked): a pin bump may merge only once its image is "
              f"on the registry — dispatch engine-build with push=true for the "
              f"repinned engine, then re-run this check (issue #1622)", file=sys.stderr)
        return 1
    print(f"[pins] every repinned engine image ({checked}) is published")
    return 0


def report(base: str) -> int:
    ids = repinned_engine_ids(base)
    print(f"[pins] {len(ids)} repinned engine(s) vs {base}: {', '.join(ids) or '-'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "report"), nargs="?", default="check")
    ap.add_argument("--base", default="")
    args = ap.parse_args(argv)
    base = base_ref.resolve_base(explicit=args.base, quiet=True)
    if args.cmd == "report":
        return report(base)
    return check(base)


if __name__ == "__main__":
    sys.exit(main())
