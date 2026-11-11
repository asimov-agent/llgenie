from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

from scripts import check_skill_code_parity as g


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


def _fake_root(tmp_path: Path, rel_md: str, text: str, name: str = "root") -> Path:
    """A fake repo root: one skill markdown at `rel_md` plus the real scripts/tests trees."""
    import shutil
    root = tmp_path / name
    root.mkdir()
    shutil.copytree(REPO / "tests", root / "tests")
    shutil.copytree(REPO / "scripts", root / "scripts")
    md = root / rel_md
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(text)
    return root


DEAD = "`scripts/this_script_does_not_exist.py` and `tests/test_never_wrote_this.py::test_zzz` "


def test_archived_fold_snapshot_is_skipped(tmp_path):
    """A FROZEN fold snapshot (.archive/, issue #2262 fold) is not the gate's subject: its
    citations are historical and rewriting them would break the byte-identical fold parity."""
    root = _fake_root(tmp_path, "agents/llgenie-planner/skills/.archive/s/SKILL.md", DEAD)
    assert g.check(root) == [], "a frozen fold snapshot must not be held to living citations"


def test_external_skill_mirror_is_skipped(tmp_path):
    """Tree copies of UPSTREAM Hermes skill docs cite the Hermes repository's tests/scripts —
    external tokens, not claims this repo owns (issue #2262 fold)."""
    root = _fake_root(tmp_path,
                      "agents/llgenie-planner/skills/autonomous-ai-agents/hermes-agent/references/x.md",
                      DEAD)
    assert g.check(root) == []
    root2 = _fake_root(tmp_path,
                       "agents/llgenie-planner/skills/software-development/hermes-agent-skill-authoring/references/x.md",
                       DEAD, name="root2")
    assert g.check(root2) == []


def test_skips_do_not_leak_to_ordinary_skills(tmp_path):
    """The same dead citation in an ordinary (non-mirror, non-archived) skill reference stays RED."""
    root = _fake_root(tmp_path, "agents/llgenie-planner/skills/ordinary-skill/references/x.md", DEAD)
    out = g.check(root)
    assert out, "the fold skips must not become a global exemption"


def test_template_family_symbols_are_never_anchors(tmp_path):
    """`tests/test_x.py::test_y` and a bare `tests/test_x.py` are the generic template family."""
    root = _fake_root(tmp_path, "agents/p/skills/s/references/r.md",
                      "proven: `tests/test_x.py::test_y` and the file `tests/test_x.py` ")
    assert g.check(root) == []
