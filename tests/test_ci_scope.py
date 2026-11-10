"""Which CI stages a diff selects — one class per rule, one case per class (#824).

`ci.yml` runs one pipeline for every change: a docs-only PR queued the same jobs as a change to
`containers/engines/`. The classifier is the decision that makes a stage selectable, and it must be
tested where it can be wrong in four ways:

  * a class that stops matching a path it owns (a `docs/**` file no longer selects `docs`);
  * a wildcard that stops selecting every class — the dangerous direction, because a quiet skip there
    hides a regression in the gate itself;
  * an unmatched path passing silently instead of failing the run;
  * the job table drifting from `ci.yml`'s real job names (measured: #871 deleted the macOS group, so a
    table written for 28 jobs described 14 jobs that no longer exist).

The last one is asserted against the workflow file itself, so the two cannot drift apart again.
"""
from __future__ import annotations


from conftest import makefiles_text
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ci_scope as cs  # noqa: E402

CI = REPO / ".github" / "workflows" / "ci.yml"


# ---- one case per class ----------------------------------------------------------

@pytest.mark.parametrize("path,expected", [
    ("docs/ARCHITECTURE.md", "docs"),
    ("agent-wiki/2026-10-28-note.md", "docs"),
    ("openspec/changes/x/proposal.md", "docs"),
    ("CHANGES.md", "docs"),
    (".hermes/skills/issue-implement/SKILL.md", "skills"),
    ("agents/llgenie-planner/SOUL.md", "skills"),
    ("tests/test_worktree_prune.py", "tests"),
    ("data/trending-quant-catalog.json", "data"),
    ("containers/engines/params/llama.cpp.json", "engines"),
    ("skills/engines/strata/SKILL.md", "engines"),
    ("security-reports/sbom.cdx.json", "security"),
    ("renovate.json", "security"),
])
def test_each_class_is_selected_by_a_path_it_owns(path, expected):
    classes, unmatched, _wide = cs.classify([path])

    assert unmatched == []
    assert expected in classes, (path, classes)


def test_containers_and_engines_are_distinct_but_overlap():
    # `containers/engines/...` belongs to both: a container change can break an engine image.
    classes, _, _wide = cs.classify(["containers/engines/params/llama.cpp.json"])
    assert {"containers", "engines"} <= set(classes)

    classes, _, _wide = cs.classify(["containers/scanners/grype/Dockerfile"])
    assert "containers" in classes and "engines" not in classes


def test_openspec_dockerfile_is_a_container_change_that_publishes_ci_images():
    """`openspec/Dockerfile` builds the openspec CI image, so it must NOT be a docs-only class (issue #824).

    Before the fix it matched the docs glob `openspec/**`, so `ci.yml` skipped it at the trigger and the
    `ci-images` job (the only publisher of the openspec image hash) never ran — any Dockerfile edit left
    `make openspec-image-pull` in `scope.yml` red on an unpublished hash. The image belongs to the
    `containers` family (like `containers/test/Dockerfile`), so `_NON_DOCS` selects `ci-images`.
    """
    classes, unmatched, _wide = cs.classify(["openspec/Dockerfile"])
    assert unmatched == []
    assert "containers" in classes, classes
    assert "docs" not in classes, classes
    # the job table keys `ci-images` on every non-docs class
    rows = dict((job, runs) for job, runs, _ in cs.select(classes))
    assert rows["ci-images"], "a Dockerfile edit for the openspec CI image must publish it"

    # the OpenSpec spec docs stay docs: a proposal edit needs no new image
    classes, _, _wide = cs.classify(["openspec/changes/x/proposal.md"])
    assert classes == ["docs"], classes
    classes, _, _wide = cs.classify(["openspec/config.yaml"])
    assert classes == ["docs"], classes


# ---- wildcards: the dangerous direction ------------------------------------------

@pytest.mark.parametrize("path", [
    "Makefile",
    "tools/Makefile",
    ".github/workflows/ci.yml",
    "scripts/ci_images.py",
    "scripts/engine_bump.py",
    "scripts/check_docs.py",
    "pytest.ini",
    ".gitleaks.toml",
    "renovate.json",
    "AGENTS.md",
])
def test_a_wildcard_path_selects_every_class(path):
    classes, unmatched, _wide = cs.classify([path])

    assert unmatched == []
    assert set(classes) == set(cs.CLASSES), (path, classes)
    assert cs.matched_wildcards([path]), path


