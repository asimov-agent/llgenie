#!/usr/bin/env python3
"""Additive-only guard for the vendored trending registry (issue #114 upstream,
OpenSpec change trending-registry-additive-only).

`data/models.json` is a verbatim copy of trending-local-llms'
`data/models.json` (scripts/sync_registry.py). The weekly sync PR replaces it
wholesale, so a sync that LOSES data — a dropped key, a dropped measurement, a
lowered t/s or engagement counter — was invisible to llgenie: `make
check-registry` only re-validates the NEW file's shape, never what it lost
against the copy already committed.

This compares the working copy against the previously committed copy
(`git show HEAD:data/models.json` by default) and fails on any loss. Additions
are always fine — only removals and shrunk values are defects. The same rule is
enforced upstream, where the store is written (trending-local-llms
`check_no_value_loss`, issue #114); this is the consumer's guard.

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

REPO = Path(__file__).resolve().parent.parent
VENDORED = REPO / "data" / "models.json"
DEFAULT_PREV = "HEAD:data/models.json"

# Lists of objects inside a model row whose entries may legitimately collapse or
# reorder upstream (merge_engines collapses concordant measurements; placeholder
# posts are rebuilt on every sort). Their KEYS are compared per model as a
# union, never per element.
KEY_UNION_LISTS = ("engines", "seen_posts", "formats")

# Scalar lists that may only ever grow.
GROW_ONLY_LISTS = ("backends", "supported_engines")

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
        before = set().union(*[set(e) for e in prev if isinstance(e, dict)])
        after = set().union(*[set(e) for e in cur if isinstance(e, dict)]) if cur else set()
        for key in sorted(before - after):
            yield path + (key,)


def _by_engine_hw(measurements) -> dict:
    """Group measurements by (engine, hardware) — the pairing the README rows and
    the trend matrix are built from."""
    out: dict = {}
    for e in measurements or []:
        out.setdefault((e.get("engine", ""), e.get("hardware", "")), []).append(e)
    return out


def compare(prev: dict, cur: dict) -> list[str]:
    """Every key, model, measurement group, t/s and engagement counter that the
    previous registry had and the current one does not."""
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

        for field in GROW_ONLY_LISTS:
            lost = [x for x in pm.get(field) or [] if x not in (cm.get(field) or [])]
            if lost:
                findings.append(f"{model_id}: {field} lost {lost}")
        lost_formats = [f.get("name") for f in pm.get("formats") or []
                        if f.get("name") not in [c.get("name") for c in cm.get("formats") or []]]
        if lost_formats:
            findings.append(f"{model_id}: formats lost {lost_formats}")

        before = _by_engine_hw(pm.get("engines"))
        after = _by_engine_hw(cm.get("engines"))
        for key in sorted(before, key=str):
            engine, hardware = key
            label = f"{engine} on {hardware or 'unspecified hardware'}"
            if key not in after:
                findings.append(f"{model_id}: measurement {label} is gone "
                                f"({len(before[key])} measured row(s) before)")
                continue
            best_before = max(tps_core(e.get("tps")) for e in before[key])
            best_after = max(tps_core(e.get("tps")) for e in after[key])
            if best_after < best_before:
                findings.append(f"{model_id}: {label} t/s lowered {best_before:g} -> {best_after:g}")
            for counter in COUNTERS:
                was = sum(e.get(counter, 0) or 0 for e in before[key])
                now = sum(e.get(counter, 0) or 0 for e in after[key])
                if now < was:
                    findings.append(f"{model_id}: {label} {counter} lowered {was} -> {now}")

    lost_engines = [e for e in (prev.get("engines") or {})
                    if e not in (cur.get("engines") or {})]
    if lost_engines:
        findings.append(f"engine registry entries gone: {lost_engines}")
    return findings


def read_prev(spec: str) -> dict:
    """`spec` is a file path, or a git revision of data/models.json."""
    p = Path(spec)
    if p.exists():
        return json.loads(p.read_text())
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", spec],
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

    if not findings:
        print(f"[check-registry-keys] OK: additive only — nothing lost vs {a.prev} "
              f"({len(cur.get('models') or [])} models)")
        return 0
    for f in findings[:REPORT_LIMIT]:
        print(f"[check-registry-keys] LOSS: {f}", file=sys.stderr)
    if len(findings) > REPORT_LIMIT:
        print(f"[check-registry-keys] ... and {len(findings) - REPORT_LIMIT} more",
              file=sys.stderr)
    print(f"[check-registry-keys] FAILED: {len(findings)} loss(es) vs {a.prev} — the "
          f"registry is additive only (no key, model, measurement, t/s or counter may "
          f"be removed). Upstream must fix the store; never widen this file.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
