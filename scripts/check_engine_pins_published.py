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

This gate closes that hole AT THE PR: an engine whose committed params text differs from the
base, OR whose computed image tag this tree would publish differs from base (a
`Dockerfile`/`entrypoint.sh`/`engine_runner.py`/tag-computation change re-tags the image
without moving a params byte — the #2517 class), is repinned by THIS change, so its exact
image tag — computed by the ONE tag formula `engine_image.resolve().tag` — must resolve a
registry manifest before the PR may merge. Red on a 404 / absent manifest, green only
when every repinned engine's tag resolves. An engine this change does NOT re-pin is never
queried, so a normal PR stays hermetic and fast; the network is touched only for engines a
bump actually moved.

No container is started, nothing is pulled or built — a registry manifest digest
lookup per repinned tag (`engine_image._digest_http`), the same hermetic-testable
probe `wait_published` uses (issue #169). LLGENIE_REGISTRY overrides the registry
(a fork's GHCR), matching every other engine path.

Usage:
    python3 scripts/check_engine_pins_published.py check [--base REF] [--all]   # exit 1 on an unavailable tag
    python3 scripts/check_engine_pins_published.py report [--base REF]  # print the repinned set

`--all` verifies EVERY committed enabled engine cell's exact tag (the full params
matrix, all backends) instead of only engines THIS change repins — the guard for
the recurring publish-gap class (#1365/#1622) where a bumped pin's image was
never rebuilt (issue #2190: tensorfold/cuda at ef27f74f sat committed while no
PR re-pinned it, so the repin-only gate never fired).

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


def retagged_engine_ids(base: str, root: Path | None = None) -> list[str]:
    """Engine ids whose image tag this tree publishes differs from `base` — the tag-identity diff.

    The published tag `<pin8>-<hash8>-<variant>` hashes the variant's params AND
    the engine's `Dockerfile.<variant>` plus `entrypoint.sh` and `engine_runner.py`
    (`engine_skills._image_inputs`) — the very framing `_tag_at`/`_current_tag`
    compute. So a Dockerfile-only change re-tags every engine while the params FILE
    is byte-identical: the #2517 class (`git diff -- containers/engines/params/`
    empty, 36 Dockerfiles changed, every committed tag moved). Comparing params text
    alone cannot see a retag; this names the engines the params diff misses.

    For every buildable engine x arch cell (the full committed matrix minus
    DISABLED — the same set the may-arm probes) it compares the tag this tree would
    publish (`ei._current_tag`) with the tag `base` would publish (`ei._tag_at`) and
    names every engine whose cells differ. An engine with no base copy (a first
    import) counts too: `_tag_at` yields '' there and nothing has published it.
    """
    root = root or REPO
    changed: set[str] = set()
    for engine, variant in committed_cells(root):
        params = json.loads((root / "containers" / "engines" / "params" / f"{engine}.json").read_text())
        if ei._current_tag(params, variant, root) != ei._tag_at(base, engine, variant, root):
            changed.add(engine)
    return sorted(changed)


def repinned_engine_ids(base: str, root: Path | None = None) -> list[str]:
    """Engine ids this change repins OR re-tags vs `base`.

    Union of two diffs, neither ever loosened:

    1. the params FILE diff — the thing a bump writes, never a skill (mirrors
       `install_engine_launchers.PARAMS`). An engine with no params copy on the
       base is repinned too: it is a first import, and nothing has published it.
    2. the tag-identity diff (`retagged_engine_ids`) — an engine whose image tag
       this tree publishes differs from `base`, because a `Dockerfile` /
       `entrypoint.sh` / `engine_runner.py` / tag-computation change re-tags the
       image without touching a params byte (issue #2517). Both the may-arm merge
       gate and the will-arm pr-trigger inherit this union, so a retagging PR
       cannot merge while its images are unpublished and is the PR that publishes
       them.
    """
    root = root or REPO
    params_dir = root / "containers" / "engines" / "params"
    ids: set[str] = set()
    for path in sorted(params_dir.glob("*.json")):
        rel = f"containers/engines/params/{path.name}"
        shown = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=root,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                               capture_output=True, text=True)
        if shown.returncode != 0 or shown.stdout != path.read_text():
            with path.open() as fh:
                ids.add(json.load(fh)["id"])
    ids.update(retagged_engine_ids(base, root))
    return sorted(ids)


def exact_tags(engine: str, variant: str) -> str:
    """The exact published tag install/CI pulls for this engine x variant."""
    return ei.resolve(engine, None, variant)["tag"]


def committed_cells(root: Path | None = None) -> list[tuple[str, str]]:
    """Every (engine, variant) the committed params declare buildable — all backends.

    The image matrix is derived from the params (every non-disabled variant is a
    CI cell), so this is the FULL committed engine set, not the repin diff. It is
    the set a fresh install can actually pull, so a cell whose tag resolves no
    manifest is a real publish-gap (the #1365/#1622 class) whether or not THIS
    change touched it — issue #2190 (tensorfold/cuda pinned ef27f74f, never
    rebuilt after the #1519 bump).
    """
    root = root or REPO
    params_dir = root / "containers" / "engines" / "params"
    cells: list[tuple[str, str]] = []
    for path in sorted(params_dir.glob("*.json")):
        with path.open() as fh:
            params = json.load(fh)
        for variant in sorted(params["variants"]):
            if ei.disabled(params["id"], variant):
                continue
            cells.append((params["id"], variant))
    return cells


def _probe(cells: list[tuple[str, str]], probe: Callable[[str], tuple[str, str]],
           registry: str, what: str) -> int:
    """Probe every (engine, variant) cell's exact tag; exit 1 when any is not published.

    `cells` is the scope being verified (the repin diff, or the full committed set);
    `what` names it in the output for the two call sites.
    """
    missing: list[str] = []
    checked = 0
    for engine, variant in cells:
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
        print(f"[pins] FAIL {len(missing)} {what} image(s) are not published "
              f"(of {checked} checked): dispatch engine-build with push=true, "
              f"then re-run this check (issue #1622)", file=sys.stderr)
        return 1
    print(f"[pins] every {what} engine image ({checked}) is published")
    return 0


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
    return _probe([(e, v) for e in ids
                   for v in _enabled_variants(e)], probe, registry, "repinned")


def check_committed(digest: Callable[[str], tuple[str, str]] | None = None,
                    registry: str | None = None, root: Path | None = None,
                    cells: list[tuple[str, str]] | None = None) -> int:
    """Exit 0 only when EVERY committed enabled engine cell's tag resolves a manifest.

    The committed set, not the repin diff: a cell whose committed tag is absent
    from GHCR is a publish-gap a fresh install hits whether or not a PR moved it
    (issue #2190). `cells` injects the set for tests.
    """
    registry = registry if registry is not None else ei.REGISTRY
    probe = digest if digest is not None else ei._digest_http
    scope = cells if cells is not None else committed_cells(root)
    if not scope:
        print("[pins] no committed engine cells; nothing to check")
        return 0
    return _probe(scope, probe, registry, "committed")


def _enabled_variants(engine: str) -> list[str]:
    params = json.loads((REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    return [v for v in sorted(params["variants"]) if not ei.disabled(engine, v)]




def report(base: str) -> int:
    ids = repinned_engine_ids(base)
    print(f"[pins] {len(ids)} repinned engine(s) vs {base}: {', '.join(ids) or '-'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "report"), nargs="?", default="check")
    ap.add_argument("--base", default="")
    ap.add_argument("--all", action="store_true",
                    help="verify EVERY committed enabled engine cell's tag, not just engines this change repins")
    args = ap.parse_args(argv)
    base = base_ref.resolve_base(explicit=args.base, quiet=True)
    if args.cmd == "report":
        return report(base)
    if args.all:
        return check_committed()
    return check(base)


if __name__ == "__main__":
    sys.exit(main())
