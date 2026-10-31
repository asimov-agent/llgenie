"""Shared pytest fixtures for the llgenie test suite.

All tests run under the gguf venv python (see Makefile `test` target). We
expose the repo root so tests can locate scripts/llgenie_serve.py / Makefile / tools.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Repo root = parent of this tests/ directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
# The ONE import root (issue #796): `scripts/` too, because the scripts import their siblings bare
# (`scripts/auto_merge.py` does `import verify_closure`). A test file that inserted this itself was
# working around a seam that belongs here, once, for the whole suite.
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import scripts.llgenie_serve as llgenie_serve  # noqa: E402  (importable: gguf+numpy come from the venv)

HOME = Path.home()
MODELS_ROOT = HOME / "models"
BIN = HOME / "bin"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def launcher() -> Path:
    """Executable ~/bin/llgenie installed by `make install`."""
    return BIN / "llgenie"


@pytest.fixture(scope="session")
def models_root() -> Path:
    return MODELS_ROOT


@pytest.fixture(scope="session")
def server_bin() -> str:
    """llama-server binary (resolved via PATH or LLAMA_SERVER)."""
    # reads the env the same way llgenie_serve.resolve_llama_server does, but
    # tolerates absence so we can assert the right error message in tests.
    env = (os.environ.get("LLAMA_SERVER") or "").strip()
    if env and Path(env).is_file():
        return env
    import shutil
    return shutil.which("llama-server") or ""


# ---------------------------------------------------------------------------
# NO-SKIP GUARD (mandatory): a skipped test is a LOUD FAILURE, never silent.
#
# THE CONTRACT (issue #1110 — one rule, read by BOTH hooks below):
# a SKIP is any report pytest marks `skipped`, in any phase and from any cause —
# `pytest.skip()`, `@pytest.mark.skipif`, a conditional skip inside the test, or an
# `xfail` marker whose test failed (pytest reports that as skipped with `wasxfail`
# set). An XFAIL is therefore NOT an exemption: this repo has no "known failure"
# bucket in the gate, because a green gate must mean every test ran and passed
# (AGENTS.md, "NO SKIPPED TESTS"). A tracked defect is locked instead by a test that
# asserts the defect's CURRENT behaviour, so fixing the defect reds that test and
# its deletion is forced mechanically rather than remembered.
# `_skip_violation()` is the ONLY place that decides what counts as a violation, so
# the two hooks cannot drift apart again. Who owns what: `pytest_runtest_logreport`
# owns the call-phase verdict (the failure lands on the test that skipped), and
# `pytest_report_teststatus` owns EVERY phase (a setup/teardown or whole-module skip
# produces no call-phase report to catch it). Mutating a report's outcome only changes
# what the terminal PRINTS — pytest computes its exit status from its own failure
# counter — so `pytest_sessionfinish` owns the one thing both hooks need: a recorded
# violation turns the process exit RED. Before issue #1110 a skipped test printed
# `FAILED` and still exited 0, so the whole guard was decorative.
# ---------------------------------------------------------------------------
def _skip_violation(report) -> bool:
    """The one contract both hooks ask: is this report a skip — xfail included?"""
    return bool(getattr(report, "skipped", False))


def _skip_violation_message(hook: str) -> str:
    return (
        "TEST SKIPPED — no skips allowed (AGENTS.md). A skipped test means a broken "
        "prerequisite is being masked. Provision the prerequisite (e.g. run "
        "`make download-test-model` / `make install` / set LLAMA_SERVER) so the test "
        "genuinely runs, or fix the test — never leave a skip. An `xfail` marker is a "
        "skip too (issue #1110): lock a tracked defect with a test that asserts its "
        "current behaviour instead. "
        f"[flagged by {hook}]"
    )


# Node ids the guard has failed in this process (one entry per test, never per phase).
_SKIP_VIOLATIONS: list[str] = []


def _fail_report(report, hook: str) -> None:
    """Mark the report failed for the reader, and remember it for the exit status."""
    report.outcome = "failed"
    report.longrepr = _skip_violation_message(hook)
    nodeid = getattr(report, "nodeid", None) or "?"
    if nodeid not in _SKIP_VIOLATIONS:
        _SKIP_VIOLATIONS.append(nodeid)


def pytest_report_teststatus(report, config):
    if _skip_violation(report):
        # Mark a skipped test as a failure in the output (loud), not silent.
        _fail_report(report, "pytest_report_teststatus")
    return None


def pytest_runtest_logreport(report):
    if report.when == "call" and _skip_violation(report):
        # Convert a skip into a hard failure at the call site (any phase is covered
        # by pytest_report_teststatus above; xfail is NOT exempt).
        _fail_report(report, "pytest_runtest_logreport")


def pytest_sessionfinish(session, exitstatus):
    """The exit status is the contract: one recorded skip turns a green run red."""
    if not _SKIP_VIOLATIONS:
        return
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(
            f"NO-SKIP GUARD: {len(_SKIP_VIOLATIONS)} skipped test(s) failed this run "
            "(AGENTS.md): " + ", ".join(sorted(_SKIP_VIOLATIONS))
        )
    if session.exitstatus == 0:
        session.exitstatus = 1  # pytest ExitCode.TESTS_FAILED
