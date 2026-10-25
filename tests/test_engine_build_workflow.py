#!/usr/bin/env python3
"""The dispatched engine-build sweep (issue #614).

ci.yml builds only the images a PR changed. This workflow is the independent whole-set sweep: one
matrix row per engine x variant from the COMMITTED params, built and verified through the same make
targets CI uses, and never triggered by a pull request, a push or a schedule.

These tests lock the parts that make it safe and useful: it exists, it is dispatch-only, it has the
guard before anything else, its matrix comes from `make engine-build-matrix` (never a hand-written
roster), every row is built AND verified, and it publishes only when asked.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "engine-build.yml"
MAKEFILE = (REPO / "Makefile").read_text()
sys.path.insert(0, str(REPO / "scripts"))

import engine_image as ei  # noqa: E402  (the real matrix code, never a copy)


def workflow() -> str:
    assert WORKFLOW.is_file(), "the dispatched engine-build workflow is missing"
    return WORKFLOW.read_text()


def test_it_is_dispatch_only_and_never_runs_on_a_pr_push_or_schedule():
    """A full 27-row sweep belongs to a maintainer asking, not to every pull request."""

    # Given the workflow's trigger block
    text = workflow()
    triggers = text.split("\non:", 1)[1].split("\npermissions:", 1)[0]

    # When  the triggers are read
    # Then  only workflow_dispatch is present
    assert "workflow_dispatch:" in triggers
    # An event key sits at two spaces inside `on:`; the dispatch INPUT named `push` is indented
    # further, so match the event form (`\n  <event>:`) rather than the bare word.
    for forbidden in ("pull_request", "push", "schedule", "cron"):
        assert f"\n  {forbidden}:" not in triggers, f"{forbidden} must not trigger the engine sweep"


def test_it_has_the_guard_before_any_secret_and_documents_itself():
    """Owner/collaborator only, and the header states the contract before you dispatch it."""

    # Given the workflow text
    text = workflow()

    # When  the header, the guard job and the job order are read
    # Then  the contract is stated and the guard is the first job
    for marker in ("# Trigger surface:", "# Flow:", "# Never:"):
        assert marker in text, marker
    jobs = re.findall(r"(?m)^  ([a-z][a-z0-9_-]*):$", text.split("\njobs:", 1)[1])
    assert jobs and jobs[0] == "guard", jobs
    assert "refused" in text.lower() or "Refused:" in text


def test_the_matrix_comes_from_the_committed_params_not_a_roster():
    """`make engine-build-matrix` is the only source of rows; it filters the real params."""

    # Given the workflow's matrix job
    text = workflow()

    # When  its command is read
    # Then  it calls the make target, with the dispatch inputs passed as make variables
    assert "make -s engine-build-matrix" in text
    assert 'ENGINE="$ENGINE"' in text and 'ARCH="$ARCH"' in text

    # And the target itself prints a GitHub matrix from the real matrix() code
    assert "engine-build-matrix:" in MAKEFILE
    out = subprocess.run(["make", "-s", "engine-build-matrix"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    rows = json.loads(out)["include"]
    assert len(rows) >= 20, f"only {len(rows)} rows: the sweep reads nothing"
    assert ei.matrix(ci=True, engine="llama.cpp"), "the filter is not wired to matrix()"


def test_every_row_is_built_and_then_verified():
    """Building without running the image is not a sweep — the row's own test mode is used."""

    text = workflow()

    # Given the build job
    # When  its steps are read
    # Then  each row is built from its params and then tested in ITS mode (serve|detect)
    assert "make build-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in text
    assert "make test-engine-stage ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }} TEST=${{ matrix.test }}" in text
    assert "matrix.engine != 'none'" in text, "the placeholder row must be skipped, not built"
    assert "max-parallel:" in text, "the sweep must fan out in parallel"


def test_it_publishes_only_when_the_dispatch_asks_for_it():
    """A verification sweep must not overwrite GHCR tags unless a human asked to publish."""

    text = workflow()

    # Given the inputs and the publish wiring
    # When  the default and the guard on the push step are read
    # Then  publishing is off by default and gated on the input
    assert 'default: "false"' in text.split("inputs:", 1)[1].split("permissions:", 1)[0]
    assert "PUSH=$PUBLISH" in text
    assert "inputs.push == 'true'" in text


def test_one_make_command_answers_every_build_scope():
    """All engines, one arch, one engine, or one engine x one arch — the same list in each case."""

    # Given the make target the sweep and a maintainer use
    def rows(*args: str) -> list[dict]:
        out = subprocess.run(["make", "-s", "engine-build-matrix", *args], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)["include"]

    # When  each scope is asked for
    every = rows()
    one_arch = rows("ARCH=cpu")
    one_engine = rows("ENGINE=llama.cpp")
    both = rows("ENGINE=llama.cpp", "ARCH=cpu")

    # Then  each is a subset of the previous, and the narrowest is exactly one row
    assert len(every) >= 20 and len(one_arch) < len(every) and len(one_engine) < len(every)
    assert len(both) == 1
    assert both[0]["engine"] == "llama.cpp" and both[0]["variant"] == "cpu"
    assert {r["variant"] for r in one_arch} == {"cpu"}
    assert {r["engine"] for r in one_engine} == {"llama.cpp"}

    # And the local build target takes the same two filters and fans out in parallel
    recipe = MAKEFILE.split("\nbuild-engines:", 1)[1].split("\ngenerate-build-engine-params:", 1)[0]
    assert "--engine" in recipe and "--arch" in recipe
    assert "xargs -r -P" in recipe, "the local build must fan out, not run one row at a time"
