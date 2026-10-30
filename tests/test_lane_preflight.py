"""One pre-push target for a host lane: run the FAST gates before the push (issue #1058).

`make lane-preflight` gives a host lane ONE command that re-checks the fast set before it pushes, so
a PR cannot open on a gate its own head fails. This file keeps it honest:

- it runs the **one** gate list — `FAST_GATES` imported from `scripts/issue_bot_gates.py`, not a
  copy (the #475 "one list" property: adding a gate stays a single edit);
- it runs **every** gate and prints `<gate>: rc=<n>` per gate plus a final `preflight: OK|FAILED (n)`
  (unlike `issue-bot-gates`, which stops at the first red because it gates a push);
- it refuses a **dirty** tree (a tracked file differing from `HEAD`), so the verdict describes the
  would-be-pushed head and not an unpushed worktree (#919's failure mode), while an untracked
  scratch file does not block it;
- a real defect on a real gate really reds the preflight — exercised with `check-import-roots` (the
  #953 class, deliberately NOT in `FAST_GATES`) through `--gates`, proving a gate outside the fast
  six can be run on demand without widening `FAST_GATES`;
- the make target exists, is `.PHONY`, and runs the script (a target that stopped naming it would be
  a green no-op).
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from scripts import lane_preflight  # noqa: E402  (the module under test)
from scripts import issue_bot_gates  # noqa: E402  (the source of the one gate list)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), check=True,
                   capture_output=True, text=True)


def _temp_repo(tmp_path: Path, makefile: str, *, commit: bool = True) -> Path:
    """A real git repo with a real Makefile whose gate targets the test controls."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "Makefile").write_text(textwrap.dedent(makefile))
    (root / "tracked.txt").write_text("baseline\n")
    if commit:
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "init")
    return root


# --------------------------------------------------------------------------
# the one list: FAST_GATES is IMPORTED, not restated
# --------------------------------------------------------------------------

def test_fast_gates_is_the_imported_object_not_a_copy():
    """`lane_preflight.FAST_GATES` must BE `issue_bot_gates.FAST_GATES` (same object)."""
    assert lane_preflight.FAST_GATES is issue_bot_gates.FAST_GATES, (
        "lane-preflight must import FAST_GATES, not restate it: identity is what keeps the "
        "one-list property (#475) — a copy drifts the day someone edits the other"
    )


def test_default_gate_set_matches_fast_gates():
    assert tuple(lane_preflight.FAST_GATES) == tuple(issue_bot_gates.FAST_GATES)


# --------------------------------------------------------------------------
# runner semantics: every gate reported, verdict printed, exit code honest
# --------------------------------------------------------------------------

def test_all_gates_pass_prints_rc_zero_and_ok(tmp_path, capsys):
    root = _temp_repo(tmp_path, """
        .PHONY: g1 g2
        g1:
        \t@true
        g2:
        \t@true
        """)
    rc = lane_preflight.run(root, ("g1", "g2"))
    out = capsys.readouterr()
    assert rc == 0
    combined = out.out + out.err
    assert "g1: rc=0" in combined and "g2: rc=0" in combined
    assert "preflight: OK" in combined


def test_a_failing_gate_reds_the_preflight_and_is_named(tmp_path, capsys):
    root = _temp_repo(tmp_path, """
        .PHONY: good bad
        good:
        \t@true
        bad:
        \t@false
        """)
    rc = lane_preflight.run(root, ("good", "bad"))
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "good: rc=0" in combined
    # make reports a failing recipe as its own nonzero (2); we only assert "failed"
    assert "bad: rc=0" not in combined and "bad: rc=" in combined
    assert "preflight: FAILED (1)" in combined and "bad" in combined


