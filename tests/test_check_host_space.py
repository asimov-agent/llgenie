"""The host tmpfs headroom gate (issue #1583), held by a fake `df` on PATH.

The gate is `scripts/check_host_space.py` behind `make check-host-space`: it reads BOTH axes of a
shared tmpfs (`df -h` space and `df -i` inodes) and refuses when either is below its documented
threshold (<20% space free OR <50k inodes free), so a lane cannot start a doomed build on a full
`/tmp`. These tests drive the module with a fake `df` binary on PATH — the same seam the launcher and
docker stubs use — so every branch (healthy, low-space, low-inodes, unreadable `df`) runs hermetically.

The real axis that matters is the exit code and the named axis in the verdict: a gate that says
"FAIL" and names `space` or `inodes` is what a lane reads, not the raw df decimals.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import check_host_space as chs

#: A maximal df -h data row; the module reads Use% -> free% = 100 - use.
#: A maximal df -i data row; the module reads IFree (field 3).
_SPACE_ROW = "tmpfs            32G  7.5G   24G  24% /tmp"
_SPACE_FULL = "tmpfs            32G   27G  5.0G  85% /tmp"
_SPACE_OK_ROW = "tmpfs            32G  7.5G   24G  20% /tmp"
_INODES_ROW = "tmpfs          1048576 877407 171169   84% /tmp"
_INODES_LOW = "tmpfs          1048576 1048000     576  100% /tmp"
_INODES_OK_ROW = "tmpfs          1048576 877407 171169   84% /tmp"


def _stub_df(bindir: Path, *, space: str, inodes: str, fail: bool = False) -> str:
    """A fake `df` on PATH returning `-h` output for USE% and `-i` output for IFree.

    GNU df uses `-h` for human sizes and `-i` for inodes; the real field we parse differs by flag, so
    the stub keys on the flag it is called with and prints the two headers + the injected row.
    """
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / "df"
    exe.write_text(
        f"""#!/bin/sh
if [ "$1" = "-i" ]; then
  echo "Filesystem      Inodes  IUsed  IFree IUse% Mounted on"
  echo '{inodes}'
elif [ "$1" = "-h" ]; then
  echo "Filesystem      Size  Used Avail Use% Mounted on"
  echo '{space}'
else
  exit 1
