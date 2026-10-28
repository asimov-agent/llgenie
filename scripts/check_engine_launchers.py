#!/usr/bin/env python3
"""Is each `~/bin/llgenie-engine-*` launcher the one the committed params say it should be?

`make engine-launchers` WRITES those scripts, and each embeds a content-addressed image
tag `:<pin[:8]>-<params_hash8>-<variant>`. Nothing compared that tag with the committed
params afterwards, so an engine pin could move and a launcher keep naming the old image:
the host then runs last month's engine and `--version` reports it happily, or a fresh
install fails hard on a tag nobody pushed, with the error pointing at the registry
instead of at the pin drift (issue #842; the same class as #178's "invariant with no
gate").

The tag hashes FOUR inputs, not just the params: the variant's params, its committed
Dockerfile, `containers/engines/entrypoint.sh` and `scripts/engine_runner.py`
(`engine_skills._image_inputs`). A checkout that differs in any of them — a branch editing the
runner, an uncommitted params edit — computes a different tag, so compare against the tree you
intend to install from and expect every launcher to look stale on a branch that touches the
runner.

**The expected tag comes from the launcher writer itself** — `install_engine_launchers.
install_plan()`, the one place that builds the (engine, variant, tag) list `install`
uses. A second copy of the tag formula would agree today and disagree later, which is
exactly the defect this check exists to catch.

Outcomes per engine:
  OK        launcher present and naming the expected tag
  STALE     launcher present and naming a different tag  -> FAIL, both tags and both pins
  MISSING   no launcher in the bin dir                   -> informational (CI's normal state)
  NOT PUBLISHED  with --check-registry: no manifest resolves for the expected tag -> FAIL

No container is started and the default run touches no network. `--check-registry` is
the only thing that talks to a registry, and it is opt-in so CI never depends on GHCR.

Usage:
    python3 scripts/check_engine_launchers.py check            # exit 1 on a stale launcher
    python3 scripts/check_engine_launchers.py check --check-registry
    python3 scripts/check_engine_launchers.py report           # print what it compares
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import engine_image as ei  # noqa: E402
import install_engine_launchers as iel  # noqa: E402  (the launcher WRITER: one formula)

#: The writer emits `IMAGE="${LLGENIE_IMAGE:-<tag>}"`; read exactly that default.
_IMAGE_LINE = re.compile(r'^\s*IMAGE="\$\{LLGENIE_IMAGE:-([^}]+)\}"\s*$', re.MULTILINE)


def launcher_path(bindir: Path, engine: str) -> Path:
    return bindir / iel.script_name(engine)


def launcher_tag(path: Path) -> str:
    """The tag the launcher script carries in its `IMAGE=` default, or '' when absent."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _IMAGE_LINE.search(text)
    return match.group(1) if match else ""


def tag_parts(tag: str) -> tuple[str, str, str]:
    """(pin, params-hash, variant) of `llgenie/x:<pin8>-<hash8>-<variant>`; blanks when'."""
    tail = tag.rsplit(":", 1)[-1] if tag else ""
    parts = tail.split("-")
    return (parts[0], parts[1], "-".join(parts[2:])) if len(parts) >= 3 else (tail, "", "")


def tag_pin(tag: str) -> str:
    """The engine pin a content-addressed tag names."""
    return tag_parts(tag)[0]


def expected(arch: str) -> list[dict]:
    """The (engine, variant, tag) list `install` would write — from the writer itself."""
    return [e for e in iel.install_plan(arch, ["all"]) if e.get("variant")]


def manifest_resolves(tag: str) -> bool:
    """Does a registry manifest resolve for this tag? Never pulls, never builds."""
    if not ei.REGISTRY:
        return False
    return subprocess.run([ei.RUNTIME, "manifest", "inspect", f"{ei.REGISTRY}/{tag}"],
                          capture_output=True).returncode == 0


def check(bindir: Path, arch: str, check_registry: bool = False) -> int:
    rows = expected(arch)
    if not rows:
        print(f"[launchers] no engine params for {arch}: nothing to compare")
        return 0
    stale, unpublished = [], []
    ok = missing = 0
    for row in rows:
        engine, want = row["engine"], row["tag"]
        path = launcher_path(bindir, engine)
        if not path.exists():
            missing += 1
            print(f"[launchers] no launcher for {engine} ({path}) - informational: a host may "
                  f"legitimately have none, CI has none")
            continue
        have = launcher_tag(path)
        if not have:
            stale.append((engine, "", want))
            print(f"[launchers] STALE {engine}: {path} carries no IMAGE= line; expected {want}")
            continue
        if have != want:
            stale.append((engine, have, want))
            print(f"[launchers] STALE {engine}: launcher tag {have} (pin {tag_pin(have)}) != "
                  f"expected {want} (pin {tag_pin(want)}): re-run `make engine-launchers "
                  f"ENGINES={engine}`")
            continue
        ok += 1
        print(f"[launchers] OK {engine} -> {want}")
    if check_registry:
        for row in rows:
            if not manifest_resolves(row["tag"]):
                unpublished.append((row["engine"], row["tag"]))
                print(f"[launchers] NOT PUBLISHED {row['engine']}: {row['tag']} resolves no manifest "
                      f"({ei.REGISTRY or 'no registry'})")
    summary = f"[launchers] {ok} ok, {len(stale)} stale, {missing} missing"
    if check_registry:
        summary += f", {len(unpublished)} not published"
    print(summary + (f" (arch {arch})" if rows else ""))
    if stale or unpublished:
        for engine, have, want in stale:
            hp, hh, hv = tag_parts(have)
            wp, wh, wv = tag_parts(want)
            what = ("an older pin" if hp != wp else "other params (same pin)" if hh != wh
                    else "another variant")
            print(f"[launchers] stale launcher names {what}: {engine} launcher "
                  f"pin={hp or '(none)'} params={hh or '(none)'} variant={hv or '(none)'} -> "
                  f"expected pin={wp} params={wh} variant={wv}", file=sys.stderr)
        return 1
    return 0


def report(bindir: Path, arch: str) -> int:
    rows = expected(arch)
    print(f"[launchers] host arch {arch}; {len(rows)} engine(s) with an image for it")
    for row in rows:
        path = launcher_path(bindir, row["engine"])
        have = launcher_tag(path) if path.exists() else "(no launcher)"
        mark = "ok" if have == row["tag"] else ("missing" if not path.exists() else "STALE")
        print(f"  {row['engine']:<28} [{row['variant']:<6}] {mark:<8} expected {row['tag']}")
        if have != "(no launcher)":
            print(f"  {'':<28} {'':<8} {'':<8} launcher {have}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("cmd", choices=("check", "report"), nargs="?", default="check")
    ap.add_argument("--bin", default=os.environ.get("BIN") or str(Path.home() / "bin"),
                    help="the bin dir the launchers live in (default: ~/bin, or $BIN)")
    ap.add_argument("--arch", default="", help="cpu|cuda|rocm|vulkan (default: this host's)")
    ap.add_argument("--check-registry", action="store_true",
                    default=os.environ.get("CHECK_REGISTRY", "") not in ("", "0", "false"),
                    help="also fail a tag no registry manifest resolves (default: no network)")
    args = ap.parse_args(argv)
    bindir = Path(args.bin).expanduser()
    arch = args.arch or iel.detected_arch()
    if args.cmd == "report":
        return report(bindir, arch)
    return check(bindir, arch, args.check_registry)


if __name__ == "__main__":
    sys.exit(main())
