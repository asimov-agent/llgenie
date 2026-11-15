"""`test-published-engine`'s three-step sequence lives in scripts/published_engine.py (#2675).

The 12-line recipe (mk/engines.mk at origin/main@dcfb96b7df) moved into the entry point as a
quoted `MAKE_SEQUENCE` of three make steps; the target recipe became the thin wrapper, and two
internal seam targets (`published-engine-pull`, `published-engine-binary`) keep the
`engine_test` / `ARCH_ARGS` / `CI_HOME` make macros where make expands them. Pinned here:

- the wrapper recipe and the two seam targets' real bodies (pull-published / engine_test-wrapped
  pytest + CI_HOME clean), with NO `##` help lines (internal targets);
- the usage guard the base recipe enforced (`test -n "$(ENGINE)" -a -n "$(ARCH)"`);
- the three steps run in order, each carrying `ENGINE=`/`ARCH=`, first failure short-circuits
  with that step's exit code, through the make binary make sets;
- the sequence is machine-readable from the file, the same seam scripts/issue_bot_gates.py and
  scripts/check_wiring.py use to keep the closure wired (#393 extended to entry points).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from conftest import makefiles_text  # noqa: E402  (include-resolving reader, #2459)
from scripts import issue_bot_gates, published_engine

SEAM_TARGETS = ("published-engine-pull", "published-engine-binary")


def _recipe(target: str) -> str:
    mk = makefiles_text(REPO)
    m = re.search(rf"^{target}:[^\n]*\n((?:[ \t].*\n)*)", mk, re.M)
    assert m, f"{target} target not found in the flattened Makefile"
    return m.group(1)


def test_the_test_published_engine_recipe_is_the_thin_wrapper_of_the_entry_point():
    # Given the flattened Makefile at this head
    tab_lines = [l for l in _recipe("test-published-engine").splitlines() if l.startswith("\t")]
    # Then it is one line, ENGINE/ARCH passed through as arguments
    assert len(tab_lines) == 1, tab_lines
    assert tab_lines[0].strip() == '@python3 scripts/published_engine.py --engine "$(ENGINE)" --arch "$(ARCH)"'


def test_the_seam_targets_keep_the_make_macros_intact_and_stay_internal():
    # Given the two internal targets the entry point calls
    pull = _recipe("published-engine-pull")
    binary = _recipe("published-engine-binary")
    # Then they run the same commands the original recipe ran inline
    assert 'python3 scripts/engine_image.py pull-published "$(ENGINE)" $(ARCH_ARGS)' in pull
    assert "engine_test,LLGENIE_PUBLISHED_PULLED=1" in binary
    assert "tests/test_published_engine_binary.py" in binary
    assert "$(CI_HOME_CLEAN)" in binary
    # And they are internal: no `##` help line, but declared .PHONY in the Makefile
    mk = makefiles_text(REPO)
    for target in SEAM_TARGETS:
        assert not re.search(rf"^{target}: ##", mk, re.M)
    assert "published-engine-pull published-engine-binary" in mk


def test_the_usage_guard_survives_the_move(capsys):
    # Given the entry point called the way the recipe calls it, without ENGINE or ARCH
    rc = published_engine.main([])
    # Then it refuses with the usage line (the base's `test -n ... -a -n ...` gate)
    assert rc == 1
    assert published_engine.USAGE in capsys.readouterr().err


def test_the_three_steps_run_in_order_with_engine_and_arch_carried(monkeypatch):
    # Given a make seam that records every call and succeeds
    calls: list[list[str]] = []
    monkeypatch.setattr(published_engine.subprocess, "call",
                        lambda argv: (calls.append(list(argv)), 0)[1])
    # When the entry point verifies a published engine
    rc = published_engine.main(["--engine", "llama.cpp", "--arch", "cpu"])
    # Then the three steps ran, in order, each through make with ENGINE=/ARCH=
    assert rc == 0
    assert [c[1] for c in calls] == ["published-engine-pull", "test-engine-image",
                                     "published-engine-binary"]
    assert all(c[2] == "ENGINE=llama.cpp" and c[3] == "ARCH=cpu" for c in calls)


def test_a_failing_step_short_circuits_with_its_own_exit_code(monkeypatch):
    # Given the middle step (test-engine-image) failing with rc 4
    seen: list[str] = []

    def fake_call(argv):
        seen.append(argv[1])
        return 4 if argv[1] == "test-engine-image" else 0

    monkeypatch.setattr(published_engine.subprocess, "call", fake_call)
    # When the entry point runs
    rc = published_engine.main(["--engine", "llama.cpp", "--arch", "cuda"])
    # Then it stops there with the step's code and never starts the binary stage
    assert rc == 4
    assert seen == ["published-engine-pull", "test-engine-image"]


def test_the_steps_run_through_the_make_binary_make_sets(monkeypatch):
    # Given MAKE points elsewhere
    monkeypatch.setenv("MAKE", "gmake")
    calls: list[list[str]] = []
    monkeypatch.setattr(published_engine.subprocess, "call", lambda argv: (calls.append(argv), 0)[1])
    published_engine.main(["--engine", "llama.cpp", "--arch", "cpu"])
    # Then every step started with it
    assert all(c[0] == "gmake" for c in calls)


def test_the_sequence_is_machine_readable_by_the_gate_seams():
    # Given the thin wrapper recipe of test-published-engine
    recipe = _recipe("test-published-engine")
    # When the issue-bot-gates entry-point seam reads the sequence out of the script
    embedded = issue_bot_gates._entry_point_sequence(REPO, recipe)
    # Then it recovers exactly the three make steps (same seam check_wiring uses)
    parsed = [
        line.strip().strip('",').removeprefix("make ")
        for line in embedded.splitlines()
        if line.strip()
    ]
    assert parsed == published_engine.sequence_targets() == [
        "published-engine-pull", "test-engine-image", "published-engine-binary"]
