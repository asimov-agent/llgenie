"""Stray run-artifact gate (issue #2484): a committed `*.log` or dot-scratch file must never merge.

`.unit2.log` (10 bytes) and `.pr874.md` (3,221 bytes) rode two PRs (#2277, #1738) to `main`
because no gate rejected a committed runtime artifact. These tests hold the gate's seams and the
acceptance criteria:

1. `.gitignore` carries a blanket `*.log` rule and `git check-ignore` answers for a new
   `.foo.log`, while a valued hidden file (`.env.example`) stays trackable;
2. `.unit2.log` / `.pr874.md` are no longer tracked (the forward `git rm` removal);
3. a planted tracked `*.log` or `.<word><digits>.<ext>` file is refused, naming the path;
4. only *tracked* files are scanned (an ignored, unstaged `.foo.log` is not a finding);
5. a dated exception honors an intentional match, and an exception whose file is gone or no
   longer matches is STALE and fails;
6. the gate is a `ci-unit` target and a `FAST_GATES` gate, so the unit lane and `make
   lane-preflight` both reach it.

Each scan test builds a tiny real git repo (the gate reads `git ls-files`), like the empty-file
gate's tests. None is skipped.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from scripts import check_file_hygiene as gate

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = (REPO / "Makefile").read_text()
#: The Makefile was split into fragments (`mk/*.mk`, issue #2457), so a target may live in a
#: fragment, not the root file. Wiring tests must read the ASSEMBLED make text the way `make`
#: does — root Makefile plus every `mk/*.mk` it includes.
MAKE_TEXT = MAKEFILE + "\n" + "\n".join(
    p.read_text() for p in sorted((REPO / "mk").glob("*.mk"))
)
FAST = (REPO / "scripts" / "issue_bot_gates.py").read_text()
GITIGNORE = (REPO / ".gitignore").read_text()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def make_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    exceptions = tmp_path / "exceptions.json"
    exceptions.write_text(json.dumps({"files": {}}))
    return root, exceptions


def _find(root: Path, exceptions: Path) -> list[str]:
    return [i["where"] for i in gate.findings(root, str(exceptions))]


# --- .gitignore is categorical, not a blacklist -------------------------------------------
def test_bare_a_dot_foo_log_is_ignored_by_real_git():
    """The blanket `*.log` rule: an arbitrary new `.foo.log` is ignored by git itself."""

    # Given the repository's .gitignore with the blanket rule committed on this branch
    assert GITIGNORE is not None

    # When  git is asked whether a new `.foo.log` (never enumerated) is ignored
    rc = _git(REPO, "check-ignore", "-q", ".foo.log").returncode

    # Then  it is ignored — a new log name cannot become committable without an ignore edit
    assert rc == 0


def test_bare_a_valued_hidden_file_stays_trackable():
    """The dot-scratch rule must not catch `.env.example` (a documented template)."""

    # Given the blanket `*.log` + dot-scratch rules
    # When  git is asked whether a valued hidden file with no digits is ignored
    rc = _git(REPO, "check-ignore", "-q", ".env.example").returncode

    # Then  it is NOT ignored — the categorical rule is narrow, not a catch-all dot blacklist
    assert rc != 0


# --- the two tracked artifacts are gone (forward removal) --------------------------------
def test_bare_the_named_artifacts_are_not_tracked():
    """`.unit2.log` and `.pr874.md` are removed from this checkout's index."""

    # Given the issue measured both as tracked on main
    # When  the current tree's tracked files are listed
    tracked = subprocess.run(  # proc-allow: test-only direct subprocess, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True).stdout

    # Then  neither stray artifact is tracked any more
    assert ".unit2.log" not in tracked
    assert ".pr874.md" not in tracked


# --- the gate refuses planted violations -------------------------------------------------
def test_a_tracked_log_is_refused(tmp_path):
    """A committed `*.log` goes the gate red, naming the path."""

    # Given a repo with a tracked log and an empty exception fixture
    root, exceptions = make_repo(tmp_path, {"run.log": "tail\n", "ok.txt": "x\n"})
    # When  the gate scans the tracked files
    # Then  the log is an artifact finding (a planted violation goes red)
    assert _find(root, exceptions) == ["run.log"]


def test_a_tracked_dot_scratch_is_refused(tmp_path):
    """A committed `.<word><digits>.<ext>` name (like `.pr874.md`) is refused."""

    # Given a repo with the issue's dot-scratch shape tracked
    root, exceptions = make_repo(tmp_path, {".pr874.md": "notes\n", "a.txt": "x\n"})
    # When  the gate scans the tracked files
    # Then  the scratch artifact is refused, naming the path
    assert _find(root, exceptions) == [".pr874.md"]


def test_a_clean_tree_passes(tmp_path):
    """Tracked files that match neither pattern produce no finding."""

    # Given a repo with only clean, non-artifact files
    root, exceptions = make_repo(tmp_path, {"README.md": "# t\n", "src/main.py": "x\n"})
    # When  the gate scans the tracked files
    # Then  there is no artifact or stale-exception finding
    assert _find(root, exceptions) == []


def test_an_untracked_ignored_log_is_not_a_finding(tmp_path):
    """The gate scans *tracked* files only — an ignored, unstaged `.foo.log` is not a finding."""

    # Given a repository where a log is written but never committed
    root, exceptions = make_repo(tmp_path, {"a.txt": "x\n"})
    (root / ".foo.log").write_text("ignored\n")
    # When  the gate scans the tracked files
    # Then  the uncommitted log does not appear (`.gitignore` already keeps it out)
    assert _find(root, exceptions) == []


# --- the allowlist is honored and expired exceptions fail --------------------------------
def test_a_dated_exception_honors_an_intentional_file(tmp_path):
    """An intentional `.log` with a recorded exception is allowed."""

    # Given a tracked fixture log and an exception that names it with a reason/date/issue
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    p = root / "tests" / "fixtures" / "sample.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("fixture\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    exceptions = tmp_path / "exc.json"
    exceptions.write_text(json.dumps({"files": {
        "tests/fixtures/sample.log": {"reason": "a deliberate fixture", "date": "2026-11-11",
                                      "issue": "#2484"},
    }}))
    # When  the gate scans the tracked tree with that fixture loaded
    # Then  the recorded exception is honored and the gate passes
    assert _find(root, exceptions) == []


def test_a_stale_exception_fails(tmp_path):
    """An exception whose file is gone (or no longer matches) is STALE and fails."""

    # Given an exception naming a file that no longer exists in the tree
    root, exceptions = make_repo(tmp_path, {"a.txt": "x\n"})
    exceptions_path = tmp_path / "exc.json"
    exceptions_path.write_text(json.dumps({"files": {
        "gone.log": {"reason": "was a fixture", "date": "2026-11-11", "issue": "#2484"},
    }}))
    # When  the gate scans the tracked tree against that fixture
    # Then  the expired exception is a stale-exception finding (it cannot outlive its reason)
    assert _find(root, exceptions_path) == ["gone.log"]


# --- the gate is wired into the unit lane and lane-preflight -----------------------------
def test_ci_unit_runs_the_hygiene_gate():
    """The unit lane reaches `make check-file-hygiene` (acceptance: wired into the unit lane)."""

    # Given the ci-unit recipe and the check-file-hygiene recipe
    m = re.search(r"^ci-unit:.*(?:\n\t[^\n]*)+", MAKE_TEXT, re.M)
    assert m, "ci-unit target not found"
    hyg = re.search(r"^check-file-hygiene:[ ]##[^\n]*", MAKE_TEXT, re.M)
    assert hyg, "check-file-hygiene target not found"

    # When  ci-unit's steps and the gate's recipe are read
    # Then  ci-unit runs the gate and the gate runs the script (not a no-op)
    assert "$(MAKE) check-file-hygiene" in m.group(0), m.group(0)
    assert "scripts/check_file_hygiene.py check" in MAKE_TEXT.split(
        "check-file-hygiene:")[1].split("\n")[1]


def test_lane_preflight_reaches_the_hygiene_gate():
    """`make lane-preflight` runs FAST_GATES, and the gate is one of them (acceptance)."""

    # Given the one gate list the issue-bot and lane-preflight both import
    fm = re.search(r"FAST_GATES[^=]*= \((.*?)\)", FAST, re.S)
    assert fm, "FAST_GATES tuple not found"

    # When  its members are read
    # Then  the hygiene gate is a fast gate, so lane-preflight reaches it
    assert '"check-file-hygiene"' in fm.group(1), fm.group(1)


def test_check_file_hygiene_is_declared_phony():
    """A file named `check-file-hygiene` must not shadow the gate (issue #392)."""

    # Given the `.PHONY:` declaration and its line continuations
    phony = []
    for line in MAKEFILE.splitlines():
        if line.startswith(".PHONY:"):
            phony.append(line.split(":", 1)[1])
        elif phony and line.startswith("\t") and not line.strip():
            pass
    joined = " ".join(l.rstrip("\\") for l in phony)

    # When  its members are read
    # Then  the gate is declared `.PHONY`, so `make` cannot run nothing while reporting green
    assert "check-file-hygiene" in joined, joined
