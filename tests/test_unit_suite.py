"""The hermetic unit suite is AGGREGATED, never enumerated (issue #393).

`make test-unit` used to name its 74 pytest files by hand on ONE recipe line, so two PRs that
added unrelated tests conflicted on the same line and a name dropped while resolving that
conflict silently stopped running. The suite is now computed by `scripts/unit_tests.py` from the
tree: every `tests/test_*.py` MINUS the dated exclusions in `tests/fixtures/unit-suite.json`.

The check is real code under test (`scripts/unit_tests.py`), and the scratch trees in the fault
tests are real files on disk — a real Makefile, real test files, a real roster — so the product
parses exactly what it parses in the repo. No stand-in for the logic under test.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import unit_tests as ut  # noqa: E402

CLI = REPO / "scripts" / "unit_tests.py"
ROSTER = REPO / "tests" / "fixtures" / "unit-suite.json"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def _tree(tmp_path: Path, makefile: str, tests: dict, roster: dict | None = None) -> Path:
    """A real checkout skeleton: a Makefile, test files, and the roster the aggregator reads."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "Makefile").write_text(makefile)
    for name, body in tests.items():
        (tmp_path / "tests").mkdir(exist_ok=True)
        (tmp_path / "tests" / name).write_text(body)
    if roster is None:
        roster = {"excluded": {}, "deselect": {}}
    (tmp_path / "tests/fixtures").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests/fixtures/unit-suite.json").write_text(json.dumps(roster))
    return tmp_path


def _entry(reason: str = "Needs real hardware and a network the hermetic image does not have.",
           target: str = "test-a", issue: int = 393, decided: str = "2026-10-20") -> dict:
    return {"reason": reason, "issue": issue, "decided": decided, "target": target}


# ---------------------------------------------------------------------------
# discovery: the suite is computed, so a new file needs no Makefile edit
# ---------------------------------------------------------------------------
def test_a_new_test_file_is_selected_without_a_makefile_edit(tmp_path):
    """The defect this change closes: adding a test used to mean editing the one shared line."""

    # Given a checkout whose unit target runs the aggregator and whose tree gains a new test
    makefile = "test-unit: ## x\n\tpython3 scripts/unit_tests.py run\n"
    root = _tree(tmp_path, makefile, {"test_old.py": "def test_old():\n    assert True\n"})
    (root / "tests" / "test_new.py").write_text("def test_new():\n    assert True\n")

    # When the selection is computed
    selection = ut.select(root)

    # Then the new file is in it and the recipe names no test file at all
    assert "tests/test_new.py" in selection
    assert "tests/test_old.py" in selection
    assert "tests/test_new.py" not in makefile

    # And the pytest invocation the aggregator builds carries it
    assert "tests/test_new.py" in ut.argv(root)


def test_every_test_file_in_the_real_tree_is_in_the_suite_or_recorded():
    """A file in neither the selection nor the roster would run in no gate — the defect."""

    # Given the real checkout, its roster and its selection
    excluded = ut.excluded(REPO)
    selection = set(ut.select(REPO))

    # When every test module is accounted for
    # Then each file is either selected or a recorded exclusion — never neither, never both
    for doc in ut.all_tests(REPO):
        assert doc in selection or doc in excluded, f"{doc} is in neither the suite nor the roster"
        assert not (doc in selection and doc in excluded), doc

    # And each exclusion carries the reason, the issue, the date and the target that runs it
    for doc, e in excluded.items():
        for field in ("reason", "issue", "decided", "target"):
            assert e.get(field), f"{doc} lacks {field}"
        assert len(e["reason"]) > 40, doc
        assert f"{e['target']}:" in (REPO / "Makefile").read_text(), doc

    # And the roster's own consistency check reports nothing
    assert ut.check(REPO) == []
    assert ut.load_roster(REPO)["decided_utc"]


def test_the_cli_lists_the_selection_and_the_exclusions():
    """`make test-unit` prints this before pytest runs, so the gate is readable."""

    # Given the real checkout
    # When the CLI lists the selection and the report
    listed = _run(REPO, "list")
    reported = _run(REPO, "report")

    # Then the selection is one path per line and the report names every exclusion's runner
    assert listed.returncode == 0, listed.stderr
    assert "tests/test_wiring.py" in listed.stdout
    assert "tests/test_health.py" not in listed.stdout
    assert reported.returncode == 0, reported.stderr
    for doc, e in ut.excluded(REPO).items():
        assert f"excluded: {doc}" in reported.stdout
        assert f"run: make {e['target']}" in reported.stdout


# ---------------------------------------------------------------------------
# the roster cannot rot: every direction is loud
# ---------------------------------------------------------------------------
def test_a_stale_or_malformed_exclusion_fails_loudly(tmp_path):
    """An exclusion for a file that is gone, or one with no reason, must not be ignored."""

    # Given a roster excluding a file that does not exist, and one with no reason
    makefile = "test-a: ## x\n\tpython3 -m pytest tests/test_b.py\n"
    tests = {"test_b.py": "def test_b():\n    assert True\n"}
    root = _tree(tmp_path, makefile, tests, {"excluded": {"tests/test_gone.py": _entry()},
                                             "deselect": {}})

    # When the roster is checked
    r = _run(root, "check")

    # Then it exits non-zero and names the stale entry
    assert r.returncode == 1, r.stdout
    assert "tests/test_gone.py" in r.stderr and "does not exist" in r.stderr

    # And an entry with no reason is refused, naming the field
    root2 = _tree(tmp_path / "b", makefile, tests,
                  {"excluded": {"tests/test_b.py": {"target": "test-a"}}, "deselect": {}})
    r2 = _run(root2, "check")
    assert r2.returncode == 1
    for field in ("reason", "issue", "decided"):
        assert field in r2.stderr


