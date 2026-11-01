#!/usr/bin/env python3
"""Additive-only guard for the vendored trending registry (issue #114 upstream,
OpenSpec change trending-registry-additive-only).

`data/models.json` is a verbatim copy of trending-local-llms'
`data/models.json` (scripts/sync_registry.py). The weekly sync PR replaces it
wholesale, so a sync that LOSES data — a dropped model, key, engine or post —
was invisible to llgenie: `make check-registry` only re-validates the NEW file's
shape, never what it lost against the copy already committed (#233).

This compares the working copy against the previously committed copy
(`git show HEAD:data/models.json` by default) and fails on a loss. Additions are
always fine.

The comparison is against the identity the PRODUCT consumes (issue #668). Upstream
rewrites its rows on every refresh — it refines a `hardware` string ("RTX 6000" ->
"RTX 6000 24GB"), re-reads a post's engagement from live X (likes can fall), rebuilds
the `seen_posts` placeholder, re-attributes a post to a more specific model row, and
upgrades a profile link to the real post URL. None of that removes a model, an engine
or a post, and every one of them used to read as a "loss" and freeze the sync for
13 days (#534). So:

  FAIL (exit 1) — a model row gone; a key gone from a model row; an engine that had a
    measurement for a model and has none now (`rank_engines` groups by engine, so that
    is the unit whose loss thins the trend list); a `backends` / `supported_engines`
    entry gone; a FORMAT (`GGUF`, `MLX`, …) gone — a non-format display name in
    `formats` is not data and cannot be lost (#698); an engine-registry entry gone; a
    stated footprint scalar (`weight_gb`, `context_tokens`, `system_ram_min`) lowered; a
    tracked post (`/status/<id>`) gone from the WHOLE store.
  NOTE (printed, not fatal) — a surviving post's stated t/s lowered (upstream
    correcting a figure), an engagement counter decreased (a live re-scrape), the
    `seen_posts` placeholder shrinking (it is derived and rebuilt on every sort).

The t/s and counter movements are printed with their numbers so a reviewer still sees
them; they are not the store's loss, they are its newest reading of a post that is
still there. A lowered footprint scalar stays fatal: it is not re-read from a post,
and it shrinks the budget llgenie allocates.

The additive-only rule is enforced upstream too, where the store is WRITTEN
(trending-local-llms `check_no_value_loss`, its issue #114); this is the consumer's
guard.

  registry_keys.py                       # prev = HEAD:data/models.json, cur = data/models.json
  registry_keys.py --prev <file> --cur <file>
  registry_keys.py --prev <git-rev>      # any git rev of data/models.json

Stdlib only. Exit 0 = additive (nothing lost), 1 = loss found / unusable input.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from .sync_registry import FORMAT_VOCAB
except ImportError:
    from sync_registry import FORMAT_VOCAB  # type: ignore

REPO = Path(__file__).resolve().parent.parent
VENDORED = REPO / "data" / "models.json"
DEFAULT_PREV = "HEAD:data/models.json"

# Lists of objects inside a model row whose entries may legitimately collapse or
# reorder upstream (merge_engines collapses concordant measurements; placeholder
# posts are rebuilt on every sort). Their KEYS are compared per model as a
# union, never per element.
KEY_UNION_LISTS = ("engines", "seen_posts", "formats")

# Lists upstream DERIVES and rebuilds on every sort, so their element keys carry no
# stored data: the `seen_posts` placeholder is regenerated from the posts in the
# window, and an emptied one (every model with no post in the last 7 days) used to
# report ten "key ... is gone" losses per model (#668). The KEY itself is still
# required — only the keys of its elements are not tracked.
DERIVED_LISTS = ("seen_posts",)

# A tracked post is a status URL. A profile link ('https://lightbrd.com/<handle>') is
# not a post identity: upstream upgrades it to the real status URL, so tracking it as
# one reads as a loss when nothing was lost.
_STATUS = re.compile(r"/status/\d+")

# Scalar lists that may only ever grow.
GROW_ONLY_LISTS = ("backends", "supported_engines")

# Stated footprint scalars that may only ever grow (MODEL_CONTRACT.md): the weight bytes
# before any context is allocated, the context the KV cache is sized for, and the system
# RAM a partial offload needs. A lowered value shrinks what llgenie budgets for.
GROW_ONLY_SCALARS = ("weight_gb", "context_tokens", "system_ram_min")

COUNTERS = ("likes", "comments", "reshares", "views", "interactions")

REPORT_LIMIT = 25

_NUM = re.compile(r"\d+(?:\.\d+)?")


def tps_core(tps) -> float:
    """The first numeric token of a t/s string ('39.3', '~50', '67-71',
    '39.3 (est)') — the store's own idea of a t/s core."""
    m = _NUM.search(str(tps or ""))
    return float(m.group()) if m else 0.0


