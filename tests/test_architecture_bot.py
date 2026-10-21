"""The architecture bot: a 6-hourly, guarded refresh of docs/ARCHITECTURE.md as one issue + PR.

Every behaviour here is the product's: the brief is derived from a REAL git repository, the
publish step drives a real branch/commit against a real bare remote, and only the GitHub API is
a stand-in (`gh` is a recorded fake, because the test must not file issues). No assertion
monkeypatches `brief`, `drift`, `publish` or any other function under test.

Scenarios map one-to-one onto `openspec/changes/feat-architecture-bot/specs/architecture-bot/spec.md`.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import architecture_bot as ab  # noqa: E402

WORKFLOW = REPO / ".github" / "workflows" / "architecture-bot.yml"
DOC = "docs/ARCHITECTURE.md"
LONG_DOC = "# Architecture\n\n" + ("This repository serves GGUF models through engine images. " * 8)

FAKE_GH = '''#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
# Only the program, the verb and the FLAGS are recorded: a body is content, and recording it would
# make an assertion about the command read the prose inside the body instead.
with open(os.environ["GH_LOG"], "a", encoding="utf-8") as fh:
    fh.write(" ".join([args[0], args[1], *[a for a in args if a.startswith("--")]]) + "\\n")
if args[:2] == ["pr", "list"]:
    print(os.environ.get("GH_PR_LIST", "[]"))
    raise SystemExit(0)
if args[:2] == ["issue", "create"]:
    sys.stdin.read()
    print("https://github.com/owner/repo/issues/7")
    raise SystemExit(0)
if args[:2] == ["pr", "create"]:
    sys.stdin.read()
    print("https://github.com/owner/repo/pull/9")
    raise SystemExit(0)
print("unexpected gh call: " + " ".join(args), file=sys.stderr)
raise SystemExit(1)
'''


# ------------------------------------------------------------------------- helpers


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout


def _repo(tmp_path: Path, doc: str | None = LONG_DOC) -> Path:
    """A real git repository with a bare `origin` and one commit (carrying the doc, by default)."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "scripts").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    if doc is not None:
        (root / "docs" / "ARCHITECTURE.md").write_text(doc)
    (root / "scripts" / "foo.py").write_text('"""Foo module: serves foo."""\n')
    (root / "Makefile").write_text("all: ## Do the whole thing\n\t@true\n")
    (root / ".github" / "workflows" / "x.yml").write_text(
        'name: x — does a thing\non:\n  schedule:\n    - cron: "1 2 * * *"\n')
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "Andy Holst")
    _git(root, "config", "user.email", "andy.holst@protonmail.com")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feat: seed the tree")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "-u", "origin", "main")
    return root


def _fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    path = tmp_path / "gh"
    path.write_text(FAKE_GH)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "gh.log"
    log.write_text("")
    return path, log


def _dirty_doc(root: Path, text: str = LONG_DOC + "\nA new paragraph about the picker.\n") -> None:
    (root / DOC).write_text(text)


# ------------------------------------------------------------------ the workflow


def test_workflow_is_six_hourly_dispatchable_and_guarded():
    """The bot owns minute :47 every 6 hours, is dispatchable, and guards before any secret."""

    # Given the architecture bot's workflow file
    text = WORKFLOW.read_text()
    wf = yaml.safe_load(text)
    on = wf.get("on") or wf.get(True)

    # When its schedule, dispatch form, concurrency and first job are read
    crons = [e["cron"] for e in on["schedule"]]
    inputs = on["workflow_dispatch"]["inputs"]
    conc = wf["concurrency"]
    first_job = next(iter(wf["jobs"]))
    guard_text = text.split("architecture:", 1)[0]

    # Then the cron is 6-hourly on :47, and both inputs are documented with defaults
    assert crons == ["47 */6 * * *"]
    assert set(inputs) == {"dry", "doc"}
    for name, spec in inputs.items():
        assert len(spec["description"]) >= 10, name
        assert "default" in spec, name

    # And it queues rather than cancels, in its own group
    assert conc == {"group": "architecture-bot", "cancel-in-progress": False}

    # And the guard runs first, and reads no secret at all
    assert first_job == "guard"
    assert "secrets." not in guard_text
    assert "collaborators/$u/permission" in guard_text
    assert "admin|maintain|write" in guard_text


# ---------------------------------------------------------------------- the brief