fi
""" + ("exit 1\n" if fail else "")
    )
    exe.chmod(0o755)
    return str(bindir)


@pytest.fixture
def env_df(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])


class _Stv:
    """Minimal stand-in for the statvfs result the module reads (f_files/f_favail)."""

    def __init__(self, files: int, favail: int) -> None:
        self.f_files = files
        self.f_favail = favail


def _mounts(tmp_path, line: str) -> str:
    """Write a /proc/mounts-style table and return its path for chs._MOUNTS_PATH."""
    p = tmp_path / "mounts"
    p.write_text(line + "\n")
    return str(p)


@pytest.fixture(autouse=True)
def hermetic_probe(tmp_path, monkeypatch) -> None:
    """Keep the inode-usage probe hermetic in EVERY test: /tmp is a tmpfs at low usage.

    Without this, `report()` would read the real host's /proc/mounts + statvfs and the suite would
    pass/fail on the host's inode pressure. Inode-specific tests override _statvfs/_MOUNTS_PATH.
    """
    monkeypatch.setattr(chs, "_MOUNTS_PATH", _mounts(tmp_path, "tmpfs /tmp tmpfs rw,nosuid 0 0"))
    monkeypatch.setattr(chs, "_statvfs", lambda m: _Stv(1_000_000, 1_000_000))


def test_inode_usage_below_threshold_no_warning(tmp_path, monkeypatch, capsys) -> None:
    """At 84% inode usage (below the 85% default) the probe prints INFO, not WARNING."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    monkeypatch.setattr(chs, "_statvfs", lambda m: _Stv(1_000_000, 160_000))  # 84% used
    code = chs.main(["check", "--mount", "/tmp"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "WARNING" not in out
    assert "84% inode utilisation (below 85% threshold)" in out


def test_inode_usage_at_threshold_warns(tmp_path, monkeypatch, capsys) -> None:
    """At exactly 85% used the probe WARNINGs naming mount, percentage and threshold."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    monkeypatch.setattr(chs, "_statvfs", lambda m: _Stv(1_000_000, 150_000))  # 85% used
    code = chs.main(["check", "--mount", "/tmp"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "WARNING" in out
    assert "/tmp" in out and "85%" in out and "85%" in out
    assert "OWNER DECISION POINT" in out


def test_inode_usage_above_threshold_warns_and_names_fields(tmp_path, monkeypatch, capsys) -> None:
    """Above threshold the WARNING names the mount, the measured % and the configured threshold."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    monkeypatch.setattr(chs, "_statvfs", lambda m: _Stv(1_000_000, 90_000))  # 91% used
    code = chs.main(["check", "--mount", "/tmp", "--inodes-use-max", "90"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "WARNING" in out
    assert "/tmp" in out
    assert "91%" in out   # measured percentage
    assert "90%" in out   # threshold (--inodes-use-max)
    assert "this check never deletes or prunes" in out


def test_inode_usage_warns_with_owner_decision_update_pct(tmp_path, monkeypatch, capsys) -> None:
    """The threshold is tunable via --inodes-use-max: lower it and a below-default run warns."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    monkeypatch.setattr(chs, "_statvfs", lambda m: _Stv(1_000_000, 700_000))  # 30% used
    code = chs.main(["check", "--mount", "/tmp", "--inodes-use-max", "25"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "WARNING" in out and "/tmp" in out and "30%" in out


def test_inode_usage_statvfs_failure_on_tmpfs_raises(tmp_path, monkeypatch) -> None:
    """A statvfs failure on a tmpfs-identified real mount surfaces as an error, not a silent skip."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    # _MOUNTS_PATH from the autouse fixture says /tmp is a tmpfs; now statvfs fails on it.
    def boom(_m):
        raise OSError("statvfs denied")
    monkeypatch.setattr(chs, "_statvfs", boom)
    with pytest.raises(chs.HostSpaceError):
        chs.main(["check", "--mount", "/tmp"])


def test_inode_usage_non_tmpfs_and_missing_mount_skip(tmp_path, monkeypatch, capsys) -> None:
    """A non-tmpfs /tmp (or one absent from the mount table) must not abort the preflight."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    # /tmp on ext4 (not the shared tmpfs): the probe is skipped with an INFO line.
    monkeypatch.setattr(chs, "_MOUNTS_PATH", _mounts(tmp_path, "/dev/sda1 /tmp ext4 rw 0 0"))
    code = chs.main(["check", "--mount", "/tmp"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "WARNING" not in out
    assert "skipped (not a tmpfs mount" in out


def test_healthy_tmpfs_exits_0_and_reports_both_axes(env_df, capsys) -> None:
    """A tmpfs above both thresholds is green and names both axes."""
    code = chs.main(["check", "--mount", "/tmp"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "OK" in out
    assert "76% space free" in out and "171,169 inodes free" in out


def test_low_space_free_is_refused(tmp_path, monkeypatch, capsys) -> None:
    """A tmpfs at 15% space free (below 20%) exits 1 naming the space axis."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_FULL,
                                        inodes=_INODES_ROW) + ":" + os.environ["PATH"])
    code = chs.main(["check", "--mount", "/tmp", "--space-min", "20"])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "FAIL" in out and "space" in out
    assert "15% space free" in out


def test_low_inodes_free_is_refused(tmp_path, monkeypatch, capsys) -> None:
    """A tmpfs with fewer than 50k free inodes exits 1 naming the inode axis."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_LOW) + ":" + os.environ["PATH"])
    code = chs.main(["check", "--mount", "/tmp", "--inodes-min", "50000"])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "FAIL" in out and "inodes" in out
    assert "got 576" in out


def test_default_thresholds_refuse_at_issue_numbers(tmp_path, monkeypatch, capsys) -> None:
    """The exact issue scenario — <20% space OR <50k inodes with default thresholds — is refused."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,   # 76% free — space fine
                                        inodes=_INODES_LOW) + ":" + os.environ["PATH"])
    code = chs.main(["check", "--mount", "/tmp"])  # defaults: space-min 20, inodes-min 50000
    out = capsys.readouterr().out
    assert code == 1, out
    assert "FAIL" in out


def test_report_mode_always_exits_0(tmp_path, monkeypatch, capsys) -> None:
    """`report` prints the measurement but never fails — it is informational."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_FULL,
                                        inodes=_INODES_LOW) + ":" + os.environ["PATH"])
    code = chs.main(["report", "--mount", "/tmp"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "space free" in out and "inodes free" in out


def test_a_df_that_cannot_be_read_is_an_error_not_a_pass(tmp_path, monkeypatch, capsys) -> None:
    """An unreadable `df` must raise/exit non-zero — a preflight may not silently proceed."""
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_ROW,
                                        inodes=_INODES_ROW,
                                        fail=True) + ":" + os.environ["PATH"])
    with pytest.raises(chs.HostSpaceError):
        chs.main(["check", "--mount", "/tmp"])


def test_a_clean_parsed_ok_boundary(tmp_path, monkeypatch, capsys) -> None:
    """At exactly the thresholds the gate is green (>= space-min, >= inodes-min)."""
    # 20% free space (exactly the min) and 50,000 inodes (exactly the min) -> OK
    _SPACE_BOUND = "tmpfs            32G   25G  6.5G  80% /tmp"
    _INODES_BOUND = "tmpfs          1048576 998576 50000 96% /tmp"
    monkeypatch.setenv("PATH", _stub_df(tmp_path / "bin",
                                        space=_SPACE_BOUND,
                                        inodes=_INODES_BOUND) + ":" + os.environ["PATH"])
    code = chs.main(["check", "--mount", "/tmp", "--space-min", "20", "--inodes-min", "50000"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "OK" in out
