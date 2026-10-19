"""Do we have a test that no secret VALUE is printed? Yes — for every key, not just the JEV one.

`scripts/check_secret_output.py` is the guard; this file is its proof. Every rule is broken on a
fixture file (one violation, the right rule id), and the guard is then run over THIS repository,
because a rule the repo itself violates is not a rule.

secret-output: test value — the marker this fixture file carries: the credential-shaped strings
below are deliberate, non-live test values, which is exactly what the marker in the guard is for.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_secret_output as cso  # noqa: E402


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return root


def _rules(root: Path) -> list[str]:
    return [v.split(": ", 1)[1].split(" —")[0] for v in cso.violations(root)]


# ---------------------------------------------------------------------------
# rule: secrets-in-run-block
# ---------------------------------------------------------------------------
def test_a_secret_interpolated_into_a_run_block_is_a_violation(tmp_path):
    root = _tree(tmp_path, {".github/workflows/a.yml": """
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: |
          curl -H "Authorization: Bearer ${{ secrets.HF_TOKEN }}" https://example.invalid
"""})
    assert _rules(root) == ["secrets-in-run-block"], cso.violations(root)


def test_a_secret_passed_through_env_is_not_a_violation(tmp_path):
    root = _tree(tmp_path, {".github/workflows/a.yml": """
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: make something
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
"""})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: prints-secret-value
# ---------------------------------------------------------------------------
def test_echoing_a_secret_value_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\necho "token: $HF_TOKEN"\n'})
    assert _rules(root) == ["prints-secret-value"], cso.violations(root)


def test_printing_the_name_and_guarding_on_it_is_not_a_violation(tmp_path):
    """The repo's own guard shape: it fails when the key is missing and prints only the NAME."""
    root = _tree(tmp_path, {"s.sh": '''#!/usr/bin/env bash
set -euo pipefail
test -n "$NOUS_API_KEY" || { echo "NOUS_API_KEY unset - refusing to spend time on a dead key"; exit 1; }
'''})
    assert cso.violations(root) == []


def test_writing_a_secret_to_a_file_is_not_a_violation(tmp_path):
    """`>> \"$HERMES_HOME/.env\"` is where a key IS allowed to live (mode 600), not output."""
    root = _tree(tmp_path, {"s.sh": '''#!/usr/bin/env bash
printf '%s=%s\\n' "TYPESAFE_API_KEY" "$TYPESAFE_API_KEY" >> "${HERMES_HOME}/.env"
'''})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: xtrace-with-secrets
# ---------------------------------------------------------------------------
def test_xtrace_in_a_file_that_reads_a_secret_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\nset -eux\nmake deploy TOKEN="$BUMP_TOKEN"\n'})
    assert "xtrace-with-secrets" in _rules(root), cso.violations(root)


def test_no_xtrace_is_not_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\nset -euo pipefail\nmake deploy TOKEN="$BUMP_TOKEN"\n'})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: value-in-argv
# ---------------------------------------------------------------------------
def test_a_secret_value_on_the_command_line_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\ndocker run -e HF_TOKEN=$HF_TOKEN img true\n'})
    assert _rules(root) == ["value-in-argv"], cso.violations(root)


def test_passing_the_name_only_is_not_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\ndocker run -e HF_TOKEN -e NOUS_API_KEY img true\n'})
    assert cso.violations(root) == []


def test_a_secret_expression_on_the_command_line_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\ndocker run -e HF_TOKEN=${{ secrets.HF_TOKEN }} img true\n'})
    assert _rules(root) == ["value-in-argv"], cso.violations(root)


# ---------------------------------------------------------------------------
# rule: secrets-in-run-block, GitHub's own token (issue #361)
# ---------------------------------------------------------------------------
def test_github_token_in_a_run_block_is_a_violation(tmp_path):
    expr = "$" + "{{ github.token }}"
    root = _tree(tmp_path, {".github/workflows/a.yml": f"""
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: |
          gh api /user -H "Authorization: Bearer {expr}"
"""})
    assert _rules(root) == ["secrets-in-run-block"], cso.violations(root)


def test_bracketed_github_token_in_a_run_block_is_a_violation(tmp_path):
    expr = "$" + "{{ github['token'] }}"
    root = _tree(tmp_path, {".github/workflows/a.yml": f"""
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: |
          curl -H "Authorization: {expr}" https://example.invalid
"""})
    assert _rules(root) == ["secrets-in-run-block"], cso.violations(root)