def test_brief_names_the_drift_since_the_docs_last_commit(tmp_path):
    """`brief` reports the doc's last commit, what moved after it, and the real surface."""

    # Given a real repository whose doc was committed, and then a script changed
    root = _repo(tmp_path)
    doc_sha = _git(root, "log", "-1", "--format=%H", "--", DOC).strip()
    (root / "scripts" / "foo.py").write_text('"""Foo module: now serves bar."""\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feat: foo serves bar")

    # When the brief is derived from that tree
    text = ab.brief(root, DOC)

    # Then it names the doc's last commit and the path that moved since
    assert doc_sha[:12] in text
    assert "scripts/foo.py" in text

    # And it carries the current doc and the real make/script surface
    assert "A new paragraph about the picker" not in text
    assert "This repository serves GGUF models" in text
    assert "`all` — Do the whole thing" in text
    assert "`scripts/foo.py` — Foo module: now serves bar." in text
    assert "`x.yml`" in text and "1 2 * * *" in text


def test_brief_treats_an_uncommitted_doc_as_a_full_rebuild(tmp_path):
    """A doc with no history is a full rebuild over the tracked tree."""

    # Given a repository whose doc has never been committed (it is new and untracked)
    root = _repo(tmp_path, doc=None)
    (root / DOC).write_text(LONG_DOC)

    # When the brief is derived
    text = ab.brief(root, DOC)

    # Then it says so, lists the tracked surface, and asks for the doc to be created
    assert "no committed history" in text
    assert "full rebuild" in text
    assert "`scripts/foo.py`" in text
    assert f"Rewrite `{DOC}`" in text


# -------------------------------------------------------------------- publishing


def test_publish_opens_one_linked_issue_and_pr(tmp_path, monkeypatch):
    """A real doc change becomes one issue, one bot-authored commit and one closing PR."""

    # Given a repository with a changed doc and a recorded `gh`
    root = _repo(tmp_path)
    _dirty_doc(root)
    gh, log = _fake_gh(tmp_path)
    monkeypatch.setenv("GH_LOG", str(log))

    # When publish runs
    result = ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))

    # Then exactly one issue and one PR were created, the PR closing the issue
    calls = log.read_text().splitlines()
    assert result["action"] == "published"
    assert result["issue"] == 7
    assert result["branch"] == "agent/architecture-20261021T1200"
    assert sum(1 for c in calls if c.startswith("issue create")) == 1
    assert sum(1 for c in calls if c.startswith("pr create") == 1)

    # And the commit carries the doc alone, authored by the bot identity
    files = _git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert files == ["docs/ARCHITECTURE.md"]
    author = _git(root, "log", "-1", "--format=%an <%ae>").strip()
    assert author == "Asimov Agent <support@docondee.com>"
    assert result["pr_body"].rstrip().endswith("closes #7")
    for part in ("Issue:", "Fix:", "Benefit:", "Technical:"):
        assert part in result["issue_body"]

    # And it never merged and never pushed to main
    assert not any(" merge" in c for c in calls)
    assert not any(c.endswith(" main") for c in calls)


def test_publish_files_nothing_without_drift(tmp_path, monkeypatch):
    """A doc identical to HEAD files no issue, no branch and no PR."""

    # Given a clean repository whose doc matches HEAD
    root = _repo(tmp_path)
    gh, log = _fake_gh(tmp_path)
    monkeypatch.setenv("GH_LOG", str(log))

    # When publish runs
    result = ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))

    # Then it reports nothing to do, and made no GitHub call at all
    assert result["action"] == "none"
    assert "identical to HEAD" in result["reason"]
    assert log.read_text() == ""


def test_publish_skips_when_an_architecture_pr_is_open(tmp_path, monkeypatch):
    """Drift a PR already carries is not filed again on the next 6-hourly run."""

    # Given an open architecture PR and a dirty doc
    root = _repo(tmp_path)
    _dirty_doc(root)
    gh, log = _fake_gh(tmp_path)
    monkeypatch.setenv("GH_LOG", str(log))
    monkeypatch.setenv("GH_PR_LIST", json.dumps([
        {"number": 12, "headRefName": "agent/architecture-20261021T0600"}]))

    # When publish runs
    result = ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))

    # Then it defers to the open PR and files nothing
    assert result["action"] == "pending"
    assert "#12" in result["reason"]
    assert not any(c.startswith("issue create") for c in log.read_text().splitlines())


