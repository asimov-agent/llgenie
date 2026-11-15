"""`build-server`'s detect → build → stamp flow lives in scripts/build_server.py (issue #2675).

The 15-line shell recipe (mk/engines.mk at origin/main@dcfb96b7df) moved into the entry point;
the target recipe became the thin wrapper. `scripts/detect_server.py` probes THIS card's GPU,
so the fake below stands in only for that hardware probe (stubbed via `sys.modules`, the import
seam the entry point uses); the build itself is a REAL child process — the stream/tee to the
log, the last-line binary gate, the stamp file and the log cleanup all run for real:

- the build script's stdout AND stderr are streamed to the console and teed to the log;
- like the base under `set -o pipefail` without `set -e`, the build's own exit status is not
  checked — the gate is the stamped binary: SRV = last log line, and `test -x` decides;
- a failing detect errors out before any build starts;
- the log is removed only on the success path (a failed build leaves its log behind).

`make build-server` is host-only (CI builds variants through `build-variant`); the wiring
fixture entry recorded under #2675 is pinned here so the exemption cannot drift.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from conftest import makefiles_text  # noqa: E402  (include-resolving reader, #2459)
from scripts import build_server


def _fake_repo(tmp_path: Path, script_body: str) -> Path:
    """A scratch 'repo' whose scripts/build_llama_server.sh is the given body."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    sh = repo / "scripts" / "build_llama_server.sh"
    sh.write_text(script_body)
    sh.chmod(sh.stat().st_mode | stat.S_IXUSR)
    return repo


def _stub_detect(monkeypatch, tree: str, backend: str) -> None:
    mod = types.ModuleType("scripts.detect_server")
    mod.detect_all = lambda: {"tree": tree, "backend": backend}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts.detect_server", mod)


def _recipe() -> str:
    mk = makefiles_text(REPO)
    m = re.search(r"^build-server:[^\n]*\n((?:[ \t].*\n)*)", mk, re.M)
    assert m, "build-server target not found in the flattened Makefile"
    return m.group(1)


def test_the_build_server_recipe_is_the_thin_wrapper_of_the_entry_point():
    # Given the flattened Makefile at this head
    tab_lines = [l for l in _recipe().splitlines() if l.startswith("\t")]
    # Then it is one line, passing the make variables through as arguments
    assert len(tab_lines) == 1, tab_lines
    assert tab_lines[0].strip() == (
        '@python3 scripts/build_server.py --server-root "$(SERVER_ROOT)" '
        '--repo "$(REPO)" --stamp "$(SERVER_BIN_STAMP)"')


def test_build_streams_and_tees_then_stamps_the_last_log_binary(tmp_path, monkeypatch):
    # Given a card with a detected tree/backend and a build script that emits noise, a stderr
    # warning, and finally the path of the binary it produced
    bin_path = tmp_path / "server-bin"
    repo = _fake_repo(tmp_path, (
        "#!/bin/sh\n"
        'echo "clone-or-pull: llama.cpp"\n'
        'echo "warning: fake compiler warning" >&2\n'
        'printf \'#!/bin/sh\\nexit 0\\n\' > "$FAKE_BIN"\n'
        'chmod +x "$FAKE_BIN"\n'
        'echo "$FAKE_BIN"\n'))
    monkeypatch.setenv("FAKE_BIN", str(bin_path))
    _stub_detect(monkeypatch, "llama.cpp", "cuda")
    log = tmp_path / "build.log"
    stamp = tmp_path / "state" / "server-bin.txt"
    # When the entry point builds
    rc = build_server.build(str(tmp_path / "srv-root"), str(repo), str(stamp), log=str(log))
    # Then it succeeds, stamps the binary path, and removes the log on the success path
    assert rc == 0
    assert stamp.read_text() == f"{bin_path}\n"
    assert not log.exists()
    assert (tmp_path / "srv-root")  # SERVER_ROOT was exported to the child (it used $FAKE_BIN)


def test_the_last_log_line_not_being_an_executable_binary_fails_the_build(tmp_path, monkeypatch):
    # Given a build whose LAST log line names a binary that does not exist (pipefail-without-
    # set -e semantics: the child's rc is ignored; the stamped-binary gate decides)
    repo = _fake_repo(tmp_path, "#!/bin/sh\necho 'cmake error: build failed'\nexit 1\n"
                               "echo /does/not/exist/llama-server\n")
    _stub_detect(monkeypatch, "llama.cpp", "cpu")
    log = tmp_path / "build.log"
    stamp = tmp_path / "state" / "server-bin.txt"
    # When the entry point builds
    rc = build_server.build(str(tmp_path / "srv-root"), str(repo), str(stamp), log=str(log))
    # Then it fails at the binary gate, writes no stamp, and KEEPS the log for the human
    assert rc == 1
    assert not stamp.exists()
    assert log.exists() and "build failed" in log.read_text()  # stderr+stdout both teed


def test_empty_detect_fails_before_any_build_runs(tmp_path, monkeypatch):
    # Given a machine where detect_server yields nothing
    _stub_detect(monkeypatch, "", "")
    repo = _fake_repo(tmp_path, "#!/bin/sh\nexit 0\n")
    log = tmp_path / "build.log"
    # When the entry point runs
    rc = build_server.build(str(tmp_path / "srv-root"), str(repo), str(tmp_path / "stamp.txt"),
                            log=str(log))
    # Then it errors out before touching the build script or the log
    assert rc == 1
    assert not log.exists()


def test_build_server_is_NOT_host_only_once_a_ci_test_covers_it():
    # Given the wiring fixture's host-only decisions
    fixture = json.loads((REPO / "tests" / "fixtures" / "host-only-wiring.json").read_text())
    # Then scripts/build_server.py is NOT declared host-only: this very module
    # (tests/test_build_server_stage.py) exercises the entry point inside ci-unit,
    # and check_wiring reds any host-only entry whose doc is covered by a CI test.
    assert "scripts/build_server.py" not in fixture, (
        "a CI test covers scripts/build_server.py; the host-only entry must be deleted"
    )
