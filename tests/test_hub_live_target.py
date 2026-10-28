#!/usr/bin/env python3
"""The hermetic unit gate carries no live-Hub work (issue #438).

`make test-unit` is the gate every change runs. Three of its tests left the machine: two answer every link in the README's trend table and
in the vendored registry, the third downloads a model's full GGUF from the Hub. On 2026-10-21 a
run sat inside the download for five minutes while pytest's `faulthandler_timeout` printed a stack dump
— and the run still reported `4911 passed`, because a dump is not a verdict. Minutes later the link test
went red on a Hub `429 Too Many Requests` while the tree was fine.

So the live checks live in their own target (the roster's `deselect` is where a decision like that is
recorded, never a `-k` expression), and the gate stays hermetic. These cases pin both halves: the node
ids are de-selected from the gate, and `make test-hub-live` names exactly them.

NO-SKIP POLICY: every case reads the real roster and the real recipe; none is skipped.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import unit_tests as ut

MAKEFILE = (REPO / "Makefile").read_text()

LIVE_NODES = (
    "tests/test_trend_pick.py::test_the_vendored_registry_links_all_answer",
    "tests/test_trend_pick.py::test_readme_links_answer_and_a_broken_copy_is_caught",
    "tests/test_trend_pick.py::test_select_downloads_a_missing_model_for_real",
)


def _target_body(name: str) -> str:
    lines = MAKEFILE.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
    body = []
    for line in lines[start + 1:]:
        if line.startswith("\t"):
            body.append(line)
        elif line.startswith("#") or not line.strip():
            continue
        else:
            break
    return "\n".join(body)


def test_the_live_hub_tests_are_out_of_the_hermetic_gate():
    """Both live checks are de-selected from `make test-unit`, by exact node id."""

    # Given the roster's de-selections, as the gate computes them
    deselected = set(ut.deselected(REPO))

    # When  the live-Hub node ids are looked for
    missing = [node for node in LIVE_NODES if node not in deselected]

    # Then  every one of them is out of the hermetic suite
    assert missing == [], f"still in the hermetic gate: {missing}"


def test_the_hub_live_target_runs_exactly_those_nodes():
    """One target owns the live checks, and it names them (no `-k`, no whole-file sweep)."""

    # Given the target that owns the network checks
    body = _target_body("test-hub-live")

    # When  its pytest invocation is read
    # Then  it runs exactly the two node ids, with the same no-cache discipline as the gate
    for node in LIVE_NODES:
        assert node in body, f"{node} is not run by test-hub-live"
    assert "-p no:cacheprovider" in body, body
    assert "-k " not in body, body

    # And it is a phony target, so no file can shadow it
    phony = MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "test-hub-live" in phony, "test-hub-live must be .PHONY"


def test_every_deselection_names_a_test_that_really_exists():
    """A de-selection of a renamed or deleted test would silently keep shrinking the gate."""

    # Given every `deselect` entry in the real roster
    roster = ut.load_roster(REPO)["deselect"]

    # When  each one is looked for in the file it names
    missing = []
    for path, tests in roster.items():
        text = (REPO / path).read_text()
        for name in tests:
            if not re.search(rf"(?m)^def {re.escape(name)}\(", text):
                missing.append(f"{path}::{name}")

    # Then  every de-selected test is still defined, and every reason names its owning target
    assert missing == [], f"de-selected but no longer defined: {missing}"
    for path, tests in roster.items():
        for name, why in tests.items():
            assert "make test-" in why or "`make test" in why, (path, name, why)


def test_the_network_tests_still_exist_and_are_the_ones_named():
    """The de-selection is about THESE tests: renaming one must move the decision with it."""

    # Given the trend-pick module the roster names
    text = (REPO / "tests" / "test_trend_pick.py").read_text()

    # When  the two live checks are looked for
    # Then  they are still there, defined exactly as the roster and the target name them
    for node in LIVE_NODES:
        name = node.split("::", 1)[1]
        assert re.search(rf"(?m)^def {re.escape(name)}\(", text), node