def test_publish_refuses_an_empty_doc(tmp_path, monkeypatch):
    """A missing or stub doc is a loud refusal, never a published stub."""

    # Given a repository with a stub doc, and a `gh` that records calls
    root = _repo(tmp_path)
    gh, log = _fake_gh(tmp_path)
    monkeypatch.setenv("GH_LOG", str(log))
    (root / DOC).write_text("too short")

    # When publish runs
    try:
        ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))
        raised = ""
    except ValueError as exc:
        raised = str(exc)

    # Then it refused, named the doc, and made no GitHub call
    assert "minimum 200" in raised
    assert log.read_text() == ""

    # And a missing doc is refused the same way
    (root / DOC).unlink()
    try:
        ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))
        raised = ""
    except ValueError as exc:
        raised = str(exc)
    assert "missing or empty" in raised


def test_publish_refuses_when_the_agent_edited_the_code(tmp_path, monkeypatch):
    """The refresh may only carry the doc; a stray tracked edit is a loud refusal."""

    # Given a dirty doc AND a tracked source file the agent touched
    root = _repo(tmp_path)
    _dirty_doc(root)
    (root / "scripts" / "foo.py").write_text('"""Foo module: tampered."""\n')
    gh, log = _fake_gh(tmp_path)
    monkeypatch.setenv("GH_LOG", str(log))

    # When publish runs
    try:
        ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))
        raised = ""
    except ValueError as exc:
        raised = str(exc)

    # Then it refused, named the stray file, and filed nothing
    assert "changed files other than" in raised
    assert "scripts/foo.py" in raised
    assert log.read_text() == ""

    # And the untracked brief is NOT treated as a stray edit
    (root / "scripts" / "foo.py").write_text('"""Foo module: serves foo."""\n')
    (root / "architecture-brief.md").write_text("run artifact\n")
    result = ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))
    assert result["action"] == "published"


def test_publish_refuses_to_commit_on_a_feature_branch(tmp_path, monkeypatch):
    """A refresh only starts from main; anything else would ride on another branch's PR."""

    # Given a repository checked out on a feature branch with a dirty doc
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "feat/other-work")
    _dirty_doc(root)
    gh, log = _fake_gh(tmp_path)
    monkeypatch.setenv("GH_LOG", str(log))

    # When publish runs
    try:
        ab.publish(root, "owner/repo", DOC, stamp="20261021T1200", gh=str(gh))
        raised = ""
    except ValueError as exc:
        raised = str(exc)

    # Then it refused, named the branch, and made no GitHub call
    assert "refusing to publish from branch 'feat/other-work'" in raised
    assert log.read_text() == ""


# ------------------------------------------------------------------ the agent leg


def test_doc_leg_is_one_scrubbed_container_call():
    """The only model leg is one container call, credential-forwarded, and scrubbed."""

    # Given the Makefile's doc recipe and its internal prompt
    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("architecture-bot-doc:", 1)[1].split("_architecture-bot-doc:", 1)[0]
    prompt = mk.split("_architecture-bot-doc:", 1)[1].split("architecture-bot-publish:", 1)[0]

    # When both are read
    # Then the public recipe requires the key, resolves the image, and pipes through the seam
    assert "require_env.py NOUS_API_KEY" in recipe
    assert "ci_images.py ensure agent" in recipe
    assert "$(call scrubbed_run," in recipe
    assert "$(AGENT_SHELL_FORWARD)" in recipe

    # And the agent may write only the doc, and may not branch/commit/push/merge
    assert "modify NO file except $(DOC)" in prompt
    assert "do not create a branch" in prompt
    assert "do not commit" in prompt and "do not push" in prompt


# ---------------------------------------------------------------------- the gates


def test_targets_and_doc_are_wired_into_the_gates():
    """The new targets are real `##` targets, in `.PHONY`, documented, and the doc exists."""

    # Given the Makefile, README and the architecture doc
    mk = (REPO / "Makefile").read_text()
    readme = (REPO / "README.md").read_text()
    doc = (REPO / DOC).read_text()
    targets = [name for name, _ in ab.public_targets(REPO)]
    phony = mk.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # When each new target is looked for
    for name in ("architecture-bot-brief", "architecture-bot-doc",
                 "architecture-bot-publish", "architecture-bot"):
        # Then it has a `##` help line, is declared phony, and is documented in the README
        assert name in targets, f"{name} has no `##` help line"
        assert name in phony, f"{name} is not in .PHONY"
        assert name in readme, f"{name} is not documented in README.md"

    # And the doc is a real map, not a stub
    assert len(doc) > 2000
    assert "install_engine_launchers.py" in doc
    assert "architecture-bot.yml" in doc
