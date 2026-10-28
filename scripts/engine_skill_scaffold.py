#!/usr/bin/env python3
"""Scaffold the engine skill a registry engine needs, from the registry's own entry.

  engine_skill_scaffold.py scaffold --engine "<registry name>" [--id <kebab>]
                                    [--registry F|URL] [--out DIR] [--servable true|false|via]
                                    [--force] [--dry] [--json]

`registry-sync` copies every engine upstream lists, and `engine_skill_gap.py spawn`
files one tracking issue per engine llgenie does not ship (#229). The step between that
issue and a buildable image was a blank page: the image is generated from
`skills/engines/<id>/SKILL.md` (`make generate-engine-params` -> params + Dockerfile per
arch, then the `engine-image-*` CI matrix), so with no skill there is no image, and with
no image `rank_engines` drops the engine and the models only it serves vanish from the
offer.

This writes the FILE, from what the registry actually states — engine name, upstream
repo URL, backends, and the `os:` those backends can run on (`METAL` alone is `darwin`,
because Metal runs natively and never in an image) — and leaves every other upstream fact
it CANNOT prove EMPTY:

- nothing here guesses a version, a commit, a license, an apt package, a build command
  or a launch flag; a guessed pin is worse than an empty one because it builds;
- `make skills-validate` treats an empty required key as missing and NAMES it, so the
  scaffold produces a loud, ordered to-do list instead of a plausible-looking skill that
  fails hours later inside an image build;
- an existing skill is never overwritten (`--force` is the explicit override).

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402
import model_engine_pick as mp  # noqa: E402

SKILLS_DIR = REPO / "skills" / "engines"
# The registry's `backend` is a human string ("CUDA / ROCm / CPU / Metal"); these are the
# container backends a skill may declare (`metal` is native-only but still a backend).
_BACKEND_WORDS = {"cuda": "cuda", "rocm": "rocm", "vulkan": "vulkan", "cpu": "cpu", "metal": "metal"}

# The backends a Linux container image serves. `metal` is the one that does not: it runs
# natively on Apple Silicon and never in an image (`engine_skills.CONTAINER_BACKENDS`).
_LINUX_BACKENDS = ("cuda", "rocm", "vulkan", "cpu")
# The `os:` value a skill declares per shape. Written in the order the repo's own
# dual-OS skills use (`os: [darwin, linux]`).
_DARWIN = ["darwin"]
_LINUX = ["linux"]
_DARWIN_LINUX = ["darwin", "linux"]

# Written EMPTY on purpose: the pinned repo is the only source of these. `validate()`
# reports an empty required key as `missing <key>`, so the list below is also the to-do.
UNPROVABLE = ("description", "ref", "pinned", "verified", "license", "formats", "upstream_watch",
              "prereqs", "install", "binary", "detect", "launch", "health", "alias_mode")


def slug(name: str) -> str:
    """The kebab id a skill directory uses (`llama.cpp (PrismML fork)` -> the caller's `--id`)."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def backends(backend: str | None, override: str | None = None) -> list[str]:
    """The skill's `backends:` list, read from the registry's backend string.

    A name the registry does not state is never invented: an unmatched string raises and
    the caller passes `--backends` from the engine's own documentation.
    """
    if override:
        got = [b.strip() for b in override.split(",") if b.strip()]
        bad = [b for b in got if b not in es.BACKENDS]
        if bad:
            raise SystemExit(f"[engine-scaffold] unknown backend(s) {bad}; allowed {list(es.BACKENDS)}")
        return got
    words = {w.strip().lower() for w in re.split(r"[/,]", backend or "")}
    found = [_BACKEND_WORDS[w] for w in _BACKEND_WORDS if w in words]
    if not found:
        raise SystemExit(f"[engine-scaffold] the registry states backend {backend!r}, which names no "
                         f"backend llgenie knows; pass --backends from the engine's own docs "
                         f"({', '.join(es.BACKENDS)})")
    return [b for b in es.BACKENDS if b in found]


def oses(backs: list[str]) -> list[str]:
    """The skill's `os:` list, derived from the backends the scaffold was given.

    `METAL` alone is a macOS engine: Metal runs natively on Apple Silicon and never in an
    image, so claiming `linux` would make `skills-validate`/`generate-engine-params` demand
    a Dockerfile for a backend upstream cannot build. Metal plus a Linux backend is both,
    and no Metal at all is Linux (every other backend is a Linux container image).
    """
    has_metal = "metal" in backs
    has_linux = any(b in _LINUX_BACKENDS for b in backs)
    if has_metal and has_linux:
        return list(_DARWIN_LINUX)
    return list(_DARWIN) if has_metal else list(_LINUX)


def os_note(backs: list[str]) -> str:
    """One sentence naming where the `os:` value came from, for the scaffold's to-do list."""
    value = ", ".join(oses(backs))
    has_metal = "metal" in backs
    has_linux = any(b in _LINUX_BACKENDS for b in backs)
    if has_metal and has_linux:
        return (f"`os: [{value}]` — the backend list names `Metal` and a Linux backend "
                f"({', '.join(b for b in backs if b in _LINUX_BACKENDS)}), so the Linux backends get "
                f"container images and Metal runs natively on Apple Silicon.")
    if has_metal:
        return (f"`os: [{value}]` — the backend list names `Metal` and no Linux backend "
                f"(CUDA/ROCm/Vulkan/CPU), so this is a macOS engine: Metal runs natively on Apple "
                f"Silicon and never in an image, so no `container:` block is expected.")
    return (f"`os: [{value}]` — the backend list names no `Metal` "
            f"({', '.join(backs)}), so every declared backend runs in a Linux container image.")


def _quote(value: str) -> str:
    return json.dumps(value)


def skill_text(name: str, spec: dict, sid: str, backs: list[str], servable: str) -> str:
    """The SKILL.md: registry facts filled in, everything else empty and named."""
    url = (spec.get("url") or "").strip()
    note = (spec.get("note") or "").strip()
    front = [
        "---",
        f"name: engine-{sid.replace('.', '-')}",
        "description: \"\"",
        f"engine: {_quote(name)}",
        f"id: {sid}",
        f"repo: {_quote(url)}",
        "ref: \"\"",
        "ref_kind: tag",
        "pinned: \"\"",
        "verified: \"\"",
        "license: \"\"",
        f"servable: {servable}",
        "backends: [" + ", ".join(backs) + "]",
        "os: [" + ", ".join(oses(backs)) + "]",
        "formats: []",
        "upstream_watch: []",
        "prereqs:",
        "install:",
        "binary: \"\"",
        "detect: \"\"",
        "launch: []",
        "health: \"\"",
        "alias_mode: \"\"",
        "---",
    ]
    body = [
        "",
        f"# {name}",
        "",
        f"Upstream: {url or '(the registry states no repo URL — find it before pinning)'}",
        "",
        (f"Registry note: {note}" if note else "Registry note: none"),
        "",
        "This file was scaffolded by `make engine-skill-scaffold`. Everything the registry",
        "does not state is EMPTY on purpose — fill it from the pinned repo, never from",
        "memory, and never with a guessed value:",
        "",
        "1. " + os_note(backs),
        "   `os:` is the ONE key this scaffold fills from evidence rather than leaving empty;",
        "   check it against the pinned repo and change it only when the repo proves a backend",
        "   the registry does not name.",
        "2. `ref` / `ref_kind` / `pinned` — the release tag (or branch) and the full 40-hex",
        "   commit it resolves to (`git ls-remote <repo> <ref>`), then set `verified` to",
        "   today's date.",
        "3. `license` — the repo's LICENSE.",
        "4. `install.<backend>` — the steps its own Dockerfile/README uses to build or",
        "   install it, one list per backend. Engines run in container images, never on the",
        "   host (Metal aside), so no venv/`--system` instructions.",
        "5. `binary` / `detect` / `launch` / `health` / `alias_mode` / `prereqs` — how its",
        "   OpenAI server starts and how `{alias}`/`{port}` reach it.",
        "6. `formats` / `upstream_watch` — the model formats it serves, and the upstream",
        "   files `make engine-bump` re-reads to derive apt/pip deltas.",
        "",
        "Then:",
        "",
        "```",
        "make skills-validate                      # names every key still empty",
        "make generate-engine-params ENGINE=" + sid,
        "make check-engine-params                  # the Dockerfile + params are committed",
        "```",
        "",
        "`engine-image-*` in CI then builds the image for every declared backend with no",
        "workflow edit, because the matrix is read from `containers/engines/params/`.",
        "",
    ]
    return "\n".join(front + body)


def scaffold(engine: str, registry_src: str | None = None, out: Path | None = None,
             sid: str | None = None, backs: str | None = None, servable: str = "true",
             force: bool = False, dry: bool = False) -> dict:
    """Write the skill for one registry engine; returns what was (or would be) done."""
    registry = mp.load_registry(registry_src)
    engines = registry.get("engines") or {}
    if engine not in engines:
        near = [n for n in engines if engine.lower() in n.lower()]
        raise SystemExit(f"[engine-scaffold] {engine!r} is not a registry engine"
                         + (f" (did you mean {near}?)" if near else ""))
    spec = engines[engine] or {}
    ident = sid or slug(engine)
    if not ident:
        raise SystemExit(f"[engine-scaffold] {engine!r} yields no id; pass --id")
    target_dir = (out or SKILLS_DIR) / ident
    path = target_dir / "SKILL.md"
    result = {"engine": engine, "id": ident, "path": str(path), "written": False,
              "backends": backends(spec.get("backend"), backs), "servable": servable}
    if path.exists() and not force:
        result["reason"] = "skill already exists (pass --force to overwrite)"
        return result
    if dry:
        result["reason"] = "would write"
        return result
    target_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(skill_text(engine, spec, ident, result["backends"], servable))
    result["written"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("cmd", choices=("scaffold",))
    ap.add_argument("--engine", required=True, help="the engine NAME exactly as the registry spells it")
    ap.add_argument("--id", default=None, help="the skill directory id (default: a kebab of the name)")
    ap.add_argument("--registry", default=None, help="models.json path or URL (default: the vendored store)")
    ap.add_argument("--out", default=None, help="skills dir (default: skills/engines)")
    ap.add_argument("--backends", default=None, help="comma list, when the registry's backend names none")
    ap.add_argument("--servable", default="true", choices=("true", "false", "via"))
    ap.add_argument("--force", action="store_true", help="overwrite an existing SKILL.md")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    result = scaffold(a.engine, a.registry, Path(a.out) if a.out else None, a.id, a.backends,
                      a.servable, a.force, a.dry)
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    if not result["written"]:
        print(f"[engine-scaffold] {result['id']}: nothing written — {result['reason']}")
        return 0
    print(f"[engine-scaffold] wrote {result['path']} "
          f"(engine {result['engine']!r}, backends {', '.join(result['backends'])})")
    print("[engine-scaffold] left empty on purpose (fill from the pinned repo): "
          + ", ".join(UNPROVABLE))
    print("[engine-scaffold] next: make skills-validate, then "
          f"make generate-engine-params ENGINE={result['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
