"""No engine skill's `detect` may die of SIGPIPE, and every one must actually run its binary.

`engine_runner` runs every step under `set -o pipefail`, so a reader that exits early (`grep -q`,
`| head -1`) makes the writer take SIGPIPE and the pipeline report 141 — which declared a perfectly
healthy `strata/rocm` binary "missing" (issue #616). The same file used to accept a `detect` that
never touched the binary at all, echoing the pin instead of the version the engine reports
(found building the v0.2.4 pin, #605).

These tests read the COMMITTED params (what the image actually runs), not the skill text, so a
regeneration that drops the fix is caught too.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / "containers" / "engines" / "params"

# A reader that stops early. `grep` without `-q`/`-m` and `sed -n 1p` read to EOF and are fine.
EARLY_EXIT = (r"grep\s+-\w*q", r"grep\s+-m\s*\d", r"\|\s*head\b", r"\|\s*head\s+-")


def _cells() -> list[tuple[str, str, dict]]:
    out = []
    for path in sorted(glob.glob(str(PARAMS / "*.json"))):
        doc = json.load(open(path))
        for arch, variant in doc["variants"].items():
            out.append((doc["id"], arch, variant))
    return out


def test_no_detect_uses_an_early_exiting_reader():
    """`detect` must not pipe into `grep -q`/`head`: under pipefail that is a 141, not a version."""

    # Given every committed engine x arch cell
    cells = _cells()

    # When  each cell's detect command is read
    offenders = {
        f"{engine}/{arch}": variant["detect"]
        for engine, arch, variant in cells
        if any(re.search(pat, variant.get("detect") or "") for pat in EARLY_EXIT)
    }

    # Then  none of them stops its reader early
    assert cells, "no committed params"
    assert offenders == {}, f"an early-exiting reader under `set -o pipefail` reports 141: {offenders}"


def test_every_detect_runs_its_own_binary():
    """A detect that never executes the binary cannot prove it is installed — it proves the pin."""

    # Given every committed cell that declares a binary
    cells = [(e, a, v) for e, a, v in _cells() if v.get("binary")]

    # When  each detect command is read
    silent = {
        f"{engine}/{arch}": variant["detect"]
        for engine, arch, variant in cells
        if "{binary}" not in (variant.get("detect") or "")
        and residue(variant) not in (variant.get("detect") or "")
    }

    # Then  every one executes the binary it is verifying
    assert silent == {}, f"detect never runs the binary: {silent}"


def residue(variant: dict) -> str:
    """The literal binary path the params carry (after `{binary}` was substituted)."""
    return str(variant.get("binary") or "")


def test_strata_detect_is_wired_to_a_documented_flag():
    """The v0.2.4 CLI answers `--version`; the skill must exercise it, not echo the pin."""

    # Given strata's committed params
    doc = json.loads((PARAMS / "strata.json").read_text())
    manifest = json.loads((REPO / "containers" / "engines" / "binaries.json").read_text())

    # When  its detect and its documented flags are read
    flags = manifest["engines"]["strata"]["cuda"]["flags"]
    detects = {a: v["detect"] for a, v in doc["variants"].items()}

    # Then  every variant runs --version and the flag is documented
    assert "--version" in flags
    for arch, detect in detects.items():
        assert detect.endswith("--version"), (arch, detect)
        assert "|" not in detect, (arch, detect)