def test_github_token_passed_through_env_is_not_a_violation(tmp_path):
    expr = "$" + "{{ github.token }}"
    root = _tree(tmp_path, {".github/workflows/a.yml": f"""
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - env:
          GH_TOKEN: {expr}
        run: gh api /user
"""})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: whole-stdout-into-output-file (issue #361)
# ---------------------------------------------------------------------------
def test_a_pipeline_into_github_output_is_a_violation(tmp_path):
    root = _tree(tmp_path, {".github/workflows/a.yml": """
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - id: x
        run: make plan | python3 -c 'import sys' >> "$GITHUB_OUTPUT"
"""})
    assert _rules(root) == ["whole-stdout-into-output-file"], cso.violations(root)


def test_a_substitution_into_github_output_is_a_violation(tmp_path):
    root = _tree(tmp_path, {".github/workflows/a.yml": """
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - id: x
        run: $(make plan) >> "$GITHUB_OUTPUT"
"""})
    assert _rules(root) == ["whole-stdout-into-output-file"], cso.violations(root)


def test_a_quoted_computed_key_value_is_not_a_violation(tmp_path):
    """The safe shape: the pipe is INSIDE the quoted argument, so the file gets one literal."""
    root = _tree(tmp_path, {".github/workflows/a.yml": """
name: a
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - id: x
        run: |
          echo "matrix=$(make plan | python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin)))')" >> "$GITHUB_OUTPUT"
"""})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: whole-stdout-into-log (issue #361)
# ---------------------------------------------------------------------------
def test_tee_into_the_job_log_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": "#!/usr/bin/env bash\nmake run | tee /dev/stderr\n"})
    assert _rules(root) == ["whole-stdout-into-log"], cso.violations(root)


def test_tee_into_a_file_is_not_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": "#!/usr/bin/env bash\nmake run | tee /tmp/out.log\n"})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: env-dump
# ---------------------------------------------------------------------------
def test_a_bare_environment_dump_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.sh": "#!/usr/bin/env bash\nenv\n"})
    assert _rules(root) == ["env-dump"], cso.violations(root)


def test_python_reading_os_environ_is_not_a_violation(tmp_path):
    root = _tree(tmp_path, {"s.py": "import os\nenv = os.environ if os.environ else {}\n"})
    assert cso.violations(root) == []


# ---------------------------------------------------------------------------
# rule: key-shaped-literal
# ---------------------------------------------------------------------------
def test_a_credential_shaped_literal_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"cfg.py": 'TOKEN = "hf_' + "A1b2C3d4E5f6G7h8I9j0K1l2M3" + '"\n'})
    assert _rules(root) == ["key-shaped-literal"], cso.violations(root)


def test_a_fixture_name_that_merely_starts_like_a_token_is_not_a_violation(tmp_path):
    """Measured: the loose pattern flagged 13 such names (`hf_get_wrapped`, `hf_download_stall`)."""
    root = _tree(tmp_path, {"t.py": 'NAME = "hf_download_stall"\nOTHER = "hf_get_wrapped"\n'})
    assert cso.violations(root) == []


def test_the_marker_declares_deliberate_test_values(tmp_path):
    # this file itself carries the marker (see the module docstring), so use a copy of it
    body = (REPO / "tests" / "test_secret_output.py").read_text()
    assert cso.TEST_VALUE_MARKER in body
    root = _tree(tmp_path, {"t.py": 'TOKEN = "hf_' + "A1b2C3d4E5f6G7h8I9j0K1l2M3" + '"\n'})
    marked = _tree(tmp_path / "marked", {"t.py": f"# {cso.TEST_VALUE_MARKER}\n"
                                                 'TOKEN = "hf_' + "A1b2C3d4E5f6G7h8I9j0K1l2M3" + '"\n'})
    assert _rules(root) == ["key-shaped-literal"]
    assert cso.violations(marked) == []


# ---------------------------------------------------------------------------
# the guard over THIS repository, and the exit code CI gates on
# ---------------------------------------------------------------------------
def test_this_repository_never_prints_a_secret_value():
    assert cso.violations(REPO) == [], cso.violations(REPO)
    assert cso.main(["check"]) == 0


