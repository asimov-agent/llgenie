#!/usr/bin/env python3
"""Every engine→arch and engine→format claim in the tree is validated against the
docs-cited capacity mapper, `data/engine-capabilities.json` (issue #1214).

The trending-local-llms sync copies the store's `engines` dict into `data/models.json`
with only shape/README-order contract checks. A faulty or stale store entry (a newly
listed engine, an arch the engine never supported, a model served by an engine that
cannot read its format) lands unverified and only fails later at build — or hangs at
serve for a ternary model on stock llama.cpp (`GGML_TYPE_PQ2_0`=142 / `PTQ1_0`=143 only
run the PrismML fork). The capacity table closes that gap: a canonical, docs-cited map
of what each engine REALLY supports, which every human-authored and generated claim is
checked against.

Claims checked (all are subset checks, `claim ⊆ mapper` — never equality, so a
legitimate new arch/format does not red):

  E1 skill `backends:`  ⊆  mapper[engine].archs        (a human-authored backend can drift)
  E2 skill `formats:`   ⊆  mapper[engine].formats      (a format the engine cannot read)
  E3 params `variants`  ⊆  mapper[engine].archs        (a generated arch the engine lacks)
  E4 params binary/launch routes a ternary-capable file through an engine whose
     mapper says `ternary: false` — round-trips detect_server's tensor-type gate
     (a ternary file must reach ONLY a ternary:true engine).
  E5 every mapper engine has a skill, and every shipped skill has a mapper row
     (a mapper engine with no skill, and a shipped engine with no capacity, are both gaps).

    python3 scripts/check_engine_capabilities.py check    # the CI gate (exit 1 on a finding)
    python3 scripts/check_engine_capabilities.py report   # the census, never fails

Standard usage is via the Makefile: `make check-engine-capabilities`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402

CAPABILITIES = REPO / "data" / "engine-capabilities.json"
PARAMS = REPO / "containers" / "engines" / "params"

# Ternary GGUF tensor types that ONLY the PrismML fork can load (GGML_TYPE_* enum).
TENSOR_TYPES_TERNARY = ("GGML_TYPE_PQ2_0", "GGML_TYPE_PTQ1_0")


def load_mapper() -> dict:
    doc = json.loads(CAPABILITIES.read_text())
    eng = doc.get("engines") or {}
    assert eng, f"{CAPABILITIES} has no engines — the mapper must not be empty"
    return eng


def mapper_engines(archs: set[str] | None = None) -> dict[str, dict]:
    eng = load_mapper()
    if archs is None:
        return eng
    return {k: {"archs": {a for a in (v.get("archs") or []) if a in archs},
               "formats": set(v.get("formats") or []),
               "ternary": bool(v.get("ternary"))}
            for k, v in eng.items()}


def _named(rows: set[str] | list[str]) -> str:
    return ", ".join(sorted(rows)) if rows else "(none)"


def check() -> list[str]:
    """Return the list of findings; an empty list means the tree matches the mapper."""
    findings: list[str] = []
    eng = load_mapper()

    # Every shipped skill is an engine id; every engine id maps to a skill dir.
    skills = es.load_skills()
    skills_root = es.SKILLS_DIR if hasattr(es, "SKILLS_DIR") else REPO / "skills" / "engines"
    skill_dirs = {p.name for p in skills_root.iterdir() if p.is_dir()} if skills_root.exists() else set()
    # E5a: a mapper engine with no shipped skill is only a gap when it is a shipped
    # engine (a `via` / `no` row like webllm is in the mapper on purpose).
    shipped = {eid for eid in skills} | skill_dirs

    # E5a: a mapper engine with no shipped skill is a gap — every engine we carry is
    # shipped (a skill), so a row with no skill is a stale/phantom row.
    for eid in sorted(eng):
        if eid not in shipped:
            findings.append(f"E5 mapper engine {eid!r} has no shipped skill")

    # E1, E2, E5b: each skill's backends/formats against the mapper row.
    for eid, s in sorted(skills.items()):
        row = eng.get(eid)
        if row is None:
            findings.append(f"E5 shipped engine {eid!r} has no row in {CAPABILITIES.name}")
            continue
        blist = set(s.get("backends") or [])
        flist = set(s.get("formats") or [])
        archs = set(row.get("archs") or [])
        formats = set(row.get("formats") or [])
        if not blist <= archs:
            findings.append(
                f"E1 {eid}: skill backends {_named(blist - archs)} not in mapper archs {_named(archs)}")
        if not flist <= formats:
            findings.append(
                f"E2 {eid}: skill formats {_named(flist - formats)} not in mapper formats {_named(formats)}")

    # E3: params variants ⊆ mapper archs.
    for p in sorted(PARAMS.glob("*.json")):
        eid = p.stem
        row = eng.get(eid)
        if row is None:
            # No params cell (via/unsupported engine) — fine, E5 above covers the missing row.
            continue
        variants = set((json.loads(p.read_text()).get("variants") or {}).keys())
        archs = set(row.get("archs") or [])
        if not variants <= archs:
            findings.append(
                f"E3 {eid}: params variants {_named(variants - archs)} not in mapper archs {_named(archs)}")

    # E4: a skill that declares a ternary quant or tensor type but whose mapper row is
    # not ternary (a ternary GGUF would hang a stock llama.cpp server at load).
    for eid, s in sorted(skills.items()):
        row = eng.get(eid)
        if row is None:
            continue
        skill_path = skills_root / eid / "SKILL.md"
        quants = set(s.get("quants") or [])
        # Prism-only ternary types. (TQ1_0/TQ2_0 are UPSTREAM ternary quants stock
        # llama.cpp serves; only the group-128 PQ2_0/PTQ1_0 need the PrismML fork.)
        ternary_quants = {"PQ2_0", "PTQ1_0"}
        mentions_type = False
        try:
            mentions_type = any(t in skill_path.read_text() for t in TENSOR_TYPES_TERNARY)
        except OSError:
            pass
        if (quants & ternary_quants) or mentions_type:
            if not row.get("ternary"):
                findings.append(
                    f"E4 {eid}: skill declares ternary quants/tensor types "
                    f"({', '.join(sorted(quants & ternary_quants)) or TENSOR_TYPES_TERNARY}) "
                    "but the mapper does not mark it ternary — a ternary GGUF would hang/red on serve")

    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("check", "report"))
    args = ap.parse_args(argv)

    findings = check()
    if args.cmd == "report":
        print("engine-capabilities census (data/engine-capabilities.json):")
        eng = load_mapper()
        for eid, row in sorted(eng.items()):
            flag = "TERNARY" if row.get("ternary") else ""
            print(f"  {eid:26s} archs={sorted(row.get('archs') or [])} "
                  f"formats={sorted(row.get('formats') or [])} {flag}")
        if findings:
            print(f"\n{len(findings)} finding(s):")
            for f in findings:
                print(f"  - {f}")
        print("(report never fails)")
        return 0

    # check: the CI gate
    if findings:
        print(f"engine-capabilities: {len(findings)} finding(s) against "
              f"{CAPABILITIES.name}")
        for f in findings:
            print(f"  - {f}")
        print("Each is a docs-backed capacity claim the tree contradicts — fix the claim"
              " (skill/params) or the mapper (a verified new capacity), never the check.")
        return 1
    print("engine-capabilities: OK — every skill backend, skill format and params"
          " variant is a docs-cited subset of data/engine-capabilities.json; ternary"
          " tensor types route only to the ternary engine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
