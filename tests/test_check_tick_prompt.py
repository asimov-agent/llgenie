"""Hermetic tests for scripts/check_tick_prompt.py (issue #2159, AC: the drift gate).

The gate reds when the live orchetran cron prompt diverges from the versioned
copy and greens when they match — including the trailing-newline normalization
(lint commits the file with a trailing newline, the live JSON value stores it
without). These tests run the real script against fixture files, no live
~/.hermes profile touched.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "check_tick_prompt.py"
)
VERSIONED = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "prompts"
    / "llgenie-orchestrator-tick.md"
)

LIVE_JOB_ID = "cc5d2bd4083a"


def _live_file(versioned_path, prompt_override=None):
    """Build a jobs.json whose single job's prompt comes from the versioned file
    (optionally overridden), matching the live shape."""
    base = versioned_path.read_text()
    # live JSON stores the prompt without the trailing newline
    stored = base[:-1] if base.endswith("\n") else base
    if prompt_override is not None:
        stored = prompt_override
    return {
        "jobs": [
            {
                "id": LIVE_JOB_ID,
                "name": "llgenie-orchestrator-tick (30m monitor)",
                "schedule": {"kind": "interval", "minutes": 30},
                "prompt": stored,
            }
        ]
    }


def _run(live_json_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--live", str(live_json_path)],
        capture_output=True,
        text=True,
        env={**os.environ},
        timeout=60,
    )


def test_gate_greens_when_live_matches(tmp_path):
    lf = tmp_path / "jobs.json"
    lf.write_text(json.dumps(_live_file(VERSIONED)))
    r = _run(lf)
    assert r.returncode == 0, r.stdout


def test_gate_greens_despite_validation_newline_on_disk(tmp_path):
    # Explicit: prove the gate normalizes the disk trailing newline rather than
    # redding on file-vs-json framing. Live prompt == versioned content.
    vtxt = VERSIONED.read_text()
    # drop a trailing newline the JSON would omit, then confirm green
    live = vtxt[:-1] if vtxt.endswith("\n") else vtxt
    lf = tmp_path / "jobs.json"
    lf.write_text(json.dumps(_live_file(VERSIONED, prompt_override=live)))
    r = _run(lf)
    assert r.returncode == 0, r.stdout


def test_gate_reds_on_content_divergence(tmp_path):
    lf = tmp_path / "jobs.json"
    lf.write_text(
        json.dumps(_live_file(VERSIONED, prompt_override="completely different"))
    )
    r = _run(lf)
    assert r.returncode == 1, r.stdout
    assert "LIVE prompt" in r.stdout


def test_gate_counts_both_byte_sizes_on_divergence(tmp_path):
    lf = tmp_path / "jobs.json"
    lf.write_text(
        json.dumps(_live_file(VERSIONED, prompt_override="diff"))
    )
    r = _run(lf)
    assert r.returncode == 1
    # both byte counts must be named so the reviewer sees the magnitude: the
    # live prompt's and the versioned copy's, as two distinct {n} b) tokens.
    sizes = re.findall(r"\((\d+) b\)", r.stdout)
    assert len(sizes) == 2, (r.stdout, sizes)
    live_n, ver_n = (int(s) for s in sizes)
    assert live_n == 4, (live_n, r.stdout)     # "diff" is 4 bytes
    assert ver_n == len(VERSIONED.read_text()), ver_n


def test_gate_exits_2_when_job_missing(tmp_path):
    lf = tmp_path / "jobs.json"
    lf.write_text(json.dumps({"jobs": [{"id": "other"}]}))
    r = _run(lf)
    assert r.returncode == 2, r.stdout
