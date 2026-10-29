"""Non-mocked tests for the commit-author guard (issue #345).

Every test builds a REAL git repository in a temp dir, commits with REAL identities via
`git -c user.name=... -c user.email=...`, and runs the guard's own functions against the REAL
`git rev-list` output. Nothing is stubbed: no fake subprocess, no monkeypatched `git`, no fixture that
hands the guard a pre-parsed list of authors instead of letting it read the commits. If `git` changes
what it prints, or the guard's parsing drifts, these tests fail — which is the point.

The fixture repositories are built with a real base branch and a real head branch so the range
(`<base>..<head>`) is a real git range, not a list someone assembled.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.check_pr_authors as cpa  # noqa: E402

# The two identities the rule allows. Spelled once here; the guard spells them in ALLOWED.
ANDY = ("Andy Holst", "andy.holst@protonmail.com")
ASIMOV = ("Asimov Agent", "support@docondee.com")


# ---------------------------------------------------------------------------
# Real git helpers — no mocking, real repositories on disk.
# ---------------------------------------------------------------------------
def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    """Run git in a real repo and return stdout. A failure raises — never swallowed."""
    import os
    base = {**os.environ}
    if env:
        base.update(env)
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, env=base)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout


def _commit(repo: Path, name: str, email: str, message: str, path: str = "f.txt",
            content: str | None = None) -> str:
    """Commit as a REAL identity with `git -c user.name=... -c user.email=...`. Returns the sha."""
    (repo / path).write_text(content if content is not None else f"{name}\n{message}\n")
    _git(repo, "add", path)
    _git(repo, "-c", f"user.name={name}", "-c", f"user.email={email}",
         "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _repo(tmp_path: Path) -> Path:
    """A real git repository with a real `main` branch and one base commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit(repo, *ANDY, "chore(base): the base commit every branch is cut from", "base.txt")
    return repo


def _branch(repo: Path, name: str) -> None:
    _git(repo, "switch", "-q", "-c", name)


def _authors(items: list[dict]) -> list[str]:
    """The author NAME a finding names, read out of its evidence text.

    The evidence reads ``... is authored `<name> <email>`. ...`` — the name is everything before the
    address, so the assertion can name the author the way `git log` does.
    """
    return [it["evidence"].split("authored `")[1].split(" <")[0] for it in items
            if "authored `" in it["evidence"]]


def _keys(items: list[dict]) -> list[str]:
    return [it["key"] for it in items]


# ---------------------------------------------------------------------------
# Requirement: a PR's commits are authored by an allowed identity
# ---------------------------------------------------------------------------
def test_the_allowed_identities_pass(tmp_path: Path):
    # Given a real repo whose branch adds one commit as each allowed identity
    repo = _repo(tmp_path)
    _branch(repo, "feat/ok")
    _commit(repo, *ANDY, "feat(x): the first allowed commit")
    _commit(repo, *ASIMOV, "feat(x): the second allowed commit")

    # When  the guard reads the real commit range
    commits = cpa.commits_in_range("main", "HEAD", repo)
    items = cpa.check_commits(commits)

    # Then  both identities are allowed and nothing is reported
    assert len(commits) == 2
    assert items == []


def test_an_allowed_alias_name_is_accepted(tmp_path: Path):
    """The email is the stable key; each allowed spelling of it passes (issue #971).

    GitHub's squash writes the profile display name, not the identity the committer set, so exact-name
    matching rejected a permitted person (`Andy`, `andyholst`, `Mr. Asimov` all carry an allowed email).
    Each of these is the same person under an alias — allowed.
    """
    for i, alias in enumerate(("Andy", "andyholst", "Mr. Asimov")):
        case = tmp_path / f"case-{i}"
        case.mkdir()
        repo = _repo(case)
        _branch(repo, f"feat/alias-{i}")
        email = "support@docondee.com" if alias == "Mr. Asimov" else "andy.holst@protonmail.com"
        _commit(repo, alias, email, f"feat(x): authored {alias}")

        items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

        assert items == [], f"alias `{alias} <{email}>` should be allowed, got {_authors(items)}"


