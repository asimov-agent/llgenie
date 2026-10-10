#!/usr/bin/env python3
"""Vendor the trending-local-llms registry into data/models.json (issue #105).

  sync_registry.py sync  [--src URL|FILE] [--dest FILE]   download, validate, write when changed
  sync_registry.py check [--dest FILE]                    validate the vendored file

The file is copied byte-for-byte (no reformatting), so `git diff` shows exactly
what upstream changed. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = "https://raw.githubusercontent.com/andyholst/trending-local-llms/master/data/models.json"
UPSTREAM_README = "https://raw.githubusercontent.com/andyholst/trending-local-llms/master/README.md"
VENDORED = REPO / "data" / "models.json"
VENDORED_README = REPO / "data" / "trending-README.md"  # the list a user reads; tests compare against it
MOST_LOVED = "## ❤️ Most loved"


def validate(raw: bytes) -> dict:
    """Parse + shape-check a registry; raise ValueError naming the first problem."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"not JSON: {e}") from None
    if not isinstance(data, dict):
        raise ValueError("top level must be an object")
    if not isinstance(data.get("engines"), dict) or not data["engines"]:
        raise ValueError("'engines' must be a non-empty object")
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("'models' must be a non-empty list")
    for i, m in enumerate(models):
        for key in ("id", "name", "vram_tier", "engines"):
            if key not in m:
                raise ValueError(f"models[{i}] ({m.get('id', '?')}) lacks {key!r}")
        if not isinstance(m["engines"], list):
            raise ValueError(f"models[{i}] ({m['id']}) 'engines' must be a list")
        for e in m["engines"]:
            if "engine" not in e:
                raise ValueError(f"models[{i}] ({m['id']}) has an engine row without 'engine'")
    return data


def readme_order(readme: str) -> list[str]:
    """Model names of the README "Most loved" table, in README order."""
    if MOST_LOVED not in readme:
        raise ValueError("README has no 'Most loved' table")
    section = readme.split(MOST_LOVED, 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| \[\*\*(.+?)\*\*\]", section, re.M)


def readme_best(readme: str, column: str) -> dict[str, str]:
    """Model name -> the engine named first in one backend column of the README
    "Most loved" table (the best measured t/s on that backend)."""
    if MOST_LOVED not in readme:
        raise ValueError("README has no 'Most loved' table")
    section = readme.split(MOST_LOVED, 1)[1].split("\n## ", 1)[0]
    lines = section.splitlines()
    header = next((l for l in lines if l.startswith("| Model")), "")
    heads = [c.strip() for c in header.strip("|").split("|")]
    if column not in heads:
        raise ValueError(f"README 'Most loved' table has no {column!r} column")
    idx = heads.index(column)
    out = {}
    for line in lines:
        m = re.match(r"^\| \[\*\*(.+?)\*\*\]", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        eng = re.search(r"\[(.+?)\]\(https://github.com/", cells[idx]) if idx < len(cells) else None
        if eng:
            out[m.group(1)] = eng.group(1)
    return out


def check_readme_matches(data: dict, readme: str) -> None:
    """The vendored registry must be the README's list: the same models, in the
    README's order, and each model's best engine per backend column is an engine
    the registry records for that model."""
    names = [m["name"] for m in data["models"]]
    order = readme_order(readme)
    if names != order:
        raise ValueError(f"models.json order {names} != README 'Most loved' order {order}")
    by_name = {m["name"]: m for m in data["models"]}
    for column in ("CUDA t/s (best)", "Metal t/s (best)", "CPU t/s (best)", "ROCm t/s (best)"):
        for name, engine in readme_best(readme, column).items():
            known = {e["engine"] for e in by_name[name].get("engines") or []} | \
                set(by_name[name].get("supported_engines") or [])
            if engine not in known:
                raise ValueError(f"{name}: README {column} names {engine!r}, which the registry "
                                 f"does not list for it (has {sorted(known)})")


def readme_links(readme: str) -> list[str]:
    """Every link in the README "Most loved" table: the model pages and the engine repos."""
    if MOST_LOVED not in readme:
        raise ValueError("README has no 'Most loved' table")
    section = readme.split(MOST_LOVED, 1)[1].split("\n## ", 1)[0]
    return re.findall(r"\]\((https?://[^)]+)\)", section)


def check_links(links: list[str], attempts: int = 5, backoff: float = 10.0) -> list[str]:
    """The links that do not answer. A link answers when a GET request comes back
    below 400 (only the status is read, not the body). GET, not HEAD: from GitHub
    Actions runners github.com answers HEAD with 504s it does not give a browser GET.
    A server error (5xx) or a network error is retried ``attempts`` times; a 4xx is
    dead at once."""
    dead = []
    for url in dict.fromkeys(links):  # order kept, duplicates dropped
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "llgenie-link-check"})
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                    if r.status >= 400:
                        dead.append(f"{url} -> {r.status}")
                break
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == attempts:
                    dead.append(f"{url} -> {e}")
                    break
            except Exception as e:  # noqa: BLE001 - a dead link is a result, not a crash
                if attempt == attempts:
                    dead.append(f"{url} -> {e}")
                    break
            time.sleep(backoff * attempt)
    return dead


