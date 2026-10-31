"""Template: pin a workflow step's BEHAVIOUR by executing it, not by grepping its text.

Copy into `tests/` (or run standalone inside the test image) and adapt. The step's `run:` body is
lifted out of the workflow YAML and executed with the downstream commands STUBBED on PATH, so the
assertions are about what the step actually did — the argv a command received and the line it printed —
and survive any re-spelling of the shell code.

Why this shape: `assert "…shell text…" in step["run"]` reds a correct rewrite while the property it
defends is unchanged, and passes a rewrite that breaks the step at runtime (e.g. `"$VAR"` under
`set -u`). See `references/ci-job-selection.md` and the SKILL.md pitfall *Pin a workflow's BEHAVIOUR*.

Adapt the three property tests to the step under test; keep the two mutation helpers — they are the
proof that the pin is worth having.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]          # .../repo
WORKFLOW = REPO / ".github/workflows/scope.yml"              # <- the workflow under test
JOB = "scope"                                                # <- the job key
STEP_MATCH = "ci-scope"                                      # <- substring of the step's `name:`
STUBBED = ("git", "make")                                    # <- commands to fake; extend as needed


def _step_body() -> str:
    """The `run:` body of the step, read from the workflow (no copies of the shell code anywhere)."""
    doc = yaml.safe_load(WORKFLOW.read_text())
    for step in doc["jobs"][JOB]["steps"]:
        if STEP_MATCH in (step.get("name") or ""):
            return step["run"]
    raise AssertionError(f"no step named *{STEP_MATCH}* in {WORKFLOW.name}:{JOB}")


def _run(body: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Execute a step body with the downstream commands stubbed; return (rc, output, recorded argv)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        argv_log = tmp / "stub.argv"
        for name in STUBBED:
            stub = bin_dir / name
            stub.write_text(f'#!/bin/sh\necho "$0 $*" >> "{argv_log}"\nexit 0\n')
            stub.chmod(0o755)
        base_env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(tmp),
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_OUTPUT": str(tmp / "out"),
        }
        base_env.update(env or {})
        proc = subprocess.run(["/bin/bash", "-c", body], cwd=tmp, env=base_env,
                              capture_output=True, text=True)
        return (proc.returncode, proc.stdout + proc.stderr,
                argv_log.read_text() if argv_log.exists() else "")


def test_resolution_without_the_optional_input():
    """Property 1: an unset input resolves to the documented default, visible in the argv."""
    rc, out, argv = _run(_step_body(), {"EVENT_BASE_REF": ""})
    assert rc == 0, out
    assert "BASE=origin/main" in argv, argv


def test_visibility_of_the_fallback():
    """Property 2: the step SAYS it fell back ('No github.base_ref for event …'), never silently."""
    rc, out, _ = _run(_step_body(), {"EVENT_BASE_REF": ""})
    assert rc == 0, out
    assert "No github.base_ref for event" in out, out


def test_a_supplied_value_is_used_verbatim():
    """Property 3: the inverse. A fallback that always said `main` passes 1 and 2 and is still wrong."""
    rc, out, argv = _run(_step_body(), {"EVENT_BASE_REF": "release/1.x"})
    assert rc == 0, out
    assert "BASE=origin/release/1.x" in argv, argv
    assert "No github.base_ref for event" not in out, out


# --- the two mutations that prove the pin is worth having -------------------------------------------
def test_behaviour_removed_reds():
    """Drop the fallback: the property tests above must be able to see it."""
    body = _step_body().replace('BASE_REF="${EVENT_BASE_REF:-main}"', 'BASE_REF="${EVENT_BASE_REF:-}"')
    _, _, argv = _run(body, {"EVENT_BASE_REF": ""})
    assert "BASE=origin/main" not in argv, argv


def test_respelling_stays_green():
    """Only the spelling changes: the suite must NOT red a correct rewrite."""
    respelled = _step_body().replace(
        'BASE_REF="${EVENT_BASE_REF:-main}"',
        'BASE_REF="${EVENT_BASE_REF:-}"\n'
        'if [ -z "$BASE_REF" ]; then\n'
        '  echo "No github.base_ref for event ${GITHUB_EVENT_NAME}: reporting the diff against main."\n'
        '  BASE_REF=main\n'
        'fi')
    rc, out, argv = _run(respelled, {"EVENT_BASE_REF": ""})
    assert rc == 0, out
    assert "BASE=origin/main" in argv, argv
