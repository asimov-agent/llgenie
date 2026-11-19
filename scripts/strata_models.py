#!/usr/bin/env python3
"""Strata's own model map, vendored as data/strata_models.json (OpenSpec
fix-engine-model-download-map).

Strata (github.com/Niko1221/Strata) runs only the GGUF files its setup.py names:
MODELS (the sizes), FAMILIES (who publishes them, the repo and the shard file
pattern) and HF_REVISIONS (the pinned Hub revision of each repo). llgenie must
download exactly those files, so it reads this copy instead of guessing from a
quant name. The copy is made by importing setup.py at the engine's pinned commit
(the skill's `pinned`), never edited by hand:

  strata_models.py sync        [--src DIR]  clone the pinned ref (or use DIR)
                                             -> write the json AND vendor the setup.py
                                             it read into data/vendor/strata/ (+ manifest)
  strata_models.py check       [--out F] [--vendor DIR]
                                             hermetic (issue #519): exit 1 when the json
                                             differs from the VENDORED pinned setup.py;
                                             never runs git, never reaches the network
  strata_models.py check-live  [--src DIR]  the explicit upstream audit: clone the pinned
                                             ref (or use DIR) and compare the LIVE setup.py

The split is the recorded answer to #519: `make ci-unit`'s `make check-strata-models`
used to shallow-fetch the pinned commit every lane run, so a GitHub hiccup reddened the
gate while the tree was fine — the #437 failure walking back in through a sibling step.
The fetch survives as `make check-strata-models-live` (`check-live`), a named target a
human or a bump lane runs on purpose.

Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "strata_models.json"
VENDOR = REPO / "data" / "vendor" / "strata"
SKILL = REPO / "skills" / "engines" / "strata" / "SKILL.md"
HF_URL = re.compile(r"^https?://[^/]+/(?P<repo>[^/]+/[^/]+)/resolve/(?P<rev>[0-9a-f]{40})/(?P<sub>.*)$")


def pinned() -> tuple[str, str, str]:
    """(repo url, ref, pinned sha) of the Strata skill."""
    text = SKILL.read_text()
    get = lambda k: re.search(rf"^{k}:\s*(\S+)", text, re.M).group(1)  # noqa: E731
    return get("repo"), get("ref"), get("pinned")


def checkout(dest: Path) -> Path:
    """Strata at the skill's pinned commit in `dest` (a shallow fetch of that sha)."""
    url, _ref, sha = pinned()
    if not (dest / ".git").exists():
        subprocess.run(["git", "init", "-q", str(dest)], check=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", url, sha], check=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", sha], check=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return dest