def _missing_key_paths(prev, cur, path=()):
    """Yield the key paths present in `prev` but gone from `cur`."""
    if isinstance(prev, dict) and isinstance(cur, dict):
        for key, value in prev.items():
            if key not in cur:
                yield path + (key,)
            else:
                yield from _missing_key_paths(value, cur[key], path + (key,))
    elif (isinstance(prev, list) and isinstance(cur, list) and prev and isinstance(prev[0], dict)
          and path and path[-1] in KEY_UNION_LISTS):
        if path[-1] in DERIVED_LISTS:
            return  # derived + rebuilt upstream: its elements store nothing (issue #668)
        before = set().union(*[set(e) for e in prev if isinstance(e, dict)])
        after = set().union(*[set(e) for e in cur if isinstance(e, dict)]) if cur else set()
        for key in sorted(before - after):
            yield path + (key,)


def _first_number(value) -> float | None:
    """The first numeric token of a stated footprint ('5.95GB Q4_K_M' -> 5.95,
    '131072' -> 131072, '128K' -> 128). None when the value states no number."""
    m = _NUM.search(str(value if value is not None else ""))
    return float(m.group()) if m else None


def _scalar_losses(prev_model: dict, cur_model: dict, where: str = "") -> list[str]:
    """Stated footprints that may only grow: the budget a run needs.

    `MODEL_CONTRACT.md` defines `weight_gb`, `context_tokens` and `system_ram_min` as the
    footprint of a run — the weight bytes before any context is allocated, the context the
    KV cache is sized for, and the system RAM a partial offload needs. Lowering one of them
    silently shrinks what llgenie budgets for, exactly like a lowered t/s or engagement
    counter shrinks the trend rank, so the same additive-only rule applies. A value that
    RESTATES the same number in another unit ('5.95GB' -> '5.95 GB') is not a loss.
    """
    out: list[str] = []
    for field in GROW_ONLY_SCALARS:
        was = _first_number(prev_model.get(field))
        now = _first_number(cur_model.get(field))
        if was is None or now is None:
            continue  # absent on either side: an addition or a removal already reported above
        if now < was:
            out.append(f"{where}{field} lowered {prev_model.get(field)!r} -> {cur_model.get(field)!r}")
    return out


_FORMAT_CANON = {name.lower(): name for name in FORMAT_VOCAB}


def _real_formats(row: dict) -> set[str]:
    """The `formats[].name` values in `row` that are formats at all (issue #698).

    `scripts/sync_registry.normalise_formats` (issue #687) drops every name outside
    FORMAT_VOCAB — upstream writes model and recipe text there ("Ornith 1.5") — and states
    the real format instead. Such a name was never data, so losing it removes nothing a
    consumer can rank or download; the same reasoning #668 applied to the derived
    `engagement.seen_posts` placeholder. A vocabulary format that disappears is still a
    loss. FORMAT_VOCAB is imported from the normaliser, so widening the vocabulary widens
    this check in the same edit.
    """
    found = set()
    for entry in row.get("formats") or []:
        canon = _FORMAT_CANON.get(str(entry.get("name") or "").strip().lower())
        if canon:
            found.add(canon)
    return found


def post_key(url) -> str | None:
    """The identity of a source post: its `/status/<id>` path, or None when the value is
    not a post (a profile link, a placeholder, empty).

    Upstream refines the `hardware` string of a measurement, re-attributes a post to a
    more specific model row (it splits one model into per-run ids) and upgrades a profile
    link to the real status URL. None of those is a lost measurement, and all three read
    as one when the identity is `(engine, hardware)` (#668).
    """
    m = _STATUS.search(str(url or ""))
    return m.group(0) if m else None


def _engine_best(model: dict) -> dict[str, float]:
    """engine name -> its best stated t/s on this model — the unit `rank_engines` keeps
    (it groups a model's measurements by engine and takes the best figure)."""
    out: dict[str, float] = {}
    for e in model.get("engines") or []:
        if not isinstance(e, dict):
            continue
        engine = str(e.get("engine") or "")
        out[engine] = max(out.get(engine, 0.0), tps_core(e.get("tps")))
    return out


