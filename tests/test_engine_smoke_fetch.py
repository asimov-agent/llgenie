"""The engine smoke fetches its tiny model through the ONE downloader (issue #385).

`scripts/engine_smoke.py::fetch_model` used to call the `hf` CLI itself with `check=True`,
so a Hub 429 during the CI engine matrix reddened the engine's job on its first answer. It
now runs `scripts/hf_download.py` — the same single download path the health check's model
fetch uses — which retries and waits the throttle out.

The real `fetch_model` runs here; the child process it starts is the stand-in (an external
system), and the assertion is on the fetch command the product built.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SMOKE = REPO / "scripts" / "engine_smoke.py"

from scripts import engine_smoke as smoke


def _fetch_argv(monkeypatch, fmt: str) -> list[str]:
    """Run the real fetch_model with the child process captured."""
    seen: list[list[str]] = []

    def fake_call(cmd, *a, **kw):
        seen.append(list(cmd))
        return 0

    monkeypatch.setattr(smoke.subprocess, "call", fake_call)
    smoke.fetch_model(fmt)
    assert seen, "fetch_model started no download"
    return seen[-1]


def test_fetch_model_runs_the_one_downloader(monkeypatch, tmp_path):
    """A named file goes to scripts/hf_download.py with repo, filename, dest and a label.

    # Given the smoke's tiny GGUF model (repo + filename) and a models dir
    # When fetch_model fetches it
    # Then the command is the downloader script with (repo, filename, dest, label)
    """
    monkeypatch.setattr(smoke, "MODELS_DIR", tmp_path)
    repo, filename = smoke.TEST_MODELS["gguf"]

    argv = _fetch_argv(monkeypatch, "gguf")

    assert argv[0] == sys.executable
    assert argv[1] == str(REPO / "scripts" / "hf_download.py")
    assert argv[2] == repo
    assert argv[3] == filename
    assert argv[4] == str(tmp_path / repo.replace("/", "__"))
    assert len(argv) == 6 and argv[5] == "gguf", argv


def test_fetch_model_asks_for_a_snapshot_when_the_format_has_no_filename(monkeypatch, tmp_path):
    """A whole-repo format (safetensors, MLX) is fetched as a snapshot through the same script.

    # Given the smoke's tiny safetensors model (a repo with no single file)
    # When fetch_model fetches it
    # Then the downloader is asked for the whole repo (`-`), not for a named file
    """
    monkeypatch.setattr(smoke, "MODELS_DIR", tmp_path)
    repo, filename = smoke.TEST_MODELS["safetensors"]
    assert filename is None, "this test needs a format with no filename"

    argv = _fetch_argv(monkeypatch, "safetensors")

    assert argv[1] == str(REPO / "scripts" / "hf_download.py")
    assert argv[2] == repo and argv[3] == "-", argv


def test_a_failed_fetch_is_loud(monkeypatch, tmp_path):
    """A non-zero download exits the smoke, naming the format.

    # Given a downloader that exits 2 (no `hf` CLI on PATH)
    # When fetch_model fetches the model
    # Then the smoke stops loudly, naming the format and the exit code
    """
    monkeypatch.setattr(smoke, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(smoke.subprocess, "call", lambda cmd, *a, **kw: 2)

    try:
        smoke.fetch_model("gguf")
    except SystemExit as exc:
        assert "gguf" in str(exc) and "2" in str(exc), str(exc)
    else:
        raise AssertionError("a failed download must stop the smoke")


def test_no_bare_hf_download_is_left_in_engine_smoke():
    """The smoke builds no `hf download` command of its own.

    # Given scripts/engine_smoke.py
    # When every string literal in its syntax tree is read
    # Then none builds a `download` command or names the `hf` CLI,
    # And  the one downloader IS named.
    """
    tree = ast.parse(SMOKE.read_text())
    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}

    assert "download" not in literals, "engine_smoke must not build its own download command"
    assert "hf" not in literals, "engine_smoke must not name the hf CLI"
    assert "hf_download.py" in literals, "engine_smoke must name the one downloader"