def test_every_gate_runs_even_after_a_failure(tmp_path, capsys):
    """Unlike issue-bot-gates, lane-preflight does not stop at the first red."""
    root = _temp_repo(tmp_path, """
        .PHONY: a b c
        a:
        \t@false
        b:
        \t@false
        c:
        \t@true
        """)
    rc = lane_preflight.run(root, ("a", "b", "c"))
    combined = capsys.readouterr()
    text = combined.out + combined.err
    assert rc == 1
    # all three reported => did not stop at a
    assert "a: rc=0" not in text and "b: rc=0" not in text and "c: rc=0" in text
    assert "preflight: FAILED (2)" in text


# --------------------------------------------------------------------------
# the would-be-pushed head: a dirty tracked tree is refused, untracked is not
# --------------------------------------------------------------------------

def test_dirty_tracked_file_is_refused(tmp_path, capsys):
    root = _temp_repo(tmp_path, """
        .PHONY: g
        g:
        \t@true
        """)
    (root / "tracked.txt").write_text("changed but not committed\n")
    rc = lane_preflight.run(root, ("g",))
    err = capsys.readouterr().err
    assert rc == 1, "a tracked file differing from HEAD must fail the preflight"
    assert "differs from HEAD" in err and "tracked.txt" in err
    assert "unpushed tree" in err


def test_untracked_file_does_not_block(tmp_path, capsys):
    root = _temp_repo(tmp_path, """
        .PHONY: g
        g:
        \t@true
        """)
    (root / "scratch-notes.txt").write_text("my lane scratch\n")
    rc = lane_preflight.run(root, ("g",))
    combined = capsys.readouterr()
    assert rc == 0, "an untracked scratch file must not red the preflight"
    assert "preflight: OK" in (combined.out + combined.err)


# --------------------------------------------------------------------------
# a real gate, a real defect: check-import-roots reds via --gates (the #953 class)
# --------------------------------------------------------------------------

def test_real_gate_outside_fast_gates_reds_the_preflight(tmp_path, capsys):
    """A real gate OUTSIDE FAST_GATES can be run on demand, and a real defect really reds it.

    Uses a self-contained ratchet-style gate (the shape of `check-import-roots`, the #953 class) so
    the test does not depend on any other branch's unmerged script: it counts offending lines and
    fails when the count exceeds a recorded baseline.
    """
    (tmp_path / "gate").mkdir()
    (tmp_path / "gate" / "ratchet.py").write_text(textwrap.dedent("""
        import json, sys
        from pathlib import Path
        base = json.loads(Path("tests/baseline.json").read_text())["count"]
        now = sum(1 for p in Path("src").rglob("*.py")
                  for line in p.read_text().splitlines() if "import scripts" in line)
        print(f"ratchet: {now} now, {base} recorded")
        sys.exit(1 if now > base else 0)
        """))
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "baseline.json").write_text('{"count": 0}\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "offender.py").write_text("import scripts.check_workflows\n")
    (tmp_path / "Makefile").write_text(
        ".PHONY: check-import-roots\n"
        "check-import-roots:\n"
        "\t@python3 gate/ratchet.py\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")

    rc = lane_preflight.run(tmp_path, ("check-import-roots",))
    combined = capsys.readouterr()
    text = combined.out + combined.err
    assert rc == 1, "a real ratchet regression must red the preflight"
    assert "check-import-roots: rc=0" not in text
    assert "preflight: FAILED (1)" in text


# --------------------------------------------------------------------------
# wiring: the make target exists, is .PHONY, and runs the script
# --------------------------------------------------------------------------

def test_make_target_exists_is_phony_and_runs_the_script():
    mk = (REPO / "Makefile").read_text()
    assert "\nlane-preflight:" in mk, "make lane-preflight must exist"
    # runs the script (a target naming nothing is a no-op)
    recipe_block = mk.split("\nlane-preflight:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/lane_preflight.py run" in recipe_block, (
        "the target must run scripts/lane_preflight.py run")
    # declared .PHONY: the target name appears somewhere in a .PHONY continuation block
    phony_text = mk.split("\n.PHONY:", 1)[1]
    assert "lane-preflight" in phony_text, "lane-preflight must be declared .PHONY"