def post_stats(registry: dict) -> dict[str, dict]:
    """Every tracked post in the store -> its best stated t/s, its summed counters and its
    largest stated footprint.

    Store-wide, over `engines[]` measurements AND the `engagement.seen_posts` placeholder:
    the same post can be a ranked row on one model and a seen-only row on another, and a
    sync that moves it between the two has lost nothing.
    """
    out: dict[str, dict] = {}
    for m in registry.get("models") or []:
        if not isinstance(m, dict):
            continue
        rows = list(m.get("engines") or []) + list((m.get("engagement") or {}).get("seen_posts") or [])
        for e in rows:
            if not isinstance(e, dict):
                continue
            key = post_key(e.get("source_post") or e.get("url"))
            if not key:
                continue
            d = out.setdefault(key, {"tps": 0.0, "counters": {}, "foot": {}, "model": m.get("id", "")})
            d["tps"] = max(d["tps"], tps_core(e.get("tps")))
            for counter in COUNTERS:
                d["counters"][counter] = d["counters"].get(counter, 0) + int(e.get(counter, 0) or 0)
            for field in GROW_ONLY_SCALARS:
                stated = _first_number(e.get(field)) or 0.0
                d["foot"][field] = max(d["foot"].get(field, 0.0), stated)
    return out


def _unposted_footprint_losses(prev_model: dict, cur_model: dict, model_id: str) -> list[str]:
    """A stated footprint that goes away on a measurement which has NO tracked post.

    Rows with a status post are compared store-wide by `post_stats` (so a relabel cannot read as
    one). A row whose `source_post` is a profile link or absent has no post identity, so its own
    `(engine, hardware)` group is the only handle — the measurement's stated footprint is data about
    that run, and losing it shrinks the budget llgenie allocates (MODEL_CONTRACT.md).
    """
    def groups(model: dict) -> dict:
        out: dict = {}
        for e in model.get("engines") or []:
            if not isinstance(e, dict) or post_key(e.get("source_post")):
                continue
            key = (str(e.get("engine") or ""), str(e.get("hardware") or ""))
            slot = out.setdefault(key, {})
            for field in GROW_ONLY_SCALARS:
                slot[field] = max(slot.get(field, 0.0), _first_number(e.get(field)) or 0.0)
        return out

    out: list[str] = []
    after = groups(cur_model)
    for (engine, hardware) in sorted(groups(prev_model)):
        before_slot = groups(prev_model)[(engine, hardware)]
        after_slot = after.get((engine, hardware))
        if after_slot is None:
            continue  # the group itself is gone: the engine-loss finding already covers it
        label = f"{engine} on {hardware or 'unspecified hardware'}"
        for field in GROW_ONLY_SCALARS:
            was, now = before_slot.get(field, 0.0), after_slot.get(field, 0.0)
            if was and now < was:
                out.append(f"{model_id}: {label} {field} lowered {was:g} -> {now:g}")
    return out


def compare(prev: dict, cur: dict) -> list[str]:
    """Every model, key, engine, list entry, stated footprint and tracked post that the
    previous registry had and the current one does not.

    What this does NOT report is intentional (issue #668): a refined `hardware` string, a
    post re-attributed to another model row, a post that moved between `engines[]` and the
    `seen_posts` placeholder, and a re-scraped counter or corrected t/s. None of them
    removes a model, an engine or a post — see `drift()` for the numbers that moved.
    """
    findings: list[str] = []
    prev_models = {m.get("id"): m for m in prev.get("models") or []}
    cur_models = {m.get("id"): m for m in cur.get("models") or []}

    for model_id, pm in prev_models.items():
        cm = cur_models.get(model_id)
        if cm is None:
            findings.append(f"model '{model_id}' is gone from the registry")
            continue

        for path in _missing_key_paths(pm, cm):
            findings.append(f"{model_id}: key '{'.'.join(str(p) for p in path)}' is gone")

        findings.extend(_scalar_losses(pm, cm, f"{model_id}: "))
        findings.extend(_unposted_footprint_losses(pm, cm, model_id))

        for field in GROW_ONLY_LISTS:
            lost = [x for x in pm.get(field) or [] if x not in (cm.get(field) or [])]
            if lost:
                findings.append(f"{model_id}: {field} lost {lost}")
        lost_formats = sorted(_real_formats(pm) - _real_formats(cm))
        if lost_formats:
            findings.append(f"{model_id}: formats lost {lost_formats}")

        # The unit the pick consumes: one row per engine, best figure. An engine that had a
        # measurement and now has none is a thin trend list; which post or hardware carried
        # that figure is upstream's bookkeeping, not llgenie's.
        before = _engine_best(pm)
        after = _engine_best(cm)
        for engine in sorted(set(before) - set(after)):
            findings.append(f"{model_id}: no measurement left for engine '{engine}' "
                            f"(it had {before[engine]:g} t/s)")

    lost_engines = [e for e in (prev.get("engines") or {})
                    if e not in (cur.get("engines") or {})]
    if lost_engines:
        findings.append(f"engine registry entries gone: {lost_engines}")

    # A tracked post that is nowhere in the new store is a measurement the store dropped,
    # whatever model it now belongs to.
    was_posts, now_posts = post_stats(prev), post_stats(cur)
    for key in sorted(set(was_posts) - set(now_posts)):
        findings.append(f"post {key} is gone from the store "
                        f"(it stated {was_posts[key]['tps']:g} t/s for {was_posts[key]['model']})")
    # A measured run's stated footprint (MODEL_CONTRACT.md: "a measurement may also carry
    # the footprint of that run") is static data about that run — a lower value shrinks the
    # budget llgenie allocates, so it is a loss, not a re-read.
    for key in sorted(set(was_posts) & set(now_posts)):
        for field in GROW_ONLY_SCALARS:
            was = was_posts[key]["foot"].get(field, 0.0)
            now = now_posts[key]["foot"].get(field, 0.0)
            if was and now < was:
                findings.append(f"post {key} {field} lowered {was:g} -> {now:g}")
    return findings