def test_a_wildcard_wins_even_beside_a_docs_path():
    # The failure that would hurt most: "it is only a markdown change" next to an AGENTS.md edit.
    classes, _, _wide = cs.classify(["docs/ARCHITECTURE.md", "AGENTS.md"])

    assert set(classes) == set(cs.CLASSES)


# ---- an unmatched path is a loud failure ----------------------------------------

def test_a_path_no_class_claims_is_reported_and_the_selection_widens():
    """Issue #860: the path is still named (so the CLI can exit 1) and the selection fails OPEN."""
    classes, unmatched, wide = cs.classify(["mystery/new-tree/file.txt"])

    assert unmatched == ["mystery/new-tree/file.txt"]
    assert set(classes) == set(cs.CLASSES)
    assert wide and "matches no class" in wide


def test_the_cli_exits_non_zero_and_names_the_unmatched_path(capsys):
    rc = cs.main(["--paths", "docs/ARCHITECTURE.md", "mystery/file.txt"])

    err = capsys.readouterr().err
    assert rc == cs.EXIT_UNCLASSIFIED
    assert "mystery/file.txt matches no class" in err


# ---- selection, and the docs-only win -------------------------------------------

def test_a_docs_only_diff_selects_fewer_than_ten_jobs_and_names_what_it_skipped():
    classes, _, _wide = cs.classify(["docs/ARCHITECTURE.md", "CHANGES.md"])
    rows = cs.select(classes)
    selected = [job for job, runs, _ in rows if runs]
    skipped = [(job, why) for job, runs, why in rows if not runs]

    assert classes == ["docs"]
    assert len(selected) < 10, selected
    assert {"guard", "linux/lint", "linux/openspec"} <= set(selected)
    # Every skipped row says which class it would have needed — the log states the decision.
    assert all("needs one of" in why for _, why in skipped), skipped


def test_an_engine_change_selects_the_engine_rows_and_the_install_proof():
    classes, _, _wide = cs.classify(["containers/engines/params/strata.json"])
    rows = dict((job, runs) for job, runs, _ in cs.select(classes))

    assert rows["linux/install"] and rows["linux/cpu-health"]
    # `scanner-images` keys on `containers`, and `containers/engines/**` IS a containers path, so an
    # engine-params change selects it too — the class granularity #824 specifies. Recorded here rather
    # than silently narrowed: sharpening the rule (scanners only for `containers/scanners/**`) is part
    # (b)'s job, not this classifier's, and a test that asserted the sharper behaviour would be
    # describing a rule the repo does not have.
    assert rows["scanner-images"], "the issue's table selects the scanners for any `containers` change"


def test_an_engine_skill_pin_change_selects_the_unit_security_battery():
    """A `skills/engines/**` SKILL.md carries dependency pins (issue #2227).

    The skill is the GENERATOR of `containers/engines/params/*.json`, which `engine_pins.py`
    inventories into the security SBOM — so a pin edited directly in the skill is a dependency pin
    that reaches `main` with NONE of the security gates unless `linux/unit` runs (`check-engine-
    pins-published`, `check-secret-output`, `check-proc-gate`, `check-security-scan`, `check-actions`).
    Before this fix the `engines` class selected only `guard`/`ci-images`/`lint`/`install`/`cpu-health`
    and SKIPPED `unit`; the `engines` class must now re-include it.
    """
    classes, _, _wide = cs.classify(["skills/engines/vllm/SKILL.md"])
    rows = dict((job, runs) for job, runs, _ in cs.select(classes))

    assert "engines" in classes, classes
    assert rows["linux/unit"], "an engine SKILL.md pin edit must run the security + pin battery"

    # `containers/engines/**` was already `unit`-selected via `containers`; adding `engines` keeps it
    # selected (a no-op re-inclusion) — assert it does not regress.
    classes, _, _wide = cs.classify(["containers/engines/params/strata.json"])
    rows = dict((job, runs) for job, runs, _ in cs.select(classes))
    assert rows["linux/unit"], "a containers/engines change must keep selecting unit"

    # Negative controls proving `unit` GAINED `engines`, not that every path runs `unit`:
    # a non-engine skill (`agents/**`) already selects `unit` via `skills`; a `docs`-only path
    # must still skip it.
    classes, _, _wide = cs.classify(["agents/llgenie-planner/SKILL.md"])
    rows = dict((job, runs) for job, runs, _ in cs.select(classes))
    assert classes == ["skills"], classes
    assert rows["linux/unit"], "a non-engine skill already selects unit via the skills class"

    classes, _, _wide = cs.classify(["docs/ARCHITECTURE.md"])
    rows = dict((job, runs) for job, runs, _ in cs.select(classes))
    assert classes == ["docs"], classes
    assert not rows["linux/unit"], "a docs-only change must still skip unit"