def test_the_report_lists_the_files_that_name_a_secret():
    rows = cso.report(REPO)
    files = {r["file"] for r in rows}
    # the bot workflows and the image's install scripts are the ones that carry keys
    for name in (".github/workflows/issue-bot.yml", ".github/workflows/fix-bot.yml",
                 "scripts/agent_jev_preflight.sh", "scripts/install_nerve_ci.sh", "Makefile"):
        assert name in files, f"{name} should name a secret variable"
    assert all(r["prints"] is False for r in rows), [r for r in rows if r["prints"]]
    assert all(r["xtrace"] is False for r in rows), [r for r in rows if r["xtrace"]]


def test_check_exits_non_zero_on_a_violation(tmp_path, capsys):
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\necho "$HF_TOKEN"\n'})
    assert cso.main(["check", "--root", str(root)]) == 1
    assert "prints-secret-value" in capsys.readouterr().err

    clean = _tree(tmp_path / "clean", {"s.sh": '#!/usr/bin/env bash\necho "HF_TOKEN unset"\n'})
    assert cso.main(["check", "--root", str(clean)]) == 0


def test_the_guard_is_wired_into_the_repo():
    """A guard no target names runs nowhere: the make target, .PHONY, help, CI job and the test."""
    mk = (REPO / "Makefile").read_text()
    assert "check-secret-output:" in mk
    assert "check-secret-output" in mk.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "make check-secret-output" in mk.split("\nhelp:", 1)[1]
    ci_unit = mk.split("\nci-unit:", 1)[1].split("\n\n", 1)[0]
    assert "check-secret-output" in ci_unit, "ci-unit must run the guard"
    assert "tests/test_secret_output.py" in mk.split("\ntest-unit:", 1)[1].split("\n\n", 1)[0]


def test_the_secret_list_matches_the_repo_secrets():
    """Issue #311: SECRET_VARS named two provider keys the repo does not define, so the guard scanned
    for a leak of a variable that can never carry a value. The list must be the credential variables
    this repo actually uses — both the ones a workflow reads and the ones the Makefile forwards to the
    agent (`AGENT_SHELL_KEYS`). Issue #379: FIRECRAWL_API_KEY was forwarded to the agent but absent
    here, so a printed value was green and the redactor did not mask it."""

    # Given the secret-output guard's list
    # When it is read
    # Then it drops the unused provider keys ...
    assert "TYPESAFE_API_KEY" in cso.SECRET_VARS, cso.SECRET_VARS
    assert "FIRECRAWL_API_KEY" in cso.SECRET_VARS, cso.SECRET_VARS
    assert "OPENROUTER_API_KEY" not in cso.SECRET_VARS, cso.SECRET_VARS
    assert "OPENCODE_API_KEY" not in cso.SECRET_VARS, cso.SECRET_VARS

    # ... and every secret a workflow actually reads is still in the list (a leak of it IS scanned)
    named: set[str] = set()
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = "\n".join(line for line in path.read_text().splitlines()
                          if not line.strip().startswith("#"))
        named |= set(re.findall(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text))

    # ... and every credential the Makefile FORWARDS to the agent is too: the forwarded list is what
    # the agent's shell receives, and the guard/redactor are the only thing that scans it.
    mk = "\n".join(line for line in (REPO / "Makefile").read_text().splitlines()
                   if not line.strip().startswith("#"))
    m = re.search(r"^AGENT_SHELL_KEYS\s*:?=\s*(.+)$", mk, re.MULTILINE)
    assert m, "AGENT_SHELL_KEYS is gone from the Makefile — the forwarding seam expects it"
    named |= set(m.group(1).split())

    missing = sorted(n for n in named if n not in cso.SECRET_VARS)
    assert not missing, f"the repo names {missing}, which the secret-output guard does not scan"


def test_a_printed_firecrawl_value_is_a_finding(tmp_path):
    """Issue #379: FIRECRAWL_API_KEY is forwarded to the agent, so printing it must be a finding."""

    # Given a script that prints the Firecrawl key's value
    root = _tree(tmp_path, {"s.sh": '#!/usr/bin/env bash\necho "key: $FIRECRAWL_API_KEY"\n'})

    # When  the guard scans it
    # Then  the printed value is the violation the other credentials already get
    assert _rules(root) == ["prints-secret-value"], cso.violations(root)