def drift(prev: dict, cur: dict) -> list[str]:
    """The numbers that MOVED without anything being lost (issue #668) — printed, never
    fatal: a surviving post's t/s corrected downward, an engagement counter re-scraped
    lower, and the derived `seen_posts` placeholder shrinking.

    They are a report, not a loss: the post, its model and its engine are still there, and
    the trend list llgenie ranks is not thinner for it. A re-read from live X can move a
    counter either way, and upstream corrects a figure it mis-read.
    """
    notes: list[str] = []
    was_posts, now_posts = post_stats(prev), post_stats(cur)
    for key in sorted(set(was_posts) & set(now_posts)):
        before, after = was_posts[key], now_posts[key]
        if before["tps"] and after["tps"] < before["tps"]:
            notes.append(f"post {key} t/s {before['tps']:g} -> {after['tps']:g} (same post, re-stated)")
        for counter in COUNTERS:
            was, now = before["counters"].get(counter, 0), after["counters"].get(counter, 0)
            if now < was:
                notes.append(f"post {key} {counter} {was} -> {now} (live re-scrape)")

    cur_models = {m.get("id"): m for m in cur.get("models") or []}
    for pm in prev.get("models") or []:
        cm = cur_models.get(pm.get("id"))
        if cm is None:
            continue
        was = len((pm.get("engagement") or {}).get("seen_posts") or [])
        now = len((cm.get("engagement") or {}).get("seen_posts") or [])
        if now < was:
            notes.append(f"{pm.get('id')}: seen_posts {was} -> {now} (derived placeholder, rebuilt)")
    return notes


def read_prev(spec: str) -> dict:
    """`spec` is a file path, or a git revision of data/models.json."""
    p = Path(spec)
    if p.exists():
        return json.loads(p.read_text())
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", spec],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                             capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"[check-registry-keys] cannot read previous registry "
                         f"'{spec}': {e.stderr.decode().strip()}") from None
    return json.loads(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Additive-only guard for the vendored trending registry")
    ap.add_argument("--prev", default=DEFAULT_PREV,
                    help=f"previous registry: file path or git rev (default {DEFAULT_PREV})")
    ap.add_argument("--cur", default=str(VENDORED))
    a = ap.parse_args(argv)

    prev = read_prev(a.prev)
    cur = json.loads(Path(a.cur).read_text())
    findings = compare(prev, cur)
    notes = drift(prev, cur)

    # The numbers that moved without a loss are printed either way, so a reviewer sees the
    # store's newest reading instead of having to diff it by hand (issue #668).
    for note in notes[:REPORT_LIMIT]:
        print(f"[check-registry-keys] NOTE: {note}")
    if len(notes) > REPORT_LIMIT:
        print(f"[check-registry-keys] ... and {len(notes) - REPORT_LIMIT} more note(s)")

    if not findings:
        print(f"[check-registry-keys] OK: additive only — nothing lost vs {a.prev} "
              f"({len(cur.get('models') or [])} models, {len(notes)} note(s))")
        return 0
    for f in findings[:REPORT_LIMIT]:
        print(f"[check-registry-keys] LOSS: {f}", file=sys.stderr)
    if len(findings) > REPORT_LIMIT:
        print(f"[check-registry-keys] ... and {len(findings) - REPORT_LIMIT} more",
              file=sys.stderr)
    print(f"[check-registry-keys] FAILED: {len(findings)} loss(es) vs {a.prev} — the "
          f"registry is additive only (no model, key, engine, list entry, stated footprint "
          f"or tracked post may be removed). Upstream must fix the store; never widen this "
          f"file.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
