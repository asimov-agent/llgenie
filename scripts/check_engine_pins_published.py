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

A one-shot 404 is the local and unit-test verdict. CI passes `--wait-min` because
the producer (`engine-build`, 240 minutes) is still compiling when this gate first
runs. The `linux / unit` job cannot hold that long: its ceiling is 120 minutes
(#1173). The waiter is its own job. It polls until every repinned tag resolves or
the wait expires. A tag that is still absent at the deadline fails the job.

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
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import engine_image as ei  # noqa: E402
import base_ref  # noqa: E402

POLL_SECONDS = 30  # a published tag is visible within a poll; the log stays alive


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


def _probe_repins(ids: list[str], probe, registry: str) -> tuple[list[str], int]:
    """Look up every buildable variant. Returns (missing refs, how many were checked)."""
    missing: list[str] = []
    checked = 0
    for engine in ids:
        params = json.loads((REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
        for variant in sorted(params["variants"]):
            if ei.disabled(engine, variant):
                continue
            tag = exact_tags(engine, variant)
            ref = f"{registry}/{tag}"
            digest, err = probe(ref)
            checked += 1
            if digest:
                print(f"[pins] PUBLISHED {ref}")
            else:
                missing.append(ref)
                print(f"[pins] NOT PUBLISHED {ref} ({err})")
    return missing, checked


def _producer_cell_conclusions(repo: str, branch: str, engine: str,
                               gh: str = "gh") -> tuple[str, str] | None:
    """The newest engine-build workflow_dispatch run on `branch` that builds `engine`,
    and its per-engine cell conclusion, or None when none such concluded run exists.

    Mirrors `engine_build_trigger._branch_producers`/`_run_builds_engine` (issue #893
    reads the producer's job state the same way). Returns (run_id, conclusion).
    """
    args = [gh, "api",
            f"repos/{repo}/actions/runs",
            "-X", "GET",
            "--jq", ('[.workflow_runs[] | select((.path == "/.github/workflows/engine-build.yml" '
                     'or .path == ".github/workflows/engine-build.yml") and .status == "completed") '
                     '| {id: (.id|tostring), conclusion, jobs_url}] '
                     '| sort_by(.id) | reverse | .[0:5]'),
            "-f", f"branch={branch}",
            "-f", "event=workflow_dispatch",
            "-f", "per_page=5"]
    raw = subprocess.run(args, capture_output=True, text=True).stdout  # proc-allow: direct gh api probe for the evidence-aware producer-cell pre-poll, tracked remainder for issue #797 (read-only GET, no timeout so a stalled call surfaces at the poll deadline)
    try:
        runs = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        return None
    prefix = f"engine-build-{engine}-"
    for run in runs:
        if not run.get("conclusion"):
            continue
        j = subprocess.run([gh, "api", run.get("jobs_url", "").replace(  # proc-allow: direct gh api probe for the producer-cell job conclusions, tracked remainder for issue #797 (read-only GET)
            "https://api.github.com/", ""),
            "--jq", f"[.jobs[] | select(.name | startswith(\"{prefix}\")) | .conclusion] | unique | .[]"],
            capture_output=True, text=True).stdout.strip()
        if j:
            return str(run["id"]), j
    return None


def check(base: str, root: Path | None = None,
          digest: Callable[[str], tuple[str, str]] | None = None,
          registry: str | None = None, wait_min: int = 0,
          repo: str = "", branch: str = "",
          producer: Callable[[str], tuple[str, str] | None] | None = None,
          gh: str = "gh") -> int:
    """Exit 0 only when every repinned engine's exact tag resolves a manifest.

    `wait_min` polls a 404 until the producer publishes the tag. Zero is one shot.

    Evidence-aware pre-poll (issue #1844): when `wait_min` is set AND the pin-producing
    cell for a repinned engine ALREADY concluded red (failure/cancelled), no publish can
    ever happen — the check concludes immediately with a recorded `skipped` decision
    instead of burning the wait. `producer` injects the cell-conclusion query (hermetic
    tests stub it); the default uses `_producer_cell_conclusions` via `gh`. `repo` names
    the repo for that real query. The wait itself is untouched: a pin whose producing
    cell is green-but-not-yet-published still polls (the gate is not weakened).
    """
    registry = registry if registry is not None else ei.REGISTRY
    probe = digest if digest is not None else ei._digest_http
    conductor = producer if producer is not None else (
        (lambda engine: _producer_cell_conclusions(repo, branch, engine, gh))
        if repo and branch else None)
    ids = repinned_engine_ids(base, root)
    if not ids:
        print("[pins] no engine this change repins; nothing to check")
        return 0
    if wait_min > 0 and conductor is not None:
        for engine in sorted(ids):
            cell = conductor(engine)
            if not cell:
                continue
            concs = [c for c in cell[1].splitlines() if c]
            red = [c for c in concs if c not in ("success", "neutral", "skipped")]
            if red:
                print(f"[pins] SKIPPED engine={engine}: pin-producing cell(s) concluded "
                      f"{', '.join(red)} (run {cell[0]}) — no publish can happen from a red "
                      f"cell, so no wait is owed (issue #1844)", file=sys.stderr)
                return 0
    deadline = time.time() + max(0, wait_min) * 60
    while True:
        missing, checked = _probe_repins(ids, probe, registry)
        if not missing:
            print(f"[pins] every repinned engine image ({checked}) is published")
            return 0
        if wait_min <= 0 or time.time() >= deadline:
            print(f"[pins] FAIL {len(missing)} repinned image(s) are not published "
                  f"(of {checked} checked): a pin bump may merge only once its image is "
                  f"on the registry — dispatch engine-build with push=true for the "
                  f"repinned engine, then re-run this check (issue #1622)", file=sys.stderr)
            return 1
        print(f"[pins] waiting for {len(missing)} tag(s); the engine-build producer "
              f"publishes them (poll {POLL_SECONDS}s, up to {wait_min} min)")
        time.sleep(POLL_SECONDS)


def report(base: str) -> int:
    ids = repinned_engine_ids(base)
    print(f"[pins] {len(ids)} repinned engine(s) vs {base}: {', '.join(ids) or '-'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "report"), nargs="?", default="check")
    ap.add_argument("--base", default="")
    ap.add_argument("--wait-min", type=int, default=0,
                    help="poll a 404 until the producer publishes the tag (0 = one shot)")
    ap.add_argument("--repo", default="",
                    help="owner/repo for the evidence-aware producer-cell pre-poll")
    ap.add_argument("--branch", default="",
                    help="branch to read producer cell conclusions from")
    args = ap.parse_args(argv)
    base = base_ref.resolve_base(explicit=args.base, quiet=True)
    if args.cmd == "report":
        return report(base)
    return check(base, wait_min=args.wait_min, repo=args.repo, branch=args.branch)


if __name__ == "__main__":
    sys.exit(main())
