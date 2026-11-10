"""Shared pytest fixtures for the llgenie test suite.

All tests run under the gguf venv python (see Makefile `test` target). We
expose the repo root so tests can locate scripts/llgenie_serve.py / Makefile / tools.
"""
from __future__ import annotations

import os
import re
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


def makefiles_text(root: Path = REPO_ROOT) -> str:
    """The top Makefile + every `mk/*.mk` it `include`s, in include order (issue #800).

    The 2,083-line Makefile split its targets into `mk/{engines,gates,ci,security,bots,install}.mk`,
    so a test that regexes or slices the Makefile text for a target must see the concatenation the
    build itself resolves — the split must not make a reader go blind the way it did `check_wiring`
    (which now resolves includes before building its graph). Same resolver contract as
    `scripts/check_wiring.py`; GNU make expands a wildcard `include mk/*.mk` to every matching file,
    sorted, and we mirror that (one pattern per directive).
    """
    body: list[str] = []
    seen: set[str] = set()
    pending: list[str] = ["Makefile"]
    while pending:
        rel = pending.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            continue
        body.append(p.read_text())
        for m in re.finditer(r"^\s*include\s+(\S+)(?:\s+#.*)?\s*$", p.read_text(), re.M):
            inc = m.group(1)
            if "*" in inc:
                pending.extend(sorted(q.relative_to(root).as_posix() for q in root.glob(inc)))
            else:
                pending.append(inc)
    return "\n\n".join(body)


def makefiles_paths(root: Path = REPO_ROOT) -> list[Path]:
    """The top Makefile + every `mk/*.mk` it `include`s, in include order (issue #800)."""
    body: list[Path] = []
    seen: set[str] = set()
    pending: list[str] = ["Makefile"]
    while pending:
        rel = pending.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            continue
        body.append(p)
        for m in re.finditer(r"^\s*include\s+(\S+)(?:\s+#.*)?\s*$", p.read_text(), re.M):
            inc = m.group(1)
            if "*" in inc:
                pending.extend(sorted(q.relative_to(root).as_posix() for q in root.glob(inc)))
            else:
                pending.append(inc)
    return body


#: A top-level make target definition line (`name: prereq ## help`), the boundary a recipe ends at
#: even when the split dropped the blank line that used to separate target blocks (issue #800).
_TARGET_LINE = re.compile(r"(?m)^([A-Za-z0-9_.%-][A-Za-z0-9_.%-]*):.*$")


def makefile_recipes(root: Path = REPO_ROOT) -> dict[str, str]:
    """`{target: its recipe text}` over the resolved makefiles (top Makefile + mk/*.mk, in include
    order, issue #800).

    The split removed the blank line that used to terminate every recipe block, so a recipe is now
    delimited by the next top-level target line, not by `\\n\\n`. Structural extraction — a recipe is
    the target's line plus the following lines until the next `^name:` — is what every test that
    slices a recipe actually wants, and it stays correct whether or not blank lines separate targets.
    """
    text = makefiles_text(root)
    spans = [(m.group(1), m.start(), m.end()) for m in _TARGET_LINE.finditer(text)]
    if not spans:
        return {}
    out: dict[str, str] = {}
    for i, (name, start, end) in enumerate(spans):
        nxt = spans[i + 1][1] if i + 1 < len(spans) else len(text)
        out[name] = text[end:nxt]
    return out


def make_recipe(name: str, root: Path = REPO_ROOT) -> str:
    """The recipe of one target (its lines after `name:` up to the next target line)."""
    recipes = makefile_recipes(root)
    assert name in recipes, f"make target {name} missing from the resolved makefiles"
    return recipes[name]


def ci_unit_steps(root: Path = REPO_ROOT) -> list[str]:
    """The make targets the ci-unit sequence runs, from `scripts/ci_unit.py` (`STEPS`, issue #800).

    The 49-line `$(MAKE) <gate>` recipe became `@python3 scripts/ci_unit.py` and the sequence moved
    into that tested module's `STEPS`; the tests that used to read the battery out of the Makefile
    now read it where it lives. Same parser as `issue_bot_gates._ci_unit_steps`.
    """
    text = (root / "scripts" / "ci_unit.py").read_text()
    block = text.split("STEPS = [", 1)[1].split("]", 1)[0]
    out: list[str] = []
    for ln in block.splitlines():
        tok = ln.strip().replace('"', "").replace("'", "").strip().strip(",").strip()
        name = tok.split()[0] if tok else ""
        if name and name not in out:
            out.append(name)
    return out


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


# Containers already running when this pytest process started. Session finish removes
# only the ones this run created (issue #1669).
_ENGINES_BEFORE: set[str] = set()


def pytest_sessionstart(session):
    global _ENGINES_BEFORE
    import scripts.install_engine_launchers as iel
    _ENGINES_BEFORE = iel.engine_container_ids()


def pytest_sessionfinish(session, exitstatus):
    """The exit status is the contract: one recorded skip turns a green run red.

    Also remove engine containers this session started (issue #1669).
    """
    import scripts.install_engine_launchers as iel
    iel.stop_new_engine_containers(_ENGINES_BEFORE)
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
