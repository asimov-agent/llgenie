#!/usr/bin/env python3
"""The committed default-range VRAM-scope view (issue #227).

`scope_models(registry, DEFAULT_VRAM_RANGE)` turns the full vendored
`data/models.json` into the set llgenie works with for its default
consumer/workstation band (8–48 GB). This script writes that view — the sorted
list of in-scope model ids, the `generated_utc`, the band and its provenance
note — to `tests/fixtures/vram-scope-view.json`, and re-checks it in CI.

Why a committed view: the issue asks that a filtered view for the default range
be committed, `make`-regenerated and CI-checked, so a change to the filter (or
to the band) is visible as a reviewable diff. `make render-vram-scope-view`
rewrites it from the live vendored registry; `make check-vram-scope-view`
fails when the committed file differs from what the renderer computes. The
view is a pure function of the vendored registry — no Hub, no network, no
engine params — so the check needs no recording and no container route.

The full registry is never touched: this is a read-time filtered view, not a
sync-time drop (`make sync-registry` stays exactly as it is).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "vram-scope-view.json"

NOTE = (
    "The default consumer/workstation VRAM band llgenie works with (8-48 GB, issue #227): "
    "a model whose README vram_tier falls in [8, 48] is in scope; a CPU/Apple-only row "
    "(no numeric tier) is always in scope; a wider/smaller box widens the band via "
    "LLGENIE_VRAM_RANGE or a scope_models(registry, vram_range) call. The vendored "
    "data/models.json is unchanged — this is a read-time filtered view, never a sync-time drop."
)


def build() -> str:
    registry = mp.load_registry()
    scoped = mp.scope_models(registry)
    ids = sorted(m["id"] for m in scoped.get("models") or [])
    out = {
        "generated_utc": registry.get("generated_utc", ""),
        "vram_range": list(mp.DEFAULT_VRAM_RANGE),
        "note": NOTE,
        "model_count_total": len(registry.get("models") or []),
        "model_count_in_scope": len(ids),
        "in_scope_model_ids": ids,
    }
    return json.dumps(out, indent=2) + "\n"


def main() -> int:
    if "--check" in sys.argv:
        have = FIXTURE.read_text() if FIXTURE.exists() else ""
        fresh = build()
        if have != fresh:
            print(f"[vram-scope-view] {FIXTURE.relative_to(REPO)} is stale. "
                  "Run make render-vram-scope-view.", file=sys.stderr)
            return 1
        print(f"[vram-scope-view] OK {FIXTURE.relative_to(REPO)}")
        return 0
    FIXTURE.write_text(build())
    print(f"[vram-scope-view] wrote {FIXTURE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