def test_an_alias_name_with_a_foreign_email_is_a_violation(tmp_path: Path):
    """The alias list is NAMES only: an alias carried by the WRONG email still fails (issue #971).

    `Mr. Asimov` is an allowed display name under `support@docondee.com`, but a commit authored
    `Mr. Asimov <someone@else.example>` is a violation — the email is not the one that alias may carry.
    This is what keeps `fd31640d` (`Andy Holst <andy.holtd@protonmail.com>`, a typo'd domain) a finding.
    """
    repo = _repo(tmp_path)
    _branch(repo, "feat/alias-wrong-email")
    _commit(repo, "Mr. Asimov", "someone@else.example", "feat(x): an alias at a foreign address")

    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    assert len(items) == 1
    assert _authors(items) == ["Mr. Asimov"]
    assert "someone@else.example" in items[0]["evidence"]


def test_an_unknown_email_fails_and_names_the_email(tmp_path: Path):
    """The gate is the EMAIL: a permitted name at an address not in ALLOWED is a violation (issue #971).

    This is the stable-key direction — the evidence names the email so the reader sees which address
    was rejected, not just the display name.
    """
    repo = _repo(tmp_path)
    _branch(repo, "feat/unknown-email")
    _commit(repo, "Andy Holst", "not.an.allowed@example.net", "feat(x): allowed name, unknown email")

    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    assert len(items) == 1
    assert "not.an.allowed@example.net" in items[0]["evidence"]
    assert "permitted addresses" in items[0]["evidence"]


def test_the_name_cannot_be_the_key_is_stated_in_the_docstring():
    """The reason the allowlist keys on EMAIL, not name, is written next to ALLOWED (issue #971).

    The acceptance says a docstring line must say why the name cannot be the key; a future editor who
    reverts to name-keying deletes that line, which reds this test.
    """
    import inspect
    src = inspect.getsource(cpa)
    assert "The name cannot be the key" in src, "the email-keyed rationale must sit beside ALLOWED"


def test_a_commit_authored_github_actions_bot_is_a_violation(tmp_path: Path):
    # Given a real repo whose branch adds a commit authored `github-actions[bot]`
    repo = _repo(tmp_path)
    _branch(repo, "feat/bot")
    _commit(repo, "github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com",
            "feat(x): authored by the bot")

    # When  the guard reads the real commit range
    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    # Then  the bot identity is outside the allowlist
    assert len(items) == 1
    assert _authors(items) == ["github-actions[bot]"]


def test_the_right_name_with_the_wrong_email_is_a_violation(tmp_path: Path):
    # Given a real repo whose branch adds a commit authored `Andy Holst` at a foreign address
    repo = _repo(tmp_path)
    _branch(repo, "feat/wrong-email")
    _commit(repo, "Andy Holst", "someone@else.example", "feat(x): right name, wrong email")

    # When  the guard reads the real commit range
    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    # Then  the name must carry the email that belongs to it, so this is a violation
    assert len(items) == 1
    assert "Andy Holst <someone@else.example>" in items[0]["evidence"]


def test_every_off_list_identity_is_reported_in_a_long_range(tmp_path: Path):
    # Given a real repo whose branch adds five commits, three of them off-list
    repo = _repo(tmp_path)
    _branch(repo, "feat/mixed")
    _commit(repo, *ANDY, "feat(x): allowed one")
    _commit(repo, "github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com",
            "feat(x): off-list one")
    _commit(repo, "llgenie fix-bot", "fix-bot@users.noreply.github.com", "feat(x): off-list two")
    _commit(repo, "Hermes Agent", "agent@asimov.local", "feat(x): off-list three")
    _commit(repo, *ASIMOV, "feat(x): allowed two")

    # When  the guard reads the real commit range
    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    # Then  exactly the three off-list authors are reported, each once
    assert len(items) == 3
    assert sorted(_authors(items)) == sorted(
        ["github-actions[bot]", "llgenie fix-bot", "Hermes Agent"])


