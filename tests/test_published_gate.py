"""`linux-published / install-published-*` runs only when this run actually pushed an image (#844).

Four install jobs used to start on every pull request, installing *published* images from GHCR and
re-proving the registry's contents on a diff that never pushed anything: four runners x ~6 minutes per
PR, and a green that could not have been red. The gate is the producer's own answer - `pushed` from the
job that resolves the engine rows - never the diff.

The shape is #828's `none` placeholder plus #824's "every check name still exists": a matrix that
resolves to one `none` row instead of the four, steps gated on the row (never a job-level `if:`), and an
unconditional first step that says in the log why the row installed nothing.
"""

from __future__ import annotations

import sys

import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CI = REPO / ".github/workflows/ci.yml"
PUBLISHED = REPO / ".github/workflows/published.yml"

FOUR = ["cpu", "cuda", "rocm", "vulkan"]


def _wf(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _on(doc: dict) -> dict:
    return doc.get("on") if "on" in doc else doc.get(True)


def _published_job() -> dict:
    return _wf(PUBLISHED)["jobs"]["install-published"]


def test_the_install_rows_are_selected_by_the_pushed_output():
    """The matrix is the producer's `pushed`, not a path filter and not a job-level `if:`."""

    job = _published_job()

    # Given the published workflow's only job
    # When  its matrix is read as text (GitHub expressions are not evaluated here, the shape is)
    matrix = job["strategy"]["matrix"]
    expression = str(matrix.get("backend") if isinstance(matrix, dict) else matrix)

    # Then  it selects the four backends ONLY on `pushed == 'true'`, and the `none` placeholder otherwise
    assert "inputs.pushed == 'true'" in expression, expression
    assert all(f'"{backend}"' in expression for backend in FOUR), expression
    assert '["none"]' in expression, expression


def test_the_pushed_input_is_declared_and_defaults_to_false():
    """A caller that says nothing gets the placeholder, not four runners: fail closed, cheaply."""

    inputs = _on(_wf(PUBLISHED))["workflow_call"]["inputs"]

    assert "pushed" in inputs, sorted(inputs)
    assert str(inputs["pushed"].get("default")) == "false", inputs["pushed"]


def test_no_install_job_is_gated_by_a_job_level_if():
    """`test_no_ci_step_or_job_is_skipped`'s rule: the family must report on every event."""

    job = _published_job()

    assert "if" not in job, "a job-level if: makes the whole check name disappear"
    assert job["name"] == "install-published-${{ matrix.backend }}", job["name"]


def test_the_none_row_states_its_reason_in_the_log():
    """A skipped row that says nothing is the failure mode this repository keeps paying for."""

    steps = _published_job()["steps"]

    # Then  the FIRST step is unconditional and names both states
    first = steps[0]
    assert "if" not in first, "the reason must be printed whether the row runs or not"
    body = first["run"]
    assert "no image pushed in this run" in body, body
    assert "pushed=${{ inputs.pushed }}" in body, body
    assert "none" in body, body


def test_every_real_step_is_skipped_on_the_none_row_only():
    """The placeholder row must do no work; the four real rows must do all of it."""

    steps = _published_job()["steps"][1:]  # the reason step has no gate by design

    for step in steps:
        # `always()` is the container-cleanup step: it must run on both rows and installs nothing
        assert step.get("if") in ("${{ matrix.backend != 'none' }}", "always()"), step.get("name") or step
    # the work steps (checkout, disk, docker, login, env, ci-engines) are all gated on the row
    assert sum(1 for step in steps if step.get("if") == "${{ matrix.backend != 'none' }}") >= 6, (
        "every step that does real work must be gated on the row")


def test_ci_feeds_the_output_from_the_job_that_resolves_the_rows():
    """`pushed` comes from `engine-matrix`, resolved once - a matrix job cannot aggregate its legs."""

    ci = _wf(CI)
    matrix_job = ci["jobs"]["engine-matrix"]
    published = ci["jobs"]["linux-published"]

    # Then  the producer publishes the output …
    assert matrix_job["outputs"]["pushed"] == "${{ steps.m.outputs.pushed }}", matrix_job["outputs"]
    # … its step writes it next to the matrix, by ASKING the script that owns the decision …
    step = next(s for s in matrix_job["steps"] if s.get("id") == "m")
    assert "scripts/engine_matrix_pushed.py" in step["run"], step["run"]
    assert '--event "${{ github.event_name }}"' in step["run"], step["run"]
    assert '--matrix "$matrix"' in step["run"], step["run"]
    assert 'echo "pushed=$(python3 scripts/engine_matrix_pushed.py' in step["run"], step["run"]
    # … and the consumer needs that job and passes the output through, with a fail-closed default.
    assert "engine-matrix" in published["needs"], published["needs"]
    assert published["with"]["pushed"] == "${{ needs.engine-matrix.outputs.pushed || 'false' }}", published["with"]


# ---------------------------------------------------------------------------------------------------
# The decision itself, run for real (issue #844). A string match on the YAML pinned the shape; these
# pin the behaviour, including the two directions of "fail closed".
sys.path.insert(0, str(REPO / "scripts"))
import engine_matrix_pushed as emp  # noqa: E402

REAL = '{"include": [{"engine": "vllm", "variant": "cuda"}, {"engine": "llama.cpp", "variant": "cpu"}]}'
NONE_ROW = '{"include": [{"engine": "none", "variant": "none"}]}'


def test_a_pull_request_never_pushes_however_many_rows_it_builds():
    """The 4 install jobs were starting on docs-only PRs: a PR builds, it does not publish."""
    assert emp.pushed("pull_request", REAL) is False


def test_a_push_with_a_real_row_pushes():
    """The `when` the owner asked for: an actual build on main means the installs must run."""
    assert emp.pushed("push", REAL) is True


def test_a_push_whose_matrix_is_only_the_none_placeholder_pushes_nothing():
    """#828's placeholder skips every step in engine-image, so there is no image to install."""
    assert emp.pushed("push", NONE_ROW) is False


def test_an_unreadable_matrix_keeps_the_installs_rather_than_skipping_them():
    """Fail closed: a parse error is not evidence that nothing was pushed."""
    assert emp.pushed("push", "not json") is True


def test_an_empty_matrix_is_no_rows_and_therefore_no_push():
    """An empty matrix is not a parse error: no rows means engine-image never ran, so nothing pushed."""
    assert emp.pushed("push", "") is False
    assert emp.pushed("push", "{}") is False


def test_the_cli_prints_the_value_the_workflow_writes_into_github_output():
    """`ci.yml` captures this exact stdout into $GITHUB_OUTPUT; `published.yml` compares it to 'true'."""
    import subprocess

    out = subprocess.run([sys.executable, str(REPO / "scripts/engine_matrix_pushed.py"),
                          "--event", "push", "--matrix", REAL],
                         capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "true", (out.returncode, out.stdout, out.stderr)


def test_the_documentation_and_the_log_line_cannot_drift_apart():
    """The doc claims a skipped row says why; the row's own first step is the source of that string."""

    docs = (REPO / "docs/BOTS.md").read_text()
    reason_line = _published_job()["steps"][0]["run"]

    # Then  the exact phrase the workflow prints is the one the documentation promises
    assert "install-published-none: SKIPPED - no image pushed in this run" in reason_line, reason_line
    assert "install-published-none: SKIPPED - no image pushed in this run" in docs, (
        "docs/BOTS.md describes the skipped row differently from what the row prints")


def test_the_none_row_does_not_run_the_engine_cleanup():
    """Measured 2026-10-28: the row failed in 4 s on the cleanup step, after doing nothing else."""

    steps = _published_job()["steps"]
    cleanup = next(s for s in steps if "Prune orphaned test containers" in (s.get("name") or ""))

    # Then  the row decision is in the shell, not in a compound `if:` (which the repo forbids)
    assert cleanup["if"] == "always()", cleanup
    body = cleanup["run"]
    assert '"none"' in body and "exit 0" in body, body
    assert "make test-clean" in body, body
