#!/usr/bin/env python3
"""Prove the committed model/GGUF links a test depends on resolve (issue #1000).

The owner's acceptance line: "all hugging face tests that use real calls are refactored out or at
least verify that the real link exists — a curl of the file is there." This is that proof, kept OUT
of the hermetic ci-unit gate:

  `make check-model-links`            static, no network, fits ci-unit: every committed
                                      model/quant link in the vendored data must have a
                                      well-formed https://huggingface.co/<repo>/resolve/<rev>/<file>
                                      URL (a malformed or empty link is a defect, named).
  `make check-model-links LIVE=1`     the real thing: probe every collected link with the ONE
                                      liveness authority, `tests/hub_probe.probe` (#256) — ranged
                                      GET, bounded 15s ladder, status-or-reason, OUTAGE_LIMIT
                                      time-bound. A link that does not return is reported as a
                                      named message, never a raw 404 or a silent green.

Exactly one probe function is used (`hub_probe.probe`); this script adds no second authority, so the
"link returns" verdict cannot drift between two implementations (the tester pins that in the unit
gate). Fixtures are not touched: the link list below IS the vendored data, parsed, never hand-edited.

Usage:
    python3 scripts/check_model_links_liveness.py check        # static, exit 1 on malformed links
    python3 scripts/check_model_links_liveness.py check --live # real Hub probes
    python3 scripts/check_model_links_liveness.py report       # print the collected links
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
import hub_probe  # noqa: E402  (the ONE liveness authority, #256)

#: The vendored files that carry links a test depends on. Everything this gate knows comes from
#: here; there is no second list to drift.
DATA_FILES = ("data/models.json", "data/trending-quant-catalog.json")

_MODELS = ("models", )
_RESOLVE = re.compile(r"^https://huggingface\.co/[^/]+/[^/]+/resolve/.+$")


def _collect() -> tuple[list[tuple[str, str]], list[str]]:
    """(caller, url, must_be_resolve) triples + any malformed-link defects.

    models.json `formats[].hf` names a REPO ROOT (a valid link to probe); the quant catalog
    carries the actual `/resolve/<rev>/<file>` links. Only a catalog link may be required to be
    a resolve URL.
    """
    links: list[tuple[str, str, bool]] = []
    defects: list[str] = []
    models = json.loads((REPO / "data" / "models.json").read_text())
    for m in models.get("models", []) if isinstance(models, dict) else models:
        name = m.get("name") or m.get("id") or "?"
        for f in m.get("formats") or []:
            hf = f.get("hf")
            if not hf:
                continue
            url = f"https://huggingface.co/{hf}"
            links.append((f"models.json:{name}", url, False))
    cat = json.loads((REPO / "data" / "trending-quant-catalog.json").read_text())
    files = cat.get("files", {}) if isinstance(cat, dict) else {}
    for model_id, engines in (files.items() if isinstance(files, dict) else []):
        for _eng, info in (engines.items() if isinstance(engines, dict) else []):
            for q in (info.get("quants") or [] if isinstance(info, dict) else []):
                url = q.get("url") or ""
                if url:
                    links.append((f"trending-quant-catalog.json:{model_id}", url, True))
    seen: set = set()
    uniq = list(dict.fromkeys((c, u, r) for c, u, r in links
                              if (c, u) not in seen and not seen.add((c, u))))
    for _caller, url, must_resolve in uniq:
        if must_resolve and not _RESOLVE.match(url):
            defects.append(f"non-resolve URL: {url}")
    return [(c, u) for c, u, _ in uniq], defects


def _check(links, defects, live: bool) -> int:
    bad = 0
    for defect in defects:
        print(f"[model-links] MALFORMED {defect}")
        bad += 1
    print(f"[model-links] {len(links)} link(s) collected from {', '.join(DATA_FILES)}")
    if not live:
        print(f"[model-links] static pass: {len(links)} well-formed, {len(defects)} malformed")
        return 1 if bad else 0
    dead = 0
    for caller, url in links:
        p = hub_probe.probe(url)
        status = "ok" if p.ok else "DEAD"
        if not p.ok:
            dead += 1
            print(f"[model-links] {status} {caller}: {url} -> {p.detail}")
        else:
            print(f"[model-links] ok      {caller}: {p.detail}")
    print(f"[model-links] live: {len(links) - dead} ok, {dead} dead, {len(defects)} malformed")
    return 1 if (bad or dead) else 0


def _report(links, defects) -> int:
    for caller, url in links:
        print(f"{caller}: {url}")
    print(f"[model-links] {len(links)} link(s), {len(defects)} malformed")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("cmd", choices=("check", "report"), nargs="?", default="check")
    ap.add_argument("--live", action="store_true",
                    default=os.environ.get("LIVE", "") not in ("", "0", "false"),
                    help="probe the real Hub with hub_probe (default: static, no network)")
    args = ap.parse_args(argv)
    links, defects = _collect()
    if args.cmd == "report":
        return _report(links, defects)
    return _check(links, defects, args.live)


if __name__ == "__main__":
    sys.exit(main())