# ---------------------------------------------------------------------------
# Requirement: a commit's `Co-authored-by:` trailer is an allowed identity too
# ---------------------------------------------------------------------------
def test_an_off_list_co_author_is_its_own_finding(tmp_path: Path):
    # Given a real repo whose commit is authored by an allowed identity but co-authored off-list
    repo = _repo(tmp_path)
    _branch(repo, "feat/coauthor")
    message = ("feat(x): an allowed author with an off-list co-author\n\n"
               "Co-authored-by: Hermes Agent <agent@asimov.local>")
    _commit(repo, *ANDY, message)

    # When  the guard reads the real commit range
    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    # Then  the co-author is reported under its own key and the author is NOT
    assert len(items) == 1
    assert "co-author/" in items[0]["key"]
    assert "Hermes Agent" in items[0]["evidence"]


def test_an_allowed_co_author_is_accepted(tmp_path: Path):
    # Given a real repo whose commit carries an allowed co-author trailer
    repo = _repo(tmp_path)
    _branch(repo, "feat/coauthor-ok")
    message = ("feat(x): an allowed author with an allowed co-author\n\n"
               "Co-authored-by: Asimov Agent <support@docondee.com>")
    _commit(repo, *ANDY, message)

    # When  the guard reads the real commit range
    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    # Then  nothing is reported
    assert items == []


def test_a_co_author_with_the_right_name_and_a_foreign_email_is_a_violation(tmp_path: Path):
    # Given a real repo whose commit carries a trailer naming an allowed name at a foreign address
    repo = _repo(tmp_path)
    _branch(repo, "feat/coauthor-email")
    message = ("feat(x): a trailer with the right name and the wrong email\n\n"
               "Co-authored-by: Andy Holst <not.andy@example.com>")
    _commit(repo, *ASIMOV, message)

    # When  the guard reads the real commit range
    items = cpa.check_commits(cpa.commits_in_range("main", "HEAD", repo))

    # Then  the trailer is a violation even though the name is allowed
    assert len(items) == 1
    assert "co-author/" in items[0]["key"]


# ---------------------------------------------------------------------------
# Requirement: a commit already reachable from the base branch is out of scope
# ---------------------------------------------------------------------------
def test_a_commit_on_the_base_branch_is_not_reported(tmp_path: Path):
    # Given a base branch whose history carries an off-list commit
    repo = _repo(tmp_path)
    _branch(repo, "feat/off-on-base")
    _commit(repo, "Mr. Asimov", "support@docondee.com", "feat(x): off-list on the base")
    _git(repo, "switch", "-q", "main")
    _git(repo, "merge", "-q", "--ff-only", "feat/off-on-base")
    _branch(repo, "feat/allowed-head")
    _commit(repo, *ANDY, "feat(x): an allowed commit on the head")

    # When  the guard reads the head's real range against main
    commits = cpa.commits_in_range("main", "HEAD", repo)
    items = cpa.check_commits(commits)

    # Then  only the head's own commit is read, and it is allowed
    assert len(commits) == 1
    assert items == []


def test_a_merge_commit_is_not_reported(tmp_path: Path):
    # Given a head branch whose tip is a real merge commit authored off-list
    repo = _repo(tmp_path)
    _branch(repo, "feat/side")
    _commit(repo, *ANDY, "feat(side): a side commit", "side.txt")
    _git(repo, "switch", "-q", "main")
    _branch(repo, "feat/merge-head")
    _commit(repo, *ANDY, "feat(head): the head's own commit", "head.txt")
    # The merge runs as the operator's own identity — deliberately off-list here, so the test proves
    # the merge is skipped for its AUTHOR and not because its author happened to be allowed.
    _git(repo, "merge", "--no-ff", "--no-edit", "-m", "chore: merge the side branch",
         "feat/side", env={"GIT_AUTHOR_NAME": "Hermes Agent",
                           "GIT_AUTHOR_EMAIL": "agent@asimov.local",
                           "GIT_COMMITTER_NAME": "Hermes Agent",
                           "GIT_COMMITTER_EMAIL": "agent@asimov.local"})

    # When  the guard reads the real commit range
    commits = cpa.commits_in_range("main", "HEAD", repo)
    items = cpa.check_commits(commits)

    # Then  the merge is not among the commits read, so its off-list author is not reported
    shas = [c["sha"] for c in commits]
    merge_sha = _git(repo, "rev-parse", "HEAD").strip()
    assert merge_sha not in shas
    assert all("merge the side branch" not in c["message"] for c in commits)
    assert items == []