def load_setup(src: Path):
    """Import Strata's setup.py as a module (it only runs main() as __main__).

    Two disciplines the vendored hermetic check (#519) needs: the checkout/vendor dir goes on
    `sys.path` so setup.py's sibling imports (`from strata_control import acquisition`) resolve
    against THAT tree, and the previous run's `strata_control` is evicted from `sys.modules`
    first, so a fixture tree, the live checkout and the vendor each import their own copy
    instead of reusing whoever imported first. No bytecode is written: the vendor tree must
    stay exactly the committed file set.
    """
    spec = importlib.util.spec_from_file_location("strata_setup", src / "setup.py")
    mod = importlib.util.module_from_spec(spec)
    stale = [k for k in sys.modules if k == "strata_control" or k.startswith("strata_control.")]
    for k in stale:
        del sys.modules[k]
    sys.path.insert(0, str(src))
    no_bc = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = no_bc
        sys.path.remove(str(src))
    return mod


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def extract(src: Path) -> dict:
    """The download-relevant part of setup.py's tables, with each family's hf URL split
    into repo / revision / subfolder template (`{q}` = the size)."""
    s = load_setup(src)
    fams = {}
    for name, fam in s.FAMILIES.items():
        hf = fam.get("hf")
        if hf is None:
            # A family with no Hub URL is legitimate — a vendor-hosted or download-free family
            # (Strata's `nvfp4` carries mmproj_sha256 / ready instead). Demanding an `hf` here
            # made EVERY Strata bump die on `KeyError: 'hf'` the moment upstream added one
            # (issue #416). Describe it as not Hub-downloadable, so the runtime can skip it.
            fams[name] = {"title": fam.get("title", name), "hub": False,
                          "file": fam.get("file"), "shards": fam.get("shards", 2),
                          "experimental": bool(fam.get("experimental"))}
            continue
        m = HF_URL.match(str(hf))
        if not m:
            raise SystemExit(f"[strata-models] FAMILIES[{name}].hf is not a pinned Hub URL: {hf}")
        # The key order is the committed file's order: `check` compares TEXT, so a reordering
        # would red `make check-strata-models` at the current pin for no data reason.
        fams[name] = {"title": fam.get("title", name), "repo": m["repo"], "revision": m["rev"],
                      "subdir": m["sub"], "file": fam.get("file"),
                      "shards": fam.get("shards", 2),
                      "experimental": bool(fam.get("experimental"))}
    models = {}
    for size, d in s.MODELS.items():
        models[size] = {"download_gb": d["download_gb"], "ram_gb": d["ram_gb"],
                        "families": list(d.get("families", ("qwen", "swift"))),
                        "experimental": bool(d.get("experimental")),
                        **({"file": d["file"]} if d.get("file") else {}),
                        **({"shards": d["shards"]} if d.get("shards") else {}),
                        # v0.2.15 added per-model Hub overrides: `quant` is the name the files
                        # and folder carry on the Hub when it differs from the catalog name
                        # (setup.py model_quant; UNSLOTH_V31_IQ4_XS's catalog name is
                        # UD-IQ4_XS-v31 but its shards live in UD-IQ4_XS/), and `revision` is
                        # the commit they live at when it is not the family's pinned one
                        # (setup.py model_url; the v31 set sits at UNSLOTH_V31_REVISION).
                        # Dropping them made llgenie build names for a directory the Hub does
                        # not have, for a set that does not exist at the family revision.
                        **({"quant": d["quant"]} if d.get("quant") else {}),
                        **({"revision": d["revision"]} if d.get("revision") else {})}
    url, ref, sha = pinned()
    return {"_generated_by": "make sync-strata-models (scripts/strata_models.py) - do not edit",
            "source": f"{url}/blob/{sha}/setup.py", "ref": ref, "pinned": sha,
            "hf_revisions": _plain(s.HF_REVISIONS), "families": fams, "models": models}


def family_shape_problems(families: dict) -> list[str]:
    """Every way a family table breaks "Hub-hosted unless explicitly not-Hub".

    A family is either Hub-hosted — a `repo`, its `revision` and its `subdir`, and no `hub` key at
    all — or explicitly not-Hub: `hub` is `False` and there is no repo/revision/subdir to build a
    URL from. Never both, never neither. WHICH families land in the second shape is the pinned
    setup.py's decision (`nvfp4` has no `hf` at v0.2.4 and none at v0.1.43), so the set is read from
    the map, never from a list here. Returns the problems by family name; empty means well-formed.
    """
    problems = []
    for name, fam in families.items():
        if fam.get("hub") is False:
            if fam.get("repo"):
                problems.append(f"{name}: marked not-Hub (`hub: false`) but carries a repo")
            for key in ("revision", "subdir"):
                if key in fam:
                    problems.append(f"{name}: marked not-Hub (`hub: false`) but carries `{key}`")
        elif "hub" in fam:
            problems.append(f"{name}: carries a `hub` key but is Hub-hosted "
                            "(only `hub: false` is ever written)")
        elif not fam.get("repo"):
            problems.append(f"{name}: neither a repo nor `hub: false`")
        else:
            # `subdir` may be "" (a family published at the repo root — Strata's `swift` is) but
            # it must be PRESENT: an absent one means the URL was never split.
            for key in ("revision", "subdir"):
                if key not in fam:
                    problems.append(f"{name}: Hub-hosted but no `{key}`")
            if not fam.get("revision"):
                problems.append(f"{name}: Hub-hosted but its `revision` is empty")
    return problems


def _src(arg: str | None, tmp: str) -> Path:
    return Path(arg) if arg else checkout(Path(tmp) / "strata")


