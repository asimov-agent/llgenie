#!/usr/bin/env python3
"""Vendor the trending-local-llms registry into data/models.json (issue #105).

  sync_registry.py sync  [--src URL|FILE] [--dest FILE]   download, validate, write when changed
  sync_registry.py check [--dest FILE]                    validate the vendored file

The file is copied byte-for-byte EXCEPT for the two normalisations below (issue #687,
a deliberate, documented departure from the verbatim rule): upstream's store started
mixing per-box experiment rows into `models[]` and writing model names into
`formats[].name`, which no consumer can rank or download from.

  1. base rows only: a row whose name is a per-box/per-recipe variant of another row
     ("Qwen3.8-27B (iPad Pro + eGPU R9700)", "… Twin Turbo") is folded into its base row —
     its measurements are appended (a post already on the base is skipped), its
     backends/supported_engines unioned — so ONE row per model remains and no
     measurement is lost;
  2. formats restricted to the vocabulary (GGUF | MLX | safetensors | mlx-safetensors |
     litertlm). An unknown name is dropped; a row left with no format states GGUF for its
     own `hf` repo, the same fallback the picker documents ("the most-downloaded
     `<name>-GGUF` repo"), unless that repo says MLX/litertlm.

The vendored README's "Most loved" table loses the folded rows with them, so the store and
the list a user reads stay the same set in the same order. Every fold/drop is printed.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .hf_auth import authorize, hub_open
except ImportError:
    from hf_auth import authorize, hub_open  # type: ignore

REPO = Path(__file__).resolve().parent.parent
_UPSTREAM_DATA = "https://raw.githubusercontent.com/andyholst/trending-local-llms/master"
UPSTREAM = f"{_UPSTREAM_DATA}/data/models.json"
UPSTREAM_README = f"{_UPSTREAM_DATA}/README.md"
# The contract the store is written against (issue #694): the JSON Schema upstream validates
# models.json with, and its prose twin. Vendored byte for byte, so a contract edit is a diff.
UPSTREAM_CONTRACT = f"{_UPSTREAM_DATA}/data/model_contract.json"
UPSTREAM_CONTRACT_DOC = f"{_UPSTREAM_DATA}/data/MODEL_CONTRACT.md"
VENDORED = REPO / "data" / "models.json"
VENDORED_README = REPO / "data" / "trending-README.md"  # the list a user reads; tests compare against it
VENDORED_CONTRACT = REPO / "data" / "model_contract.json"
VENDORED_CONTRACT_DOC = REPO / "data" / "MODEL_CONTRACT.md"
MOST_LOVED = "## ❤️ Most loved"
# The recorded README-link answers `make check-registry` replays instead of the live Hub
# (issue #1178). Recorded during a live `sync-registry`; a link the recording lacks is a
# stale snapshot (loud), so it cannot silently bless a new dead link.
README_LINK_ANSWERS = REPO / "tests" / "fixtures" / "readme-link-answers.json"


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


def _contract_paths(dest: Path) -> tuple[Path, Path]:
    """The contract files that sit beside a store file."""
    return dest.with_name(VENDORED_CONTRACT.name), dest.with_name(VENDORED_CONTRACT_DOC.name)


def _require(obj: dict, keys: list[str], where: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(f"{where} lacks {', '.join(repr(k) for k in missing)}")


def check_contract(data: dict, schema: dict) -> None:
    """Validate a store against the vendored upstream contract (issue #694).

    Every rule is READ from the schema, never restated here: the top-level ``required``
    keys, each model row's ``required`` keys, the engine name ``propertyNames.pattern``,
    an engine entry's ``required`` keys and its ``backend`` ``enum``, the model ``id``
    ``pattern``, and ``formats``' ``minItems`` plus its items' ``required`` keys. A
    contract edit that adds a required key is therefore honoured on the next run without
    touching this file.

    Only that subset is enforced: a full JSON-Schema engine is a dependency
    (``jsonschema``) this repository cannot add from a fork PR, because a fork-head
    ``pull_request`` token cannot publish the new test image (#651). A rule the schema
    states outside that subset is not enforced here — reported on #694, not hidden.
    """
    props = schema.get("properties") or {}
    _require(data, list(schema.get("required") or []), "the store")

    engines = data.get("engines")
    if not isinstance(engines, dict) or not engines:
        raise ValueError("'engines' must be a non-empty object")
    engine_props = props["engines"]
    name_pattern = (engine_props.get("propertyNames") or {}).get("pattern")
    engine_entry = engine_props.get("additionalProperties") or {}
    for name in engines:
        if name_pattern and not re.fullmatch(name_pattern, str(name)):
            raise ValueError(f"engine name {name!r} does not match the contract's {name_pattern!r}")
        _require(engines[name], list(engine_entry.get("required") or []), f"engine {name!r}")
        backend = engine_entry.get("properties", {}).get("backend", {})
        if backend.get("enum") and engines[name].get("backend") not in backend["enum"]:
            raise ValueError(f"engine {name!r} backend {engines[name].get('backend')!r} is not one of "
                             f"the contract's {len(backend['enum'])} backends")

    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("'models' must be a non-empty list")
    model_schema = props["models"]["items"]
    model_props = model_schema.get("properties") or {}
    id_pattern = (model_props.get("id") or {}).get("pattern")
    formats_schema = model_props.get("formats") or {}
    format_entry = formats_schema.get("items") or {}
    min_formats = formats_schema.get("minItems") or 0
    for i, m in enumerate(models):
        where = f"models[{i}] ({m.get('id', '?')})"
        _require(m, list(model_schema.get("required") or []), where)
        if not isinstance(m["engines"], list):
            raise ValueError(f"{where} 'engines' must be a list")
        for e in m["engines"]:
            if "engine" not in e:
                raise ValueError(f"{where} has an engine row without 'engine'")
        if id_pattern and not re.fullmatch(id_pattern, str(m["id"])):
            raise ValueError(f"{where} id does not match the contract's {id_pattern!r}")
        formats = m["formats"]
        if not isinstance(formats, list) or len(formats) < min_formats:
            raise ValueError(f"{where} 'formats' must be a list of at least {min_formats}")
        for j, f in enumerate(formats):
            _require(f, list(format_entry.get("required") or []), f"{where} formats[{j}]")


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


#: A Hub model page: `https://huggingface.co/<org>/<repo>` and nothing else.
HUB_MODEL_PAGE = re.compile(r"^https?://(?:www\.)?huggingface\.co/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)/?$")


def hub_api_url(url: str) -> str | None:
    """The Hub API URL that answers for a Hub model page link, else None.

    A model page is asked at `/api/models/<org>/<repo>`: the endpoint the token
    authenticates, and the one that answers a plain 200/404. The page itself answers a
    token-bearing GET with the Hub's 429 (measured 2026-10-26, issue #690). Any other
    link — a non-Hub host, or a Hub collection/dataset/docs URL — is checked as written.
    """
    m = HUB_MODEL_PAGE.match(url.split("?", 1)[0].split("#", 1)[0])
    return f"https://huggingface.co/api/models/{m.group(1)}/{m.group(2)}" if m else None


def check_links(links: list[str], timeout: float = 30) -> list[str]:
    """The links that do not answer. A link answers when a GET comes back below 400
    (only the status is read, not the body). GET, not HEAD: from GitHub Actions runners
    github.com answers HEAD with 504s it does not give a browser GET.

    Each link is asked at the URL that answers its question: a Hub model page through
    the Hub API (`hub_api_url`), everything else as written. Every request goes through
    `hf_auth.hub_open` — the repo's ONE Hub policy — so a 429 waits the Hub's window
    instead of reading as a dead link, a 5xx or transport failure retries on that
    policy's ladder, and a 401/403/404 is definitive on the first attempt (issue #690).
    `hub_open` attaches the token to a Hub endpoint only, so a non-Hub host is fetched
    plainly."""
    dead = []
    for url in dict.fromkeys(links):  # order kept, duplicates dropped
        target = hub_api_url(url) or url
        try:
            req = urllib.request.Request(
                target, method="GET", headers={"User-Agent": "llgenie-link-check"})
            with hub_open(req, timeout=timeout) as r:
                if r.status >= 400:
                    dead.append(f"{url} -> {r.status}")
        except urllib.error.HTTPError as e:
            dead.append(f"{url} -> {e}")
        except Exception as e:  # noqa: BLE001 - a dead link is a result, not a crash
            dead.append(f"{url} -> {e}")
    return dead


def fetch(src: str) -> bytes:
    if src.startswith(("http://", "https://")):
        req = authorize(urllib.request.Request(src, headers={"User-Agent": "llgenie-sync-registry"}))
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            return r.read()
    return Path(src).read_bytes()


#: The format vocabulary a consumer can act on (issue #687). Anything else in
#: `formats[].name` is upstream's display text, not a format.
FORMAT_VOCAB = ("GGUF", "MLX", "safetensors", "mlx-safetensors", "litertlm")

def _format_key(name: str) -> str:
    """A format name as a comparison key: letters and digits only, lowercased.

    Upstream writes the SAME format in several spellings — `LiteRT-LM` for `litertlm`,
    `MLX-Safetensors` for `mlx-safetensors` — and a strict equality made the normaliser
    read a real format as display text, drop it, and restate GGUF for a repo that serves no
    GGUF at all (measured on the 2026-10-27 store: `gemma-4-e2b` lost its litertlm entry).
    """
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


_FORMAT_CANON = {_format_key(v): v for v in FORMAT_VOCAB}


def _canon_format(name: str) -> str | None:
    """The vocabulary spelling of a format name, or None when it is not a format."""
    return _FORMAT_CANON.get(_format_key(name))


def _format_from_repo(*hints: str) -> str | None:
    """The format a repo id (or a row's id/name) states: mlx / litertlm / -GGUF, else None."""
    low = " ".join(str(h or "") for h in hints).lower()
    if "litertlm" in low:
        return "litertlm"
    if "mlx" in low:
        return "MLX"
    if "-gguf" in low or low.endswith("/gguf"):
        return "GGUF"
    return None


def normalise_formats(row: dict) -> tuple[list[dict], str]:
    """`row`'s formats restricted to the vocabulary; a row left with none states GGUF for
    its own repo (the picker's documented `<name>-GGUF` fallback), unless that repo names
    another format. Returns (formats, note) — note is "" when nothing was dropped."""
    kept: list[dict] = []
    dropped: list[str] = []
    for z in row.get("formats") or []:
        canon = _canon_format(z.get("name"))
        if canon is None:
            dropped.append(str(z.get("name")))
            continue
        entry = dict(z)
        entry["name"] = canon
        if canon not in [k["name"] for k in kept]:
            kept.append(entry)
    note = ""
    if dropped and not kept:
        repo = row.get("hf") or ""
        stated = _format_from_repo(repo, row.get("id"), row.get("name")) or "GGUF"
        kept = [{"name": stated, "hf": repo}]
        note = f"{row.get('id')}: formats {dropped} are not formats; stated {stated} for {repo}"
    elif dropped:
        note = f"{row.get('id')}: dropped non-format formats {dropped}"
    return kept, note


def normalise(data: dict) -> tuple[dict, list[str]]:
    """The store llgenie vendors: every upstream row, one per id, formats in the vocabulary.

    Upstream's `models[]` rows are distinct entities (a base model, a merged finetune, an
    MLX conversion, a run on one box) and its own README lists each as its own row, so this
    does NOT fold rows: which of them are "the same model" is upstream's data model to
    decide, and a name heuristic here would drop real models (`Qwen3.8-27B Defiance
    Uncensored` is a finetune, `Qwen3-1.7B (Woodcock on MLX)` is a run of a model upstream
    lists nowhere else). What IS unambiguous is a duplicated row and a `formats[].name`
    that is a model name instead of a format — both are normalised, and every change is
    printed (issue #687).
    """
    notes: list[str] = []
    rows: list[dict] = []
    seen: dict[str, str] = {}
    for row in data.get("models") or []:
        row = dict(row)
        key = str(row.get("id") or row.get("name") or "")
        if key in seen:
            notes.append(f"dropped duplicate row {key!r} (same id as {seen[key]!r})")
            continue
        seen[key] = key
        fmts, note = normalise_formats(row)
        row["formats"] = fmts
        if note:
            notes.append(note)
        rows.append(row)
    out = dict(data)
    out["models"] = rows
    return out, notes


def _summary(data: dict) -> str:
    return f"generated_utc={data.get('generated_utc', '?')} models={len(data['models'])}"


def sync(src: str, dest: Path, readme_src: str | None = UPSTREAM_README,
         readme_dest: Path | None = None, contract_src: str | None = UPSTREAM_CONTRACT,
         contract_doc_src: str | None = UPSTREAM_CONTRACT_DOC) -> int:
    """Copy the registry, the README it was generated with, and the contract it is written
    against — after checking the registry's shape and that it is the README's list in order.

    The contract is vendored, not enforced here: `check()` validates the store against it
    (issue #694), which is the gate the sync job runs on the files this writes."""
    readme_dest = readme_dest or dest.with_name(VENDORED_README.name)
    contract_dest, contract_doc_dest = _contract_paths(dest)
    raw = fetch(src)
    try:
        new = validate(raw)
        readme = fetch(readme_src).decode() if readme_src else None
        if readme is not None:
            check_readme_matches(new, readme)
        contract = fetch(contract_src) if contract_src else None
        contract_doc = fetch(contract_doc_src).decode() if contract_doc_src else None
    except ValueError as e:
        print(f"[sync-registry] REJECTED {src}: {e}", file=sys.stderr)
        return 1
    # Everything below vendors the NORMALISED store (issue #687): one row per model, formats
    # in the vocabulary, and the README carrying the same rows in the same order.
    store, notes = normalise(new)
    if readme is not None:
        check_readme_matches(store, readme)
    raw = (json.dumps(store, indent=2, ensure_ascii=False) + "\n").encode()
    for note in notes:
        print(f"[sync-registry] note: {note}")

    old = dest.read_bytes() if dest.exists() else b""
    def _unchanged(path: Path, value: str | bytes | None) -> bool:
        if value is None or not path.exists():
            return True
        current = path.read_bytes()
        return current == (value.encode() if isinstance(value, str) else value)

    same_rest = (_unchanged(readme_dest, readme) and _unchanged(contract_dest, contract)
                 and _unchanged(contract_doc_dest, contract_doc))
    if old == raw and same_rest:
        print(f"[sync-registry] unchanged: {dest} ({_summary(store)})")
        return 0
    before = _summary(validate(old)) if old else "(none)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    if readme is not None:
        readme_dest.write_text(readme)
    if contract is not None:
        contract_dest.write_bytes(contract)
    if contract_doc is not None:
        contract_doc_dest.write_text(contract_doc)
    # Record the README-link answers the hermetic `check-registry` replays (issue #1178),
    # only when writing the canonical location — a -o override must not clobber the fixture.
    if readme is not None and dest.resolve() == VENDORED.resolve():
        links = readme_links(readme)
        answers = {u: ("dead" if check_links([u]) else "ok") for u in links}
        README_LINK_ANSWERS.parent.mkdir(parents=True, exist_ok=True)
        README_LINK_ANSWERS.write_text(
            json.dumps({"note": "README-link answers replayed by `make check-registry` "
                                "(issue #1178); regenerate with `make sync-registry`.",
                        "links": answers}, indent=2) + "\n")
    print(f"[sync-registry] updated {dest}: {before} -> {_summary(store)}"
          f"{' (+contract)' if contract is not None else ''}")
    return 0


def check(dest: Path, readme: Path | None = None, snapshot: Path | None = None) -> int:
    if not dest.exists():
        print(f"[check-registry] missing {dest}: run make sync-registry", file=sys.stderr)
        return 1
    readme = readme or dest.with_name(VENDORED_README.name)
    contract, _ = _contract_paths(dest)
    try:
        data = validate(dest.read_bytes())
        if not contract.exists():
            raise ValueError(f"missing {contract}: run make sync-registry")
        check_contract(data, json.loads(contract.read_bytes()))
        if readme.exists():
            check_readme_matches(data, readme.read_text())
            links = readme_links(readme.read_text())
            if snapshot is not None:
                # Hermetic link probe (issue #1178): read the recorded README-link answers
                # instead of the live Hub. A link the recording lacks is a stale snapshot —
                # loud, so a snapshot cannot silently bless a new dead link. The live probe
                # lives on the ci-hf-live seam (`make check-registry LIVE=1`).
                answers = json.loads(snapshot.read_text()).get("links", {})
                dead = [f"{u} -> {answers[u]}" for u in links if answers.get(u) == "dead"]
                stale = [u for u in links if u not in answers]
                if stale:
                    raise ValueError(f"README links not in the recorded answers ({snapshot}); "
                                     "run make sync-registry to refresh it:\n  "
                                     + "\n  ".join(stale))
                if dead:
                    raise ValueError("dead README links (recorded):\n  " + "\n  ".join(dead))
            else:
                dead = check_links(links)
                if dead:
                    raise ValueError("dead README links:\n  " + "\n  ".join(dead))
        elif dest == VENDORED:
            raise ValueError(f"missing {readme}: run make sync-registry")
    except ValueError as e:
        print(f"[check-registry] {dest}: {e}", file=sys.stderr)
        return 1
    print(f"[check-registry] OK {dest} ({_summary(data)}; contract satisfied, README order matches, "
          f"links answer)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("sync", "check"))
    ap.add_argument("--src", default=UPSTREAM)
    ap.add_argument("--dest", default=str(VENDORED))
    ap.add_argument("--snapshot", default=str(README_LINK_ANSWERS),
                    help="check mode: read the README-link answers from this recorded file "
                         "instead of the live Hub (issue #1178). Pass --no-snapshot for the "
                         "live probe (the ci-hf-live seam).")
    ap.add_argument("--no-snapshot", action="store_true",
                    help="check mode: probe the README links live (the ci-hf-live seam)")
    a = ap.parse_args(argv)
    if a.cmd == "sync":
        return sync(a.src, Path(a.dest))
    snap = None if a.no_snapshot else Path(a.snapshot)
    return check(Path(a.dest), snapshot=snap)


if __name__ == "__main__":
    sys.exit(main())
