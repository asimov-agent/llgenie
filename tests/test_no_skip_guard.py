"""The no-skip guard states ONE contract in both of its hooks (issue #1110).

`tests/conftest.py` carries two guards: `pytest_report_teststatus` (every phase) and
`pytest_runtest_logreport` (the call phase). They once disagreed about `xfail` — one
treated an `xfail` report as a skip violation, the other exempted it — so a marker
could be walked into the hermetic gate while the guard read green.

This file loads the REAL `tests/conftest.py` (never a copy of its logic) and drives
each hook on its own, so an exemption reintroduced in just one hook reds a test that
names that hook. Real subprocess runs then prove the pair, wired together the way
pytest wires them: an `xfail` (and a module-level `skipif`) turns the run RED with a
non-zero exit, and a clean run stays GREEN.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

CONFTEST_PATH = Path(__file__).resolve().parent / "conftest.py"
REPORT_TESTSTATUS = "pytest_report_teststatus"
RUNTEST_LOGREPORT = "pytest_runtest_logreport"
HOOKS = (REPORT_TESTSTATUS, RUNTEST_LOGREPORT)


@pytest.fixture(autouse=True)
def _clean_guard():
    """Each test measures the guard from a clean slate (the run-scoped ledger)."""
    CONFTEST._SKIP_VIOLATIONS.clear()
    yield
    CONFTEST._SKIP_VIOLATIONS.clear()


def _load_conftest():
    spec = importlib.util.spec_from_file_location("llgenie_conftest_under_test", CONFTEST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFTEST = _load_conftest()


def _report(**overrides):
    """A pytest report stand-in: the four fields the guard reads, nothing else."""
    fields = {"skipped": False, "when": "call", "outcome": "passed", "wasxfail": None}
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _drive(hook, report):
    """Call one hook on its own, with the arity pytest calls it with."""
    fn = getattr(CONFTEST, hook)
    if hook == REPORT_TESTSTATUS:
        return fn(report, None)
    return fn(report)


@pytest.mark.parametrize("hook", HOOKS)
def test_each_hook_treats_an_xfail_as_a_skip_violation(hook):
    """An xfail report is `skipped` with `wasxfail` set; neither hook may exempt it."""

    # Given a report exactly as pytest emits it for a test that failed behind xfail
    report = _report(skipped=True, when="call", outcome="skipped",
                     wasxfail="known defect, tracked in an issue")

    # When  one hook sees that report on its own
    _drive(hook, report)

    # Then  the hook fails it, and says which hook refused the exemption
    assert report.outcome == "failed", (
        f"{hook} exempted an xfail — the two no-skip hooks disagree again (issue #1110)"
    )
    assert hook in report.longrepr, f"{hook} must name itself in the violation message"


@pytest.mark.parametrize("hook", HOOKS)
def test_each_hook_treats_a_plain_skip_as_a_violation(hook):
    """A skip with no xfail marker is the case both hooks were written for."""

    # Given a plain `pytest.skip()` report
    report = _report(skipped=True, when="call", outcome="skipped", wasxfail=None)

    # When  one hook sees it
    _drive(hook, report)

    # Then  it is a failure
    assert report.outcome == "failed", f"{hook} let a plain skip through"
    assert "no skips allowed" in report.longrepr


@pytest.mark.parametrize("hook", HOOKS)
def test_each_hook_leaves_a_passing_report_untouched(hook):
    """The guard fails skips only — it must not rewrite a passing test."""

    # Given a normal passing call-phase report
    report = _report(skipped=False, when="call", outcome="passed")

    # When  one hook sees it
    _drive(hook, report)

    # Then  nothing about it changed
    assert report.outcome == "passed"
    assert not hasattr(report, "longrepr")


def test_report_teststatus_owns_every_phase_so_a_setup_xfail_is_caught():
    """`pytest_runtest_logreport` is call-phase only; the status hook covers the rest."""

    # Given an xfail that failed during setup (no call-phase report exists)
    report = _report(skipped=True, when="setup", outcome="skipped", wasxfail="fixture defect")

    # When  the status hook sees it
    CONFTEST.pytest_report_teststatus(report, None)

    # Then  it is a failure — a module-level skip cannot slip past the call-phase hook
    assert report.outcome == "failed"


def test_the_shared_predicate_is_the_one_decision():
    """Both hooks ask `_skip_violation`; that predicate is the single contract."""

    # Given the predicate the conftest exposes
    predicate = CONFTEST._skip_violation

    # When  it is asked about an xfail, a plain skip, and a pass
    # Then  xfail and skip are violations, a pass is not
    assert predicate(_report(skipped=True, wasxfail="x")) is True
    assert predicate(_report(skipped=True, wasxfail=None)) is True
    assert predicate(_report(skipped=False)) is False


def test_sessionfinish_turns_a_recorded_violation_into_a_red_exit():
    """The ledger, not the printed line, is what makes the run red."""

    # Given a session that would otherwise exit GREEN, and the guard's ledger
    session = SimpleNamespace(
        exitstatus=0,
        config=SimpleNamespace(
            pluginmanager=SimpleNamespace(getplugin=lambda name: None)
        ),
    )

    # When  a skip was recorded by either hook and the session finishes
    _drive(REPORT_TESTSTATUS, _report(skipped=True, nodeid="tests/test_x.py::test_skip"))
    CONFTEST.pytest_sessionfinish(session, session.exitstatus)

    # Then  the process exit is FAILED (1), never the green 0 pytest computed
    assert session.exitstatus == 1


def test_sessionfinish_leaves_a_clean_run_green():
    """With no recorded violation the guard changes nothing."""

    # Given a session with an empty ledger
    session = SimpleNamespace(
        exitstatus=0,
        config=SimpleNamespace(
            pluginmanager=SimpleNamespace(getplugin=lambda name: None)
        ),
    )

    # When  the session finishes
    CONFTEST.pytest_sessionfinish(session, session.exitstatus)

    # Then  the exit status is untouched
    assert session.exitstatus == 0


def test_the_testing_doc_states_the_xfail_position_and_the_replacement():
    """The rule a lane reads is written in the docs, not only in my head."""

    # Given the testing page a lane is pointed at
    doc = Path(__file__).resolve().parent.parent / "docs" / "TESTING.md"

    # When  it is read
    text = doc.read_text(encoding="utf-8")

    # Then  it says xfail is a skip, and names the pattern whose removal is forced
    assert "`xfail` is a **skip**" in text
    assert "forced mechanically" in text
    assert "asserts the defect's **current** behaviour" in text


def _write_run(tmp_path, files: dict[str, str]):
    """A throwaway pytest root whose conftest re-exports the REAL hooks by path."""
    conftest = tmp_path / "conftest.py"
    conftest.write_text(
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('llgenie_conftest_e2e', {str(CONFTEST_PATH)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "pytest_report_teststatus = mod.pytest_report_teststatus\n"
        "pytest_runtest_logreport = mod.pytest_runtest_logreport\n"
        "pytest_sessionfinish = mod.pytest_sessionfinish\n",
        encoding="utf-8",
    )
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    return conftest


@pytest.mark.parametrize(
    "probe,body,nodeid",
    [
        (
            "test_xfail_probe.py",
            "import pytest\n\n\n"
            "@pytest.mark.xfail(reason='known defect', strict=False)\n"
            "def test_xfail_known_defect():\n"
            "    assert False, 'the tracked defect'\n",
            "test_xfail_known_defect",
        ),
        (
            "test_skip_probe.py",
            "import pytest\n\n\n"
            "def test_plain_skip():\n"
            "    pytest.skip('needs a prerequisite')\n",
            "test_plain_skip",
        ),
        (
            "test_module_skip_probe.py",
            "import pytest\n\n"
            "pytestmark = pytest.mark.skipif(True, reason='module skip')\n\n\n"
            "def test_inside_a_skipped_module():\n"
            "    assert True\n",
            "test_inside_a_skipped_module",
        ),
    ],
)
def test_a_real_skip_or_xfail_run_exits_red(tmp_path, probe, body, nodeid):
    """End to end: pytest wires the hooks in, and the exit status is the contract."""

    # Given a real pytest root that adds nothing but the repo's own hooks
    _write_run(tmp_path, {probe: body})

    # When  the file runs
    red = subprocess.run(
        [sys.executable, "-m", "pytest", probe, "-p", "no:cacheprovider", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
    )

    # Then  the run is RED (non-zero exit) and names the test and the guard
    assert red.returncode != 0, (
        f"{probe} stayed green (exit 0) while printing a failure:\n{red.stdout}\n{red.stderr}"
    )
    assert nodeid in red.stdout
    assert "no skips allowed" in red.stdout


def test_a_clean_run_exits_green(tmp_path):
    """The guard fails skips — it must not red an honestly passing run."""

    # Given a real pytest root with only a passing test, behind the repo's hooks
    _write_run(tmp_path, {"test_clean_probe.py": "def test_clean_probe():\n    assert True\n"})

    # When  it runs
    green = subprocess.run(
        [sys.executable, "-m", "pytest", "test_clean_probe.py", "-p", "no:cacheprovider", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
    )

    # Then  it exits GREEN
    assert green.returncode == 0, f"a clean run went red:\n{green.stdout}\n{green.stderr}"
