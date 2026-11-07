from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_skill_code_parity as g  # noqa: E402


def _write_ref(tmp_path: Path, profile: str, text: str) -> Path:
    """A minimal skill reference under the gate's scan surface."""
    ref = tmp_path / "agents" / profile / "skills" / "s" / "references" / "r.md"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(text)
    return ref


def _root(tmp_path: Path, ref: Path) -> Path:
    """A fake repo root: the ref plus the real scripts/tests it must resolve against."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "agents").mkdir(parents=True)
    # copy the real tests tree so test citations resolve *through* the tree the gate reads
    import shutil
    shutil.copytree(REPO / "tests", root / "tests")
    shutil.copytree(REPO / "scripts", root / "scripts")
    # move the written reference into this fake root
    target = root / ref.relative_to(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(ref), str(target))
    return root


def test_green_anchor_resolves(tmp_path):
    """A citation of a real hermetic test resolves; the gate is clean on a green anchor."""
    ref = _write_ref(tmp_path, "p",
                     "proven: `tests/test_auto_merge.py::test_a_stale_marker_green_head_is_retried_"
                     "and_merged`. ")
    root = _root(tmp_path, ref)
    assert g.check(root) == []


def test_mutation_stale_test_id_reds(tmp_path):
    """Plant a citation of a test that does not exist — the gate must name it (issue #745's prove)."""
    ref = _write_ref(tmp_path, "p",
                     "proven: `tests/test_auto_merge.py::test_this_test_never_existed`. ")
    root = _root(tmp_path, ref)
    out = g.check(root)
    assert out, "a cited test id that does not exist must fail the gate"
    assert "test_this_test_never_existed" in out[0]


def test_suite_excluded_test_reds(tmp_path):
    """A citation whose test file is NOT in the hermetic suite must fail (it cannot pass).

    The fake tree's roster excludes one file; a citation to it must be named, proving the gate
    reasons about the SUITE (what runs), not just the file existing on disk.
    """
    ref = _write_ref(tmp_path, "p",
                     "proven: `tests/test_excluded_by_roster.py::test_something`. ")
    root = _root(tmp_path, ref)
    # the fake tree has no roster — build one that excludes the cited file
    fixture = root / "tests" / "fixtures"
    fixture.mkdir(parents=True, exist_ok=True)
    roster = {
        "note": "test roster",
        "decided_utc": "2026-01-01T00:00:00Z",
        "excluded": {"tests/test_excluded_by_roster.py": {
            "reason": "x" * 40, "issue": "#0", "decided": "2026-01-01", "target": "ci-slow"}},
        "deselect": {},
    }
    (fixture / "unit-suite.json").write_text(json.dumps(roster))
    # 1) the cited file exists on disk...
    (root / "tests" / "test_excluded_by_roster.py").write_text("def test_something():\n    pass\n")
    # 2) ...but is excluded from the suite -> the citation has no living proof
    out = g.check(root)
    assert any("not in the hermetic suite" in f for f in out)


def test_mutation_broken_symbol_reds(tmp_path):
    """A backticked repository-owned symbol that does not resolve must be named."""
    ref = _write_ref(tmp_path, "p", "the gate `scripts/this_script_does_not_exist.py` is the seam. ")
    root = _root(tmp_path, ref)
    out = g.check(root)
    assert any("this_script_does_not_exist.py" in f for f in out)
