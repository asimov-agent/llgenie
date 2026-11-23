"""tests for scripts/host_ci_monitor_wrapper.py (issue #3016).

Every wrapper state is driven hermetically: a local-path git remote, a fake Makefile, tmp_path
clones — zero network, zero host paths. The assertions are on the exact stdout string, because that
is what the Hermes monitor cron hashes: a failed refresh must be distinguishable from the
"target not landed yet" line, byte for byte.
"""
from __future__ import annotations

import subprocess

import scripts.host_ci_monitor_wrapper as wrapper

GREEN_MAKEFILE = "ci-monitor:\n\t@echo MONITOR-OK\n"
STDERR_MAKEFILE = "ci-monitor:\n\t@echo MONITOR-OK\n\t@echo gh-fetch detail 1>&2\n"
NO_TARGET_MAKEFILE = "all:\n\t@echo nothing here\n"


def _git(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=(str(cwd) if cwd is not None else None), capture_output=True, text=True, check=True
    )


def _origin(tmp_path, makefile: str):
    origin = tmp_path / "origin"
    origin.mkdir()
    # Explicit branch: a container or host with init.defaultBranch=master would otherwise
    # leave the remote without a `main` branch and the wrapper's `fetch origin main` would
    # fail for fixture reasons, not wrapper reasons (issue #3016 battery).
    _git("init", "-q", "-b", "main", cwd=origin)
    _git("config", "user.email", "test@example.invalid", cwd=origin)
    _git("config", "user.name", "fixture", cwd=origin)
    (origin / "Makefile").write_text(makefile)
    (origin / "scripts").mkdir()
    (origin / "scripts" / "noop.txt").write_text("x\n")
    _git("add", "-A", cwd=origin)
    _git("commit", "-q", "-m", "fixture target", cwd=origin)
    return origin


def _clone(tmp_path, origin, makefile: str = GREEN_MAKEFILE):
    clone = tmp_path / "clone"
    _git("clone", "-q", str(origin), str(clone))
    if makefile != _origin_makefile(origin):
        _git("config", "user.email", "test@example.invalid", cwd=clone)
        _git("config", "user.name", "fixture", cwd=clone)
        (clone / "Makefile").write_text(makefile)
        _git("add", "-A", cwd=clone)
        _git("commit", "-q", "-m", "local fake make", cwd=clone)
    return clone


def _origin_makefile(origin):
    return (origin / "Makefile").read_text()


def _run(monkeypatch, clone):
    monkeypatch.setattr(wrapper, "REPO", clone)
    code = wrapper.main()
    return code


def test_green_clone_refresh_runs_make_and_passes_stdout_through(tmp_path, monkeypatch, capsys):
    origin = _origin(tmp_path, GREEN_MAKEFILE)
    clone = _clone(tmp_path, origin)
    code = _run(monkeypatch, clone)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "MONITOR-OK\n"
    # The clone really was refreshed to origin/main.
    head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True)
    tip = subprocess.run(["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True)
    assert head.stdout.strip() == tip.stdout.strip()


def test_failed_fetch_prints_clone_refresh_failed(tmp_path, monkeypatch, capsys):
    origin = _origin(tmp_path, GREEN_MAKEFILE)
    clone = _clone(tmp_path, origin)
    # A remote that no longer exists: `git fetch origin main` exits non-zero (issue #3016 Repro A).
    _git("remote", "set-url", "origin", str(tmp_path / "gone.git"), cwd=clone)
    code = _run(monkeypatch, clone)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "MONITOR-ERROR clone-refresh-failed\n"
    assert "fetch:" in captured.err
    assert "make-ci-monitor-failed" not in captured.out


def test_dirty_clone_prints_clone_refresh_failed(tmp_path, monkeypatch, capsys):
    origin = _origin(tmp_path, GREEN_MAKEFILE)
    clone = _clone(tmp_path, origin)
    (clone / "untracked.txt").write_text("dirty\n")  # issue #3016 Repro B
    code = _run(monkeypatch, clone)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "MONITOR-ERROR clone-refresh-failed\n"
    assert "clone dirty" in captured.err
    assert "make-ci-monitor-failed" not in captured.out


def test_pre_target_clone_still_prints_make_failed(tmp_path, monkeypatch, capsys):
    # A refreshed, clean clone whose Makefile lacks the ci-monitor rule: the honest
    # "not landed yet" line — no false refresh alarm (issue #3016 AC3).
    origin = _origin(tmp_path, NO_TARGET_MAKEFILE)
    clone = _clone(tmp_path, origin, makefile=NO_TARGET_MAKEFILE)
    code = _run(monkeypatch, clone)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "MONITOR-ERROR make-ci-monitor-failed\n"
    assert "clone-refresh-failed" not in captured.out


def test_green_make_stderr_is_passed_through(tmp_path, monkeypatch, capsys):
    origin = _origin(tmp_path, GREEN_MAKEFILE)
    clone = _clone(tmp_path, origin, makefile=STDERR_MAKEFILE)
    code = _run(monkeypatch, clone)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "MONITOR-OK\n"
    assert "gh-fetch detail" in captured.err