def test_an_exclusion_naming_a_target_that_does_not_run_it_fails(tmp_path):
    """The roster cannot claim a runner that does not run the file."""

    # Given an exclusion naming a target the Makefile does not define
    makefile = "test-a: ## x\n\tpython3 -m pytest tests/test_b.py\n"
    tests = {"test_b.py": "def test_b():\n    assert True\n"}
    root = _tree(tmp_path, makefile, tests,
                 {"excluded": {"tests/test_b.py": _entry(target="no-such-target")}, "deselect": {}})

    # When the roster is checked
    r = _run(root, "check")

    # Then it names the target that does not exist
    assert r.returncode == 1, r.stdout
    assert "no-such-target" in r.stderr and "not a make target" in r.stderr

    # And a target that exists but whose recipe does not name the file fails the same way
    makefile2 = "test-a: ## x\n\tpython3 -m pytest tests/test_c.py\n"
    root2 = _tree(tmp_path / "b", makefile2, {**tests, "test_c.py": "def test_c():\n    assert True\n"},
                  {"excluded": {"tests/test_b.py": _entry(target="test-a")}, "deselect": {}})
    r2 = _run(root2, "check")
    assert r2.returncode == 1
    assert "tests/test_b.py" in r2.stderr and "test-a" in r2.stderr

    # And the script hop counts as running it: `make test-engine` -> engine_smoke.py -> the test
    makefile3 = "test-engine: ## x\n\tpython3 scripts/engine_smoke.py --image\n"
    root3 = _tree(tmp_path / "c", makefile3,
                  {"test_b.py": "def test_b():\n    assert True\n",
                   "test_c.py": "def test_c():\n    assert True\n"},
                  {"excluded": {"tests/test_b.py": _entry(target="test-engine")}, "deselect": {}})
    (root3 / "scripts").mkdir(exist_ok=True)
    (root3 / "scripts" / "engine_smoke.py").write_text(
        'SUITE = ["tests/test_b.py"]\n')
    r3 = _run(root3, "check")
    assert r3.returncode == 0, r3.stderr


def test_a_deselection_of_a_gone_test_fails_and_run_refuses_to_start(tmp_path):
    """A deselected node id no longer defined would silently shrink nothing — but the record lies."""

    # Given a roster deselecting a test the file does not define
    makefile = "test-unit: ## x\n\tpython3 scripts/unit_tests.py run\n"
    tests = {"test_b.py": "def test_b():\n    assert True\n"}
    roster = {"excluded": {}, "deselect": {"tests/test_b.py": {"test_gone": "No longer hermetic; "
              "the live runner is make test-engine-bump-live."}}}
    root = _tree(tmp_path, makefile, tests, roster)

    # When the roster is checked, and when `run` is asked to start the gate
    r, run = _run(root, "check"), _run(root, "run")

    # Then both refuse, naming the node id
    assert r.returncode == 1 and "test_gone" in r.stderr
    assert run.returncode == 2 and "refusing to start pytest" in run.stderr


# ---------------------------------------------------------------------------
# the invocation: exact node ids, never a `-k` substring
# ---------------------------------------------------------------------------
def test_the_invocation_deselects_by_node_id_and_never_by_k():
    """`-k` matches substrings, so a new test whose name contains a deselected name would be dropped."""

    # Given the real roster's deselections and the invocation the gate runs
    nodes = ut.deselected(REPO)
    args = ut.argv(REPO)

    # When the invocation is read
    # Then every deselection is an exact node id, and `-k` appears nowhere
    assert nodes, "the roster de-selects nothing, so this cannot prove the node-id rule"
    for node in nodes:
        assert node in args, node
        assert args[args.index(node) - 1] == "--deselect", node
        assert "::" in node, node
    assert "-k" not in args

    # And the deselections really are tests in the files they name
    for node in nodes:
        doc, _, name = node.partition("::")
        assert doc in ut.select(REPO), doc
        assert f"def {name}(" in (REPO / doc).read_text(), node


# ---------------------------------------------------------------------------
# the seam: the wiring guard sees what the aggregator selects
# ---------------------------------------------------------------------------
def test_the_wiring_guard_sees_the_aggregator_selection():
    """A discovered file runs in `make test-unit` though the recipe never names it."""

    # Given the real checkout
    import check_wiring as cw  # noqa: E402  (imported here: the seam lives in that module)

    graph = cw.graph(REPO)

    # When the wiring graph is read
    # Then the discovery seam is present and attributes the selection to the unit target
    assert "test-unit" in graph["aggregated"], sorted(graph["aggregated"])
    selection = graph["aggregated"]["test-unit"]
    assert "tests/test_unit_suite.py" in selection

    # And each selected document is reachable through the target that runs the aggregator
    for doc in selection:
        assert any("test-unit" in w for w in graph["ci_reachable"][doc]), (doc, graph["ci_reachable"][doc])

    # And the guard's own check passes on the real tree
    assert cw.check(graph, cw.load_exceptions(REPO / cw.EXCEPTIONS)) == []