def test_an_engine_pin_change_is_held_to_the_security_gate_set_in_ci_unit():
    """Regression: the security + pin battery lives ONLY in `linux/unit` (issue #2227).

    If `scripts/ci_scope.py` `_STAGES["unit"]` loses `engines`, this test reds — the exact change that
    would let a `skills/engines/*/SKILL.md` pin skip every security gate. `Makefile` `ci-unit`
    (bash 1821-1860) is the sole carrier of `check-engine-pins-published` / `check-secret-output` /
    `check-proc-gate` / `check-security-scan` / `check-actions`, so the unit re-inclusion is the gate.
    """
    # Assert the named gate targets still live under the `ci-unit` body — if the battery moves, the
    # unit-reinclusion test must move with it, not silently guard a target that no longer exists.
    makefile = makefiles_text()
    body = makefile.split("ci-unit:")[1].split("\n\n")[0]
    for target in ("check-engine-pins-published", "check-secret-output", "check-proc-gate",
                   "check-security-scan", "check-actions"):
        assert target in body, f"{target} moved out of ci-unit — re-anchor the #2227 unit test"



def test_the_report_prints_one_class_line_per_class_and_one_verdict_per_job():
    classes, _, _wide = cs.classify(["tests/test_ci_scope.py"])
    rows = cs.select(classes)
    lines = cs.report(classes, rows, ["tests/test_ci_scope.py"], None)

    assert "[ci-scope] class=tests" in lines
    assert sum(1 for line in lines if "[ci-scope] job=" in line) == len(cs.JOBS)
    assert any(line.startswith("[ci-scope] scope: ") for line in lines)


# ---- the table cannot drift from the workflow ------------------------------------

def test_every_job_the_classifier_names_exists_in_ci_yml():
    workflow = yaml.safe_load(CI.read_text())
    real = set(workflow["jobs"])
    named = {job.split("/")[0] for job, _ in cs.JOBS}      # `linux/unit` -> the `linux` job

    missing = named - real
    assert not missing, f"the classifier names jobs ci.yml does not have: {sorted(missing)}"


def test_the_docs_trigger_list_matches_the_docs_class_minus_its_wildcards():
    docs_globs = set(cs.CLASSES["docs"])
    ignore = [p for p in cs.DOCS_TRIGGER_IGNORE if not p.startswith("!")]
    negations = [p[1:] for p in cs.DOCS_TRIGGER_IGNORE if p.startswith("!")]

    # Every ignored glob is a docs glob, and every wildcard that is a docs glob is re-included.
    assert set(ignore) <= docs_globs, set(ignore) - docs_globs
    wildcard_docs = {w for w in cs.WILDCARDS if w in docs_globs}
    assert wildcard_docs <= set(negations), (wildcard_docs, negations)


def test_a_markdown_file_outside_a_docs_directory_is_not_docs():
    """A path is `docs` because of its DIRECTORY, never because its extension is `.md` (#824 review)."""
    classes, _, _wide = cs.classify(["tests/fixtures/notes.md"])
    assert classes == ["tests"], classes

    classes, _, _wide = cs.classify(["docs/ARCHITECTURE.md", "agent-wiki/n.md", "openspec/changes/x/p.md",
                                     "README.md", "CHANGES.md"])
    assert classes == ["docs"], classes


def test_the_trigger_list_is_the_docs_class_and_nothing_else():
    assert set(cs.DOCS_TRIGGER_IGNORE) == set(cs.CLASSES["docs"])
    assert not any(g.startswith("!") for g in cs.DOCS_TRIGGER_IGNORE)
    assert "*" not in " ".join(cs.DOCS_TRIGGER_IGNORE).replace("**", ""), cs.DOCS_TRIGGER_IGNORE


def test_a_blank_path_entry_is_the_empty_diff_not_an_unclassifiable_one():
    classes, unmatched, wide = cs.classify([""])
    assert unmatched == [] and set(classes) == set(cs.CLASSES) and "empty diff" in wide


def test_ci_yml_ignores_exactly_the_docs_trigger_list():
    """The YAML and the classifier are the same decision, so they cannot drift (issue #824)."""
    workflow = yaml.safe_load(CI.read_text())
    on = workflow.get("on") or workflow.get(True)
    declared = on["pull_request"]["paths-ignore"]

    assert declared == list(cs.DOCS_TRIGGER_IGNORE), declared
    # And the push trigger carries NO path filter: `main` must never be under-tested.
    assert "paths-ignore" not in on["push"] and "paths" not in on["push"]