def fetch(src: str) -> bytes:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "llgenie-sync-registry"})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            return r.read()
    return Path(src).read_bytes()


def _summary(data: dict) -> str:
    return f"generated_utc={data.get('generated_utc', '?')} models={len(data['models'])}"


def sync(src: str, dest: Path, readme_src: str | None = UPSTREAM_README,
         readme_dest: Path | None = None) -> int:
    """Copy the registry (and the README it was generated with) byte for byte,
    after checking the registry's shape and that it is the README's list in order."""
    readme_dest = readme_dest or dest.with_name(VENDORED_README.name)
    raw = fetch(src)
    try:
        new = validate(raw)
        readme = fetch(readme_src).decode() if readme_src else None
        if readme is not None:
            check_readme_matches(new, readme)
    except ValueError as e:
        print(f"[sync-registry] REJECTED {src}: {e}", file=sys.stderr)
        return 1
    old = dest.read_bytes() if dest.exists() else b""
    same_readme = readme is None or (readme_dest.exists() and readme_dest.read_text() == readme)
    if old == raw and same_readme:
        print(f"[sync-registry] unchanged: {dest} ({_summary(new)})")
        return 0
    before = _summary(validate(old)) if old else "(none)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    if readme is not None:
        readme_dest.write_text(readme)
    print(f"[sync-registry] updated {dest}: {before} -> {_summary(new)}")
    return 0


def check(dest: Path, readme: Path | None = None) -> int:
    if not dest.exists():
        print(f"[check-registry] missing {dest}: run make sync-registry", file=sys.stderr)
        return 1
    readme = readme or dest.with_name(VENDORED_README.name)
    try:
        data = validate(dest.read_bytes())
        if readme.exists():
            check_readme_matches(data, readme.read_text())
            dead = check_links(readme_links(readme.read_text()))
            if dead:
                raise ValueError("dead README links:\n  " + "\n  ".join(dead))
        elif dest == VENDORED:
            raise ValueError(f"missing {readme}: run make sync-registry")
    except ValueError as e:
        print(f"[check-registry] {dest}: {e}", file=sys.stderr)
        return 1
    print(f"[check-registry] OK {dest} ({_summary(data)}; README order matches, links answer)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("sync", "check"))
    ap.add_argument("--src", default=UPSTREAM)
    ap.add_argument("--dest", default=str(VENDORED))
    a = ap.parse_args(argv)
    return sync(a.src, Path(a.dest)) if a.cmd == "sync" else check(Path(a.dest))


if __name__ == "__main__":
    sys.exit(main())