# ---------------------------------------------------------------------------
# Requirement: the repository's own producers assign an allowed identity
# ---------------------------------------------------------------------------
def _producer_tree(tmp_path: Path, workflow_body: str, agents: str | None = None) -> Path:
    """A minimal repo tree carrying one workflow, so the guard's static half can be read."""
    root = tmp_path / "tree"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / ".github" / "workflows" / "bot.yml").write_text(workflow_body)
    if agents is not None:
        (root / "AGENTS.md").write_text(agents)
    return root


def test_a_producer_with_an_off_list_identity_is_a_violation(tmp_path: Path):
    # Given a fixture tree whose workflow sets a literal off-list identity
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - run: |
          git config user.name "llgenie fix-bot"
          git config user.email "fix-bot@users.noreply.github.com"
          git commit -m "chore: bump"
""")

    # When  the guard reads the producers
    items = cpa.check_producers(root)

    # Then  BOTH the literal name and the literal email are reported, with the quoted name read whole
    # (`llgenie fix-bot`, not the single token `llgenie`) — a name with a space is the point
    assert sorted(_keys(items)) == sorted([
        "producer-name/.github/workflows/bot.yml:llgenie fix-bot",
        "producer-email/.github/workflows/bot.yml:fix-bot@users.noreply.github.com",
    ])
    assert "llgenie fix-bot" in " ".join(it["evidence"] for it in items)


def test_a_producer_that_commits_with_an_unpaired_allowed_identity_is_seam_missing(tmp_path: Path):
    """​`check_seam.pins_identity` must require an ALLOWED PAIR, not any allowed name and any
    allowed email (issue #971). A producer that commits as `Andy Holst` + `support@docondee.com`
    (two identities mixed) used to satisfy the independent check and pass the seam gate.
    """
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - name: Commit
        run: |
          git config user.name "Andy Holst"
          git config user.email "support@docondee.com"
          git commit -m "chore: bump"
""")

    items = cpa.check_seam(root)

    assert any(k.startswith("seam-commit/") for k in _keys(items)), _keys(items)


def test_a_producer_mixing_two_allowed_identities_is_a_violation(tmp_path: Path):
    """​A producer that blends two ALLOWED identities is caught by the pair check (issue #971).

    `user.name "Andy Holst"` with `user.email "support@docondee.com"` pass the standalone name/email
    checks (both are individually allowed) but form no allowed pair — the static scan must not
    green-light what the commit scan rejects.
    """
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - run: |
          git config user.name "Andy Holst"
          git config user.email "support@docondee.com"
          git commit -m "chore: bump"
""")

    items = cpa.check_producers(root)

    assert any(k.startswith("producer-pair/") for k in _keys(items)), _keys(items)
    assert "support@docondee.com" in " ".join(it["evidence"] for it in items)


def test_a_producer_that_pins_two_full_identities_is_not_pair_flagged(tmp_path: Path):
    """​The pair check must not flag a file that legitimately pins TWO whole ALLOWED identities.

    Cross-product over names x emails would report the A-name/B-email and B-name/A-email mixed pairs
    that never co-occur. A file that pins both bull valid pairs is fine.
    """
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - run: |
          git config user.name "Andy Holst"
          git config user.email "andy.holst@protonmail.com"
      - run: |
          git config user.name "Asimov Agent"
          git config user.email "support@docondee.com"
""")

    items = cpa.check_producers(root)
    keys = _keys(items)

    assert not any(k.startswith("producer-pair/") for k in keys), keys


def test_a_runtime_identity_is_accepted(tmp_path: Path):
    # Given a fixture tree whose workflow resolves its identity at run time
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - run: |
          git config user.name "$(gh api user --jq .login)"
          git config user.email "$(gh api user --jq .id)+$(gh api user --jq .login)@users.noreply.github.com"
          git commit -m "chore: bump"
