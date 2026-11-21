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
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import engine_image as ei  # noqa: E402
import base_ref  # noqa: E402


def repinned_cells(base: str, root: Path | None = None) -> list[tuple[str, str]]:
    """The (engine, variant) CELLS whose published TAG identity moves from `base` (issue #2590).

    The cell-granularity view behind `retagged_engine_ids`: the same pair of functions that
    build the real tag — `_current_tag` for this tree, `_tag_at` for `base` — collected per
    cell instead of deduped to an engine id. A cell whose params copy is missing at `base`,
    or whose tag inputs cannot be read there, has the base tag `""` != its current tag: a
    first import moves every enabled cell of that engine. Disabled cells never move.

    The will-arm (`engine_build_trigger`) dispatches at THIS granularity: an arch-less
    producer dispatch of a `DEFAULT_CPU_ONLY` engine builds only its cpu cell (issue #1836
    narrowing), so a repinned GPU cell of such an engine was never built — the #2582 rocm
    tag stayed unpublished while only the cpu cell got a producer run. Naming the cell and
    dispatching `engine=<id> arch=<variant>` activates the #2561 rule: an explicit selection
    must build the cell it names or die at the matrix step.
    """
    root = root or REPO
    params_dir = root / "containers" / "engines" / "params"
    moved: list[tuple[str, str]] = []
    for path in sorted(params_dir.glob("*.json")):
        try:
            with path.open() as fh:
                params = json.load(fh)
            engine = params["id"]
            for variant in sorted(params.get("variants", {})):
                if ei.disabled(engine, variant):
                    continue
                if ei._tag_at(base, engine, variant, root) != ei._current_tag(params, variant, root):
                    moved.append((engine, variant))
        except (KeyError, ValueError, OSError):
            # Not engine-shaped params (a harness fixture) or an input file the digest
            # cannot read: tag identity cannot judge this file, so its own text diff
            # decides it — the union only ADDS verdicts it can compute confidently.
            continue
    return moved


def retagged_engine_ids(base: str, root: Path | None = None) -> list[str]:
    """Engine ids whose published TAG identity moves between `base` and this tree.

    `engine_skills._image_inputs` hashes the variant params + the variant's
    committed Dockerfile + `entrypoint.sh` + `engine_runner.py` into the
    `<pin8>-<hash8>-<variant>` tag, so a change to ANY of those bytes retags the
    cell. The params-FILE diff alone misses Dockerfile-only edits: merge
    `aa700cf27` (#2517) changed 36 Dockerfiles and no params file, both repin
    consumers saw an empty diff, and 28 committed tags merged unpublished — main
    went red (issue #2559). Both sides are the functions that build the real tag:
    `_current_tag` for this tree, `_tag_at` for `base`. Disabled cells never move.

    This is the engine-deduped view of `repinned_cells` (#2590): one comparison path,
    two granularities.
    """
    return list(dict.fromkeys(engine for engine, _variant in repinned_cells(base, root)))


