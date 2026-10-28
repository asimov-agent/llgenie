#!/usr/bin/env python3
"""Generate data/trending-quant-catalog.json from the REAL registry + live Hub.

The HF class table llgenie's business logic reads (ONE committed file in the repo
root data dir). For every trending model in data/models.json it records, per engine
that can run it: the archs that engine supports and the real quantized files it can
read — each with its concrete, downloadable
`https://huggingface.co/<repo>/resolve/<rev>/<file>` link. Shape:

    { model: { engine: { "arch": [..], "quants": [
        {"repo","revision","path","files","size_gb","url"} ] } } }

Each `quants` row is ONE download plan (a single file, or a shard set / whole-repo
snapshot that llgenie downloads as a unit). `url` is the resolvable link of the file
llgenie loads; `files` is everything to download (all shards / snapshot files).

This generator is SEPARATE tooling, NOT llgenie runtime logic, and makes no LLM
calls. It reads Hub repo trees (llgenie's _hub_json, cached on disk) and NEVER
downloads a model. Run `make sync-quant-catalog` to refresh when the registry or Hub
changes; CI gates drift with `make check-quant-catalog`.

Update link-validation: when an older generated catalog already exists, only the
NEWLY-ADDED links are HTTP-probed (ranged 200) — the unchanged ones are trusted from
the prior generation, so a refresh is cheap and points at exactly what changed. On a
first generation (no prior file) every link is validated. A permanently-dead new
link (404/403) aborts the sync.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

OUT = REPO / "data" / "trending-quant-catalog.json"
FIXTURE = REPO / "tests" / "fixtures" / "trending-quant-catalog.json"
REGISTRY = REPO / "data" / "models.json"
GB = 2**30


def _resolve_url(repo, rev, path):
    return f"{mp.HF}/{repo}/resolve/{rev or 'main'}/{path}"


def _engine_formats(eng):
    info = mp.engine_ids().get(eng)
    return info["formats"] if info else []


def _repos_for(model, fmt):
    """The Hub repos a `mlx-safetensors` / `safetensors` cell may be planned from.

    The SAME rule `model_engine_pick.plan_download()` applies, because the table is what the
    pick reads: an `mlx-safetensors` plan comes only from a repo whose name marks MLX (the
    store's `formats[].hf` plus the `<name>-MLX*` conversions the live search finds), and a
    `safetensors` plan only from a repo whose name does not. Measured on the 2026-10-27 store:
    without this a `safetensors` cell pointed at an MLX-converted repo (`qwen3-4b` served by
    vLLM), and the MLX cell pointed at the base repo (`google/gemma-3-1b-it`, gated), so the
    table offered a download the engine cannot load while `plan_download()` refused it.
    """
    repos = [f["hf"] for f in model.get("formats") or [] if f.get("hf")]
    if fmt == "mlx-safetensors":
        repos += mp.mlx_repos(model)
    return [r for r in dict.fromkeys(repos) if ("mlx" in r.lower()) == (fmt == "mlx-safetensors")]


def _plan_row(repo, revision, path, files, size_gb, dir=False):
    return {"repo": repo, "revision": revision, "path": path, "files": files,
            "size_gb": round(size_gb, 6),
            **({"dir": True} if dir else {}),
            "url": _resolve_url(repo, revision, path or (files[0] if files else ""))}


def _model_catalog(m):
    """{engine: {arch, quants}} for a model — one row per real quant download plan
    (single file, shard set, or whole-repo snapshot), from the LIVE Hub (trees only)."""
    out = {}
    for eng in sorted(set(m.get("supported_engines") or []) | {e["engine"] for e in m.get("engines") or []}):
        fmts = _engine_formats(eng)
        if not fmts:
            continue
        items = []
        eng_id = mp.engine_ids().get(eng, {}).get("id")
        # own-checkpoint engines (Strata/TensorFold): only THEIR real plans (pinned
        # shards / MLX checkpoints) belong in the catalog, never a generic repo
        if eng_id == "strata":
            # Strata's setup.py installs ONE family of checkpoints — the repo its default
            # family names — so a model that is not that family has no Strata plan at all,
            # however many t/s measurements say Strata ran it (`strata_serves`, the same gate
            # `plan_download(engine="strata")` applies). Measured on the 2026-10-27 store:
            # without it every model Strata was measured on got a cell pointing at the
            # Qwen3.8-Flash-Next pack (61.9 GB) as its own weights.
            if not mp.strata_serves(m):
                continue
            # Strata is RAM-sensitive: its setup.py picks Q2_0 below 60 GB of RAM and
            # IQ3_XXS from 60 GB up. Record BOTH real plans so the pick can choose the
            # right quant for the host's RAM (the catalog is the source of truth).
            for ram in (16, 64):  # low-RAM Q2_0 and high-RAM IQ3_XXS
                plan = mp.strata_plan(ram)
                if plan:
                    for f in plan["files"]:
                        items.append(_plan_row(plan["repo"], plan["revision"], f, [f],
                                               plan["size"] / GB))
        elif eng_id == "tensorfold":
            # TensorFold publishes its own MLX checkpoints per supported family
            # (TensorFold/<base>-MLX-*). List EVERY real checkpoint it publishes for
            # the model — like the gguf/mlx/safetensors branches list ALL real quantized
            # plans ("the pick filters by the host's budget; the table lists ALL real
            # quants"), so a model TensorFold can serve always has a catalog cell even
            # when no checkpoint fits a mid-size sample card. A model TensorFold does
            # not publish at all gets no cell (rank_engines refuses to offer it: an
            # engine with no downloadable plan is not a recommendation).
            from model_engine_pick import tensorfold_repos
            for repo in tensorfold_repos(m):
                snap = mp._snapshot(repo)
                if snap:
                    items.append(_plan_row(repo, "main", "", snap["files"],
                                           snap["size"] / GB, dir=True))
        for fmt in fmts:
            if eng_id in ("strata", "tensorfold"):
                continue  # own-checkpoint engines: catalog holds only their own plans
            if fmt == "gguf":
                repo = mp.gguf_repo(m)
                if repo:
                    for w in mp.gguf_weights(repo):
                        items.append(_plan_row(repo, "main", w["files"][0], w["files"],
                                               w["size"] / GB))
            elif fmt in ("mlx-safetensors", "safetensors"):
                for repo in _repos_for(m, fmt):
                    snap = mp._snapshot(repo)
                    if snap:  # the pick filters by the host's budget; the table lists ALL real quants
                        items.append(_plan_row(repo, "main", "", snap["files"],
                                               snap["size"] / GB, dir=True))
            elif fmt == "litertlm":
                for repo in [f["hf"] for f in m.get("formats") or [] if f.get("hf")]:
                    fs = [f for f in mp._tree(repo) if f.get("type") == "file"
                          and f["path"].endswith(".litertlm")]
                    for f in fs:
                        items.append(_plan_row(repo, "main", f["path"], [f["path"]],
                                               int(f["size"]) / GB))
        # dedupe by (repo, path); keep engine order
        seen, uniq = set(), []
        for it in items:
            k = (it["repo"], it["path"])
            if k not in seen:
                seen.add(k)
                uniq.append(it)
        if uniq:
            info = mp.engine_ids().get(eng) or {}
            arch = sorted(info.get("variants") or [])
            if arch:  # only engines with at least one enabled image belong in the table
                out[eng] = {"arch": arch, "quants": uniq}
    return out


#: The outcome of probing one link. Only DEAD fails a sync: a gated file EXISTS and this token may
#: not read it, which is a repository-access setting rather than a broken link (issue #418).
PROBE_OK, PROBE_GATED, PROBE_DEAD = "ok", "gated", "dead"


def _probe_status(url, timeout=20.0) -> str:
    """Probe a link with a 1-byte ranged GET (never a download) and classify it.

    ``ok``     — 200/206: the file is there and readable with the credential we have.
    ``gated``  — 401/403: the file is there and this credential may not read it. The repo already
                 treats this as REACHABLE, not dead (`make web-coverage`, OpenSpec agent-web-reach:
                 "a credential-gated URL is not a dead one"), and reading it as dead reds the whole
                 weekly sync on a file that exists (issue #418: `meta-models/Muse-Spark-Open-…`).
    ``dead``   — anything else (404/410, a 5xx, a transport error): the link cannot be verified.
    """
    import urllib.error
    import urllib.request
    try:
        from hf_auth import authorize
    except ImportError:
        from scripts.hf_auth import authorize  # type: ignore
    req = authorize(urllib.request.Request(
        url, method="GET", headers={"Range": "bytes=0-0", "User-Agent": "llgenie-catalog"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return PROBE_OK if r.status in (200, 206) else PROBE_DEAD
    except urllib.error.HTTPError as e:
        return PROBE_GATED if e.code in (401, 403) else PROBE_DEAD
    except (urllib.error.URLError, TimeoutError, OSError):
        return PROBE_DEAD


def _probe_exists(url, timeout=20.0) -> bool:
    """True when the file is really there (readable, or gated but present)."""
    return _probe_status(url, timeout) != PROBE_DEAD


def _all_urls(cat: dict) -> set:
    return {it["url"] for engs in cat.get("files", {}).values()
            for cell in engs.values() for it in cell["quants"]}


def links_to_validate(new_urls: set, prior: dict | None) -> list[str]:
    """Which of the freshly-generated links must be HTTP-probed on a sync:
    the NEWLY-ADDED URLs vs the previous generated table (a mature refresh is
    cheap), or ALL URLs on a first generation (no prior table). This is the pure,
    MR-visible decision behind 'validate the new links against the old generated
    file; otherwise validate all on the first run'."""
    if not prior:
        return sorted(new_urls)
    return sorted(new_urls - _all_urls(prior))


def _plan_key(q: dict) -> tuple:
    """A plan's identity inside one (model, engine) cell: the repo, the file it loads, the
    files the download needs, its size and its link. Two plans with the same key are the same
    download, however the live search ordered them."""
    return (q.get("repo"), q.get("path"), tuple(q.get("files") or ()),
            q.get("size_gb"), q.get("url"))


def _classify_missing_plan(plan: dict, probe) -> str:
    """Probe a plan the generation dropped and say what kind of absence it is (issue #769).

    The plan's own link answers the question the live SEARCH cannot: a repo that still serves the
    file (``ok``, or ``gated`` — exists, this token may not read it) fell off a search page, and
    that is churn; a repo that answers 404/410 is gone, and that is a dead plan. A transport error
    reads as ``dead`` here on purpose — an unverifiable plan must not be silently blessed.
    """
    url = plan.get("url")
    if not url:
        return PROBE_DEAD
    return probe(url)


def carry_over(committed: dict, generated: dict, probe=None) -> tuple[dict, list[str], list[str]]:
    """Carry a still-reachable committed plan into a fresh sync instead of dropping it (#769).

    A sync used to be purely additive in one direction: whatever the live search returned was the
    new table, so a plan that fell off a search page vanished from the picker even though its repo
    answered 200 (measured: `ToPo-ToPo/Ornith-1.5-35B-A3B-mlx-4bit`). This re-inserts every plan
    the generation dropped whose link still answers — kept in its own (model, engine) cell, and
    printed with the reason — and leaves a genuinely dead plan out.

    Returns `(payload, kept, dropped)` where `kept`/`dropped` are the readable lines a sync prints.
    A section or engine the generation lost entirely is not resurrected: that is a structural
    change (`compare()` fails on it), not search churn.
    """
    probe = probe or _probe_status
    import copy
    merged = copy.deepcopy(generated)
    kept: list[str] = []
    dropped: list[str] = []
    old_files = committed.get("files") or {}
    new_files = merged.get("files") or {}
    for mid, engines in old_files.items():
        if mid not in new_files:
            continue
        for eng, cell in engines.items():
            fresh = new_files[mid].get(eng)
            if fresh is None:
                continue
            have = {_plan_key(q) for q in fresh.get("quants") or []}
            for q in cell.get("quants") or []:
                if _plan_key(q) in have:
                    continue
                kind = _classify_missing_plan(q, probe)
                if kind == PROBE_DEAD:
                    dropped.append(f"{mid}/{eng}: {q.get('url')} (the link answers 404/410)")
                    continue
                fresh.setdefault("quants", []).append(q)
                kept.append(f"{mid}/{eng}: {q.get('url')} (still reachable: {kind}; the live "
                            f"search no longer returns it)")
    return merged, kept, dropped


def compare(committed: dict, generated: dict, probe=None) -> tuple[list[str], list[str]]:
    """The committed table against a fresh generation, as `(failures, notes)`.

    A row the committed table HAS must be regenerated identically: an engine that lost an
    arch, a plan whose repo/files/size/url changed, or a registry the catalog was not
    rendered for (`meta.generated_utc`) — each is a FAILURE, because the catalog is what
    llgenie reads and a silent change would ship an unverified download.

    What the live Hub re-reads is a NOTE, because the table is regenerated from a SEARCH
    (`mlx_repos()`/`tensorfold_repos()` query huggingface.co `sort=downloads`), so the same
    set of plans comes back in a different ORDER as the repos' download counts move, and a
    new conversion upstream publishes shows up as an extra row. Measured 2026-10-27: on
    `main` itself, `qwen3.8-flash-next-125b`/MLX regenerated as the same 14 plans in a
    different order, which turned `make check-quant-catalog` red for a reason no PR caused
    and blocked every PR on the repository. Recording the new order/rows is the weekly
    `make sync-quant-catalog`'s job; the check reports them and stays green — the same rule
    the registry guard applies to data the store re-reads.

    A committed plan the generation no longer contains is one of TWO different events, and
    the gate must say which (issue #769). The plan's own link is probed:

    * ``ok``/``gated`` — the repo still serves the file; only the live SEARCH stopped
      returning it (a page moved, a repo became gated). A NOTE: kept, never a failure, so a
      search page cannot turn every PR red — measured 2026-10-28 on `main` `ea80ab4`: the six
      `SolsticeAI/Nanbeige4.3-33B-mlx-*` plans answered 401 and
      `ToPo-ToPo/Ornith-1.5-35B-A3B-mlx-4bit` answered 200 while the gate was red;
    * ``dead`` — 404/410, the repository is gone, so dropping the plan is the correct action
      and this IS a failure: the committed catalog records a download nothing serves.

    `probe` is `_probe_status` unless a caller injects one; the gate probes only the plans a
    generation dropped, so a clean catalog costs no requests.
    """
    probe = probe or _probe_status
    failures: list[str] = []
    notes: list[str] = []

    was, now = (committed.get("meta") or {}).get("generated_utc"), \
               (generated.get("meta") or {}).get("generated_utc")
    if was != now:
        failures.append(f"the catalog was rendered for registry {was!r}, the vendored one is "
                        f"{now!r} — run make sync-quant-catalog")

    old_files, new_files = committed.get("files") or {}, generated.get("files") or {}
    for mid, engines in old_files.items():
        if mid not in new_files:
            failures.append(f"{mid}: the model's whole catalog section is gone")
            continue
        for eng, cell in engines.items():
            fresh = new_files[mid].get(eng)
            if fresh is None:
                failures.append(f"{mid}/{eng}: the engine's section is gone")
                continue
            if cell.get("arch") != fresh.get("arch"):
                failures.append(f"{mid}/{eng}: arch list {cell.get('arch')} -> "
                                f"{fresh.get('arch')}")
            have = {_plan_key(q) for q in fresh.get("quants") or []}
            for q in cell.get("quants") or []:
                if _plan_key(q) in have:
                    continue
                kind = _classify_missing_plan(q, probe)
                if kind == PROBE_DEAD:
                    failures.append(f"{mid}/{eng}: the committed plan {q.get('url')} is gone "
                                    f"(the link answers 404/410) — nothing serves it, drop it "
                                    f"with make sync-quant-catalog")
                else:
                    notes.append(f"{mid}/{eng}: the committed plan {q.get('url')} is still "
                                 f"reachable ({kind}) but the live search no longer returns "
                                 f"it — kept, not a failure; the sync carries it over")
            old_order = [_plan_key(q) for q in cell.get("quants") or []]
            new_order = [_plan_key(q) for q in fresh.get("quants") or []]
            if set(old_order) == set(new_order) and old_order != new_order:
                notes.append(f"{mid}/{eng}: the live search lists the same "
                             f"{len(new_order)} plan(s) in a different order — the next sync "
                             f"records it")

    for mid, engines in new_files.items():
        if mid not in old_files:
            notes.append(f"{mid}: a model the committed catalog does not cover yet")
            continue
        for eng, cell in engines.items():
            old = old_files[mid].get(eng)
            if old is None:
                notes.append(f"{mid}/{eng}: a new (model, engine) section")
                continue
            seen = {_plan_key(q) for q in old.get("quants") or []}
            for q in cell.get("quants") or []:
                if _plan_key(q) not in seen:
                    notes.append(f"{mid}/{eng}: a plan the committed table does not record "
                                 f"yet: {q.get('repo')} ({q.get('size_gb')} GB)")
    return failures, notes


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generate / check the HF class table of the "
                                             "trending models' real quant links.")
    ap.add_argument("--check", action="store_true",
                    help="regenerate to a temp payload and fail (exit 1) if it differs "
                         "from the committed data/trending-quant-catalog.json")
    ap.add_argument("--skip-link-check", action="store_true",
                    help="generate without probing any link (default: probe only the "
                         "NEWLY-ADDED links vs the prior generated file, all on first run)")
    ap.add_argument("-o", "--out", default=str(OUT), help="output path")
    args = ap.parse_args()

    reg = mp.load_registry(str(REGISTRY))
    catalog = {"generated_utc": reg.get("generated_utc", ""),
               "models": {m["id"]: _model_catalog(m) for m in reg["models"]}}
    out = {mid: engs for mid, engs in catalog["models"].items() if engs}
    payload = {"meta": {"generated_utc": catalog["generated_utc"],
                        "source": "data/models.json + live Hugging Face Hub",
                        "note": "HF class table (data/trending-quant-catalog.json): per "
                                "trending model, per engine, the archs that engine "
                                "supports and the real quantized download plans with "
                                "their downloadable resolve links. Generated by "
                                "scripts/gen_trending_quant_catalog.py, read by "
                                "llgenie's pick logic; never the model itself."},
               "files": out}
    text = json.dumps(payload, indent=2) + "\n"
    dest = Path(args.out)

    # ---- a sync keeps what is still downloadable (issue #769) --------------------
    # The generation is read from a SEARCH, so a plan can fall off a page while its repo still
    # serves the file. A sync that wrote the search's answer verbatim deleted a downloadable plan
    # from the picker; a plan whose link is really gone (404/410) is still dropped, loudly.
    if not args.check:
        prior = json.loads(dest.read_text()) if dest.exists() else None
        if prior:
            payload, kept, dropped = carry_over(prior, payload)
            text = json.dumps(payload, indent=2) + "\n"
            for line in kept:
                print(f"[sync] kept {line}")
            for line in dropped:
                print(f"[sync] dropped {line}")
            out = payload["files"]

    new_urls = _all_urls(payload)

    # ---- update-time link validation (only run on generate, not --check) ----------
    if not args.check and not args.skip_link_check:
        prior = json.loads(dest.read_text()) if dest.exists() else None
        probes = links_to_validate(new_urls, prior)
        status = {u: _probe_status(u) for u in probes}
        dead = [u for u, s in status.items() if s == PROBE_DEAD]
        gated = [u for u, s in status.items() if s == PROBE_GATED]
        if dead:
            print(f"FAIL: {len(dead)} newly-generated link(s) do not resolve (HTTP):", file=sys.stderr)
            for u in dead[:20]:
                print(f"  {u}", file=sys.stderr)
            return 1
        print(f"[sync] validated {len(probes)} link(s) on the live Hub "
              f"(new-vs-old={len(new_urls - _all_urls(prior)) if prior else 'first-run, all'}; "
              f"gated={len(gated)}); {len(new_urls)} total in the table")
        for u in gated[:10]:
            print(f"[sync]   gated (exists, this token may not read it): {u}")

    if args.check:
        if not dest.exists():
            print(f"FAIL: committed catalog missing at {dest} (run make sync-quant-catalog)", file=sys.stderr)
            return 1
        failures, notes = compare(json.loads(dest.read_text()), payload)
        if failures:
            print(f"FAIL: {dest} is stale (run make sync-quant-catalog)", file=sys.stderr)
            for line in failures[:40]:
                print(f"  {line}", file=sys.stderr)
            if len(failures) > 40:
                print(f"  ... and {len(failures) - 40} more", file=sys.stderr)
            return 1
        # rows the LIVE Hub now offers and the committed table does not record yet: the
        # weekly sync writes them, so they are reported, never failed (see compare())
        for note in notes[:20]:
            print(f"[quant-catalog] NOTE: {note}")
        if len(notes) > 20:
            print(f"[quant-catalog] NOTE: ... and {len(notes) - 20} more")
        print(f"OK: {dest} matches the generator"
              f"{f'; {len(notes)} note(s) for the next sync' if notes else ''}")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    # the committed test fixture mirrors the canonical data/ table exactly, so a sync
    # that changes a link or drops a section is caught as regression by the fixture test.
    # Only sync it when writing the canonical location — a -o override (generator edge
    # tests / a preview) must not clobber the committed fixture.
    if dest.resolve() == OUT.resolve():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(text)
    n_files = sum(len(cell["quants"]) for engs in out.values() for cell in engs.values())
    loc = " + fixture %s" % FIXTURE if dest.resolve() == OUT.resolve() else ""
    print(f"wrote {dest}{loc}: {len(out)} models, {n_files} real quant links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
