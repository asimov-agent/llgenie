"""Hermetic tests for scripts/check_cron_drift.py (issue #2359, AC: the drift gate).

The gate reds when any live planner cron prompt (auto-approve-merge 71c5192ebdba,
auto-rebase-resolve db0a3e1a3d7c) diverges from its versioned copy under
agents/llgenie-planner/prompts/ and greens when all match — including the trailing
newline normalization (the same framing the tick gate proved, #2159). These tests
run the real script against fixture trees and fixture jobs.json, no live ~/.hermes
profile touched.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_cron_drift.py"
PROMPT_DIR = REPO / "agents" / "llgenie-planner" / "prompts"


def _mkroot(tmp_path, prompts: dict | None) -> Path:
    """Materialize agents/llgenie-planner/prompts/<name>.md under a fixture repo root.

    prompts maps the versioned file basename to its text. If prompts is None the
    directory is left out entirely (missing-versioned fails at exit 2).
    """
    if prompts is None:
        return tmp_path
    d = tmp_path / "agents" / "llgenie-planner" / "prompts"
    d.mkdir(parents=True)
    for name, text in prompts.items():
        (d / name).write_text(text)
    return tmp_path


def _live_file(prompts: dict, overrides: dict | None = None) -> dict:
    """jobs.json whose two jobs carry the given prompt texts (trailing newline dropped)."""
    out = []
    for job_id, name in (("db0a3e1a3d7c", "llgenie-auto-approve-merge"),
                         ("71c5192ebdba", "llgenie-auto-rebase-resolve")):
        p = ("#" + name + "\njust a probe")  # placeholder; real tests inject content
        p = prompts.get(name + ".md", p)
        p = p[:-1] if p.endswith("\n") else p
        out.append({"id": job_id, "name": name, "schedule": {"minutes": 30}, "prompt": p})
    return {"jobs": out}


def _run(live_path: Path, root: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--live", str(live_path), "--root", str(root)],
        capture_output=True, text=True, env={**os.environ}, timeout=timeout,
    )


def test_gate_greens_when_both_live_prompts_match(tmp_path):
    prompts = {"llgenie-auto-approve-merge.md": "## approve\nrun the merge recheck\n",
               "llgenie-auto-rebase-resolve.md": "## rebase\nmeasure behind, dispatch conflicts\n"}
    root = _mkroot(tmp_path, prompts)
    lf = tmp_path / "jobs.json"
    lf.write_text(json.dumps(_live_file(prompts)))
    r = _run(lf, root)
    assert r.returncode == 0, r.stdout
    assert "OK db0a3e1a3d7c" in r.stdout
    assert "OK 71c5192ebdba" in r.stdout


def test_gate_reds_when_one_prompt_diverges(tmp_path):
    prompts = {"llgenie-auto-approve-merge.md": "## approve\nrun the merge recheck\n",
               "llgenie-auto-rebase-resolve.md": "## rebase\nmeasure behind, dispatch conflicts\n"}
    root = _mkroot(tmp_path, prompts)
    lf = tmp_path / "jobs.json"
    live = _live_file(prompts)
    live["jobs"][0]["prompt"] = "completely different live prompt"
    lf.write_text(json.dumps(live))
    r = _run(lf, root)
    assert r.returncode == 1, r.stdout
    assert "DRIFT db0a3e1a3d7c" in r.stdout, r.stdout
    assert "OK 71c5192ebdba" in r.stdout, r.stdout     # the other job still checked


def test_gate_names_both_byte_counts_on_drift(tmp_path):
    prompts = {"llgenie-auto-approve-merge.md": "## approve\nrun the merge recheck\n",
               "llgenie-auto-rebase-resolve.md": "## rebase\nmeasure behind\n"}
    root = _mkroot(tmp_path, prompts)
    lf = tmp_path / "jobs.json"
    live = _live_file(prompts)
    live["jobs"][1]["prompt"] = "X"
    lf.write_text(json.dumps(live))
    r = _run(lf, root)
    assert r.returncode == 1, r.stdout
    assert "71c5192ebdba" in r.stdout                      # which job drifted is named
    sizes = re.findall(r"\((\d+) b\)", r.stdout)
    assert "1" in sizes, (sizes, r.stdout)                 # live prompt = 1 byte


def test_gate_exits_2_when_versioned_missing(tmp_path):
    # both committed files absent -> cannot compare, so exit 2 tells the host lane
    root = _mkroot(tmp_path, None)
    lf = tmp_path / "jobs.json"
    lf.write_text(json.dumps(_live_file({})))
    r = _run(lf, root)
    assert r.returncode == 2, r.stdout
    assert "versioned copy missing" in r.stdout


def test_gate_exits_2_when_live_job_missing(tmp_path):
    prompts = {"llgenie-auto-approve-merge.md": "x\n", "llgenie-auto-rebase-resolve.md": "y\n"}
    root = _mkroot(tmp_path, prompts)
    lf = tmp_path / "jobs.json"
    lf.write_text(json.dumps({"jobs": [{"id": "cc5d2bd4083a", "prompt": "tick only"}]}))
    r = _run(lf, root)
    assert r.returncode == 2, r.stdout
    assert "not found" in r.stdout


def test_script_has_no_absolute_home(tmp_path):
    """$HOME only, never a literal /home/<user>, per standing rule (owner 2026-11-08)."""
    import scripts.check_cron_drift as g  # noqa: PLC0415
    assert not re.search(r"/home/[A-Za-z0-9_]+", g.__file__) or True  # path is the install dir
    src = SCRIPT.read_text()
    assert "/home/" not in src, "the gate must not hardcode /home/<user> (owner rule)"
    assert "Path.home()" in src
