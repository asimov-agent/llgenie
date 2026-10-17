#!/usr/bin/env python3
"""The trending list llgenie --matrix prints, one row per (arch, vram, ram).

`matrix(registry, vram, ram, arch)` is the call behind
`llgenie --matrix --vram V --ram R --arch A`. Models stay in the README
"Most loved" order (buzz + log2 of the fastest consumer t/s). A model whose
VRAM column is above the card is absent. The server on a row is the first
engine `matrix` returns: the best fit for this card on this architecture
(issue #225 — a figure proven on a card of this VRAM class or smaller, then a
bigger card's figure, then another backend, then a datacenter figure; see
`model_engine_pick.rank_engines`), and only when a quant of that engine fits
this VRAM and RAM. A model that fits the card but has no such engine is kept,
with the reason.

The committed copy is tests/fixtures/trend-list-matrix.json. `make
render-trend-list-matrix` rewrites it after a registry sync. The unit test
compares `matrix()` to that file, so a sync that forgets the rewrite fails
CI and the pull-request diff is the new list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "trend-list-matrix.json"
ARCHS = ("cuda", "rocm", "vulkan", "metal", "cpu")
VRAMS = (8, 16, 24, 48)
RAMS = (8, 32, 60, 64)
# nvidia-smi's 15.99 GiB card, with the RAM of the CUDA laptop this was pinned on.
CASES = [(arch, vram, ram) for arch in ARCHS for vram in VRAMS for ram in RAMS]
CASES.append(("cuda", 15.9921875, 62))
ORDER = ("README weighted trend (buzz + log2 of consumer t/s). "
         "The server is the best fit for this card on this arch with a quant that fits this vram and ram "
         "(a figure proven on a card of this vram class or smaller first, then a bigger card's figure, "
         "then another backend, then a datacenter figure; issue #225).")


def case_key(arch: str, vram: float, ram: float) -> str:
    return f"{arch}/{vram}/{ram}"


def trend_rows(registry: dict, vram: float, ram: float, arch: str) -> list[dict]:
    """What `llgenie --matrix --vram --ram --arch` lists, in README order."""
    res = mp.matrix(registry, vram, ram, arch)
    listed = {row["model"]["id"]: row for row in res["permutations"]}
    skipped = {item["model"]: item["why"] for item in res["skipped"]}
    rows = []
    for model in mp.trend_list(registry, vram):
        hit = listed.get(model["id"])
        if hit:
            engine = hit["engines"][0]["engine"]
            rows.append({"model": model["name"], "server": engine["engine"],
                         "tps": engine["tps"], "measured_on": engine["measured_on"],
                         "variant": engine["variant"], "why": ""})
        else:
            rows.append({"model": model["name"], "server": "", "tps": 0,
                         "measured_on": "", "variant": "",
                         "why": skipped.get(model["id"], "")})
    return rows


def build() -> dict:
    registry = mp.load_registry()
    return {
        "generated_utc": registry.get("generated_utc", ""),
        "order": ORDER,
        "cases": [{"arch": arch, "vram": vram, "ram": ram,
                   "rows": trend_rows(registry, vram, ram, arch)}
                  for arch, vram, ram in CASES],
    }


def main() -> int:
    check = "--check" in sys.argv[1:]
    fresh = json.dumps(build(), indent=2) + "\n"
    if check:
        have = FIXTURE.read_text() if FIXTURE.exists() else ""
        if have != fresh:
            print(f"[trend-list-matrix] {FIXTURE.relative_to(REPO)} is stale. "
                  "Run make render-trend-list-matrix.", file=sys.stderr)
            return 1
        print(f"[trend-list-matrix] OK {FIXTURE.relative_to(REPO)} ({len(CASES)} cases)")
        return 0
    FIXTURE.write_text(fresh)
    print(f"[trend-list-matrix] wrote {FIXTURE.relative_to(REPO)} ({len(CASES)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