def _copy_module(src: Path, vendor_dir: Path, name: str) -> bool:
    """Copy one importable module (or package `__init__`) from a checkout into the vendor tree."""
    rel = Path(name.replace(".", "/"))
    mod_f, pkg_init = src / f"{rel}.py", src / rel / "__init__.py"
    if mod_f.exists():
        (vendor_dir / f"{rel}.py").parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mod_f, vendor_dir / f"{rel}.py")
        return True
    if pkg_init.exists():
        (vendor_dir / rel).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pkg_init, vendor_dir / rel / "__init__.py")
        return True
    return False


def vendor(src: Path, vendor_dir: Path) -> None:
    """Commit the very source the map was derived from, plus the manifest that pins it.

    Written only by `sync`. The vendored pair is the source and the proof together: the map
    must derive from EXACTLY these bytes, and `check` can prove "these bytes are the skill pin's
    bytes" from the manifest alone — same pin, every file hashes to its recorded sha256.

    The vendor is not just `setup.py`: the pinned setup.py imports its sibling package at module
    level (`from strata_control import acquisition, tls, netpolicy, atomic` — #3722 TLS pinning),
    so importing it needs that import surface. `sync` discovers it by importing the vendored
    setup.py from the vendor dir alone, copying whatever module the interpreter asks for next,
    until the import succeeds. That keeps the vendor the MINIMAL tree that reproduces the map,
    and a stale/tampered vendor fails the check loudly rather than quietly importing from
    somewhere else.
    """
    url, ref, sha = pinned()
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    vendor_dir.mkdir(parents=True)
    shutil.copyfile(src / "setup.py", vendor_dir / "setup.py")
    for _ in range(200):  # a bounded convergence, not a fallback: exhaustion is a loud failure
        try:
            extract(vendor_dir)
            break
        except ModuleNotFoundError as exc:
            missing = exc.name or str(exc)
            if not _copy_module(src, vendor_dir, missing):
                raise SystemExit(f"[strata-models] sync cannot vendor the import surface setup.py "
                                 f"needs: {missing!r} is not importable from {src}")
        except ImportError as exc:
            m = re.search(r"cannot import name '(\w+)' from '([\w.]+)'", str(exc))
            if not m or not _copy_module(src, vendor_dir, f"{m[2]}.{m[1]}"):
                raise SystemExit(f"[strata-models] sync cannot vendor the import surface setup.py "
                                 f"needs: {exc}")
    else:
        raise SystemExit("[strata-models] sync: the vendored import surface did not converge; "
                         "setup.py's module-level imports need more than 200 modules")
    files = sorted(p.relative_to(vendor_dir).as_posix()
                   for p in vendor_dir.rglob("*") if p.is_file())
    (vendor_dir / "manifest.json").write_text(json.dumps({
        "_generated_by": "make sync-strata-models (scripts/strata_models.py) - do not edit",
        "url": url, "ref": ref, "pinned": sha,
        "files": {f: hashlib.sha256((vendor_dir / f).read_bytes()).hexdigest() for f in files},
    }, indent=2) + "\n")


