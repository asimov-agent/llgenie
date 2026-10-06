#!/usr/bin/env python3
"""Strata's own model map, vendored as data/strata_models.json (OpenSpec
fix-engine-model-download-map).

Strata (github.com/Niko1221/Strata) runs only the GGUF files its setup.py names:
MODELS (the sizes), FAMILIES (who publishes them, the repo and the shard file
pattern) and HF_REVISIONS (the pinned Hub revision of each repo). llgenie must
download exactly those files, so it reads this copy instead of guessing from a
quant name. The copy is made by importing setup.py at the engine's pinned commit
(the skill's `pinned`), never edited by hand:

  strata_models.py sync  [--src DIR]   clone the pinned ref (or use DIR) -> write the json
  strata_models.py check [--src DIR]   exit 1 when the json differs from the pinned setup.py

Stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "strata_models.json"
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
        subprocess.run(["git", "init", "-q", str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", url, sha], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", sha], check=True)
    return dest


def load_setup(src: Path):
    """Import Strata's setup.py as a module (it only runs main() as __main__)."""
    spec = importlib.util.spec_from_file_location("strata_setup", src / "setup.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(src))
    try:
        spec.loader.exec_module(mod)
    finally:
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
        m = HF_URL.match(fam["hf"])
        if not m:
            raise SystemExit(f"[strata-models] FAMILIES[{name}].hf is not a pinned Hub URL: {fam['hf']}")
        fams[name] = {"title": fam["title"], "repo": m["repo"], "revision": m["rev"], "subdir": m["sub"],
                      "file": fam["file"], "shards": fam.get("shards", 2),
                      "experimental": bool(fam.get("experimental"))}
    models = {}
    for size, d in s.MODELS.items():
        models[size] = {"download_gb": d["download_gb"], "ram_gb": d["ram_gb"],
                        "families": list(d.get("families", ("qwen", "swift"))),
                        "experimental": bool(d.get("experimental")),
                        **({"file": d["file"]} if d.get("file") else {}),
                        **({"shards": d["shards"]} if d.get("shards") else {})}
    url, ref, sha = pinned()
    return {"_generated_by": "make sync-strata-models (scripts/strata_models.py) - do not edit",
            "source": f"{url}/blob/{sha}/setup.py", "ref": ref, "pinned": sha,
            "hf_revisions": _plain(s.HF_REVISIONS), "families": fams, "models": models}


def _src(arg: str | None, tmp: str) -> Path:
    return Path(arg) if arg else checkout(Path(tmp) / "strata")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("sync", "check"))
    ap.add_argument("--src", help="a Strata checkout at the pinned commit (default: fetch it)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        # setup.py's own order is kept: its default family is the first, its default size the first
        want = json.dumps(extract(_src(a.src, tmp)), indent=2) + "\n"
    out = Path(a.out)
    have = out.read_text() if out.exists() else ""
    if a.cmd == "check":
        if have != want:
            print(f"[strata-models] FAIL {out} differs from Strata's setup.py at the pinned commit; "
                  "run `make sync-strata-models`", file=sys.stderr)
            return 1
        print(f"[strata-models] {out} matches Strata's setup.py at the pinned commit")
        return 0
    if have == want:
        print(f"[strata-models] {out} unchanged")
        return 0
    out.write_text(want)
    print(f"[strata-models] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
