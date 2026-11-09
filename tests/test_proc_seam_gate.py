"""Unit tests for scripts/check_proc_gate.py — the subprocess-confines-to-the-seam gate (issues #797, #2229).

The gate refuses a bare `subprocess.run`/`check_output`/`Popen` in ANY production python (scripts/*.py
and agents/**/scripts/*.py — the #2229 broadening) except scripts/proc.py (the policy seam) or a line
carrying a `# proc-allow: <reason>`. The tests/ population is SCANNED and SURFACED in the census but
NOT event-gated: a test's job is to spawn subprocess and assert on its output, so a bare site there is
the harness, not a dropped exit code. The report prints the census of the allowed remainder, so the
tracked direct-call sites are a visible, shrinking number.
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


def test_check_reds_on_a_bare_agent_lane_subprocess(tmp_root):
    # #2229: a production bot-lane script is ENFORCED exactly like scripts/ — a bare subprocess.run
    # without the seam or a # proc-allow: is a gate finding, wherever it lives.
    root = _tree_with(
        "agents/llgenie-some-lane/skills/a-skill/scripts/probe.py",
        "import subprocess\n"
        "subprocess.run(['gh', 'api', 'repos/x'])\n",
        tmp_root,
    )
    items = pg.bare_sites(root)
    assert len(items) == 1
    assert "probe.py:2" in items[0]["where"]
    assert items[0]["enforced"] is True


def test_check_allows_agent_lane_site_with_proc_allow(tmp_root):
    # #2229: the seam + `# proc-allow:` are the ONLY two escapes in the enforced agent-lane population.
    root = _tree_with(
        "agents/llgenie-some-lane/scripts/pr_watch.py",
        "import subprocess\n"
        "p = subprocess.run(['gh', 'api'], capture_output=True)  "
        "# proc-allow: rc inspected before use, tracked remainder for #2229\n",
        tmp_root,
    )
    assert pg.bare_sites(root) == []


def test_check_does_not_red_on_bare_test_subprocess(tmp_root):
    # #2229: the tests/ population is SCANNED (surfaced in the census, never invisible) but NOT
    # event-gated — a test spawning subprocess is the harness, and hard-gating it would force a
    # whole-tree carve (the AC3 weakening).
    root = _tree_with("tests/test_something.py",
                      "import subprocess\n"
                      "r = subprocess.run(['make', '-n', 'unit'])\n",
                      tmp_root)
    assert pg.bare_sites(root) == []
    all_sites = pg.sites(root)
    assert len([s for s in all_sites if s["population"] == "tests" and not s["allowed"]]) == 1


def test_check_lists_both_enforced_and_surfaced_in_output(tmp_root, capsys):
    # #2229: check surfaces the test census alongside the enforced finding.
    root = _tree_with("scripts/bad.py", "import subprocess\nsubprocess.run(['go'])\n", tmp_root)
    _tree_with("tests/test_t.py", "import subprocess\nsubprocess.run(['make'])\n", root)
    rc = pg.main(["check", "--root", str(root)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "scripts/bad.py" in out
    assert "tests/ surfaced:" in out