def repinned_engine_ids(base: str, root: Path | None = None) -> list[str]:
    """Engine ids whose published images differ from `base`: params diff UNION tag identity.

    The params FILE stays the first comparison — the thing a bump writes, never a
    skill (mirrors `install_engine_launchers.PARAMS`) — and everything it named
    before is still named (issue #1622 behaviour, never loosened). Tag identity
    (issue #2559) adds what file text cannot see: Dockerfile, entrypoint, runner
    or tag-computation edits retag every cell they hash. An engine with no params
    copy on the base is repinned too: it is a first import, and nothing has
    published it.
    """
    root = root or REPO
    params_dir = root / "containers" / "engines" / "params"
    moved = {engine for engine, _variant in repinned_cells(base, root)}
    ids: list[str] = []
    for path in sorted(params_dir.glob("*.json")):
        rel = f"containers/engines/params/{path.name}"
        shown = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=root,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                               capture_output=True, text=True)
        with path.open() as fh:
            engine = json.load(fh)["id"]
        if shown.returncode != 0 or shown.stdout != path.read_text() or engine in moved:
            ids.append(engine)
    return ids


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
           registry: str, what: str, patience_seconds: float = 0.0,
           sleep: Callable[[float], None] = time.sleep,
           clock: Callable[[], float] = time.monotonic,
           retry_seconds: float = 120.0,
           alias_check: bool = False) -> int:
    """Probe every (engine, variant) cell's exact tag; exit 1 when any is not published.

    `cells` is the scope being verified (the repin diff, or the full committed set);
    `what` names it in the output for the two call sites.

    `patience_seconds` (issue #2973): a committed-scope live run may overlap the main
    CI pipeline that pushes those very images, so a manifest that is absent NOW may
    land within the pipeline's normal push window. Every cell is probed once first;
    only the UNRESOLVED refs are re-probed every `retry_seconds` until one bounded
    deadline for the whole check (never one window per cell), resolving green the
    moment a manifest appears. A genuinely unpublished ref still reds at the
    deadline — never later. 0 (the default everywhere else, incl. every PR lane)
    keeps today's immediate red: a pin bump may still not merge while its image
    is unpublished.
    """
    tags = {f"{registry}/{exact_tags(engine, variant)}": (engine, variant)
            for engine, variant in cells}
    resolved: dict[str, tuple[str, str, str]] = {}  # ref -> (engine, variant, digest)
    unresolved: dict[str, str] = {}
    for ref, (engine, variant) in tags.items():
        d, err = probe(ref)
        if d:
            resolved[ref] = (engine, variant, d)
        else:
            unresolved[ref] = err
    if unresolved and patience_seconds > 0:
        deadline = clock() + patience_seconds
        while unresolved and clock() + retry_seconds <= deadline:
            for ref, err in unresolved.items():
                print(f"[pins] PATIENCE {ref} unresolved ({err}); re-probing within the "
                      f"{patience_seconds:.0f}s push window (issue #2973)")
            sleep(retry_seconds)
            for ref in list(unresolved):
                d, err = probe(ref)
                if d:
                    resolved[ref] = (tags[ref][0], tags[ref][1], d)
                    del unresolved[ref]
                else:
                    unresolved[ref] = err
    missing: list[str] = []
    for ref, (engine, variant) in tags.items():
        if ref in resolved:
            print(f"[pins] PUBLISHED {ref}")
        else:
            missing.append(ref)
            print(f"[pins] NOT PUBLISHED {ref} ({unresolved[ref]})")
            # Issue #2561 contract line: the canonical selection for this cell — the
            # COMMITTED engine id (dots intact, NOT the ghcr package spelling), the
            # variant, and the committed tag suffix. registry-liveness dispatches
            # engine-build from exactly these lines; package names are a namespace
            # where dots are illegal and must never be reverse-parsed back into ids.
            print(f"[select] {engine} {variant} {exact_tags(engine, variant).split(':')[-1]}")
    lagged: list[str] = []
    if alias_check:
        # Issue #2987: a published unique tag does NOT mean the cell's :<variant>
        # alias points at it. Issue #178 moves the alias on main only, and under
        # tag-existence semantics a merged pin/content change whose producer ran
        # moving_tags=false leaves the alias on an older digest forever. Compare
        # the alias digest with the committed pin digest and emit the same
        # [select] contract line, so liveness dispatches the moving push.
        for ref, (engine, variant) in tags.items():
            if ref not in resolved:
                continue  # already NOT PUBLISHED and selected above
            alias_ref = f"{ref.rpartition(':')[0]}:{variant}"
            ad, aerr = probe(alias_ref)
            if ad and ad == resolved[ref][2]:
                print(f"[pins] ALIAS OK {alias_ref}")
            else:
                lagged.append(alias_ref)
                if not ad:
                    reason = "alias resolves no manifest"
                else:
                    reason = f"alias {ad} != committed {resolved[ref][2]}"
                print(f"[pins] ALIAS LAG {alias_ref} ({reason}) behind committed {ref}")
                print(f"[select] {engine} {variant} {exact_tags(engine, variant).split(':')[-1]}")
            # Issue #2988: the engine's `:latest` belongs to its CANONICAL variant
            # cell only — `engine_image.engine_latest_variant` (issue #638), the
            # exact rule `publish_refs` uses to append `:latest`, so publisher and
            # gate never disagree about ownership. Probe `:latest` once per engine,
            # from that cell's iteration; a lag or an absent manifest is an alias
            # lag: the `[select]` line names the cell whose moving sweep republishes
            # both `:<variant>` and `:latest`.
            if variant != ei.engine_latest_variant(ei.resolve(engine, None, variant)):
                continue  # a non-canonical cell never owns the engine's :latest
            latest_ref = f"{ref.rpartition(':')[0]}:latest"
            ld, lerr = probe(latest_ref)
            if ld and ld == resolved[ref][2]:
                print(f"[pins] LATEST OK {latest_ref}")
            else:
                lagged.append(latest_ref)
                if not ld:
                    reason = "latest resolves no manifest"
                else:
                    reason = f"latest {ld} != committed {resolved[ref][2]}"
                print(f"[pins] ALIAS LAG {latest_ref} ({reason}) behind committed {ref}")
                print(f"[select] {engine} {variant} {exact_tags(engine, variant).split(':')[-1]}")
    if missing:
        print(f"[pins] FAIL {len(missing)} {what} image(s) are not published "
              f"(of {len(tags)} checked): dispatch engine-build with push=true, "
              f"then re-run this check (issue #1622)", file=sys.stderr)
        return 1
    if lagged:
        print(f"[pins] FAIL {len(lagged)} {what} alias(es) lag the committed pin tags "
              f"(of {len(tags)} checked): dispatch engine-build with push=true "
              f"(moving tags), then re-run this check (issues #2987/#2988)", file=sys.stderr)
        return 1
    print(f"[pins] every {what} engine image ({len(tags)}) is published"
          + (" and every arch alias and engine :latest matches its committed tag"
             if alias_check else ""))
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
                    cells: list[tuple[str, str]] | None = None,
                    patience_seconds: float | None = None,
                    alias_check: bool | None = None,
                    sleep: Callable[[float], None] = time.sleep,
                    clock: Callable[[], float] = time.monotonic) -> int:
    """Exit 0 only when EVERY committed enabled engine cell's tag resolves a manifest.

    The committed set, not the repin diff: a cell whose committed tag is absent
    from GHCR is a publish-gap a fresh install hits whether or not a PR moved it
    (issue #2190). `cells` injects the set for tests.

    `patience_seconds=None` reads the knob from `ENGINE_PINS_PATIENCE_SECONDS`
    (issue #2973): `ci-hf-live` sets it to the main CI image-push window so a pin
    whose image lands mid-battery resolves green; every other caller leaves the env
    unset and stays immediate-red. A non-numeric knob value warns and stays 0.

    `alias_check=None` reads the knob from `ENGINE_PINS_ALIAS` (issue #2987):
    `registry-liveness` sets `1` so a committed pin whose `:<variant>` arch alias
    still points at an older digest selects the cell for the moving push; every
    other caller (PR lanes, `ci-hf-live`) leaves it unset and keeps the tag-only
    semantics. `1`/`true` turn it on, `0`/`false`/empty turn it off, anything else
    warns on stderr and stays off. With the knob on the SAME check also gates the
    engine-level `:latest` alias of each engine's canonical variant cell (issue
    #2988, `engine_image.engine_latest_variant` ownership): no second knob exists.
    """
    registry = registry if registry is not None else ei.REGISTRY
    probe = digest if digest is not None else ei._digest_http
    scope = cells if cells is not None else committed_cells(root)
    if patience_seconds is None:
        raw = os.environ.get("ENGINE_PINS_PATIENCE_SECONDS", "0")
        try:
            patience_seconds = max(0.0, float(raw))
        except ValueError:
            print(f"[pins] WARN ENGINE_PINS_PATIENCE_SECONDS={raw!r} is not a number; "
                  "staying impatient (issue #2973)", file=sys.stderr)
            patience_seconds = 0.0
    if alias_check is None:
        raw = os.environ.get("ENGINE_PINS_ALIAS", "0")
        norm = raw.strip().lower()
        if norm in ("1", "true"):
            alias_check = True
        elif norm in ("", "0", "false"):
            alias_check = False
        else:
            print(f"[pins] WARN ENGINE_PINS_ALIAS={raw!r} is neither on nor off; "
                  "staying without the alias check (issue #2987)", file=sys.stderr)
            alias_check = False
    if not scope:
        print("[pins] no committed engine cells; nothing to check")
        return 0
    return _probe(scope, probe, registry, "committed", patience_seconds, sleep,
                  clock, alias_check=alias_check)


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
