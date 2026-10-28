#!/usr/bin/env python3
"""The classifier that decides which CI jobs a diff needs (issue #824).

One case per change class, one per wildcard, and the two decisions that make the design safe: a
docs-only diff must select fewer than ten jobs, and a path that matches no class must fail loudly rather
than select nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import ci_scope  # noqa: E402  (the module under test, from the repo's own scripts/)


def test_a_docs_only_diff_selects_fewer_than_ten_jobs():
    """The whole point: one markdown file must not queue the 28-job matrix."""

    # Given the diff of PR #767 (one markdown file)
    # When  the class is computed
    result = ci_scope.scope(["docs/ARCHITECTURE.md"])

    # Then  it is the docs class alone, and it selects only the gates a doc needs
    assert result["classes"] == ["docs"]
    assert len(result["jobs"]) < 10, result["jobs"]
    assert set(result["jobs"]) == {"guard", "linux/lint", "macos/lint", "linux/openspec", "macos/openspec"}
    assert "engine-matrix" in result["skipped"] and "ci-images" in result["skipped"]


def test_every_class_is_reachable_by_its_own_paths():
    """A class that no path reaches is a class that can never select anything."""

    # Given one representative path per class
    samples = {
        "docs": "CHANGES.md", "skills": ".hermes/skills/issue-triage/SKILL.md",
        "workflows": ".github/workflows/ci.yml", "scripts": "scripts/llgenie_serve.py",
        "tests": "tests/test_ci_scope.py", "data": "data/models.json",
        "containers": "containers/test/Dockerfile", "engines": "containers/engines/params/vllm.json",
        "security": "security-reports/scan.md",
    }
    for name, path in samples.items():
        # When  that single path is classified
        classes = ci_scope.classify([path])
        # Then  it reaches its class
        assert name in classes, (name, path, classes)


def test_the_wildcard_paths_select_every_class_and_every_job():
    """Makefile, tools/**, .github/**, the CI scripts and AGENTS.md can change what any gate proves."""

    # Given each wildcard path on its own
    for path in ("Makefile", "tools/requirements.in", ".github/workflows/ci.yml",
                 "scripts/ci_scope.py", "scripts/engine_image.py", "scripts/check_docs.py",
                 "pytest.ini", ".gitleaks.toml", "renovate.json", "AGENTS.md"):
        result = ci_scope.scope([path])
        # Then  every class is present and every job is selected
        assert set(result["classes"]) == set(ci_scope.CLASSES), (path, result["classes"])
        assert result["skipped"] == [], (path, result["skipped"])


def test_a_scripts_change_selects_the_code_gates_but_not_the_engine_rows():
    """A real code change keeps the gates it needs and drops the families it cannot affect."""

    # Given a change to a shared script and its test
    result = ci_scope.scope(["scripts/llgenie_serve.py", "tests/test_llgenie_serve.py"])

    # Then  unit/install run, the engine family does not
    assert {"scripts", "tests"} <= set(result["classes"])
    for job in ("linux/unit", "macos/unit", "linux/install", "ci-images"):
        assert job in result["jobs"], job
    for job in ("engine-matrix", "engine-base", "linux-published", "test-published"):
        assert job in result["skipped"], job


def test_an_engine_change_selects_the_engine_family():
    """A pin bump is exactly what the engine rows exist to prove."""

    result = ci_scope.scope(["containers/engines/params/strata.json"])

    assert "engines" in result["classes"]
    for job in ("engine-matrix", "engine-base", "engine-image", "linux-published"):
        assert job in result["jobs"], job


def test_a_path_that_matches_no_class_fails_loudly():
    """Silence is the failure mode this repository keeps paying for (#801, #817)."""

    result = ci_scope.scope(["docs/ARCHITECTURE.md", "somewhere/unknown.bin"])

    assert result["unknown"] == ["somewhere/unknown.bin"]
    # and the CLI turns that into a non-zero exit
    assert ci_scope.main(["jobs", "--paths", "somewhere/unknown.bin"]) == 1
    assert ci_scope.main(["jobs", "--paths", "docs/ARCHITECTURE.md"]) == 0


def test_the_cli_reports_the_selected_and_skipped_jobs(capsys):
    """The check a reader sees must name both sides of the decision."""

    code = ci_scope.main(["jobs", "--paths", "docs/ARCHITECTURE.md"])

    out = capsys.readouterr().out
    assert code == 0
    assert "classes: docs" in out
    assert "skipped:" in out and "engine-matrix" in out.split("skipped:")[1]


# ---------------------------------------------------------------------------------------------------
# The wiring: the classifier is only half the design. The other half is that the TRIGGERS select the
# stages and one always-present check says so (issue #824) — a classifier nothing calls, or a filter
# whose class nobody reports, would be the silent absence this issue exists to prevent.
def _workflow(name: str) -> dict:
    """A workflow file parsed off disk (`on:` comes back as the boolean True in YAML 1.1)."""
    import yaml

    return yaml.safe_load((REPO / ".github/workflows" / name).read_text())


def _trigger(doc: dict, event: str) -> dict:
    on = doc.get("on") if "on" in doc else doc.get(True)
    return (on or {}).get(event) or {}


def test_ci_yml_filters_only_the_docs_class_on_pull_request():
    """The 28-job matrix is skipped for a docs-only diff, and never for a push to main."""

    # Given ci.yml's pull_request trigger
    pr = _trigger(_workflow("ci.yml"), "pull_request")

    # Then  it ignores exactly the paths a documentation change touches …
    ignored = set(pr.get("paths-ignore") or [])
    assert {"**/*.md", "docs/**", "agent-wiki/**", "openspec/**"} <= ignored, ignored
    # … every one of them is the docs class, so the filter cannot hide a code change
    for pattern in ignored:
        sample = pattern.replace("**/", "").replace("**", "") or "README.md"
        assert ci_scope.classify([sample]).keys() == {"docs"}, (pattern, sample)
    # … and a push to main is NOT filtered: a merge must keep the full matrix
    push = _trigger(_workflow("ci.yml"), "push")
    assert "paths" not in push and "paths-ignore" not in push, push


