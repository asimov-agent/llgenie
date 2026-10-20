#!/usr/bin/env python3
"""A committed credential VALUE is caught — and the scanner is proven able to catch one (issue #360).

`make check-secret-output` reads the SHAPES a script prints; `make secret-scan` reads the VALUE a human
or a bot committed, which a shape rule cannot see (a PAT, a JWT, an AWS-style key, a bearer inside a
URL). `make secret-scan-history` reads the history, and `make secret-scan-self-test` plants a fake
credential and requires the scan to fail — a scanner that silently does nothing is a false green.

This suite is hermetic (it needs no container): it pins the configuration and the wiring that make the
three targets real, and the scan itself runs in CI's linux job (`make secret-scan`,
`make secret-scan-self-test`). NO-SKIP POLICY: every case runs a real assertion; none is skipped.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / ".gitleaks.toml"
SELF_TEST = REPO / "scripts" / "secret_scan_self_test.py"
WORKFLOW = REPO / ".github" / "workflows" / "pipeline.yml"

sys.path.insert(0, str(REPO / "scripts"))
import check_secret_output as cso  # noqa: E402


# ---------------------------------------------------------------------------
# the configuration: it must actually scan, and it must not allowlist a live value
# ---------------------------------------------------------------------------
def test_the_config_extends_the_default_rule_set():
    """`[extend] useDefault = true` is what makes the scanner use gitleaks' own rules.

    A config without it scans nothing and exits zero on a tree full of live keys — the false green
    this whole change exists to prevent.
    """
    # Given the repository's gitleaks config
    text = CONFIG.read_text()

    # Then  it extends the default rules, and it does not define rules of its own that replace them
    assert "[extend]" in text and "useDefault = true" in text, text
    assert "[[rules]]" not in text, "a custom rule set replaces the defaults; extend them instead"


def test_every_allowlist_entry_is_a_documented_non_live_path():
    # Given the allowlist entries
    text = CONFIG.read_text()

    # Then  each path is one of the files that deliberately carry a non-live shape
    allowed = {
        r"scripts/check_secret_output\.py$",
        r"tests/test_secret_output\.py$",
        r"tests/test_scrub_log\.py$",
        r"tests/test_secret_scan\.py$",
        r"tests/test_agent_nerve\.py$",
    }
    paths = set(re.findall(r"'''(.*?)'''", text.split("[[allowlists]]", 1)[1]))
    path_entries = {p for p in paths if "\\." in p or p.endswith("$")}
    unexpected = path_entries - allowed
    assert not unexpected, f"the scanner allowlists a path nobody reviewed: {sorted(unexpected)}"

    # And a live value can never be allowlisted by shape: no allowlist may name a real token prefix
    for entry in paths:
        assert not re.search(r"ghp_|github_pat_|sk-[A-Za-z0-9]{10,}", entry), entry


def test_the_self_test_plants_a_value_without_committing_one():
    """The plant is built from parts, so this repository carries no credential-shaped literal."""
    # Given the self-test script's source
    text = SELF_TEST.read_text()

    # Then  it assembles the plant at run time and the guard's own shape rule does not match it
    assert "PLANT = " in text and "+" in text.split("PLANT = ", 1)[1].splitlines()[0], text
    assert not cso.KEY_SHAPED.search(text), "the self-test commits a credential-shaped literal"


# ---------------------------------------------------------------------------
# the wiring: three targets, and the job that runs them
# ---------------------------------------------------------------------------
def test_the_three_targets_exist_and_name_real_inputs():
    mk = (REPO / "Makefile").read_text()
    scanner = (REPO / "scripts" / "secret_scan.py").read_text()

    # Then a working-tree scan, a history scan and a self-test exist
    for target in ("secret-scan:", "secret-scan-history:", "secret-scan-self-test:"):
        assert re.search(rf"(?m)^{re.escape(target)}", mk), f"{target} is missing"

    # And the working-tree scan runs the committable-set scanner (issue #382), which carries the
    # pinned image, the repository config and `--redact` — the scan's inputs live in ONE place.
    assert "python3 scripts/secret_scan.py" in mk
    assert "ghcr.io/gitleaks/gitleaks:v8.30.1" in scanner
    assert "dir" in scanner and "--redact" in scanner and "--no-banner" in scanner
    assert CONFIG.name in scanner, "the scanner must run the repository's own config"
    # And the history scan still uses the pinned image + config directly (it reads .git, not a tree)
    assert "ghcr.io/gitleaks/gitleaks:v8.30.1" in mk
    assert "--config /repo/.gitleaks.toml" in mk and "--redact" in mk
    assert "python3 scripts/secret_scan_self_test.py" in mk

    # And the history scan refuses a worktree instead of reporting an unread history
    assert "if [ -f .git ]" in mk and "needs a real clone" in mk


# ---------------------------------------------------------------------------
# the committable set (issue #382): ignored paths are not scanned
# ---------------------------------------------------------------------------
def test_the_committable_set_excludes_ignored_paths(tmp_path):
    """The regression: `gitleaks dir` walked `tests/__pycache__/*.pyc` and reported the suites' own
    sentinels on a clean tree. The set must be what `git add` would take, nothing else."""

    sys.path.insert(0, str(REPO / "scripts"))
    import secret_scan

    # Given a real git checkout with a tracked file, a fresh untracked file, and an ignored artifact
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitignore").write_text("__pycache__/\n")
    (root / "tracked.txt").write_text("tracked\n")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "planted.pyc").write_text("ignored artifact\n")

    # When  the committable set is computed by the real git
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=root, check=True)
    (root / "fresh.txt").write_text("fresh\n")
    names = secret_scan.committable(root)

    # Then  the tracked and the fresh untracked file are in it ...
    assert "tracked.txt" in names and "fresh.txt" in names and ".gitignore" in names, names

    # ... and the ignored artifact is NOT — a credential there is not a leak of this repository
    assert not [n for n in names if n.startswith("__pycache__")], names


def test_no_ignored_path_is_in_the_real_committable_set():
    """Every path the scan reads is one git would accept, so the command the README documents stops
    reporting findings for files nobody can commit."""

    sys.path.insert(0, str(REPO / "scripts"))
    import secret_scan

    # Given the real checkout's committable set
    names = secret_scan.committable(REPO)

    # Then  it is not empty, carries the repository's own files, and holds no ignored path
    assert len(names) > 50, f"only {len(names)} files — the set looks broken, not clean"
    assert "Makefile" in names and ".gitleaks.toml" in names, "the config must be in the set"
    ignored = []
    for name in names:
        r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", name], capture_output=True)
        if r.returncode == 0:
            ignored.append(name)
    assert not ignored, f"the scan would read ignored paths: {ignored[:10]}"


def test_the_wrapper_separates_a_finding_from_a_scan_that_could_not_run():
    """A scanner that cannot run produced NO verdict: it must never be reported as "a credential is
    present", and never as clean (issue #382 — the exit code is the signal)."""

    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("\nsecret-scan:", 1)[1].split("\n\n", 1)[0]

    # Then the finding case is exit 1, named as a credential ...
    assert "if [ $$rc -eq 1 ]" in recipe, recipe
    assert "SECRET SCAN FAILED: a credential shape is present in the working tree." in recipe
    # ... and every other non-zero exit says the scan could NOT run, and never claims a clean tree
    assert "elif [ $$rc -ne 0 ]" in recipe, recipe
    assert "COULD NOT RUN" in recipe and "NO verdict" in recipe
    assert "not a finding" in recipe


def test_ci_runs_the_scan_and_its_self_test_on_linux():
    text = WORKFLOW.read_text()

    # Then the linux job runs both …
    for cmd in ("make secret-scan", "make secret-scan-self-test"):
        assert cmd in text, f"CI never runs `{cmd}`"
        line = next(i for i, l in enumerate(text.splitlines()) if l.strip().endswith(cmd))
        block = "\n".join(text.splitlines()[max(0, line - 2):line + 4])

        # … and only where a container engine exists (the macOS job has none)
        assert "runner.os == 'Linux'" in block, block

    # And the guard this scan complements is still run by ci-unit
    assert "check-secret-output" in text or "ci-unit" in text
