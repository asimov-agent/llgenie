#!/usr/bin/env python3
"""The trending list llgenie --matrix prints, one row per (arch, vram, ram).

`matrix(registry, vram, ram, arch)` is the call behind
`llgenie --matrix --vram V --ram R --arch A`. Models are in the CARD's order: the
README's tier-local `### Up to N GB` ranking for that card first, then the rows it
does not rank in the store's own trend order (issue #669) — never the store file's
positions. A model whose measured evidence does not place it on the card is absent
(a run on this size or smaller, else `vram_min`, else `weight_gb`). The server on a
row is the first engine `matrix` returns: the best fit for this card on this
architecture (issue #225 — a figure proven on a card of this VRAM class or smaller,
then a bigger card's figure, then another backend, then a datacenter figure; see
`model_engine_pick.rank_engines`), and only when a quant of that engine fits
this VRAM and RAM. A model that fits the card but has no such engine is kept,
with the reason.

The committed copy is tests/fixtures/trend-list-matrix.json. `make
render-trend-list-matrix` rewrites it after a registry sync. The unit test
compares `matrix()` to that file, so a sync that forgets the rewrite fails
CI and the pull-request diff is the new list.

`--check` is HERMETIC (issue #1080): it replays the Hub answers recorded in
tests/fixtures/hub-snapshot.json, so `matrix()` — whose `why` strings ask the Hub
for a repo's real file sizes (`gguf_weights`/`mlx_repos`) — is a pure function of
the vendored registry plus that recording and the gate needs no route at all.
`--check --live` is the old live comparison; the render path records the snapshot
and writes both files in one run, so the fixture can never describe a Hub answer
the recording does not carry. Regenerating: `make render-trend-list-matrix`.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "trend-list-matrix.json"
SNAPSHOT = REPO / "tests" / "fixtures" / "hub-snapshot.json"
#: The fixture records the engine-variant signature the matrix was rendered
#: against, so a change to `containers/engines/params/*.json` (an engine added,
#: an arch/variant gained or lost) RE-PINS the fixture by showing up as a
#: fingerprint mismatch -- the add/params path has no other forcing step (issue
#: #1232). Cosmetic param edits that do not change the engine->variant map the
#: matrix consumes (a version/ref/base bump, an apt/env change under an existing
#: variant) leave it untouched and do not force a re-render.
FINGERPRINT_KEY = "engine_variant_fingerprint"


def params_signature() -> str:
    """The engine id -> sorted arch variants map the matrix consumes, as JSON.

    This is exactly what `model_engine_pick.engine_ids()` returns (read from the
    generated `containers/engines/params/*.json`), so a params/arch delta that
    shifts the matrix is guaranteed to change this signature, and one that cannot
    shift the matrix (no variant added/removed, no engine added/removed) does not.
    """
    return json.dumps({name: sorted(info["variants"])
                       for name, info in sorted(mp.engine_ids().items())}, sort_keys=True)


def fingerprint() -> str:
    """sha256 of the engine->variants signature; the fixture records it."""
    return hashlib.sha256(params_signature().encode()).hexdigest()[:16]


ARCHS = ("cuda", "rocm", "vulkan", "metal", "cpu")
VRAMS = (8, 16, 24, 48)
RAMS = (8, 32, 60, 64)
# nvidia-smi's 15.99 GiB card, with the RAM of the CUDA laptop this was pinned on.
CASES = [(arch, vram, ram) for arch in ARCHS for vram in VRAMS for ram in RAMS]
CASES.append(("cuda", 15.9921875, 62))
ORDER = ("Card's list order: the README's tier-local 'Up to N GB' ranking for the card, then the "
         "rows it does not rank in the store's own trend order (band -> trend score -> posts -> "
         "peak t/s, computed — never the store file's positions), issue #669. "
         "The server is the best fit for this card on this arch with a quant that fits this vram and ram "
         "(a figure proven on a card of this vram class or smaller first, then a bigger card's figure, "
         "then another backend, then a datacenter figure; issue #225).")


def case_key(arch: str, vram: float, ram: float) -> str:
    return f"{arch}/{vram}/{ram}"


def trend_rows(registry: dict, vram: float, ram: float, arch: str) -> list[dict]:
    """What `llgenie --matrix --vram --ram --arch` lists, in README order.

    The row set is the one `matrix()` itself considered: `trend_list` applies the store's
    `system_ram_min` floor as well as the card gate (issue #669), so asking it without the
    RAM printed a row `matrix()` never looked at — a model with an empty server AND an empty
    reason (measured on the 2026-10-27 store, cuda/16 GB/8 GB RAM).
    """
    res = mp.matrix(registry, vram, ram, arch)
    listed = {row["model"]["id"]: row for row in res["permutations"]}
    skipped = {item["model"]: item["why"] for item in res["skipped"]}
    rows = []
    for model in mp.trend_list(registry, vram, ram):
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
        FINGERPRINT_KEY: fingerprint(),
        "generated_utc": registry.get("generated_utc", ""),
        "order": ORDER,
        "cases": [{"arch": arch, "vram": vram, "ram": ram,
                   "rows": trend_rows(registry, vram, ram, arch)}
                  for arch, vram, ram in CASES],
    }


def main() -> int:
    args = sys.argv[1:]
    check = "--check" in args
    live = "--live" in args
    if check:
        if live:
            fresh = json.dumps(build(), indent=2) + "\n"
        else:
            with mp.hub_snapshot_file(SNAPSHOT):
                fresh = json.dumps(build(), indent=2) + "\n"
        have = FIXTURE.read_text() if FIXTURE.exists() else ""
        # The param/arch coupling (issue #1232): the committed fixture records
        # the engine->variant signature it was rendered against (build() already
        # computed `fresh` from the same injected Hub source above -- live or the
        # recorded snapshot). A params/arch delta that changed the engine->variant
        # map -- even one that leaves the rows byte-identical -- makes that
        # recorded signature stale, so the add/params path is forced to re-render
        # and re-pin. Name the required target; the hermetic replay is what the
        # added engine/arch is measured against.
        if have != fresh:
            print(f"[trend-list-matrix] {FIXTURE.relative_to(REPO)} is stale. "
                  "Run make render-trend-list-matrix.", file=sys.stderr)
            return 1
        source = "live" if live else f"recorded {SNAPSHOT.relative_to(REPO)}"
        print(f"[trend-list-matrix] OK {FIXTURE.relative_to(REPO)} ({len(CASES)} cases, {source})")
        return 0
    with mp.hub_recording() as recorded:
        fresh = json.dumps(build(), indent=2) + "\n"
    FIXTURE.write_text(fresh)
    mp.write_hub_snapshot(SNAPSHOT, recorded)
    print(f"[trend-list-matrix] wrote {FIXTURE.relative_to(REPO)} ({len(CASES)} cases) and "
          f"{SNAPSHOT.relative_to(REPO)} ({len(recorded)} Hub answers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
