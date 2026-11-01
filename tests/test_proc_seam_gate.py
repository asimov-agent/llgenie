"""Unit tests for scripts/check_proc_gate.py — the subprocess-confines-to-the-seam gate (issue #797).

The gate refuses a bare `subprocess.run`/`check_output`/`Popen` in ANY scripts/*.py except
scripts/proc.py (the policy seam) or a line carrying a `# proc-allow: <reason>`. The report prints the
census of the allowed remainder, so the tracked direct-call sites are a visible, shrinking number.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import scripts.check_proc_gate as pg


def _tree_with(path: str, content: str, root: Path) -> Path:
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return root


def test_check_ok_when_all_subprocess_is_in_proc_py_or_proc_allow(tmp_path):
    # Given a scripts tree where every subprocess site is either in proc.py or # proc-allow:-tagged
    root = _tree_with("scripts/proc.py",
                      "import subprocess\n"
                      "def run_ok(c):\n    return subprocess.run(c, capture_output=True)\n", tmp_path)
    _tree_with("scripts/ci_images.py",
               'import subprocess\n'
               'r = subprocess.run(["ls"])  # proc-allow: legacy direct call, tracked remainder\n',
               root)
    # When the gate checks
    items = pg.bare_sites(root)
    # Then no bare site remains
    assert items == []


@pytest.fixture
def tmp_root(tmp_path):
    return tmp_path


def test_check_reds_on_a_bare_subprocess_run(tmp_root):
    # Given a scripts module with a bare subprocess.run (no proc-allow, not proc.py)
    root = _tree_with("scripts/engine_image.py",
                      "import subprocess\n"
                      "r = subprocess.run(['nerdctl', 'images'])\n", tmp_root)
    # When it is scanned
    items = pg.bare_sites(root)
    # Then the gate refuses exactly that site, naming its file:line
    assert len(items) == 1
    assert items[0]["where"] == "scripts/engine_image.py:2"
    assert items[0]["allowed"] is False


def test_check_allow_is_not_fooled_by_import_line(tmp_root):
    # Given only the `import subprocess` line (not a call site)
    root = _tree_with("scripts/ok.py", "import subprocess\n", tmp_root)
    # Then the gate reports no call-site finding
    assert pg.bare_sites(root) == []


def test_check_proc_allow_line_is_honoured(tmp_root):
    # Given a site carrying a # proc-allow: reason
    root = _tree_with("scripts/auto_merge.py",
                      "import subprocess\n"
                      "out = subprocess.run(['gh', 'api'], capture_output=True)  "
                      "# proc-allow: claim-path read tracked for #799\n",
                      tmp_root)
    # Then it is not bare (the census counts it as the allowed remainder)
    assert pg.bare_sites(root) == []
    allowed = pg.allowed_sites(root)
    assert len(allowed) == 1
    assert "claim-path" in (allowed[0]["reason"] or "")


def test_report_prints_a_census_of_allowed_and_bare(tmp_root, capsys):
    # Given a mixed tree
    root = _tree_with("scripts/proc.py",
                      "import subprocess\ndef run_ok(c):\n    return subprocess.run(c, capture_output=True)\n",
                      tmp_root)
    _tree_with("scripts/detect_server.py",
               "import subprocess\n"
               "out = subprocess.run(['which', 'nvcc'], capture_output=True)  # proc-allow: fallback probe\n",
               root)
    _tree_with("scripts/engine_image.py", "import subprocess\nsubprocess.run(['x'])\n", root)
    # When the report is printed
    rc = pg.main(["report", "--root", str(root)])
    out = capsys.readouterr().out
    # Then it exits 0 and prints the census with both the allowed remainder and the bare site
    assert rc == 0
    assert "census" in out
    assert "detect_server.py:2" in out
    assert "BARE" in out


def test_check_exits_1_on_a_bare_site_0_when_clean(tmp_path, capsys):
    bad = _tree_with("scripts/bad.py", "import subprocess\nsubprocess.run(['go'])\n", tmp_path)
    assert pg.main(["check", "--root", str(bad)]) == 1
    good_root = _tree_with("scripts/good.py",
                      "import subprocess\n"
                      "subprocess.run(['go'])  # proc-allow: tracked remainder\n", tmp_path / "good")
    assert pg.main(["check", "--root", str(good_root)]) == 0
