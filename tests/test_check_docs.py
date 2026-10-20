"""Is every user-facing make target documented in README.md? (issue #257)

AGENTS.md: "Any change that adds, renames, or alters a user-facing feature, `make`
command, target, or workflow MUST be mirrored in `README.md` in the same change" and
"Track progress in `agent-wiki/` as dated `YYYY-MM-DD-<name>.md` entries". Neither was
enforced, so a target could ship and never appear in the README the user reads, and a
work record could reference nothing at all.

The check is real code under test (`scripts/check_docs.py`) and the scratch trees in the
fault tests are real files on disk (a real Makefile, a real README.md, real work records)
— the product parses exactly what it parses in the repo. No stand-in for the logic.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_docs as cd  # noqa: E402
import unit_tests as ut  # noqa: E402  (the unit-suite aggregator, issue #393)

CLI = REPO / "scripts" / "check_docs.py"
README = REPO / "README.md"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    """The real CLI, against a real checkout (the repo by default, a scratch tree in tests)."""
    return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def _tree(tmp_path: Path, makefile: str, readme: str, wiki: dict | None = None,
          exceptions: dict | None = None) -> Path:
    """A real checkout skeleton: a Makefile, a README.md, work records, optional decisions."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "Makefile").write_text(makefile)
    (tmp_path / "README.md").write_text(readme)
    for name, body in (wiki or {}).items():
        (tmp_path / "agent-wiki").mkdir(exist_ok=True)
        (tmp_path / "agent-wiki" / name).write_text(body)
    if exceptions is not None:
        (tmp_path / "tests/fixtures").mkdir(parents=True, exist_ok=True)
        (tmp_path / "tests/fixtures/docs-exceptions.json").write_text(json.dumps(exceptions))
    return tmp_path


# ---------------------------------------------------------------------------
# the real tree
# ---------------------------------------------------------------------------
def test_the_real_tree_documents_every_user_facing_target():
    """Every make target `make help` prints is documented in README.md, and every work
    record references the issue or PR it implements."""

    # Given the real checkout
    info = cd.graph(REPO)

    # When the documentation is checked
    errors = cd.problems(info)

    # Then nothing is missing, nothing is stale, no record is unreferenced
    assert errors == [], errors

    # And the tree it checked is the real one, not a trivially empty one
    assert len(info["targets"]) > 90, len(info["targets"])
    assert len(info["documented"]) == len(info["targets"])
    assert len(info["wiki"]) > 20, len(info["wiki"])


def test_the_report_names_documented_missing_and_work_record_references():
    """`make docs-report` is this: the target census and what each work record cites."""

    # Given the real checkout
    info = cd.graph(REPO)

    # When the report is rendered
    text = cd.report(info)

    # Then it counts the surface and every work record is listed with its references
    assert "user-facing (## help) make targets" in text
    for name in info["wiki"]:
        assert f"agent-wiki/{name}:" in text
    assert "NO issue/PR reference" not in text and "MISSING" not in text

    # And the CLI's checked mode agrees with the library (the CI shape)
    r = _run(REPO, "check")
    assert r.returncode == 0, r.stderr
    assert "documented in README.md" in r.stdout


