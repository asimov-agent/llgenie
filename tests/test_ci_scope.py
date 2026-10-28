#!/usr/bin/env python3
"""The classifier that decides which CI jobs a diff needs (issue #824).

One case per change class, one per wildcard, and the two decisions that make the design safe: a
docs-only diff must select fewer than ten jobs, and a path that matches no class must fail loudly rather
than select nothing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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
    assert {"docs/**", "agent-wiki/**", "openspec/**", "README.md", "CHANGES.md"} == ignored, ignored
    # … every one of them classifies as the docs class alone, so the filter cannot hide a code change.
    # Sample with a concrete path per pattern: a naive "**/*.md" -> "README.md" substitution is what let
    # the first version of this test pass while the trigger skipped the registry gate for data/*.md.
    samples = {"docs/**": "docs/ARCHITECTURE.md", "agent-wiki/**": "agent-wiki/2026-10-28-x.md",
               "openspec/**": "openspec/changes/x/proposal.md", "README.md": "README.md",
               "CHANGES.md": "CHANGES.md"}
    for pattern in ignored:
        sample = samples[pattern]
        assert set(ci_scope.classify([sample])) == {"docs"}, (pattern, sample)
    # … and markdown that a real gate reads is NOT ignored, so its jobs still run (#824 review finding)
    for sample in ("data/trending-README.md", "data/MODEL_CONTRACT.md",
                   ".hermes/skills/issue-triage/SKILL.md", "skills/engines/dflash2/SKILL.md",
                   "tests/fixtures/agents/happy_brief_rulebook.md"):
        # markdown a real gate reads is NOT the docs class, so no ignore pattern can swallow it
        assert "docs" not in ci_scope.classify([sample]), sample
        assert not any(ci_scope._match(sample, p) for p in ignored), sample
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

    # Then  it is path-filtered to exactly the same list ci.yml ignores — the two workflows split one
    # class, so a path one ignores the other must run
    ci_ignored = set(_trigger(_workflow("ci.yml"), "pull_request").get("paths-ignore") or [])
    assert set(pr.get("paths") or []) == ci_ignored, (set(pr.get("paths") or []), ci_ignored)
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

def test_every_make_target_the_new_workflows_call_actually_exists():
    """A workflow that calls a target nobody defined is a red run for a typo, not for the change.

    The two new workflows are the seam where a name can drift: `scope.yml` runs `make ci-scope` and
    `docs.yml` runs the gates a docs change can break. A renamed target would go unnoticed until a
    docs PR went red, so the names are pinned here — the same class of defect as a comment that cites
    a test which does not exist.
    """

    # Given the alternating targets the new workflows invoke
    makefile = (ROOT / "Makefile").read_text()
    defined = set(re.findall(r"^([A-Za-z0-9_./%-]+):", makefile, re.M))

    # Then  every `make <target>` in them is a real target
    for workflow in ("scope.yml", "docs.yml"):
        raw = (ROOT / ".github" / "workflows" / workflow).read_text()
        called = {m for m in re.findall(r"make\s+([A-Za-z0-9_./-]+)", raw) if not m.startswith("-")}
        assert called, workflow
        missing = sorted(called - defined)
        assert not missing, f"{workflow} calls undefined targets: {missing}"


# ---------------------------------------------------------------------------------------------------
# An error or an empty diff must map to the FULL pipeline, never to an empty selection (#824) — and one
# MUST-run / MUST-NOT-run row per class, because a filter nobody measured is a filter nobody can trust.
def _ci_yml_pull_request() -> dict:
    import yaml

    doc = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    on = doc.get("on") if "on" in doc else doc.get(True)
    return (on or {}).get("pull_request") or {}


def _docs_yml_paths() -> set[str]:
    import yaml

    doc = yaml.safe_load((REPO / ".github/workflows/docs.yml").read_text())
    on = doc.get("on") if "on" in doc else doc.get(True)
    return set((on or {}).get("pull_request", {}).get("paths") or [])


def test_an_empty_diff_widens_and_passes(capsys):
    """No diff is not evidence that a stage is unnecessary - and it is not something a human can fix.

    So it widens to the whole pipeline and EXITS 0: a red always-on check on a merge-queue ref, a
    dispatch or a force-push that nets to no change would be an unfixable red. An unclassifiable path
    is different - that one a human must act on, so it exits 1 (the next test).
    """

    # Given a diff the classifier is handed with no paths at all (a merge queue, a force-push, a
    # dispatch — the shapes the tool may be asked about without a diff)
    # When  the CLI is asked
    rc = ci_scope.main(["jobs", "--paths"])

    # Then  it says WIDE, selects every family, and still exits non-zero so the check is loud
    out = capsys.readouterr().out
    assert rc == 0, out
    total = len(ci_scope.ALWAYS) + len(ci_scope.JOBS) + 1
    assert f"jobs ({total} of {total})" in out, out
    assert "WIDE: empty diff" in out, out
    assert "this is not a failure" in out, out


def test_a_path_the_classifier_refuses_can_never_be_ignored_by_the_trigger():
    """The structural half of fail-closed: the ignore list IS the docs class, so an unclassifiable
    path leaves `ci.yml` to run the full matrix — an empty selection is unreachable by construction."""

    # Given a path no class matches
    weird = "some/unclassified/thing.xyz"
    assert ci_scope.main(["jobs", "--paths", weird]) == 1  # loud: the check reds

    # When  the trigger's ignore list is checked against it
    ignored = _ci_yml_pull_request().get("paths-ignore") or []

    # Then  no ignore pattern swallows it, so a diff containing it keeps every job
    assert ignored, "ci.yml must carry the docs-class filter for this test to mean anything"
    assert not any(ci_scope._match(weird, pattern) for pattern in ignored), ignored


def test_each_class_has_one_must_run_and_one_must_not_run_row():
    """One row per class: the stage the class needs MUST run, a stage it cannot need MUST NOT."""

    # Given one representative path per class, with the stages that class must and must not select
    rows = {
        "skills": (".hermes/skills/issue-triage/SKILL.md",
                   {"linux/unit", "linux/agents-read", "engine-matrix"},
                   {"linux/openspec", "scanner-images", "engine-base"}),
        # `.github/**` is a WILDCARD: a workflow change must select every stage, so it has no MUST-NOT row
        "workflows": (".github/workflows/queued-alarm.yml",
                      {"linux/unit", "engine-matrix", "scanner-images", "linux/openspec"},
                      set()),
        "tests": ("tests/test_ci_scope.py",
                  {"linux/unit"},
                  {"engine-matrix", "scanner-images", "linux/openspec"}),
        "data": ("data/models.json",
                 {"linux/unit", "linux/install", "linux/top-tier"},
                 {"engine-base", "scanner-images"}),
        "containers": ("containers/test/Dockerfile",
                       {"linux/unit", "engine-matrix", "engine-base", "scanner-images"},
                       {"linux/openspec"}),
        "security": ("security-reports/scan.md",
                     {"scanner-images"},
                     {"engine-matrix", "linux/unit", "linux/top-tier"}),
    }
    for name, (path, must_run, must_not) in rows.items():
        # When  that single path is classified into its jobs
        selected = set(ci_scope.scope([path])["jobs"])
        # Then  the class is among those the path reaches (a `SKILL.md` is a markdown doc AND a skill),
        #       its stage runs, and the stage it cannot need does not
        assert name in ci_scope.scope([path])["classes"], (name, path)
        assert must_run <= selected, (name, must_run - selected)
        assert not (must_not & selected), (name, must_not & selected)


def test_markdown_outside_the_docs_paths_is_not_the_docs_class():
    """Markdown is not documentation by extension here — the case a `**/*.md` filter gets wrong."""

    # Given the three markdown files a `**/*.md` ignore list would silently skip, plus a real doc
    cases = {
        "data/trending-README.md": {"data"},                              # read by sync_registry.py
        ".hermes/skills/issue-triage/SKILL.md": {"skills"},                # the legs' contract
        "tests/fixtures/agents/happy_brief_rulebook.md": {"tests"},        # a unit fixture
        "docs/ARCHITECTURE.md": {"docs"},                                 # the one that IS a doc
    }
    for path, expected in cases.items():
        # When  classified
        got = set(ci_scope.scope([path])["classes"])
        # Then  only the class its location names — never `docs` by extension
        assert got == expected, (path, got)


def test_the_docs_class_is_exactly_the_trigger_list():
    """The workflow and the classifier must agree, or the printed selection lies about the trigger."""

    # Given the trigger's ignore list, the docs workflow's filter, and the classifier's class
    ignored = set(_ci_yml_pull_request().get("paths-ignore") or [])
    docs_filter = _docs_yml_paths()
    declared = set(ci_scope.CLASSES["docs"])

    # Then  all three are ONE decision: ci.yml ignores exactly what docs.yml runs exactly what the
    #       classifier prints. A drift in any pair makes the printed selection a lie about a trigger.
    assert ignored == declared, ("ci.yml vs CLASSES['docs']", ignored ^ declared)
    assert docs_filter == declared, ("docs.yml vs CLASSES['docs']", docs_filter ^ declared)


def test_an_unclassifiable_path_selects_every_job_and_still_fails(capsys):
    """Fail closed in both directions: the decision is the full pipeline AND the exit is non-zero."""

    # Given a path no class matches
    # When  the CLI is asked which jobs it needs
    rc = ci_scope.main(["jobs", "--paths", "some/unclassified/thing.xyz"])

    # Then  it selects everything (never an empty set) and still fails (never a quiet green)
    out = capsys.readouterr().out
    total = len(ci_scope.ALWAYS) + len(ci_scope.JOBS) + 1
    assert rc == 1, out
    assert "WIDE: path matches no class" in out, out
    assert f"jobs ({total} of {total})" in out, out
    assert set(ci_scope.scope(["some/unclassified/thing.xyz"])["jobs"]) < set(ci_scope.wide()["jobs"])


def test_the_make_target_surfaces_a_refusal_instead_of_going_green():
    """`scope.yml` runs `make ci-scope`: if the recipe swallowed the exit, an unreadable diff is green."""

    import subprocess

    # Given a BASE that cannot be diffed at all (a ref that does not exist)
    proc = subprocess.run(["make", "ci-scope", "BASE=refs/heads/no-such-ref"], cwd=REPO,
                          capture_output=True, text=True)

    # Then  the target surfaces the failure instead of a green with no decision in it
    assert proc.returncode != 0, (proc.returncode, proc.stdout[-400:])

    # And an empty diff is NOT that case: it widens and passes, because there is nothing to fix
    empty = subprocess.run(["python3", "scripts/ci_scope.py", "jobs", "--paths"], cwd=REPO,
                           capture_output=True, text=True)
    assert empty.returncode == 0, (empty.returncode, empty.stdout[-300:])


def test_every_detected_class_is_also_printed_as_a_greppable_line(capsys):
    """`scope.yml`'s header promises a `class=<name>` line per class: keep that promise true."""

    # Given a diff that touches two classes
    # neither path is a WILDCARD: `Makefile` and `scripts/**` select every class, which is a different test
    paths = ["docs/ARCHITECTURE.md", "data/models.json"]
    ci_scope.main(["jobs", "--paths", *paths])

    # Then  each detected class has its own `class=` line, and the summary still names them all
    out = capsys.readouterr().out
    detected = set(ci_scope.classify(paths))
    assert detected == {"data", "docs"}, detected
    for name in detected:
        assert f"[ci-scope] class={name}" in out, (name, out)
    assert "classes: data, docs" in out, out


