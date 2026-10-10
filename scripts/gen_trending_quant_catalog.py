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
            plan = mp.tensorfold_plan(m, mp.weight_budget_gb(24, mp.is_moe(m), 64) * GB)
            if plan:
                items.append(_plan_row(plan["repo"], plan.get("revision", "main"),
                                       plan["files"][0] if plan["files"] else "",
                                       plan["files"], plan["size"] / GB))
        for fmt in fmts:
            if eng_id in ("strata", "tensorfold"):
                continue  # own-checkpoint engines: catalog holds only their own plans
            if fmt == "gguf":
                repo = mp.gguf_repo(m)
                if repo:
                    for w in mp.gguf_weights(repo):
                        items.append(_plan_row(repo, "main", w["files"][0], w["files"],
                                               w["size"] / GB))
            elif fmt == "mlx-safetensors":
                repos = [f["hf"] for f in m.get("formats") or [] if f.get("hf")]
                repos += mp.mlx_repos(m)
                for repo in dict.fromkeys(repos):
                    snap = mp._snapshot(repo)
                    if snap:  # the pick filters by the host's budget; the table lists ALL real quants
                        items.append(_plan_row(repo, "main", "", snap["files"],
                                               snap["size"] / GB, dir=True))
            elif fmt == "safetensors":
                for repo in [f["hf"] for f in m.get("formats") or [] if f.get("hf")]:
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


def _probe_exists(url, timeout=20.0) -> bool:
    """A 1-byte ranged GET returns 200/206 — the real file exists (never a download)."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, method="GET",
                                 headers={"Range": "bytes=0-0", "User-Agent": "llgenie-catalog"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status in (200, 206)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False


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

    new_urls = _all_urls(payload)

    # ---- update-time link validation (only run on generate, not --check) ----------
    if not args.check and not args.skip_link_check:
        prior = json.loads(dest.read_text()) if dest.exists() else None
        probes = links_to_validate(new_urls, prior)
        dead = [u for u in probes if not _probe_exists(u)]
        if dead:
            print(f"FAIL: {len(dead)} newly-generated link(s) do not resolve (HTTP):", file=sys.stderr)
            for u in dead[:20]:
                print(f"  {u}", file=sys.stderr)
            return 1
        print(f"[sync] validated {len(probes)} link(s) on the live Hub "
              f"(new-vs-old={len(new_urls - _all_urls(prior)) if prior else 'first-run, all'}); "
              f"{len(new_urls)} total in the table")

    if args.check:
        if not dest.exists():
            print(f"FAIL: committed catalog missing at {dest} (run make sync-quant-catalog)", file=sys.stderr)
            return 1
        if dest.read_text() != text:
            print(f"FAIL: {dest} is stale (run make sync-quant-catalog)", file=sys.stderr)
            import difflib
            sys.stderr.writelines(difflib.unified_diff(dest.read_text().splitlines(True),
                                                       text.splitlines(True), "committed", "generated"))
            return 1
        print(f"OK: {dest} matches the generator")
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
    main()
