"""The openspec gate must cover the change under review, not a hardcoded name (issue #156).

`ci-openspec` validated `NAME=ci-pipeline` and the loop defaulted to `NAME=llama-ai-tooling`, so the
change a commit introduced was structurally validated only if someone remembered. These tests read the
gate itself: the CI job must validate every active change, and the loop must do the same unless a name
is given.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)


def _recipe(text: str, target: str) -> str:
    """The recipe lines of one Makefile target."""
    m = re.search(rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n)+)", text, re.M)
    assert m, f"target {target} not found"
    return m.group(1)


def test_ci_validates_every_active_change():
    """`ci-openspec` runs the all-changes gate, and names no single change."""

    # Given the Makefile (the top + its mk/*.mk includes — openspec-validate-all lives behind one)
    mk = makefiles_text()

    # When  its ci-openspec and openspec-validate-all recipes are read
    ci = _recipe(mk, "ci-openspec")
    all_changes = _recipe(mk, "openspec-validate-all")

    # Then  CI validates every change, and no hardcoded name survives
    assert "openspec-validate-all" in ci
    assert "openspec-validate NAME=" not in ci
    assert "openspec validate --changes" in all_changes


def test_the_loop_validates_all_changes_without_a_name():
    """The loop's openspec stage validates every change unless `NAME` names one."""

    # Given the loop harness
    src = (REPO / "scripts" / "loop_harness.py").read_text()

    # When  its openspec stage is read
    stage = next(line for line in src.splitlines() if '"openspec"' in line)

    # Then  no hardcoded change name remains, and the all-changes target is the default
    assert "llama-ai-tooling" not in src
    assert "openspec-validate-all" in src
    assert "openspec-validate" in stage


def test_openspec_run_writes_as_the_invoking_user():
    """issue #433: the OpenSpec CLI run WRITES into the mounted repo, so it must
    map to the invoking uid:gid like TEST_OPTS does — never `-u root`."""

    # Given the Makefile seam definitions
    mk = makefiles_text()

    # When  the two write-path option variables are read
    os_opts = next(l for l in mk.splitlines() if l.startswith("OS_OPTS :="))
    test_opts = next(l for l in mk.splitlines() if l.startswith("TEST_OPTS :="))

    # Then  both map the invoking uid:gid, OS_OPTS carries no -u root,
    # and the CLI gets a world-writable HOME on the mapped uid
    for line in (os_opts, test_opts):
        assert "id -u" in line and "id -g" in line, line
        assert "-u root" not in line, line
    assert "-e HOME=/tmp" in os_opts


def test_only_the_carved_out_stages_run_as_root():
    """issue #433 / #2563: exactly the docker.sock engine stage and the
    root-tree cleaner may mount the repo as root, each named by variable."""

    # Given every root-user container run in the Makefile seams
    mk = makefiles_text()
    root_runs = {
        line.split(":", 1)[0].split()[0]
        for line in mk.splitlines()
        if ":=" in line and "-u root" in line
    }

    # When  the set is compared to the carved-out pair
    # Then  no other definition runs root (OS_OPTS joined the mapped side)
    assert root_runs == {"ENGINE_TEST_ARGS", "CI_HOME_CLEAN"}

    # And   no mk/*.mk recipe hardcodes a root run around the variables
    for mk_file in (REPO / "mk").glob("*.mk"):
        assert "-u root" not in mk_file.read_text(), mk_file.name
