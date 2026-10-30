"""The CLI is named after the project, and the old name is gone (#251, #816).

Two things this pins:

1. **The rename guard.** The CLI module is `scripts/llgenie_serve.py`; no live file
   may mention the old module name again. `llama-server` (upstream's binary), its
   shim, `build_llama_server.sh`, `LLAMA_SERVER*`/`LLAMA_CUBLAS`/`LLAMA_HOST` and
   the dated history under `agent-wiki/` and merged `openspec/changes/` are NOT
   what this guards — they are upstream's names and the record of what happened.
2. **The seam split.** llgenie's own knobs carry llgenie's name
   (`LLGENIE_BACKEND`, `LLGENIE_RAM_BYTES`, …) and the old `LLAMA_*` names keep
   working as deprecated aliases, so no host or CI job breaks on the rename.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import env_seam  # noqa: E402
import detect_server  # noqa: E402
import module_name_guard as guard  # noqa: E402

# ONE rule, shared with the writer (issue #573): the architecture bot's doc refresh is checked by
# `guard.offenders()` before it commits, so a rule fixed here cannot leave the bot writing what this
# test refuses.
OLD_MODULE = guard.OLD_MODULE
SKIP_DIRS = guard.SKIP_DIRS
ALLOWED_PREFIXES = guard.ALLOWED_PREFIXES


def live_files():
    """Every live text file, minus the shim, history, and this guard itself.

    This file is the one place that *must* spell out the old name (it is what it
    forbids), so it excludes itself rather than special-casing its own text.
    """
    me = Path(__file__).resolve()
    # GIT-TRACKED files only (issue #350): a scratch artefact or a bot's gitignored working file
    # (`refine-in.md`) reddened the local loop while a fresh CI checkout stayed green.
    for p in guard.live_files(REPO):
        if not p.is_file() or set(p.parts) & SKIP_DIRS or p.resolve() == me:
            continue
        rel = str(p.relative_to(REPO))
        if any(rel.startswith(pre) for pre in ALLOWED_PREFIXES):
            continue
        if p.suffix.lower() in guard.SKIP_SUFFIXES:
            continue
        try:
            yield rel, p.read_text()
        except (UnicodeDecodeError, OSError):
            continue


def test_no_live_file_mentions_the_old_module_name():
    """The tree is clean — the same check the architecture bot runs before it publishes (#573)."""

    # Given the whole tree, with this guard test excluded (it spells the name it forbids)
    hits = guard.hits(REPO, exclude=[Path(__file__)])

    # Then  no live file names the retired module
    assert not hits, (
        "the CLI module is scripts/llgenie_serve.py (#251); these files still name it "
        f"llama_serve: {hits}"
    )


def test_the_binary_and_upstream_names_are_untouched():
    """The guard is about the module, not about llama.cpp — those names must survive."""
    joined = "\n".join(text for _, text in live_files())
    for keep in ("llama-server", "build_llama_server.sh", "LLAMA_SERVER", "LLAMA_CUBLAS"):
        assert keep in joined, f"{keep} is upstream's name and must not be renamed away"
    assert (REPO / "scripts" / "build_llama_server.sh").exists()


def test_the_shim_is_gone_and_the_real_cli_still_runs():
    """The retired module is not importable, and the entry point that replaced it works (#816)."""

    # Given the checkout, where the deprecated shim has been deleted
    assert not (REPO / "scripts" / "llama_serve.py").exists()

    # When  the old module is resolved and the real CLI is asked for its help
    old_spec = importlib.util.find_spec("scripts.llama_serve")
    new_spec = importlib.util.find_spec("scripts.llgenie_serve")
    r = subprocess.run([sys.executable, "scripts/llgenie_serve.py", "--help"],
                       cwd=str(REPO), capture_output=True, text=True, timeout=780)

    # Then  only the new module resolves, and it actually reaches the CLI — not a hollow removal
    assert old_spec is None, "the retired module must not be importable"
    assert new_spec is not None, "scripts.llgenie_serve must be the importable entry point"
    assert r.returncode == 0, r.stderr
    assert "usage" in (r.stdout + r.stderr).lower()


def test_the_installed_artifacts_point_at_the_new_module():
    mk = (REPO / "Makefile").read_text()
    assert "scripts/llgenie_serve.py" in mk
    assert OLD_MODULE.search(mk) is None, "the Makefile must name the module by its new name"


# --------------------------------------------------------------------------
# the seams: llgenie's name wins, the old name still works
# --------------------------------------------------------------------------

def test_every_recorded_seam_is_actually_read_by_the_code():
    """No aspirational aliases: each SEAMS row must appear in the sources."""
    sources = "\n".join(text for rel, text in live_files() if rel.startswith(("scripts/", "Makefile")))
    for new, old in env_seam.SEAMS.items():
        assert new in sources, f"{new} is in the seam table but nothing reads it"
        assert old in sources, f"{old} (the deprecated alias) is not read anywhere"


def test_the_new_name_wins_and_the_old_one_still_works():
    env = {"LLGENIE_BACKEND": "cuda", "LLAMA_BACKEND": "cpu"}
    assert env_seam.env_seam("LLGENIE_BACKEND", "LLAMA_BACKEND", env) == "cuda"
    assert env_seam.env_seam("LLGENIE_BACKEND", "LLAMA_BACKEND", {"LLAMA_BACKEND": "cpu"}) == "cpu"
    assert env_seam.env_seam("LLGENIE_BACKEND", "LLAMA_BACKEND", {}) is None
    # an empty new value is "unset", so the alias is still honoured
    assert env_seam.env_seam("LLGENIE_BACKEND", "LLAMA_BACKEND",
                             {"LLGENIE_BACKEND": "", "LLAMA_BACKEND": "metal"}) == "metal"


def test_seam_lookup_accepts_either_name_and_refuses_a_stranger():
    assert env_seam.seam("LLGENIE_RAM_BYTES", {"LLGENIE_RAM_BYTES": "12"}) == "12"
    assert env_seam.seam("LLAMA_RAM_BYTES", {"LLAMA_RAM_BYTES": "12"}) == "12"
    with pytest.raises(KeyError):
        env_seam.seam("LLAMA_SERVER")


def test_detect_server_honours_both_spellings(monkeypatch):
    monkeypatch.setenv("LLGENIE_BACKEND", "cpu")
    monkeypatch.delenv("LLAMA_BACKEND", raising=False)
    assert detect_server.detect_backend() == "cpu"
    monkeypatch.delenv("LLGENIE_BACKEND", raising=False)
    monkeypatch.setenv("LLAMA_BACKEND", "cpu")
    assert detect_server.detect_backend() == "cpu"


def test_detect_server_prefers_the_new_spelling(monkeypatch):
    monkeypatch.setenv("LLGENIE_RAM_BYTES", str(8 * 1024 ** 3))
    monkeypatch.setenv("LLAMA_RAM_BYTES", str(99 * 1024 ** 3))
    assert detect_server.detect_card_ram_bytes() == 8 * 1024 ** 3


def test_detect_server_writes_the_new_spelling_for_its_children():
    """--backend/--ram-gb export the new names, so child processes see one convention."""
    src = (REPO / "scripts" / "detect_server.py").read_text()
    assert 'os.environ["LLGENIE_BACKEND"]' in src and 'os.environ["LLGENIE_RAM_BYTES"]' in src


def test_the_shared_rule_reads_one_text():
    """The rule the bot runs before it publishes is the rule this suite enforces (#573)."""

    # Given a line naming the retired module — BUILT, never spelled: this file must stay clean for
    # the guard it tests
    retired = "llama" + "_serve"

    # When  the shared rule reads it
    found = guard.offenders(f"| `{retired}.py` (deprecated alias) |")

    # Then  it is named, and the new module name is not
    assert found == [retired], found
    assert guard.is_clean("the launcher is `scripts/llgenie_serve.py`") is True


def test_the_guard_refuses_a_resurrected_shim_and_keeps_the_history(tmp_path):
    """The dated record says whatever was true then; a resurrected shim is an ordinary offender."""

    # Given a tree with a file at the retired shim path, a history entry, and a live doc
    retired = "llama" + "_serve"
    for d in ("scripts", "agent-wiki", "docs"):
        (tmp_path / d).mkdir()
    (tmp_path / "scripts" / f"{retired}.py").write_text(f"# {retired}\n")
    (tmp_path / "agent-wiki" / "2026-01-01-x.md").write_text(f"# {retired}\n")
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(f"# {retired}\n")

    # When  the tree is checked
    found = guard.hits(tmp_path)

    # Then  the shim path and the live doc are hits; the dated history is not — the shim's own
    # exemption was retired with the shim (#816)
    assert found == ["docs/ARCHITECTURE.md", f"scripts/{retired}.py"], found


def test_a_gitignored_file_naming_the_old_module_does_not_redden_the_guard(tmp_path):
    """The guard reads what git tracks (issue #350), so an untracked, gitignored working file is
    not a finding — CI checks out the tracked tree, and it must be the same verdict here."""

    # Given a gitignored file the refiner leaves in the checkout, naming the old module
    scratch = REPO / "refine-in.md"
    assert "refine-in.md" in (REPO / ".gitignore").read_text(), "the fixture relies on .gitignore"
    scratch.write_text("the old module llama_serve.py, quoted by a bot artifact\n")
    try:
        # When  the guard reads the repo
        seen = {str(p.relative_to(REPO)) for p in guard.live_files(REPO)}
        found = guard.hits(REPO, exclude=[Path(__file__)])
    finally:
        scratch.unlink(missing_ok=True)

    # Then  the gitignored file is neither read nor a finding
    assert "refine-in.md" not in seen
    assert "refine-in.md" not in found, found


def test_the_cli_is_green_on_this_tree(capsys):
    """The entry point `make check-module-names` runs is the CLI, so the CLI must pass here (#812)."""

    # Given this repository, where no live file names the old module
    # When  the CLI judges the whole tree
    rc = guard.main(["check", "--root", str(REPO)])
    out = capsys.readouterr()

    # Then  it passes and says so — the exact case that was red before #812
    assert rc == 0, out.err
    assert "OK" in out.out


def test_the_cli_refuses_a_planted_old_name(tmp_path, capsys):
    """The negative control: excluding one file must not blunt the rule for every other live file."""

    # Given a live file that names the retired module
    (tmp_path / "planted.py").write_text("from scripts import llama_serve  # planted\n")

    # When  the CLI judges that tree
    rc = guard.main(["check", "--root", str(tmp_path)])
    err = capsys.readouterr().err

    # Then  it refuses, naming exactly that file
    assert rc == 1
    assert "planted.py" in err


def test_the_self_exclusion_is_a_decision_not_a_hole(capsys):
    """`--include-self` judges this file too, so the exclusion is provably what makes the CLI green."""

    # Given the CLI's exclusion, which names exactly this test file and nothing else
    assert guard.SELF_EXCLUDED == ("tests/test_rename_llgenie_serve.py",)

    # When  the CLI is asked to judge it as well
    rc = guard.main(["check", "--root", str(REPO), "--include-self"])
    err = capsys.readouterr().err

    # Then  the file the exclusion names is exactly the file the rule would refuse
    assert rc == 1
    assert "tests/test_rename_llgenie_serve.py" in err