def hermetic_src(vendor_dir: Path) -> Path | None:
    """The vendor chain `check` reads instead of fetching (#519), or None + the named failure.

    Four assertions, each naming `make sync-strata-models` as the repair: the pair exists; its
    manifest pin equals the skill's pin (a bump that forgot to re-vendor is a stale vendor, not
    a green check); every recorded file hashes to its sha256 (a hand-edit of a vendored file is
    a tamper, not a source); and the tree carries no file the manifest did not record (an extra
    module could smuggle an import the pinned source never ran).
    """
    _url, _ref, sha = pinned()
    setup_p, man_p = vendor_dir / "setup.py", vendor_dir / "manifest.json"
    if not setup_p.exists() or not man_p.exists():
        print(f"[strata-models] FAIL {vendor_dir} carries no committed setup.py/manifest; "
              "run `make sync-strata-models`", file=sys.stderr)
        return None
    try:
        man = json.loads(man_p.read_text())
    except ValueError as exc:
        print(f"[strata-models] FAIL {man_p} is not valid json ({exc}); "
              "run `make sync-strata-models`", file=sys.stderr)
        return None
    if man.get("pinned") != sha:
        print(f"[strata-models] FAIL the vendor was made for pin {man.get('pinned')!r} but "
              f"{SKILL.relative_to(REPO)} pins {sha!r}; the bump did not re-run "
              "`make sync-strata-models`", file=sys.stderr)
        return None
    recorded = man.get("files") or {}
    if "setup.py" not in recorded:
        print(f"[strata-models] FAIL {man_p} records no setup.py; run `make sync-strata-models`",
              file=sys.stderr)
        return None
    for name, want_sha in sorted(recorded.items()):
        f = vendor_dir / name
        if not f.is_file():
            print(f"[strata-models] FAIL the vendored {name} named by the manifest is missing; "
                  "run `make sync-strata-models`", file=sys.stderr)
            return None
        if hashlib.sha256(f.read_bytes()).hexdigest() != want_sha:
            print(f"[strata-models] FAIL the vendored {name} does not hash to the manifest sha256 "
                  f"({want_sha!r}); the vendor was edited after `make sync-strata-models` wrote it",
                  file=sys.stderr)
            return None
    extra = sorted(p.relative_to(vendor_dir).as_posix()
                   for p in vendor_dir.rglob("*")
                   if p.is_file() and p.relative_to(vendor_dir).as_posix() not in recorded
                   and p.name != "manifest.json")
    if extra:
        print(f"[strata-models] FAIL {vendor_dir} carries files the manifest never recorded: "
              f"{', '.join(extra)}; run `make sync-strata-models`", file=sys.stderr)
        return None
    return vendor_dir


def _verify_against(out: Path, want: str) -> int:
    """The shared verdict of both compare paths: committed-map shape first, then identity."""
    have = out.read_text() if out.exists() else ""
    # A hand-edited map is named by what is wrong with it, not left to a 100-line diff: the
    # family shapes are the invariant every consumer relies on (#416 made one shape optional).
    try:
        problems = family_shape_problems(json.loads(have)["families"])
    except (ValueError, KeyError, TypeError):
        problems = [f"not a Strata map (cannot read `families` from {out})"]
    if problems:
        for p in problems:
            print(f"[strata-models] FAIL {p}", file=sys.stderr)
        print(f"[strata-models] FAIL {out} is malformed; run `make sync-strata-models`",
              file=sys.stderr)
        return 1
    if have != want:
        print(f"[strata-models] FAIL {out} differs from Strata's setup.py at the pinned commit; "
              "run `make sync-strata-models`", file=sys.stderr)
        return 1
    print(f"[strata-models] {out} matches Strata's setup.py at the pinned commit")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("sync", "check", "check-live"))
    ap.add_argument("--src", help="a Strata checkout at the pinned commit (sync/check-live; "
                                  "default: fetch it). `check` NEVER fetches: without --src it "
                                  "reads the vendored copy named by --vendor.")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--vendor", default=str(VENDOR),
                    help="the vendored setup.py/manifest pair (default: data/vendor/strata/) "
                         "that `check` compares against and `sync` writes")
    a = ap.parse_args(argv)
    out, vendor_dir = Path(a.out), Path(a.vendor)

    if a.cmd == "check":
        # Hermetic (#519): the committed vendor IS the pinned upstream source. This branch
        # makes no git call and opens no socket, ever.
        src = Path(a.src) if a.src else hermetic_src(vendor_dir)
        if src is None:
            return 1
        return _verify_against(out, json.dumps(extract(src), indent=2) + "\n")

    if a.cmd == "check-live":
        # The explicit upstream audit — the only CHECK path that fetches.
        with tempfile.TemporaryDirectory(prefix="strata-check-live-") as tmp:
            src = _src(a.src, tmp)
            return _verify_against(out, json.dumps(extract(src), indent=2) + "\n")

    with tempfile.TemporaryDirectory() as tmp:
        # setup.py's own order is kept: its default family is the first, its default size the first
        src = _src(a.src, tmp)
        want = json.dumps(extract(src), indent=2) + "\n"
        vendor(src, vendor_dir)
    have = out.read_text() if out.exists() else ""
    if have == want:
        print(f"[strata-models] {out} unchanged")
        return 0
    out.write_text(want)
    print(f"[strata-models] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
