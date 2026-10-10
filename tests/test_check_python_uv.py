"""check_python.py Linux auto-provision of Python 3.11 via uv (issue #122 pr branch):
`make -C tools create-venv` must find a uv-managed python3.11 even when it is not on
PATH, and when uv is on PATH but no 3.11 exists, provision it with `uv python install
3.11` — the Linux analogue of the macOS brew path. A host with neither uv nor 3.11
still fails closed with a clear message.

Hermetic: no real uv install, no PATH reads, no real ~/.local/share/uv — the resolver's
search root, version check and install calls are all monkeypatched, so CI never
provisions or touches a real host Python.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def cp(monkeypatch, tmp_path):
    """Load check_python fresh and point uv's managed dir at a tmp root, so every
    uv-python search is hermetic."""
    mod = types.ModuleType("check_python_under_test")
    spec = importlib.util.spec_from_file_location("check_python_under_test",
                                                  REPO / "scripts" / "check_python.py")
    impl = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(impl)
    fake_root = tmp_path / "uv-python"
    monkeypatch.setattr(impl, "uv_python_root", lambda: str(fake_root))
    # the test runner itself is 3.11; make the resolver think it is 3.14 so every test
    # actually exercises the PATH / uv / brew search instead of the "we are already
    # 3.11" short-circuit (running_is_want is a test-only seam, never the real check)
    monkeypatch.setattr(impl, "running_is_want", lambda: False)
    monkeypatch.setattr(impl, "uv_install_python311", lambda: True)
    return impl, fake_root


def _make_uv_dir(impl, root, exe="python3.11"):
    """Create a uv-managed CPython 3.11 dir (its bin/python3.11) and force the
    resolver to treat it as a 3.11 (version_of patched), so the search is hermetic."""
    d = root / "cpython-3.11.9-linux-x86_64-gnu" / "bin"
    d.mkdir(parents=True, exist_ok=True)
    exe_path = d / exe
    exe_path.write_text("#!/bin/sh\necho 3 11\n")
    exe_path.chmod(0o755)


# ---- uv-managed python not on PATH is found ---------------------------------------
def test_finds_uv_managed_python311_not_on_path(cp, monkeypatch):
    # Given a uv-managed python3.11 that is NOT on PATH (the exact Linux host: uv
    #   manages 3.11 but there is no `python3.11` in PATH)
    impl, root = cp
    _make_uv_dir(impl, root)

    # When find_python311 looks beyond PATH (uv managed dir is consulted)
    monkeypatch.setattr(impl.shutil, "which", lambda n: None)  # no python3.11 on PATH
    monkeypatch.setattr(impl, "version_of",
                        lambda p: (3, 11) if p.endswith("python3.11") else None)

    # Then it resolves the uv-managed interpreter (no PATH/brew hit needed)
    found = impl.find_python311()
    assert found and found == str(root / "cpython-3.11.9-linux-x86_64-gnu" / "bin" / "python3.11")


# ---- PATH wins over uv ------------------------------------------------------------
def test_prefers_path_python_over_uv(cp, monkeypatch):
    # Given both a PATH python3.11 and a uv-managed one
    impl, root = cp
    _make_uv_dir(impl, root)

    # When the resolver runs with python3.11 on PATH
    monkeypatch.setattr(impl.shutil, "which",
                        lambda n: "/usr/bin/python3.11" if n == "python3.11" else None)
    monkeypatch.setattr(impl, "version_of",
                        lambda p: (3, 11) if p == "/usr/bin/python3.11" else None)
    monkeypatch.setattr(impl.os.path, "isfile",
                        lambda p: p == "/usr/bin/python3.11" or p.endswith("python3.11"))

    # Then the PATH interpreter wins (uv is only a fallback for hosts without it)
    assert impl.find_python311() == "/usr/bin/python3.11"


# ---- uv auto-provision when 3.11 is missing --------------------------------------
def test_auto_provisions_via_uv_when_missing(cp, monkeypatch):
    # Given a Linux host with uv on PATH but no python3.11 anywhere (find_python311
    #   returns nothing before install; the install makes it appear)
    impl, root = cp
    calls = []

    def fake_install():
        calls.append("installed")
        return True

    monkeypatch.setattr(impl, "uv_install_python311", fake_install)
    # find_python311 returns None on the first resolve, then the now-managed path
    state = {"n": 0}
    uv_exe = str(root / "cpython-3.11.9-linux-x86_64-gnu" / "bin" / "python3.11")

    def fake_find():
        state["n"] += 1
        return None if state["n"] == 1 else uv_exe

    monkeypatch.setattr(impl, "find_python311", fake_find)
    monkeypatch.setattr(impl.sys, "platform", "linux")
    monkeypatch.setattr(impl.shutil, "which", lambda n: "/usr/bin/uv" if n == "uv" else None)

    # When the resolver runs and 3.11 is missing
    found = impl.resolve()

    # Then it provisions via uv and returns the now-managed py311
    assert calls == ["installed"]
    assert found == uv_exe


# ---- fails closed with neither uv nor 3.11 ----------------------------------------
def test_fails_closed_with_no_uv_and_no_311(cp, monkeypatch):
    # Given a host with neither uv nor any python3.11
    impl, root = cp
    calls = []
    monkeypatch.setattr(impl.sys, "platform", "linux")
    monkeypatch.setattr(impl.shutil, "which", lambda n: None)
    monkeypatch.setattr(impl, "find_python311", lambda: None)
    monkeypatch.setattr(impl, "uv_install_python311", lambda: calls.append(1) or True)

    # When resolve is called
    found = impl.resolve()

    # Then it does NOT provision (uv absent) and returns None -> make fails closed
    assert calls == []
    assert found is None


# ---- real_main exits 1 with the actionable message -------------------------------
def test_real_main_fails_closed_with_actionable_message(cp, monkeypatch, capsys):
    # Given a host with no python3.11 and no way to get one
    impl, root = cp
    monkeypatch.setattr(impl, "resolve", lambda: None)
    # When the make-venv gate runs
    rc = impl.real_main([])
    # Then it exits 1 and the message points at the uv route
    assert rc == 1
    assert "uv python install 3.11" in capsys.readouterr().err
