"""Is every test/script wired to the Makefile — and does CI actually run it? (issue #237)

AGENTS.md: "All verification — locally and in CI — MUST run through the Makefile" and
"A new test file is invisible until a make target names it". Nothing enforced either, so
`tests/test_engine_bump_build.py` existed, was named by no target, and ran in NO gate —
it read as coverage while proving nothing.

The check is real code under test (`scripts/check_wiring.py`): the graph of targets,
prerequisites, workflow steps and python dependencies. The scratch trees in the fault
tests are real files on disk (a real Makefile, real workflows, real test files) — the
product parses exactly what it parses in the repo, and the production code still builds
the report. No stand-in for the logic under test.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_wiring as cw  # noqa: E402
import unit_tests as ut  # noqa: E402  (the unit-suite aggregator, issue #393)

CLI = REPO / "scripts" / "check_wiring.py"
EXCEPTIONS = REPO / "tests" / "fixtures" / "host-only-wiring.json"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def _tree(tmp_path: Path, makefile: str, tests: dict, workflows: dict | None = None,
          exceptions: dict | None = None) -> Path:
    """A real checkout skeleton: a Makefile, test files, workflows, optional decisions."""
    (tmp_path / "Makefile").write_text(makefile)
    for name, body in tests.items():
        (tmp_path / "tests").mkdir(exist_ok=True)
        (tmp_path / "tests" / name).write_text(body)
    for name, body in (workflows or {}).items():
        (tmp_path / ".github/workflows").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".github/workflows" / name).write_text(body)
    if exceptions is not None:
        (tmp_path / "tests/fixtures").mkdir(parents=True, exist_ok=True)
        (tmp_path / "tests/fixtures/host-only-wiring.json").write_text(json.dumps(exceptions))
    return tmp_path


# ---------------------------------------------------------------------------
# the real tree
# ---------------------------------------------------------------------------
def test_the_real_tree_has_no_unwired_document():
    """Every test and script in the repo is reachable from a make target, and any document
    only a target CI never runs is a dated decision in tests/fixtures/host-only-wiring.json."""

    # Given the real checkout
    graph = cw.graph(REPO)
    exceptions = cw.load_exceptions(EXCEPTIONS)

    # When the wiring is checked
    errors = cw.check(graph, exceptions)

    # Then nothing is unwired, nothing is stale, and every workflow target exists
    assert errors == [], errors
    assert len(graph["docs"]) > 80, len(graph["docs"])

    # And every document is either reached by the CI workflows or recorded as host-only
    recorded = set(exceptions["documents"])
    for doc in graph["docs"]:
        assert graph["ci_reachable"][doc] or doc in recorded, doc
        assert not (graph["ci_reachable"][doc] and doc in recorded), doc

    # And each recorded decision carries the reason and the target a human runs
    for doc, e in exceptions["documents"].items():
        assert doc.startswith("tests/") and (REPO / doc).exists(), doc
        assert len(e["reason"]) > 40 and e["decided"] and e["target"], doc
        assert f"{e['target']}:" in (REPO / "Makefile").read_text(), doc


def test_the_report_names_every_document_and_the_host_only_decisions():
    """`make wiring-report` is this: how each document is wired, and what is host-only."""

    # Given the real checkout
    graph, exceptions = cw.graph(REPO), cw.load_exceptions(EXCEPTIONS)

    # When the report is rendered
    text = cw.report(graph, exceptions)

    # Then it counts the tree and lists every recorded host-only document with its target
    assert "run in CI" in text and "host-only" in text
    for doc, e in exceptions["documents"].items():
        assert f"host-only: {doc}" in text and f"(run: make {e['target']})" in text
    assert "UNWIRED" not in text and "NOT IN CI" not in text


# ---------------------------------------------------------------------------
# the gate: an unwired file is loud, naming it completes the fix
# ---------------------------------------------------------------------------
def test_a_new_test_file_no_target_names_fails_and_naming_it_fixes_it(tmp_path):
    """The exact defect the repo had: a test file in the tree that no gate runs."""

    # Given a checkout whose test-unit names only tests/test_a.py
    root = _tree(tmp_path,
                 ".PHONY: test-unit\ntest-unit: ## x\n\tpython3 -m pytest tests/test_a.py\n",
                 {"test_a.py": "def test_a():\n    assert True\n",
                  "test_b.py": "def test_b():\n    assert True\n"},
                 {"ci.yml": "jobs:\n  unit:\n    steps:\n      - run: make test-unit\n"})

    # When the wiring is checked
    r = _run(root, "check")

    # Then it exits 1 and names the file that runs nowhere
    assert r.returncode == 1, r.stdout
    assert "tests/test_b.py is wired to nothing" in r.stderr
    assert "tests/test_a.py" not in r.stderr

    # And naming it in the target the CI job runs is the fix
    (root / "Makefile").write_text(".PHONY: test-unit\ntest-unit: ## x\n\tpython3 -m pytest tests/test_a.py tests/test_b.py\n")
    ok = _run(root, "check")
    assert ok.returncode == 0, ok.stderr


def test_a_target_ci_never_runs_needs_a_dated_decision_and_goes_stale(tmp_path):
    """A host-only check is allowed — as a recorded decision, and it must not rot."""

    # Given a test only a target CI never calls
    makefile = ".PHONY: host-only\nhost-only: ## x\n\tpython3 -m pytest tests/test_h.py\n"
    root = _tree(tmp_path, makefile, {"test_h.py": "def test_h():\n    assert True\n"})

    # When the wiring is checked
    r = _run(root, "check")

    # Then it fails, naming the host-only situation and the decisions file
    assert r.returncode == 1
    assert "reachable only by a target CI never runs" in r.stderr and "host-only-wiring.json" in r.stderr

    # And a reasoned, dated decision records it
    _tree(root, makefile, {}, exceptions={"documents": {
        "tests/test_h.py": {"reason": "needs a Metal GPU that no CI runner has",
                            "target": "host-only", "decided": "2026-10-14"}}})
    assert _run(root, "check").returncode == 0

    # And once CI runs that target, the decision is stale and must be deleted
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (root / ".github/workflows/ci.yml").write_text("jobs:\n  h:\n    steps:\n      - run: make host-only\n")
    stale = _run(root, "check")
    assert stale.returncode == 1
    assert "runs in CI now" in stale.stderr

    # And a decision missing its reason is refused, never silently accepted
    (root / "tests/fixtures/host-only-wiring.json").write_text(json.dumps(
        {"documents": {"tests/test_h.py": {"target": "host-only", "decided": "2026-10-14"}}}))
    bad = _run(root, "check")
    assert bad.returncode != 0 and "lacks reason" in bad.stderr


def test_a_target_whose_help_line_claims_ci_coverage_is_guarded(tmp_path):
    """Issue #239: the other half of the lie. A help line that says CI runs this target, while no
    CI job reaches it, is read by a human at `make help` time and believed."""

    # Given a target that says CI runs it, and a workflow that does not
    makefile = ".PHONY: claims other\nclaims: ## CI job nothing: fail when the guard is asleep\n\techo hi\n"
    root = _tree(tmp_path, makefile, {}, {"ci.yml": "jobs:\n  x:\n    steps:\n      - run: make other\n"})
    (root / "Makefile").write_text(makefile + "other:\n\techo other\n")

    # When the wiring is checked
    r = _run(root, "check")

    # Then the claim is an error, and it names the file a decision goes in
    assert r.returncode == 1, r.stdout + r.stderr
    assert "claims CI coverage" in r.stderr and "host-only-wiring.json" in r.stderr

    # And a reasonless decision is refused, not accepted
    _tree(root, makefile + "other:\n\techo other\n", {},
          {"ci.yml": "jobs:\n  x:\n    steps:\n      - run: make other\n"},
          exceptions={"documents": {}, "targets": {"claims": {"reason": "not wired on purpose"}}})
    bad = _run(root, "check")
    assert bad.returncode != 0 and "lacks decided" in (bad.stdout + bad.stderr)

    # And a reasoned, dated decision settles it
    _tree(root, makefile + "other:\n\techo other\n", {},
          {"ci.yml": "jobs:\n  x:\n    steps:\n      - run: make other\n"},
          exceptions={"documents": {}, "targets": {
              "claims": {"reason": "runs in the host's loop only", "decided": "2026-10-15"}}})
    assert _run(root, "check").returncode == 0

    # And wiring it settles it too - with no decision to rot
    (root / ".github/workflows/ci.yml").write_text("jobs:\n  x:\n    steps:\n      - run: make claims\n")
    (root / "tests/fixtures/host-only-wiring.json").write_text(json.dumps({"documents": {}}))
    assert _run(root, "check").returncode == 0

    # And once CI reaches it, a leftover decision is stale and must be deleted
    (root / "tests/fixtures/host-only-wiring.json").write_text(json.dumps(
        {"documents": {}, "targets": {"claims": {"reason": "x", "decided": "2026-10-15"}}}))
    stale = _run(root, "check")
    assert stale.returncode == 1 and "reached by CI now" in (stale.stdout + stale.stderr)


def test_a_workflow_that_calls_a_missing_make_target_fails(tmp_path):
    """A typo in a `run:` block is an error, not a silent no-op."""

    # Given a workflow calling a target that does not exist
    root = _tree(tmp_path, ".PHONY: test-unit\ntest-unit: ## x\n\tpython3 -m pytest tests/test_a.py\n",
                 {"test_a.py": "def test_a():\n    assert True\n"},
                 {"ci.yml": "jobs:\n  unit:\n    steps:\n      - run: make ci-unti\n"})

    # When the wiring is checked
    r = _run(root, "check")

    # Then it names the typo
    assert r.returncode == 1
    assert "ci.yml calls `make ci-unti`" in r.stderr


# ---------------------------------------------------------------------------
# the .PHONY rule (issue #392): a file with a target's name makes it a green no-op
# ---------------------------------------------------------------------------
def test_an_undeclared_target_runs_nothing_and_the_guard_catches_it(tmp_path):
    """The hazard is real `make` behaviour, and the guard names it."""

    # Given a checkout whose target is NOT declared .PHONY, and a file carrying its name
    body = "test-unit: ## x\n\t@echo RAN-RECIPE\n\tpython3 -m pytest tests/test_a.py\n"
    root = _tree(tmp_path, body, {"test_a.py": "def test_a():\n    assert True\n"},
                 {"ci.yml": "jobs:\n  unit:\n    steps:\n      - run: make test-unit\n"})
    (root / "test-unit").write_text("a scratch file, left behind\n")

    # When the real make runs that target
    run = subprocess.run(["make", "-C", str(root), "test-unit"], capture_output=True, text=True)

    # Then it runs NOTHING and reports success — the green no-op the rule exists for
    assert run.returncode == 0, run.stdout + run.stderr
    assert "up to date" in run.stdout + run.stderr and "RAN-RECIPE" not in run.stdout, run.stdout

    # And the guard is loud about it, naming the target
    r = _run(root, "check")
    assert r.returncode == 1, r.stdout
    assert "`make test-unit` is not declared .PHONY" in r.stderr and "'test-unit'" in r.stderr

    # And declaring it .PHONY fixes both: the recipe runs, and the guard is clean
    (root / "Makefile").write_text(".PHONY: test-unit\n" + body)
    run2 = subprocess.run(["make", "-C", str(root), "test-unit"], capture_output=True, text=True)
    assert run2.returncode == 0 and "RAN-RECIPE" in run2.stdout, run2.stdout
    assert _run(root, "check").returncode == 0


def test_a_target_that_produces_a_file_of_its_name_is_recorded_not_phony(tmp_path):
    """A stamp-style target (a real file of its own name) is exempt — as a dated decision."""

    # Given a target whose recipe writes a file with the target's own name, and no .PHONY
    body = "build-stamp:\n\ttouch build-stamp\n"
    root = _tree(tmp_path, body, {}, {"ci.yml": "jobs:\n  x:\n    steps:\n      - run: make build-stamp\n"})

    # When the wiring is checked
    r = _run(root, "check")

    # Then the undeclared target is reported, with the decisions file as the way out
    assert r.returncode == 1 and "`make build-stamp` is not declared .PHONY" in r.stderr

    # And a reasoned, dated "not_phony" decision exempts it
    _tree(root, body, {}, {"ci.yml": "jobs:\n  x:\n    steps:\n      - run: make build-stamp\n"},
          exceptions={"documents": {}, "targets": {},
                      "not_phony": {"build-stamp": {"reason": "the recipe writes build-stamp itself",
                                                    "decided": "2026-10-20"}}})
    assert _run(root, "check").returncode == 0

    # And a decision for a target that no longer exists is stale too
    (root / "tests/fixtures/host-only-wiring.json").write_text(json.dumps(
        {"documents": {}, "not_phony": {"gone-stamp": {"reason": "x", "decided": "2026-10-20"}}}))
    gone = _run(root, "check")
    assert gone.returncode == 1 and "is not a make target" in gone.stderr

    # And once the target IS declared .PHONY, the decision is stale and must be deleted
    (root / "Makefile").write_text(".PHONY: build-stamp\n" + body)
    (root / "tests/fixtures/host-only-wiring.json").write_text(json.dumps(
        {"documents": {}, "not_phony": {"build-stamp": {"reason": "the recipe writes build-stamp itself",
                                                         "decided": "2026-10-20"}}}))
    stale = _run(root, "check")
    assert stale.returncode == 1 and "delete the not_phony entry" in stale.stderr

    # And a decision without a reason is refused, never silently accepted
    (root / "tests/fixtures/host-only-wiring.json").write_text(json.dumps(
        {"documents": {}, "not_phony": {"build-stamp": {"decided": "2026-10-20"}}}))
    bad = _run(root, "check")
    assert bad.returncode != 0 and "lacks reason" in bad.stderr


def test_the_real_tree_declares_every_target_phony():
    """The repo itself obeys the rule, and the roster is derived — never a hand list."""

    # Given the real checkout's wiring graph and its dated decisions
    g = cw.graph(REPO)
    exceptions = cw.load_exceptions(EXCEPTIONS)

    # When  the .PHONY rule is applied
    errors = [e for e in cw.check(g, exceptions) if "is not declared .PHONY" in e]

    # Then  no target is undeclared, and the phony set covers every parsed target
    assert errors == [], "\n".join(errors)
    assert not set(g["recipes"]) - set(g["phony"]), sorted(set(g["recipes"]) - set(g["phony"]))
    # And the rule is not vacuous: the tree has real targets and a real declaration block
    assert len(g["recipes"]) >= 150 and len(g["phony"]) >= 150, (len(g["recipes"]), len(g["phony"]))


# ---------------------------------------------------------------------------
# the wiring of the guard itself
# ---------------------------------------------------------------------------
def test_the_guard_runs_in_ci_unit_and_this_file_runs_in_test_unit():
    """The guard is only real when the pipeline runs it."""

    # Given the Makefile
    mk = (REPO / "Makefile").read_text()

    # When the ci-unit job and the unit suite are read
    # Then ci-unit runs the wiring check, and this test file is in the discovered suite
    assert "$(MAKE) check-wiring" in mk.split("\nci-unit:", 1)[1].split("\n\n", 1)[0]
    assert "tests/test_wiring.py" in ut.select(REPO)
    assert "check-wiring:" in mk and "wiring-report:" in mk

    # And the removed dead test file is gone for good
    assert not (REPO / "tests" / "test_engine_bump_build.py").exists()