def test_the_scope_workflow_has_no_path_filter_and_runs_the_docs_gates():
    """`scope` is the always-present check: no filter, one job named `scope`, the docs gates inside."""
    path = REPO / ".github" / "workflows" / "scope.yml"
    workflow = yaml.safe_load(path.read_text())
    on = workflow.get("on") or workflow.get(True)

    assert "paths" not in on["pull_request"] and "paths-ignore" not in on["pull_request"], on
    # `scope` runs the docs gates; the `guard` job is REQUIRED by test_workflow_guards for a
    # dispatchable workflow (issue #295), so it sits beside `scope` and `scope` needs it — the same
    # shape ci.yml uses. The always-present check is still the single `scope` gate.
    assert list(workflow["jobs"]) == ["guard", "scope"], workflow["jobs"]
    assert workflow["jobs"]["scope"].get("needs") == ["guard"], workflow["jobs"]["scope"].get("needs")
    runs = " ".join(step.get("run", "") for step in workflow["jobs"]["scope"]["steps"])
    for gate in ("make ci-scope", "make ci-lint", "make check-docs", "make check-wiring",
                 "make check-issue-bodies", "make ci-openspec"):
        assert gate in runs, (gate, runs)
    # No new third-party action: the one `uses:` is the same pinned checkout ci.yml uses.
    uses = [step["uses"] for step in workflow["jobs"]["scope"]["steps"] if "uses" in step]
    assert uses == ["actions/checkout@11d5960a326750d5838078e36cf38b85af677262"], uses



# ---- issue #860: the fail-open decision lives in the library, not in main() -------

def test_an_empty_diff_selects_every_class_with_a_wide_reason():
    """A caller that imports `classify()` must get the safe answer, not a 3-job selection."""
    classes, unmatched, wide = cs.classify([])

    assert set(classes) == set(cs.CLASSES), classes
    assert unmatched == []
    assert wide and "empty diff" in wide, wide


def test_an_unknown_path_selects_every_class_and_still_names_the_path():
    classes, unmatched, wide = cs.classify(["random/unknown.xyz"])

    assert set(classes) == set(cs.CLASSES)
    assert unmatched == ["random/unknown.xyz"]
    assert wide and "random/unknown.xyz" in wide


def test_the_library_and_the_cli_agree_on_an_unreadable_diff():
    """Negative control for #860: revert the widening inside `classify()` and this reds.

    `main()` no longer substitutes anything, so the CLI's answer IS the library's answer — if someone
    moves the widening back up into `main()`, the two diverge again and this assertion catches it.
    """
    classes, unmatched, wide = cs.classify(["random/unknown.xyz"])
    rows = cs.select(classes)
    selected = [job for job, runs, _ in rows if runs]

    assert len(selected) == len(cs.JOBS), selected          # the CLI would print every job
    assert unmatched, "the CLI must still exit non-zero for an owed glob"
    assert wide, "the reason is what the log prints"
    # And the empty case is exit 0, not a red: nothing to fix, but everything selected.
    assert set(cs.classify([])[0]) == set(cs.CLASSES)


# ---- issue #1061: an unknown class is a caller bug, not a narrowing --------------

def test_select_refuses_an_unknown_class_naming_it_and_the_valid_set():
    """A mistyped class used to select 2 of 10 jobs with no error (issue #1061)."""
    with pytest.raises(ValueError) as excinfo:
        cs.select(["tests_typo"])

    message = str(excinfo.value)
    assert "tests_typo" in message, message
    # Every real class is named, so the caller does not have to read the source to fix the typo.
    valid = [name for name in cs.CLASSES if name not in "tests_typo"]
    assert all(name in message for name in valid), message


def test_select_names_every_unknown_entry_not_just_the_first():
    with pytest.raises(ValueError) as excinfo:
        cs.select(["unit", "docs", "enginez"])

    message = str(excinfo.value)
    assert "unit" in message and "enginez" in message, message


def test_select_an_empty_class_list_is_legal_and_selects_the_always_on_jobs():
    """`--paths ''` is the documented always-jobs case: an empty list must not raise."""
    rows = cs.select([])
    always = {job for job, needs in cs.JOBS if needs is None}

    assert {job for job, runs, _ in rows if runs} == always
    assert len(always) < len(cs.JOBS)


def test_select_every_real_class_still_returns_every_job():
    rows = cs.select(list(cs.CLASSES))

    assert len(rows) == len(cs.JOBS)
    assert all(runs for _, runs, _ in rows)
