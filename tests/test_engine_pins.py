"""The engine install-string dependency pins are inventoried into the scan (issue #1282).

The pins a cell actually installs (`torch==2.14.0`, `litert-lm==0.19.1`, `ziglang==0.17.0`, the
`--index-url` for the rocm/cpu/cuda wheels) are JSON strings inside `containers/engines/params/*.json`,
which no scanner parses as a dependency declaration. This module walks the committed install lines,
writes the pins as a requirements-shaped artifact the SAME Trivy/Syft pass scans, and `make
check-security-scan` fails when the pins are absent (a blind spot the engine runtime deps would
hide in). Proven on fixtures + the real committed tree — no Docker and no network.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
import scripts.engine_pins as ep  # noqa: E402


def _params(tmp_path: Path, install_lines: list[str]) -> Path:
    """A single-variant params fixture in the real parameters dir shape."""
    d = tmp_path / "params"
    d.mkdir(exist_ok=True)
    p = d / "engine.json"
    p.write_text(json.dumps({
        "engine": "Fixture",
        "variants": {"cpu": {"install": install_lines, "env": {}}},
    }, indent=2), encoding="utf-8")
    return p


def test_the_documented_engine_pin_classes_are_inventoried(tmp_path, monkeypatch):
    """Every `--index-url` install line with an explicit `name==version` pin is seen, bound to its
    committed source + variant. We assert classes (a pinned torch + index, a pinned litert, a pinned
    ziglang), never exact versions — the pins churn with each engine bump."""
    monkeypatch.setattr(ep, "PARAMS", REPO / "containers" / "engines" / "params")

    rows = ep.inventory()
    pins = {(r["package"], r["version"]) for r in rows}
    by_needle = {
        r["package"]: (r["pin"], r["index_url"]) for r in rows
    }

    # The three documented fixed-version classes reach the scan set.
    assert "torch" in by_needle, f"no pinned torch install inventoried in {rows}"
    assert "litert-lm" in by_needle, "litert-lm pin not inventoried"
    assert "ziglang" in by_needle, "ziglang pin not inventoried"
    # Every index-url the cell pins to is carried, not dropped.
    idx = [r["index_url"] for r in rows]
    assert any("rocm" in u for u in idx), f"no rocm index-url: {idx}"
    assert any("cu" in u for u in idx), f"no cuda index-url: {idx}"
    assert any("cpu" in u for u in idx), f"no cpu index-url: {idx}"
    # Every inventoried pin has an explicit, non-empty version (Exact version, not a bare name).
    assert all(r["version"] for r in rows), "a pin was inventoried with an empty version"
    # Every row is bound to its committed source + variant (nothing rationalised by hand).
    assert all(r["source"].startswith("containers/engines/params/") for r in rows)
    # No pin is double-counted at the same source/variant.
    keys = [(r["source"], r["variant"], r["pin"]) for r in rows]
    assert len(keys) == len(set(keys)), "a pin was inventoried twice for one variant"


def test_the_requirements_artifact_carries_the_pins_sha_bound(tmp_path, monkeypatch):
    """`make engine-pins` writes a scan-consumable requirements file + a manifest naming the head."""
    p = _params(tmp_path,
                ["uv pip install --system torch==2.5.0 --index-url https://x.example/whl/cu"])
    monkeypatch.setattr(ep, "PARAMS", p.parent)
    monkeypatch.setattr(ep, "REPORTS", tmp_path)

    rc = ep.write_inventory(tmp_path)

    assert rc == 0
    req = (tmp_path / "engine-pins" / "requirements.txt").read_text(encoding="utf-8")
    assert "torch==2.5.0" in req and "--index-url https://x.example/whl/cu" in req
    manifest = json.loads((tmp_path / "engine-pins" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 1
    assert manifest["pins"][0]["package"] == "torch" and manifest["pins"][0]["version"] == "2.5.0"
    # the sha-bound annotation: the manifest names a head sha for the in-repo case.
    assert manifest["head_sha"]


def test_the_real_tree_inventory_includes_a_requirements_shape(tmp_path, monkeypatch):
    """The committed tree's engine pins produce a non-empty requirements file whose lines are
    `name==version` (plus the source/variant comment and any index-url), the shape Trivy/Syft read."""
    monkeypatch.setattr(ep, "PARAMS", REPO / "containers" / "engines" / "params")
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(ep, "REPORTS", reports)

    rc = ep.write_inventory(reports)

    assert rc == 0
    req = (reports / "engine-pins" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert req, "the committed tree produced no engine-pin requirements lines"
    for line in req:
        pin = line.split("  #")[0].strip()
        assert re.match(r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.\-*]+$", pin), f"bad requirements line: {line!r}"


def test_check_fails_when_no_pins_are_inventoried(tmp_path, monkeypatch):
    """`make check-security-scan` cannot pass with the engine runtime deps out of the scan set:
    a params dir with no pinned install is a blind spot the gate must refuse."""
    empty = tmp_path / "params"
    empty.mkdir()
    (empty / "blah.json").write_text(json.dumps({"variants": {"cpu": {"install": ["echo hi"]}}}),
                                     encoding="utf-8")
    monkeypatch.setattr(ep, "PARAMS", empty)
    monkeypatch.setattr(ep, "REPORTS", tmp_path / "never")

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ep.check()
    assert rc == 1
    assert "blind spot" in buf.getvalue()


def test_check_fails_when_an_inventoried_pin_is_absent_from_the_sbom(tmp_path, monkeypatch):
    """The SBOM is the artifact trivy/grype match: an engine pin absent from it must red the gate."""
    p = _params(tmp_path,
                ["uv pip install --system torch==2.5.0 --index-url https://x.example/whl/cu"])
    monkeypatch.setattr(ep, "PARAMS", p.parent)
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(ep, "REPORTS", reports)
    (reports / "sbom.cdx.json").write_text(json.dumps({
        "components": [{"purl": "pkg:pypi/requests@2.0"}],
    }), encoding="utf-8")

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ep.check()
    assert rc == 1
    assert "torch" in buf.getvalue() and "sbom.cdx.json" in buf.getvalue()


def test_check_passes_when_every_pin_is_present_in_the_sbom(tmp_path, monkeypatch):
    """Once the SBOM covers the invented engine pins, `make check-security-scan` is green."""
    p = _params(tmp_path,
                ["uv pip install --system torch==2.5.0 --index-url https://x.example/whl/cu"])
    monkeypatch.setattr(ep, "PARAMS", p.parent)
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(ep, "REPORTS", reports)
    (reports / "sbom.cdx.json").write_text(json.dumps({
        "components": [{"purl": "pkg:pypi/torch@2.5.0"}],
    }), encoding="utf-8")

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ep.check()
    assert rc == 0
