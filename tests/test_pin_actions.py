"""The action-pin gate (issue #719): every GitHub Action runs at a commit, not at a moving tag.

A tag in someone else's repository is a pointer that moves without a commit here. The gate must
fail on a floating ref, pass on a 40-hex SHA and on this repository's own `./…` refs, and `update`
must be idempotent — a second run changes nothing, because a gate whose fix re-writes the file
every time produces an uncommittable diff.

Each rule is proven on a fixture tree first; then the gate is run over THIS repository, because a
convention the repo itself violates is not a convention.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import pin_actions as pa

SHA = "11d5960a326750d5838078e36cf38b85af677262"


def _tree(tmp_path: Path, body: str) -> Path:
    """A repository-shaped fixture: one workflow file, module REPO pointed at the tree."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "one.yml").write_text(body, encoding="utf-8")
    return tmp_path


def _workflow(uses: str) -> str:
    return (
        "name: one — a fixture\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  go:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - uses: {uses}\n"
    )


def test_floating_tag_fails_the_gate(tmp_path, monkeypatch):
    """`actions/checkout@v4` is refused: the tag can move under the job."""

    # Given a workflow whose only action floats on a tag
    monkeypatch.setattr(pa, "REPO", _tree(tmp_path, _workflow("actions/checkout@v4")))

    # When  the gate runs
    rc = pa.check()

    # Then  it fails, so the PR cannot merge with a mutable ref
    assert rc == 1


def test_full_sha_passes_the_gate(tmp_path, monkeypatch):
    """A 40-hex commit is the only accepted third-party ref."""

    # Given a workflow pinned to a full commit SHA
    monkeypatch.setattr(pa, "REPO", _tree(tmp_path, _workflow(f"actions/checkout@{SHA} # v4")))

    # When  the gate runs
    rc = pa.check()

    # Then  it passes
    assert rc == 0


def test_short_sha_fails_the_gate(tmp_path, monkeypatch):
    """A 7-char prefix is not a pin: GitHub resolves it, but a rewrite can collide."""

    # Given a workflow pinned to an abbreviated SHA
    monkeypatch.setattr(pa, "REPO", _tree(tmp_path, _workflow("actions/checkout@11d5960 # v4")))

    # When  the gate runs
    rc = pa.check()

    # Then  it fails
    assert rc == 1


def test_local_action_and_reusable_workflow_are_exempt(tmp_path, monkeypatch):
    """This repository's own content cannot move independently, so it needs no pin."""

    # Given a workflow using the repo's own composite action and reusable workflow
    body = (
        "name: one — a fixture\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  go:\n"
        "    uses: ./.github/workflows/pipeline.yml\n"
        "  other:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: ./.github/actions/docker\n"
    )
    monkeypatch.setattr(pa, "REPO", _tree(tmp_path, body))

    # When  the gate runs
    rc = pa.check()

    # Then  it passes with no third-party refs to judge
    assert rc == 0


def test_non_action_uses_value_is_not_judged(tmp_path, monkeypatch):
    """`uses: job` (a matrix value) is not an action ref and must not fail the gate."""

    # Given a workflow whose `uses:` names a matrix value, not an action
    monkeypatch.setattr(pa, "REPO", _tree(tmp_path, _workflow("job")))

    # When  the gate runs
    rc = pa.check()

    # Then  it passes — the gate refuses refs it can judge, never text it cannot
    assert rc == 0


def test_report_names_each_ref_and_its_state(tmp_path, monkeypatch, capsys):
    """The report is what a reader uses to see the pin state of every ref."""

    # Given a tree with one floating ref
    monkeypatch.setattr(pa, "REPO", _tree(tmp_path, _workflow("actions/checkout@v4")))

    # When  the report runs
    pa.report()

    # Then  it prints the state, the file:line and the tag
    out = capsys.readouterr().out
    assert "FLOATING" in out
    assert "actions/checkout @ v4" in out
    assert ".github/workflows/one.yml:8" in out


def test_update_pins_and_keeps_the_tag_readable(tmp_path, monkeypatch):
    """`update` rewrites the ref to a SHA and keeps `# v4` so the diff is reviewable."""

    # Given a tree with a floating ref and a resolver that answers a known commit
    root = _tree(tmp_path, _workflow("actions/checkout@v4"))
    monkeypatch.setattr(pa, "REPO", root)
    monkeypatch.setattr(pa, "resolve", lambda action, tag: SHA)

    # When  update runs
    pa.update()

    # Then  the file carries the SHA and the tag comment, and the gate now passes
    text = (root / ".github/workflows/one.yml").read_text(encoding="utf-8")
    assert f"actions/checkout@{SHA} # v4" in text
    assert pa.check() == 0


def test_update_is_idempotent(tmp_path, monkeypatch):
    """A pinned tree is left byte-identical, so a second `make update-actions` is a no-op."""

    # Given a tree that is already pinned
    root = _tree(tmp_path, _workflow(f"actions/checkout@{SHA} # v4"))
    monkeypatch.setattr(pa, "REPO", root)
    monkeypatch.setattr(pa, "resolve", lambda action, tag: "0" * 40)
    before = (root / ".github/workflows/one.yml").read_text(encoding="utf-8")

    # When  update runs over it
    pa.update()

    # Then  nothing changed — no resolver call was even needed
    after = (root / ".github/workflows/one.yml").read_text(encoding="utf-8")
    assert after == before


def test_this_repository_is_fully_pinned(monkeypatch):
    """The convention holds in the tree that ships the gate."""

    # Given the real repository
    monkeypatch.setattr(pa, "REPO", REPO)
    floating = [f for f in pa.findings() if f["action_like"] and not f["pinned"]]

    # When  every action ref is read
    # Then  none of them floats
    assert floating == [], [f"{f['file']}:{f['line']} {f['ref']}" for f in floating]