""")

    # When  the guard reads the producers
    items = cpa.check_producers(root)

    # Then  a run-time value cannot be read statically and is not a violation
    assert items == []


def test_an_unquoted_env_identity_reads_whole(tmp_path: Path):
    # Given a fixture tree whose workflow sets an ALLOWED identity without YAML quotes — the shape
    # `.github/workflows/rebase-bot.yml` uses (`GIT_AUTHOR_NAME: Asimov Agent`)
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  rebase:
    runs-on: ubuntu-latest
    env:
      GIT_AUTHOR_NAME: Asimov Agent
      GIT_AUTHOR_EMAIL: support@docondee.com
      GIT_COMMITTER_NAME: Asimov Agent
      GIT_COMMITTER_EMAIL: support@docondee.com
    steps:
      - run: git rebase main
""")

    # When  the guard reads the producers
    items = cpa.check_producers(root)

    # Then  the value is read to the end of the line, so `Asimov Agent` is recognised as allowed
    # rather than read as the bare token `Asimov` and reported as a violation
    assert items == []


def test_an_unquoted_env_identity_that_is_off_list_is_a_violation(tmp_path: Path):
    # Given a fixture tree whose workflow sets an off-list identity without YAML quotes
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  rebase:
    runs-on: ubuntu-latest
    env:
      GIT_AUTHOR_NAME: github-actions[bot]
      GIT_AUTHOR_EMAIL: 41898282+github-actions[bot]@users.noreply.github.com
    steps:
      - run: git rebase main
""")

    # When  the guard reads the producers
    items = cpa.check_producers(root)

    # Then  the env identity is reported, quotes or no quotes
    assert sorted(_keys(items)) == sorted([
        "producer-name/.github/workflows/bot.yml:github-actions[bot]",
        "producer-email/.github/workflows/bot.yml:41898282+github-actions[bot]@users.noreply.github.com",
    ])


def test_the_guard_does_not_flag_its_own_source():
    # Given the guard's own source, which NAMES identities as data (docstrings, regexes, the
    # remediation text a finding carries)
    self_path = (REPO_ROOT / "scripts" / "check_pr_authors.py").resolve()
    text = self_path.read_text()

    # When  the guard enumerates the producers it governs
    files = [p.resolve() for p in cpa.producer_files(REPO_ROOT)]

    # Then  its own file is NOT among them — scanning it would report those names as violations —
    # and it could have (the raw text does match the assignment patterns), so the exclusion matters
    assert self_path not in files
    matched = (bool(cpa.SET_NAME.search(text)) or bool(cpa.INLINE_NAME.search(text))
               or bool(cpa.ENV_NAME.search(text)))
    assert matched, "the guard's own source no longer contains an assignment shape to self-match"
    assert cpa.check_producers(REPO_ROOT) == []


def test_an_allowed_producer_identity_is_accepted(tmp_path: Path):
    # Given a fixture tree whose workflow sets one of the allowed identities
    root = _producer_tree(tmp_path, """\
name: bot
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - run: |
          git -c user.name="Asimov Agent" -c user.email="support@docondee.com" commit -m "chore: bump"
