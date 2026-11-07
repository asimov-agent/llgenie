#!/usr/bin/env python3
"""The #902 restore-condition measurement + ordered restore list (issue #902/#817).

These tests lock the CLI contract so the restore never silently can't run: `measure --repo` is on
the MEASURE subparser (the Makefile and docstring both put `--repo` AFTER `measure`), and the
ordered restore list comes from `bots/pause.toml` in `restore_first` + `restore_after` order.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from scripts import bots_restore_health as b


def _stub_gh(tmp_path) -> str:
    """A `gh` stub that answers the /actions/runs probe with no runs (healthy queue), so measure is
    hermetic: it exercises parsing + the probe seam without a live API."""

    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
    gh.chmod(0o755)
    return str(gh)


def test_measure_accepts_repo_after_the_subcommand(tmp_path):
    """The Makefile (`CMD=measure REPO=...`) and the docstring both pass `--repo` AFTER `measure`;
    the parser must accept it there, or `make bots-restore-health CMD=measure` can never run (the
    #1879 restore can never be measured). `--repo` is a MEASURE subparser option, and the top-level
    parser no longer also swallows it before the subcommand.
    """

    # Given the documented `measure --repo owner/repo` argument order
    # When  main() is invoked exactly as the Makefile and docstring spell it
    # Then  argparse accepts it (this is the #1879 defect: it used to error "unrecognized arguments")
    rc = b.main(["measure", "--repo", "asimov-agent/llgenie", "--gh", _stub_gh(tmp_path),
                 "--now", "2026-11-07T00:00:00+00:00"])
    assert rc == 0, f"measure --repo must parse and return 0 (healthy stub), got rc={rc}"


def test_measure_requires_repo(tmp_path):
    """Without --repo, measure must refuse (issue #902: the queue measurement is per-repo)."""
    try:
        b.main(["measure", "--gh", _stub_gh(tmp_path), "--now", "2026-11-07T00:00:00+00:00"])
    except SystemExit as e:
        assert e.code != 0, "measure without --repo must exit non-zero"
    else:
        raise AssertionError("measure without --repo must SystemExit(2)")


def test_restore_prints_the_recorded_order():
    """`restore` prints `restore_first` then `restore_after` from bots/pause.toml — the cheap common
    bots first so the board wakes early, the heaviest last (the #902 decision)."""

    first = list(b.load_pause()["restore_first"])
    after = list(b.load_pause()["restore_after"])
    ordered = b.restore_order()
    assert ordered[:len(first)] == first, "restore order must lead with restore_first"
    assert ordered[len(first):] == after, "restore order must end with restore_after"
    # restore() CLI prints the same, one per line
    out = subprocess.run([sys.executable, str(b.__file__), "restore"],
                         capture_output=True, text=True, cwd=REPO)
    assert out.returncode == 0
    assert out.stdout.splitlines() == ordered
