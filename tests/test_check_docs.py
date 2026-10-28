"""Is every user-facing make target documented, and is the README a user guide? (issues #257, #678)

AGENTS.md: a change is recorded as its own dated note in `agent-wiki/`, indexed in `CHANGES.md`,
in the same commit; a user-facing make target must be documented in the README or a `docs/` page it
links; and `README.md` is the user guide, never an appended change log. None of it was enforced, so
a target could ship undocumented and every landed change could append another issue-numbered
section to the README until it was 2,600 lines of work record (issue #678).

The check is real code under test (`scripts/check_docs.py`) and the scratch trees in the fault
tests are real files on disk (a real Makefile, a real README.md, a real CHANGES.md, real work
records, real `docs/` pages) — the product parses exactly what it parses in the repo. No stand-in
for the logic.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import check_docs as cd
from scripts import unit_tests as ut

CLI = REPO / "scripts" / "check_docs.py"
README = REPO / "README.md"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    """The real CLI, against a real checkout (the repo by default, a scratch tree in tests)."""
    return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def _tree(tmp_path: Path, makefile: str, readme: str, wiki: dict | None = None,
          exceptions: dict | None = None, changes: str | None = None,
          docs: dict | None = None, link_changes: bool = True,
          fragments: dict | None = None) -> Path:
    """A real checkout skeleton: a Makefile, a README.md, an index, work records, docs pages.

    The index is one row per file under `docs/changes.d/` (issue #934): `fragments` defaults to one
    well-formed row per wiki note, so a fault test fails for exactly the thing it breaks. `changes`
    is the rendered/committed `CHANGES.md`; both can be overridden to test the index itself.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "Makefile").write_text(makefile)
    text = readme if (not link_changes or "CHANGES.md" in readme) else readme + "\n[changes](CHANGES.md)\n"
    (tmp_path / "README.md").write_text(text)
    for name, body in (wiki or {}).items():
        (tmp_path / "agent-wiki").mkdir(exist_ok=True)
        (tmp_path / "agent-wiki" / name).write_text(body)
    if fragments is None:
        fragments = {name[:-3] if name.endswith(".md") else name: None for name in (wiki or {})}
    (tmp_path / cd.FRAGMENTS).mkdir(parents=True, exist_ok=True)
    for stem, row in fragments.items():
        if row is None:
            row = f"| 2026-10-14 | change | [{stem}.md](agent-wiki/{stem}.md) | #257 |"
        (tmp_path / cd.FRAGMENTS / f"{stem}.md").write_text(row if row.endswith("\n") else row + "\n")
    for rel, body in (docs or {}).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    if changes is None:
        rows = "\n".join(f"| 2026-10-14 | change | [n](agent-wiki/{name[:-3]}.md) | #257 |"
                         for name in (wiki or {}))
        changes = "# Changes\n\n| Date | Change | Record | Issue / PR |\n|---|---|---|---|\n" + rows + "\n"
    (tmp_path / "CHANGES.md").write_text(changes)
    if exceptions is not None:
        (tmp_path / "tests/fixtures").mkdir(parents=True, exist_ok=True)
        (tmp_path / "tests/fixtures/docs-exceptions.json").write_text(json.dumps(exceptions))
    return tmp_path


# ---------------------------------------------------------------------------
# the real tree
# ---------------------------------------------------------------------------
def test_the_real_tree_documents_every_user_facing_target():
    """Every make target `make help` prints is documented in the README or a docs page it links,
    and every work record references the issue or PR it implements and is indexed in CHANGES.md."""

    # Given the real checkout
    info = cd.graph(REPO)

    # When the documentation is checked
    errors = cd.problems(info)

    # Then nothing is missing, nothing is stale, no record is unreferenced and every note is indexed
    assert errors == [], errors

    # And the tree it checked is the real one: the user guide plus the reference docs it links
    assert len(info["targets"]) > 90, len(info["targets"])
    assert len(info["documented"]) == len(info["targets"])
    assert len(info["wiki"]) > 20, len(info["wiki"])
    assert set(info["fragments"]) == set(info["wiki"]), "every note has exactly one index row"
    assert set(info["changes_links"]) == {stem + ".md" for stem in info["wiki"]}, \
        "the rendered CHANGES.md links every note once"
    assert "docs/BOTS.md" in info["surface"], info["surface"]
    assert info["change_headings"] == [], info["change_headings"]