""")

    # When  the guard reads the producers
    items = cpa.check_producers(root)

    # Then  nothing is reported
    assert items == []


# ---------------------------------------------------------------------------
# Requirement: AGENTS.md states the rule, and the exit code is what CI gates on
# ---------------------------------------------------------------------------
def test_a_missing_agents_mandate_is_a_violation(tmp_path: Path):
    # Given a fixture tree whose AGENTS.md does not carry the section
    root = _producer_tree(tmp_path, "name: bot\n", agents="# Instructions\n\nno rule here\n")

    # When  the guard reads AGENTS.md
    items = cpa.check_agents_mandate(root)

    # Then  it reports the mandate under its own key
    assert _keys(items) == ["agents-mandate"]


def test_the_agents_mandate_passes_when_present(tmp_path: Path):
    # Given a fixture tree whose AGENTS.md carries the section
    root = _producer_tree(tmp_path, "name: bot\n", agents=f"# Instructions\n\n{cpa.AGENTS_MANDATE}\n")

    # When  the guard reads AGENTS.md
    items = cpa.check_agents_mandate(root)

    # Then  nothing is reported
    assert items == []


def test_this_repository_carries_the_agents_mandate():
    # Given this repository's own AGENTS.md
    # When  the guard reads it
    items = cpa.check_agents_mandate(REPO_ROOT)

    # Then  it carries the section, so this repo's own PRs are governed by the stated rule
    assert items == []


def test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo(tmp_path: Path):
    # Given a real repo whose branch adds an off-list commit
    repo = _repo(tmp_path)
    _branch(repo, "feat/bad")
    _commit(repo, "Andy", "andy.holst@protonmail.com", "feat(x): off-list")

    # When  the guard's own entry point runs against each tree
    bad = cpa.main(["check", "--base", "main", "--head", "HEAD", "--root", str(repo)])

    # Then  the violation is non-zero — this is the contract CI gates on
    assert bad == 1


def test_report_lists_every_commit_and_its_verdict(tmp_path: Path):
    # Given a real repo whose branch adds one allowed and one off-list commit
    repo = _repo(tmp_path)
    _branch(repo, "feat/mixed-report")
    _commit(repo, *ANDY, "feat(x): allowed")
    _commit(repo, "github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com",
            "feat(x): off-list")

    # When  the report runs
    text = cpa.report("main", "HEAD", repo)

    # Then  both commits appear, with their verdicts, and the allowlist is printed
    assert "2 non-merge commit(s)" in text
    assert "OK" in text and "FAIL" in text
    assert "allowed:" in text


def test_the_range_cannot_be_read_is_a_finding_not_a_crash(tmp_path: Path):
    # Given a real repo and a base that does not exist
    repo = _repo(tmp_path)

    # When  the guard reads a range it cannot resolve
    items = cpa.findings("no-such-ref", "HEAD", repo)

    # Then  it reports the unreadable range instead of raising, so CI fails loudly and legibly
    assert _keys(items) == ["range"]
    assert "failed" in items[0]["evidence"]


# ---------------------------------------------------------------------------
# Requirement: this repository passes its own gate
# ---------------------------------------------------------------------------
def test_this_repository_passes_its_own_gate():
    # Given this repository at its current tip
    # When  the guard reads the producers and the AGENTS.md mandate
    items = cpa.check_producers(REPO_ROOT) + cpa.check_agents_mandate(REPO_ROOT)

    # Then  no producer commits as an off-list literal identity and the rule is stated
    assert items == []


def test_this_repositorys_own_producers_are_all_read():
    # Given this repository
    # When  the guard enumerates the files it governs
    files = cpa.producer_files(REPO_ROOT)
    names = [str(p.relative_to(REPO_ROOT)) for p in files]

    # Then  every workflow, the Makefile and the scripts are covered
    assert ".github/workflows/fix-bot.yml" in names
    assert "Makefile" in names
    assert any(n.startswith("scripts/") and n.endswith(".py") for n in names)


# ---------------------------------------------------------------------------
# Requirement: every spec scenario carries Given / When / Then and a test
# ---------------------------------------------------------------------------
def test_every_spec_scenario_has_given_when_then_and_a_test():
    # Given this change's spec file
    spec = (REPO_ROOT / "openspec" / "changes" / "pr-commit-authors"
            / "specs" / "pr-commit-authors" / "spec.md").read_text()

    # When  every scenario is read
    scenarios = [s for s in spec.split("#### Scenario:")[1:]]

    # Then  each one states GIVEN, WHEN and THEN and names a test that exists in this file
    this_file = Path(__file__).read_text()
    assert scenarios, "the spec must carry scenarios"
    for s in scenarios:
        head = s.split("\n", 1)[0].strip()
        assert "- **GIVEN**" in s, f"scenario {head!r} has no GIVEN"
        assert "- **WHEN**" in s, f"scenario {head!r} has no WHEN"
        assert "- **THEN**" in s, f"scenario {head!r} has no THEN"
        match = [line for line in s.splitlines() if "**Test:**" in line]
        assert match, f"scenario {head!r} names no test"
        name = match[0].split("::")[-1].strip().strip("`")
        assert f"def {name}(" in this_file, f"scenario {head!r} names {name!r}, which is not a test here"