def test_the_scope_workflow_has_no_filter_and_reports_one_check():
    """Absence must be legible: the always-present check names the classes the diff selected."""

    # Given the scope workflow
    doc = _workflow("scope.yml")
    pr = _trigger(doc, "pull_request")

    # Then  it carries NO path filter of its own (it must run on every PR)
    assert "paths" not in pr and "paths-ignore" not in pr, pr
    # And one job named exactly `scope` runs the classifier through make
    assert "scope" in doc["jobs"], list(doc["jobs"])
    run = " ".join(step.get("run", "") for step in doc["jobs"]["scope"]["steps"])
    assert "make ci-scope" in run, run
    # And it cannot silently pass a diff nobody can classify: the script fails on an unknown path
    assert ci_scope.main(["jobs", "--paths", "no-such-dir/thing.xyz"]) == 1


def test_the_docs_workflow_runs_the_gates_a_docs_change_can_break():
    """The docs class gets its own workflow, and it runs the gates the matrix would have run."""

    # Given the docs workflow
    doc = _workflow("docs.yml")
    pr = _trigger(doc, "pull_request")

    # Then  it is path-filtered to the same docs class ci.yml ignores
    assert {"**/*.md", "docs/**", "agent-wiki/**", "openspec/**"} <= set(pr.get("paths") or [])
    # And every gate that a documentation change can break is one of its steps
    run = " ".join(step.get("run", "") for step in doc["jobs"]["docs"]["steps"])
    for gate in ("make ci-lint", "make check-docs", "make check-wiring", "make check-issue-bodies",
                 "make check-workflows", "make check-dispatch-forms", "make ci-openspec"):
        assert gate in run, (gate, run)


def test_every_skipped_job_names_the_class_that_skipped_it():
    """The AC: the log names each skipped stage WITH the class that skipped it (issue #824).

    A bare list of absent names says a job did not run, never whether that was RIGHT — the reader
    would have to re-derive the rule. The reason travels with the name.
    """

    # Given PR #767's docs-only diff
    result = ci_scope.scope(["docs/ARCHITECTURE.md"])

    # Then  every skipped job carries a reason, and it names exactly the classes that select it
    assert set(result["skipped_reasons"]) == set(result["skipped"])
    for job in result["skipped"]:
        reason = result["skipped_reasons"][job]
        if job == "ci-images":
            assert reason == "needs a class other than docs", reason
            continue
        assert reason.startswith("needs one of "), (job, reason)
        named = set(reason[len("needs one of "):].split(", "))
        assert named == set(ci_scope.JOBS[job]), (job, reason)


def test_the_cli_prints_the_reason_beside_each_skipped_job(capsys):
    """`make ci-scope` is what the `scope` check runs, so its log must carry the reason too."""

    # Given the CLI run on a docs-only diff
    assert ci_scope.main(["jobs", "--paths", "docs/ARCHITECTURE.md"]) == 0
    out = capsys.readouterr().out

    # Then  the skipped line names a reason for at least the engine family
    skipped_line = out.split("skipped:", 1)[1]
    assert "engine-matrix (needs one of " in skipped_line, skipped_line