def test_the_report_names_documented_missing_work_records_and_the_index():
    """`make docs-report` is this: the target census, what each note cites, and its index state."""

    # Given the real checkout
    info = cd.graph(REPO)

    # When the report is rendered
    text = cd.report(info)

    # Then it counts the surface, and every work record is listed with its references and index row
    assert "user-facing (## help) make targets" in text
    for name in info["wiki"]:
        assert f"agent-wiki/{name}.md:" in text
    assert "NO issue/PR reference" not in text and "MISSING" not in text and "NOT INDEXED" not in text
    assert f"docs/changes.d: {len(info['fragments'])} index row(s)" in text and "CHANGES.md:" in text

    # And the CLI's checked mode agrees with the library (the CI shape)
    r = _run(REPO, "check")
    assert r.returncode == 0, r.stderr
    assert "own index row in docs/changes.d" in r.stdout


# ---------------------------------------------------------------------------
# the gate: an undocumented target is loud, documenting it completes the fix
# ---------------------------------------------------------------------------
def test_a_user_facing_target_no_doc_mentions_fails_and_documenting_it_fixes_it(tmp_path):
    """The exact defect: a target ships, `make help` prints it, no document mentions it."""

    # Given a checkout whose README documents `make install` but not `make lint-fix`
    root = _tree(tmp_path,
                 "install: ## Install everything\n\t@true\nlint-fix: ## Append the missing newline\n\t@true\n",
                 "# llgenie\n\n```\nmake install   # install everything\n```\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it names the target no doc learned about, and only that one
    assert len(problems) == 1, problems
    assert "`make lint-fix` is user-facing" in problems[0]
    assert "install" not in problems[0]

    # And documenting it in the README is the fix
    (root / "README.md").write_text(
        "# llgenie\n\n[changes](CHANGES.md)\n\n```\nmake install   # install everything\n"
        "make lint-fix  # append the missing newline\n```\n")
    assert cd.problems(cd.graph(root)) == []


def test_an_automation_target_is_documented_in_a_docs_page_the_readme_links(tmp_path):
    """A bot/CI target belongs in `docs/BOTS.md`, not the user guide — and it counts as documented."""

    # Given a README that links a docs page, and a target documented only on that page
    root = _tree(tmp_path,
                 "fix-bot-sweep: ## Repair the PR the bot owns\n\t@true\n",
                 "# llgenie\n\n[changes](CHANGES.md)\n\nSee [the bots](docs/BOTS.md).\n",
                 docs={"docs/BOTS.md": "# Bots\n\n`make fix-bot-sweep` repairs a PR.\n"})

    # When the documentation is checked
    assert cd.problems(cd.graph(root)) == []

    # And a docs page the README does NOT link does not document anything
    (root / "README.md").write_text("# llgenie\n\n[changes](CHANGES.md)\n")
    problems = cd.problems(cd.graph(root))
    assert len(problems) == 1 and "`make fix-bot-sweep` is user-facing" in problems[0], problems


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
    """A target may be documented nowhere — as a recorded, dated decision that cannot rot."""

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

    # And once a document describes it, the decision is STALE and must be deleted
    (root / "README.md").write_text("# llgenie\n\n[changes](CHANGES.md)\n\n```\nmake internal-only  # an internal switch\n```\n")
    stale = cd.problems(cd.graph(root))
    assert len(stale) == 1 and "STALE" in stale[0], stale

    # And a decision missing its reason/date/issue is refused, never silently accepted
    for missing in ("reason", "decided", "issue"):
        entry = {"reason": "r", "decided": "2026-10-14", "issue": 256}
        entry.pop(missing)
        (root / "README.md").write_text("# llgenie\n\n[changes](CHANGES.md)\n")
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
# the change record: one note per change, indexed — never appended to the README
# ---------------------------------------------------------------------------
def test_a_note_with_no_index_row_fails_and_its_own_row_file_fixes_it(tmp_path):
    """A change's record is only findable when its own index row exists (issue #934)."""

    # Given a real note whose index row does not exist
    root = _tree(tmp_path, "install: ## Install\n\t@true\n", "# llgenie\n\n```\nmake install\n```\n",
                 wiki={"2026-10-14-change.md": "# Change\n\nIssue #257.\n"},
                 fragments={}, changes="# Changes\n\n| Date | Change | Record | Issue / PR |\n|---|---|---|---|\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it names the row the change owes, and the note is otherwise well-formed
    assert len(problems) == 1, problems
    assert "2026-10-14-change.md: is not indexed" in problems[0]
    assert "docs/changes.d/2026-10-14-change.md" in problems[0]
    assert _run(root, "check").returncode != 0

    # And the fix is the change's OWN row file — a file no other change can conflict with
    (root / "docs/changes.d/2026-10-14-change.md").write_text(
        "| 2026-10-14 | change | [2026-10-14-change.md](agent-wiki/2026-10-14-change.md) | #257 |\n")
    assert cd.problems(cd.graph(root)) == []
    assert _run(root, "check").returncode == 0


def test_deleting_the_note_a_row_indexes_fails_naming_the_note(tmp_path):
    """The index cannot invent history: a row whose note is gone is a defect, and it is loud."""

    # Given a note and its one-row index file
    note = "# Change\n\nIssue #257.\n"
    root = _tree(tmp_path, "install: ## Install\n\t@true\n", "# llgenie\n\n```\nmake install\n```\n",
                 wiki={"2026-10-14-change.md": note},
                 changes="# Changes\n\n| Date | Change | Record | Issue / PR |\n|---|---|---|---|\n")
    assert cd.problems(cd.graph(root)) == []

    # When the note is deleted and its row survives
    (root / "agent-wiki/2026-10-14-change.md").unlink()

    # Then the gate is RED, naming the row and the note that does not exist
    problems = cd.problems(cd.graph(root))
    assert len(problems) == 1, problems
    assert "docs/changes.d/2026-10-14-change.md: links agent-wiki/2026-10-14-change.md, " \
           "which does not exist" in problems[0]
    red = _run(root, "check")
    assert red.returncode != 0 and "which does not exist" in red.stderr, red.stderr

    # And restoring the note is GREEN again
    (root / "agent-wiki/2026-10-14-change.md").write_text(note)
    assert cd.problems(cd.graph(root)) == []
    green = _run(root, "check")
    assert green.returncode == 0 and "ok:" in green.stdout, green.stdout


def test_a_malformed_index_row_fails(tmp_path):
    """A row must be exactly one well-formed row: a date, a summary, its own note, an issue/PR."""

    # Given a fragment that is not a single row, one with no issue reference, and one that
    # indexes somebody else's note
    cases = {
        "two-lines": "| 2026-10-14 | change | [n](agent-wiki/two-lines.md) | #257 |\n"
                     "| 2026-10-15 | another | [n](agent-wiki/two-lines.md) | #257 |\n",
        "not-a-row": "change, see #257\n",
        "no-ref": "| 2026-10-14 | change | [n](agent-wiki/no-ref.md) | nothing |\n",
        "bad-date": "| 14/10/2026 | change | [n](agent-wiki/bad-date.md) | #257 |\n",
        "other-note": "| 2026-10-14 | change | [n](agent-wiki/someone-else.md) | #257 |\n",
    }
    for stem, row in cases.items():
        root = _tree(tmp_path / stem, "install: ## Install\n\t@true\n",
                     "# llgenie\n\n```\nmake install\n```\n",
                     wiki={f"{stem}.md": "# Change\n\nIssue #257.\n"},
                     fragments={stem: row},
                     changes="# Changes\n\n| Date | Change | Record | Issue / PR |\n|---|---|---|---|\n")

        # When the documentation is checked
        problems = cd.problems(cd.graph(root))

        # Then the malformed row is named, never silently indexed
        assert len(problems) == 1, (stem, problems)
        assert f"docs/changes.d/{stem}.md:" in problems[0], (stem, problems)
        assert _run(root, "check").returncode != 0

    # And the shapes are named: not one row, an unparsable row, no reference, a bad date, a
    # fragment indexing a note that is not its own
    for stem, needle in (("two-lines", "a fragment is exactly one row"),
                         ("not-a-row", "is not a row"),
                         ("no-ref", "names no issue or PR"),
                         ("bad-date", "is not YYYY-MM-DD"),
                         ("other-note", "must index the note of its own name")):
        root = tmp_path / stem
        assert any(needle in p for p in cd.problems(cd.graph(root))), (stem, needle)


def test_the_readme_must_link_the_change_index(tmp_path):
    """A reader reaches the history through the README; an unlinked index is unfindable."""

    # Given a README with no link to CHANGES.md
    root = _tree(tmp_path, "install: ## Install\n\t@true\n", "# llgenie\n\n```\nmake install\n```\n",
                 link_changes=False)

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it says the README does not reach the index
    assert len(problems) == 1 and "does not link CHANGES.md" in problems[0], problems


def test_the_readme_carries_no_change_history(tmp_path):
    """The exact defect of issue #678: a change appended a section to the README instead of a note."""

    # Given a README with an issue-numbered section, as every landed change used to append
    root = _tree(tmp_path, "install: ## Install\n\t@true\n",
                 "# llgenie\n\n[changes](CHANGES.md)\n\n```\nmake install\n```\n\n"
                 "## Installation is isolated (issue #275)\n\ntext\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then it names the heading and where the change belongs
    assert len(problems) == 1, problems
    assert "is change history" in problems[0] and "agent-wiki" in problems[0]

    # And a `## Changes`/`## Changelog` heading is refused the same way
    (root / "README.md").write_text(
        "# llgenie\n\n[changes](CHANGES.md)\n\n```\nmake install\n```\n\n## Changelog\n\n- one\n")
    again = cd.problems(cd.graph(root))
    assert len(again) == 1 and "is change history" in again[0], again

    # And the generated dispatch table belongs in docs/BOTS.md, not the user guide
    (root / "README.md").write_text(
        "# llgenie\n\n[changes](CHANGES.md)\n\n```\nmake install\n```\n\n"
        "<!-- dispatch-forms:begin -->\n| w |\n<!-- dispatch-forms:end -->\n")
    marker = cd.problems(cd.graph(root))
    assert len(marker) == 1 and "dispatch table" in marker[0], marker


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
    assert "the PR it implements" in agents

    # And the rule is a dated note with its own row — never an append to the README
    assert "Never document a change by appending a" in agents
    assert "a bot never writes `README.md` at all" in agents

    # And `## Record of work` points at it rather than repeating the old, unguarded wording
    record = agents.split("## Record of work", 1)[1]
    assert "make check-docs" in record and "SAME commit" in record

    # And the README documents the gate the user is expected to run, and links the index
    assert "make check-docs" in readme and "make docs-report" in readme
    assert "](CHANGES.md)" in readme and "](docs/ARCHITECTURE.md)" in readme


# ---------------------------------------------------------------------------
# the change-record rule names the fragment, not a CHANGES.md append (issue #942)
# ---------------------------------------------------------------------------
def test_change_record_rule_names_the_fragment_and_names_the_renderer():
    """Every document that states the rule tells a contributor what a change ADDS. `CHANGES.md` is
    rendered from `docs/changes.d/<note-stem>.md` (issue #934), so a rule that still asks for a row
    in `CHANGES.md` publishes the append point the repository removed."""

    # Given every file that states the change-record rule
    texts = cd.rule_doc_texts(REPO)

    # When each statement is checked for an instruction to append a row to CHANGES.md
    offenders = {name: found for name, found in
                 ((n, cd.append_point_violations(t)) for n, t in texts.items()) if found}

    # Then the only paths allowed to still name it are the recorded, issue-numbered exceptions
    assert set(offenders) <= set(cd.APPEND_POINT_EXCEPTIONS), offenders

    # And the corpus is not all exempt: most statements read clean, and they say what to add instead
    assert len(texts) - len(offenders) >= 2, sorted(texts)
    for name in ("docs/ARCHITECTURE.md", "docs/BOTS.md"):
        assert "docs/changes.d/" in texts[name], name
        assert "make changes-index" in texts[name], name


def test_the_gate_reds_on_a_reintroduced_changes_append_and_greens_on_the_fragment(tmp_path):
    """Falsifiable in both directions: a document that tells a contributor to put its row in
    `CHANGES.md` fails the gate, the same document rewritten to the fragment shape passes, and the
    gate names the file and the replacement rather than just the word `CHANGES.md`."""

    # Given a checkout whose rule page asks for a row in CHANGES.md
    root = _tree(tmp_path,
                 "install: ## Install everything\n\t@true\n",
                 "# llgenie\n\n```\nmake install   # install everything\n```\n")
    rule = root / "docs" / "RULES.md"
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text(
        "# Rules\n\nEvery change appends its row to `CHANGES.md`, newest first, in the same commit.\n")

    # When the documentation is checked
    problems = cd.problems(cd.graph(root))

    # Then exactly the reintroduced append point fails, and the error names the replacement
    assert len(problems) == 1, problems
    assert "docs/RULES.md: tells a contributor to add its row to CHANGES.md" in problems[0]
    assert "docs/changes.d/<note-stem>.md" in problems[0]
    assert "make changes-index" in problems[0]

    # And the real CLI reports it too — this is the gate CI runs, not just a helper
    r = _run(root, "check")
    assert r.returncode == 1 and "docs/RULES.md" in r.stderr, r.stdout + r.stderr

    # And the fragment shape is the fix: name what the change adds, and the renderer
    rule.write_text(
        "# Rules\n\nEvery change adds `docs/changes.d/<note-stem>.md`; `CHANGES.md` is rendered by\n"
        "`make changes-index` and no change edits it.\n")
    assert cd.problems(cd.graph(root)) == []
    assert _run(root, "check").returncode == 0

    # And a recorded exception cannot outlive its reason: a clean file under an exemption is STALE
    cd.APPEND_POINT_EXCEPTIONS["docs/RULES.md"] = {"issue": 942, "decided": "2026-10-29",
                                                   "reason": "test"}
    try:
        stale = cd.problems(cd.graph(root))
        assert len(stale) == 1 and "append-point exception" in stale[0] and "STALE" in stale[0], stale
    finally:
        del cd.APPEND_POINT_EXCEPTIONS["docs/RULES.md"]


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
