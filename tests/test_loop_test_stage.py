"""The loop's `test` stage asserts the host install on the HOST (issue #317).

`make test` is the loop's `test` stage. It used to run `tests/test_install.py` through `$(TEST_RUN)`,
which on Linux is `docker run … -e HOME=/root` (Makefile `TEST_OPTS`) — and the install tests resolve
their artifacts from `HOME` (`tests/conftest.py`). Inside that `--rm` container `/root/bin/llgenie`
cannot exist, so under the no-skip policy six assertions failed on every Linux host, and the loop
stage could never be green for a reason unrelated to the change being verified (measured on `29080c7`:
`6 failed, 1 passed`; on `08f585f`: the same six, `330 passed` in the stage).

These tests read the real Makefile recipes — no mocks, no subprocess — and pin the contract that keeps
the assertions in the gate without pretending a container holds a host install.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"

#: `$(TEST_RUN)` is the containerized command on Linux and the venv python on macOS.
CONTAINERIZED = "TEST_RUN"


def _recipe(target: str) -> str:
    """The recipe lines of `target:`, without the target line itself."""
    text = MAKEFILE.read_text()
    match = re.search(rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n|\n(?=\t))*)", text, re.M)
    assert match, f"no recipe for `{target}:` in the Makefile"
    return match.group(1)


def test_test_stage_does_not_run_install_tests_in_the_container():
    """The containerized command must not name tests/test_install.py (#317).

    The install tests read `HOME / "bin"`, and `$(TEST_RUN)` sets `HOME=/root` on Linux: naming the
    file there is the bug — the assertions cannot pass, and they are not proving anything about the
    host install the way the gate claims.
    """
    recipe = _recipe("test")
    container_lines = [l for l in recipe.splitlines() if CONTAINERIZED in l]
    assert container_lines, "the `test` recipe no longer runs a containerized command"
    for line in container_lines:
        assert "tests/test_install.py" not in line, (
            "`make test` runs tests/test_install.py inside $(TEST_RUN): on Linux that is a `--rm` "
            "container with HOME=/root, where the install artifacts cannot exist, so the stage can "
            "only ever fail (#317). Run the install assertions on the host instead."
        )


def test_test_stage_calls_the_host_install_verification():
    """`make test` must reach tests/test_install.py through the host target."""
    recipe = _recipe("test")
    assert re.search(r"\$\(MAKE\)\s+test-install-host", recipe), (
        "`make test` must call `$(MAKE) test-install-host`, so the install assertions still run — "
        "on the host, where ~/bin/llgenie and ~/models actually exist (#317)."
    )


def test_host_install_target_runs_the_install_tests_with_the_host_python():
    """`test-install-host` is the one place those assertions run, and it uses the host's python."""
    recipe = _recipe("test-install-host")
    assert "tests/test_install.py" in recipe, (
        "`test-install-host` must run tests/test_install.py; it is the target `make test` now "
        "delegates the install assertions to (#317)."
    )
    assert "$(PY)" in recipe, "`test-install-host` must use the host's $(PY), not $(TEST_RUN)"
    assert CONTAINERIZED not in recipe, (
        "`test-install-host` must not run in a container: it asserts the host's own install (#317)."
    )


def test_install_assertions_are_still_in_some_gate():
    """Removing them from the containerized command must not remove them from every gate."""
    reachable = ["test", "test-install-host", "test-install-ci", "ci-install"]
    for target in reachable:
        recipe = _recipe(target) if re.search(rf"^{re.escape(target)}:", MAKEFILE.read_text(), re.M) else ""
        if "tests/test_install.py" in recipe:
            return
    raise AssertionError(
        "no gate runs tests/test_install.py any more; the install assertions were dropped, not moved"
    )