# ---------------------------------------------------------------------------
# the gate: an undocumented target is loud, documenting it completes the fix
# ---------------------------------------------------------------------------
def test_a_user_facing_target_no_readme_mentions_fails_and_documenting_it_fixes_it(tmp_path):
    """The exact defect: a target ships, `make help` prints it, the README never mentions it."""

    # Given a checkout whose README documents `make install` but not `make lint-fix`
    root = _tree(tmp_path,
                 "install: ## Install everything\n\t@true\nlint-fix: ## Append the missing newline\n\t@true\n",
                 "# llgenie\n\n```\nmake install   # install everything\n```\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it names the target the README never learned about, and only that one
    assert len(problems) == 1, problems
    assert "`make lint-fix` is user-facing" in problems[0]
    assert "install" not in problems[0]

    # And documenting it in the README is the fix
    (root / "README.md").write_text(
        "# llgenie\n\n```\nmake install   # install everything\nmake lint-fix  # append the missing newline\n```\n")
    assert cd.problems(cd.graph(root)) == []


def test_a_documented_target_is_matched_whole_token_and_a_pattern_by_its_stem(tmp_path):
    """`docs-report` does not document `docs`, and `run-engine-%` is documented as its stem."""

    # Given a README that only mentions the LONGER target name, not the shorter one
    root = _tree(tmp_path,
                 "docs: ## Write them\n\t@true\ndocs-report: ## Show them\n\t@true\n",
                 "# llgenie\n\n```\nmake docs-report  # show them\n```\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then the substring decoy is refused: `docs` is still undocumented
    assert any("`make docs` is user-facing" in p for p in problems), problems
    assert not any("`make docs-report`" in p for p in problems), problems

    # And a pattern target is documented by its stem, without the `%`
    stem = _tree(tmp_path / "stem",
                 "run-engine-%: ## Run one engine image\n\t@true\n",
                 "# llgenie\n\n```\nmake run-engine-<engine>-<arch> MODEL=m\n```\n")
    assert cd.problems(cd.graph(stem)) == []


def test_an_omission_is_a_dated_exception_and_that_record_goes_stale(tmp_path):
    """A target may stay out of the README — as a recorded, dated decision that cannot rot."""

    # Given an undocumented user-facing target
    makefile = "internal-only: ## An internal switch\n\t@true\n"
    root = _tree(tmp_path, makefile, "# llgenie\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it fails, naming the target and the decisions file
    assert len(problems) == 1 and "docs-exceptions.json" in problems[0], problems

    # And a reasoned, dated decision records it
    _tree(root, makefile, "# llgenie\n", exceptions={"decided_utc": "2026-10-14", "targets": {
        "internal-only": {"reason": "an agent-only switch, no user-facing behaviour",
                          "decided": "2026-10-14", "issue": 256}}})
    assert cd.problems(cd.graph(root)) == []

    # And once the README documents it, the decision is STALE and must be deleted
    (root / "README.md").write_text("# llgenie\n\n```\nmake internal-only  # an internal switch\n```\n")
    stale = cd.problems(cd.graph(root))
    assert len(stale) == 1 and "STALE" in stale[0], stale

    # And a decision missing its reason/date/issue is refused, never silently accepted
    for missing in ("reason", "decided", "issue"):
        entry = {"reason": "r", "decided": "2026-10-14", "issue": 256}
        entry.pop(missing)
        (root / "README.md").write_text("# llgenie\n")
        (root / "tests/fixtures/docs-exceptions.json").write_text(json.dumps({"targets": {"internal-only": entry}}))
        bad = _run(root, "check")
        assert bad.returncode != 0 and f"lacks {missing!r}" in bad.stderr, bad.stderr


def test_a_work_record_that_references_no_issue_fails(tmp_path):
    """`agent-wiki/` is the record of an implementation — it must name what it implements."""

    # Given a work record that names no issue and no PR
    root = _tree(tmp_path, "install: ## Install\n\t@true\n", "# llgenie\n\n```\nmake install\n```\n",
                 wiki={"2026-10-14-something.md": "# Something\n\nWe changed the pipeline.\n"})

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it fails, naming the record
    assert len(problems) == 1, problems
    assert "2026-10-14-something.md: references no issue or PR" in problems[0]

    # And a reference — an issue number or a PR number — is the fix
    (root / "agent-wiki/2026-10-14-something.md").write_text(
        "# Something\n\nWe changed the pipeline (issue #257, PR #257).\n")
    assert cd.problems(cd.graph(root)) == []


# ---------------------------------------------------------------------------
# the mandate itself is stated, in AGENTS.md and in the README
# ---------------------------------------------------------------------------
def test_agents_md_and_readme_state_the_documentation_mandate():
    """AGENTS.md carries the rule the guard enforces, and the README documents the gate
    (a rule nobody can read is not a rule)."""

    # Given the rulebook and the user-facing doc
    agents = (REPO / "AGENTS.md").read_text()
    readme = (REPO / "README.md").read_text()

    # When the mandate is looked up
    # Then AGENTS.md makes it mandatory, in the same commit, and names the gate
    assert "### Documentation is part of the change" in agents
    assert "MANDATORY, durable" in agents.split("### Documentation is part of the change", 1)[1][:200]
    assert "in the SAME commit" in agents and "make check-docs" in agents
    assert "reference the issue and the PR it implements" in agents

    # And `## Record of work` points at it rather than repeating the old, unguarded wording
    record = agents.split("## Record of work", 1)[1]
    assert "make check-docs" in record and "SAME commit" in record

    # And the README documents the gate the user is expected to run
    assert "### Documentation is part of the change (issue #257)" in readme
    assert "make check-docs" in readme and "make docs-report" in readme


# ---------------------------------------------------------------------------
# the wiring of the guard itself
# ---------------------------------------------------------------------------
def test_the_guard_runs_in_ci_unit_and_this_file_runs_in_test_unit():
    """The guard is only real when the pipeline runs it."""

    # Given the Makefile
    mk = (REPO / "Makefile").read_text()

    # When the ci-unit job and the unit suite are read
    ci_unit = mk.split("\nci-unit:", 1)[1].split("\n\n", 1)[0]

    # Then ci-unit runs the docs check, and this test file is in the discovered unit suite
    assert "$(MAKE) check-docs" in ci_unit
    assert "tests/test_check_docs.py" in ut.select(REPO)
    assert "check-docs:" in mk and "docs-report:" in mk

    # And both targets are declared phony, so a file named `check-docs` cannot shadow them
    phony = mk.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "check-docs" in phony and "docs-report" in phony
