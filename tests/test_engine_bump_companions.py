"""Unit tests for the engine-bump companion contract (issue #2865).

The 2026-11-16 engine-bump wave (PRs #2855-#2859) went red three times per PR
for want of companions the lane never produced:

1. the guard gate: the PR body carried no `OPENSPEC: <change>` line, and
   `scripts/check_pr_hygiene.py` refuses a body without one;
2. the docs/scope gate: a bump touches `containers/` and
   `make check-docs`'s change->note contract wants an `agent-wiki/` note paired
   with a `docs/changes.d/` row; the lane wrote neither;
3. the unit gate: the regen rewrote the *previous* bump's frozen
   `docs/changes.d/` row (#2857 rewrote 2026-11-15-llama.cpp-bump.md), never
   touched the engine's own SKILL.md pin lines (vllm's `base:` stayed at
   v0.33.0 while its Dockerfiles moved to v0.34.0), and left the frozen
   `_image_hash` asserts at the old hashes.

These tests pin the fixed behaviour hermetically: they point the module's
`REPO_ROOT` / `SKILLS_DIR` at a tmp tree and exercise the exact functions the
lane calls. NO-SKIP POLICY: every test runs on any host.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

from scripts import engine_bump as eb  # noqa: E402
from scripts import engine_skills as es  # noqa: E402

#: A llama.cpp-shaped bump row: a branch pin, so the ref does not move and the
#: shas do — the exact shape the #144 machinery substitutes.
_ROW = {
    "old_sha": "84e6c41f" + "0" * 32,
    "new_sha": "e0314933" + "1" * 32,
    "old_ref": "master",
    "new_ref": "master",
}


@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    """Point the lane's writable roots at an empty tmp tree."""
    monkeypatch.setattr(eb, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(es, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(es, "SKILLS_DIR", tmp_path / "skills" / "engines")
    return tmp_path


def test_bump_writes_a_matching_agent_wiki_and_changes_d_pair(fake_repo):
    """The lane writes the note pair `make check-docs` demands (issue #2865)."""

    # Given a lane tree with the two record directories
    (fake_repo / "agent-wiki").mkdir()
    (fake_repo / "docs" / "changes.d").mkdir(parents=True)

    # When bump() writes its companions for one engine
    wiki, fragment = eb._write_companion_notes("llama.cpp", _ROW)

    # Then the pair shares one stem (the check-docs pairing contract)
    assert wiki == fake_repo / "agent-wiki" / wiki.name
    assert fragment == fake_repo / "docs" / "changes.d" / fragment.name
    assert wiki.stem == fragment.stem
    assert wiki.name.startswith("20") and wiki.name.endswith("-llama.cpp-bump.md")

    # And the row is a table row that links the note the way every hand-written
    # changes.d row does
    wiki_text = wiki.read_text()
    row_text = fragment.read_text()
    assert wiki_text.startswith("# 20") and "llama.cpp engine bump" in wiki_text
    assert "#107" in wiki_text and "#2865" in wiki_text
    assert row_text.startswith("| 20") and row_text.rstrip().endswith("|")
    link = f"[{wiki.name}](agent-wiki/{wiki.name})"
    assert link in row_text
    assert (fake_repo / link.split("](")[1][:-1]).is_file()


def test_changes_d_rows_of_earlier_bumps_survive_a_pin_rewrite(fake_repo):
    """A rewrite moves live asserts, never the row a previous bump recorded."""

    # Given a tree holding a previous bump's changes.d row naming the OLD pin
    hist = fake_repo / "docs" / "changes.d" / "2026-11-15-llama.cpp-bump.md"
    hist.parent.mkdir(parents=True)
    hist.write_text(
        "| 2026-11-15 | engine bump: llama.cpp re-pinned "
        "`84e6c41f` -> `84e6c41f` | [x](agent-wiki/x.md) | #107 |\n"
    )
    before = hist.read_text()

    # And a live test naming the old sha
    live = fake_repo / "tests" / "test_engine_skills.py"
    live.parent.mkdir(parents=True)
    live.write_text('PIN = "84e6c41f" + "0" * 32  # the pinned commit\n')

    # When a new bump rewrites the pin asserts
    changed = eb._rewrite_pin_asserts(
        "llama.cpp", _ROW["old_sha"], _ROW["new_sha"],
        _ROW["old_ref"], _ROW["new_ref"],
    )

    # Then the live test moved and the historical row did not (issue #2865)
    assert "tests/test_engine_skills.py" in changed
    assert live.read_text().startswith('PIN = "e0314933"')
    assert hist.read_text() == before


def test_skill_md_pin_lines_follow_the_bump(fake_repo):
    """The bumped engine's SKILL.md moves with the regen (issue #2865)."""

    # Given a skill whose base and tag name the old pin
    skill_md = es.SKILLS_DIR / "llama.cpp" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\n"
        "id: llama.cpp\n"
        "base: docker.io/library/ubuntu:24.04\n"
        "---\n"
        "Built cell: llgenie/llama.cpp:84e6c41f-dead1234-cuda\n"
        "\n"
        "History note: an earlier lane recorded something else here.\n"
    )

    # When the bump rewrites pin asserts
    changed = eb._rewrite_pin_asserts(
        "llama.cpp", _ROW["old_sha"], _ROW["new_sha"],
        _ROW["old_ref"], _ROW["new_ref"],
    )

    # Then the pin-bearing line moved and plain prose did not
    text = skill_md.read_text()
    assert "skills/engines/llama.cpp/SKILL.md" in changed
    assert "llgenie/llama.cpp:e0314933-dead1234-cuda" in text
    assert "84e6c41f" not in text
    assert "History note: an earlier lane recorded something else here." in text


def test_frozen_image_hash_asserts_move_with_a_regen(fake_repo):
    """A regen that changes an engine's image hash moves the frozen literals."""

    # Given tests that freeze the hash half of the engine's tags
    frozen = fake_repo / "tests" / "test_engine_skills_frozen.py"
    frozen.parent.mkdir()
    frozen.write_text(
        'def test_tag():\n'
        '    assert es._image_hash(params, "cuda") == "7c022c51"  '
        '# llgenie/llama-cpp:84e6c41f-7c022c51-cuda\n'
        '    unrelated = "7c022c51deadbeefcafe"\n'
    )

    # When the lane rewrites the hashes a regen moved
    touched = eb._rewrite_frozen_hashes([("7c022c51", "abcdef12")], "llama.cpp")

    # Then only lines that actually pin the tag/hash moved
    assert touched == ["tests/test_engine_skills_frozen.py"]
    text = frozen.read_text()
    assert '== "abcdef12"' in text
    assert "llgenie/llama-cpp:84e6c41f-abcdef12-cuda" in text
    assert 'unrelated = "7c022c51deadbeefcafe"' in text


def test_variant_hashes_reads_the_params_tree_on_disk(fake_repo):
    """`_variant_hashes` reads the same seam `image_spec` builds tags from."""

    # Given a params file for the engine
    params_dir = fake_repo / "containers" / "engines" / "params"
    params_dir.mkdir(parents=True)
    (params_dir / "llama.cpp.json").write_text('{"id": "llama.cpp", "variants": {}}\n')

    # When the lane snapshots the hash halves, the params it cannot resolve
    # (no dockerfiles in the fake tree) yield an empty map rather than a crash
    assert eb._variant_hashes("llama.cpp") == {}


def test_engine_bump_workflow_stages_the_notes_and_names_the_openspec_change():
    """The commit step stages agent-wiki/ and the body names an active change."""

    # Given the workflow the lane runs
    wf = (REPO_ROOT / ".github" / "workflows" / "engine-bump.yml").read_text()

    # When we inspect the staging and body steps
    stage_lines = [l for l in wf.splitlines() if "git add" in l]
    assert stage_lines, "no git add step found"
    assert any("agent-wiki/" in l for l in stage_lines), (
        "the bump commit must stage agent-wiki/ so the note pair lands (#2865)"
    )
    assert "OPENSPEC: publish-changed-pin-images" in wf, (
        "the bump PR body must carry the OPENSPEC line the hygiene gate reads (#2865)"
    )

    # And the named change really is an active OpenSpec change
    assert (REPO_ROOT / "openspec" / "changes" / "publish-changed-pin-images").is_dir()
