"""Non-mocked tests for the ONE commit-identity seam (issue #840).

Every test builds a REAL git repository in a temp dir and reads the identity through the same
`git config --show-origin` / `git var GIT_AUTHOR_IDENT` calls the seam uses. Nothing is stubbed: the
point of the seam is that git's own precedence decides which identity a commit would carry, so the
tests run git rather than a fake that agrees with the seam's assumptions.

The regression this file exists for is in `test_an_ambient_off_list_email_reds_the_preflight`: an
ambient `~/.gitconfig`-style value (`andy@asimov.local`) used to reach a head because nothing asserted
the identity the leg would ACTUALLY commit as until the end of `linux / unit`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.check_pr_authors as cpa  # noqa: E402
import scripts.git_identity as gi  # noqa: E402

ANDY = ("Andy Holst", "andy.holst@protonmail.com")
ASIMOV = ("Asimov Agent", "support@docondee.com")


# ---------------------------------------------------------------------------
# Real git helpers — no mocking, real repositories on disk.
# ---------------------------------------------------------------------------
def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    base = {**os.environ}
    base.pop("GIT_AUTHOR_NAME", None)
    base.pop("GIT_AUTHOR_EMAIL", None)
    base.pop("GIT_COMMITTER_NAME", None)
    base.pop("GIT_COMMITTER_EMAIL", None)
    base.pop("EMAIL", None)
    if env:
        base.update(env)
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, env=base)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout


def _repo(tmp_path: Path) -> Path:
    """A real git repository on `main` with one commit, and NO identity configured."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "-c", f"user.name={ANDY[0]}", "-c", f"user.email={ANDY[1]}",
         "commit", "-m", "chore(base): the base commit every branch is cut from")
    return repo


# ---------------------------------------------------------------------------
# Requirement: the seam is the ONE place the automation's identity comes from
# ---------------------------------------------------------------------------
def test_the_seam_derives_the_bot_half_of_the_allowlist():
    # Given the policy the guard enforces
    # When  the seam states the identity every automation leg commits as
    name, email = gi.identity()

    # Then  it is one of the two allowlisted pairs, read from ALLOWED rather than restated
    assert name == "Asimov Agent"
    assert cpa.ALLOWED[name] == email == "support@docondee.com"


def test_the_seam_names_both_allowed_identities_in_its_evidence():
    # Given the allowlist in check_pr_authors
    # When  the seam builds the sentence a finding quotes
    note = gi.allowed_note()

    # Then  both pairs are named, so a red says what IS allowed
    for name, email in cpa.ALLOWED.items():
        assert f"{name} <{email}>" in note


def test_apply_writes_the_allowlisted_identity_into_the_repository(tmp_path: Path):
    # Given a repository whose git config holds no identity
    repo = _repo(tmp_path)
    # When  the seam is applied
    gi.apply(repo)

    # Then  the repository's own config carries the allowed pair and the pre-flight passes
    assert _git(repo, "config", "user.name").strip() == ASIMOV[0]
    assert _git(repo, "config", "user.email").strip() == ASIMOV[1]
    assert gi.check(repo) == []


def test_an_ambient_off_list_email_reds_the_preflight(tmp_path: Path):
    # Given a repository whose git config holds the correct-LOOKING name with a wrong domain —
    # the identity two PRs reached a head with, and the one an ambient ~/.gitconfig supplies
    repo = _repo(tmp_path)
    _git(repo, "config", "user.name", "Andy Holst")
    _git(repo, "config", "user.email", "andy@asimov.local")

    # When  the pre-flight asserts the identity a commit would carry
    items = gi.check(repo)

    # Then  it reds, names the identity, the FILE it came from and the allowlist
    assert len(items) == 1
    evidence = items[0]["evidence"]
    assert "Andy Holst <andy@asimov.local>" in evidence
    assert "user.email" in evidence
    assert "andy.holst@protonmail.com" in evidence and "support@docondee.com" in evidence


def test_an_environment_override_reds_the_preflight_and_names_the_variable(tmp_path: Path):
    # Given a repository whose config is correct but whose leg exports a wrong identity —
    # the `-c`/`GIT_AUTHOR_*` mechanism the issue's correction identifies as the real cause
    repo = _repo(tmp_path)
    gi.apply(repo)
    env = {"GIT_AUTHOR_EMAIL": "agent@asimov.invalid"}

    # When  the pre-flight reads git's own precedence
    got = gi.resolve(repo)
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        items = gi.check(repo)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # Then  the env value wins over the correct config, and the finding names the variable
    assert got["email"] == ASIMOV[1]
    assert len(items) == 1
    assert "agent@asimov.invalid" in items[0]["evidence"]
    assert "GIT_AUTHOR_EMAIL" in items[0]["evidence"]


def test_the_pr_body_line_is_the_identity_a_reviewer_reads():
    # Given the seam's identity
    # When  a producer renders the PR body's author line
    line = gi.pr_author_line()

    # Then  a reviewer sees the exact pair without `gh api`
    assert line == "Author: Asimov Agent <support@docondee.com>"


def test_the_report_names_the_identity_its_source_and_the_allowlist(tmp_path: Path):
    repo = _repo(tmp_path)
    gi.apply(repo)
    text = gi.report(repo)

    # Then  the report is OK and states both halves' source and the allowlist
    assert "[git-identity] OK" in text
    assert "name  source:" in text and "email source:" in text
    assert "support@docondee.com" in text and "andy.holst@protonmail.com" in text


def test_the_cli_exits_non_zero_on_an_off_list_identity_and_zero_after_apply(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "config", "user.name", "Asimov Agent")
    _git(repo, "config", "user.email", "agent@asimov.invalid")

    # When  the CLI runs its pre-flight
    red = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "git_identity.py"),
                          "check", "--cwd", str(repo)], capture_output=True, text=True)

    # Then  it fails with the finding, and apply turns it green
    assert red.returncode == 1, red.stdout + red.stderr
    assert "outside the allowlist" in red.stdout
    subprocess.run(["git", "config", "user.email", ASIMOV[1]], cwd=str(repo), check=True)
    green = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "git_identity.py"),
                            "check", "--cwd", str(repo)], capture_output=True, text=True)
    assert green.returncode == 0, green.stdout + green.stderr
    assert "commits as Asimov Agent <support@docondee.com>" in green.stdout


def _guard_steps() -> list[str]:
    """The `run:` text of the `guard` job's steps, in order."""
    import yaml
    doc = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    return [str(step.get("run", "")) for step in doc["jobs"]["guard"]["steps"]]


def test_the_guard_job_runs_the_preflight_before_the_heavy_rows():
    # Given the cheap pre-flight job's steps, in order
    steps = _guard_steps()

    # When  the first step that names each command is located
    def first(marker: str) -> int:
        return next(i for i, run in enumerate(steps) if marker in run)

    # Then  the identity is applied, asserted, and the commit scan runs BEFORE the row decision —
    #       so an off-allowlist author reds in seconds instead of after `linux / unit`
    assert first("make git-identity-apply") < first("make check-git-identity")
    assert first("make check-git-identity") < first("make check-pr-authors")
    assert first("make check-pr-authors") < first("make ci-slow-rows")


def test_the_guard_job_checks_out_the_history_the_scan_reads():
    # Given the guard job's checkout step
    import yaml
    doc = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    checkout = next(s for s in doc["jobs"]["guard"]["steps"]
                    if str(s.get("uses", "")).startswith("actions/checkout"))

    # Then  it fetches the base branch, without which `base..HEAD` cannot be read
    assert checkout.get("with", {}).get("fetch-depth") == 0
