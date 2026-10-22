#!/usr/bin/env python3
"""The Strata download checks are not part of the hermetic unit gate (issue #437).

`make test-unit` is the gate every change runs, so nothing in it may leave the machine.
`tests/test_strata_download.py` does: a session fixture shallow-fetches Strata's pinned commit over git,
another imports that checkout's `setup.py`, a third pip-installs the engine's requirements, and several
cases read the live Hub at Strata's pinned revisions. On 2026-10-21 the macOS runner's
`git fetch --depth 1 https://github.com/Niko1221/Strata <sha>` exited 128 and the gate reported nine
errors (`4889 passed, 3 deselected, 9 errors`) while the tree was fine.

So the file is recorded in the roster's `excluded` (the ONE place a "not hermetic" decision lives, with
its reason, issue, date and owning target) and `make test-strata-live` runs it.

These cases pin both halves, hermetically: the file is out of the gate, the target names it, and the file
still carries the live fetch the decision is about — a rewrite that makes it hermetic has to move the
decision with it.

NO-SKIP POLICY: every case reads the real roster, the real Makefile and the real test file; none is
skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import unit_tests as ut  # noqa: E402  (the aggregator the gate runs)

MAKEFILE = (REPO / "Makefile").read_text()
DOC = "tests/test_strata_download.py"
TARGET = "test-strata-live"


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


def _phony() -> str:
    return MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]


def test_the_strata_download_file_is_out_of_the_hermetic_gate():
    """The file's network work is out of `make test-unit`'s selection."""

    # Given the hermetic selection the gate computes by discovery
    selection = set(ut.select(REPO))

    # When  the Strata download file is looked for
    # Then  it is not there, so no unit run fetches Strata, installs its deps or reads the Hub
    assert DOC not in selection, f"{DOC} is still in the hermetic gate"
    assert DOC in ut.excluded(REPO), f"{DOC} is not recorded in the roster's exclusions"


def test_the_strata_live_target_runs_the_whole_file():
    """One target owns the file, and it names the file (no `-k`, no node-id sweep)."""

    # Given the target that owns the network checks
    body = _target_body(TARGET)

    # When  its pytest invocation is read
    # Then  it runs the file, with the same no-cache discipline as the gate
    assert DOC in body, f"{TARGET} does not run {DOC}"
    assert "-p no:cacheprovider" in body, body
    assert "-k " not in body, body

    # And it is a phony target, so no file can shadow it
    assert TARGET in _phony(), f"{TARGET} must be .PHONY"


def test_the_roster_entry_names_the_issue_and_its_target():
    """The exclusion is a dated decision, tied to this issue and to the target that runs it."""

    # Given the roster entry for the Strata download file
    entry = ut.excluded(REPO)[DOC]

    # When  its fields are read
    # Then  it names the issue, a real reason and the owning target
    assert entry["issue"] == 437, entry
    assert entry["target"] == TARGET, entry
    assert len(entry["reason"]) >= ut.MIN_REASON, entry
    assert f"make {TARGET}" in entry["reason"], entry
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["decided"]), entry


def test_the_file_still_carries_the_fetch_the_decision_names():
    """The exclusion describes THIS file: the live checkout and Hub reads must still be in it."""

    # Given the Strata download test module and the checkout helper it calls
    text = (REPO / DOC).read_text()
    checkout = (REPO / "scripts" / "strata_models.py").read_text()

    # When  its session fixture and its live-Hub cases are read
    # Then  the network work the exclusion names is still there
    assert "sm.checkout(" in text, "the Strata checkout fixture is gone"
    assert re.search(r'"fetch",\s*"-q",\s*"--depth",\s*"1"', checkout), "the pinned-commit fetch is gone"
    assert "ISTA-DASLab/" in text, "the live-Hub repository the file reads is gone"