def test_the_reporting_check_survives_the_events_that_carry_no_pr():
    """`scope` is legibility: a merge-queue ref, a force-push or a dispatch must still report (#824)."""

    import yaml

    doc = yaml.safe_load((REPO / ".github/workflows/scope.yml").read_text())
    on = doc.get("on") if "on" in doc else doc.get(True)

    # Then  all three events are wired, and none of them filters by path - a filtered reporter
    #       disappears exactly on the unusual diff, which is when a reader needs it most
    assert set(on) == {"pull_request", "merge_group", "workflow_dispatch"}, sorted(on)
    for event, cfg in on.items():
        cfg = cfg or {}
        assert "paths" not in cfg and "paths-ignore" not in cfg, (event, cfg)

    # And the steps do not depend on `github.base_ref` existing: a dispatch and a merge-queue ref
    # have none, and an empty ref makes `git diff <base>...HEAD` fail - a failing reporter is not a report
    steps = doc["jobs"]["scope"]["steps"]
    body = "\n".join(step.get("run", "") for step in steps)
    assert "${EVENT_BASE_REF:-main}" in body, body
    assert "No github.base_ref for event" in body, body


def test_a_blank_path_entry_is_the_same_as_no_diff_at_all(capsys):
    """`--paths "$CHANGED"` with an empty variable is a shell artifact, not an unclassifiable path."""

    # Given a literally empty path entry (the shape an unquoted/empty variable produces)
    rc = ci_scope.main(["jobs", "--paths", ""])

    # Then  it is the empty-diff case: widen, and pass - never a red a human cannot act on
    out = capsys.readouterr().out
    total = len(ci_scope.ALWAYS) + len(ci_scope.JOBS) + 1
    assert rc == 0, out
    assert f"jobs ({total} of {total})" in out, out
    assert "WIDE: empty diff" in out, out


def test_a_blank_entry_does_not_hide_a_real_unknown_path():
    """Whitespace is dropped; a real unclassifiable path next to it still fails the run."""

    assert ci_scope.main(["jobs", "--paths", "", "  ", "nope/x.xyz"]) == 1
