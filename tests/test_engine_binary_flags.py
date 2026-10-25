"""The engine-binary flag check: every flag a user types must answer (issue #580).

The bump PR's CI runs `make test-engine-image`, whose first check executes the built image's engine
binary with the flags its manifest documents plus the flags a user types. It used to pass on the
FIRST flag that answered, so a release that dropped `--help` — or a binary that only knows
`--version` — sailed through and broke the first user who typed `-h`.

These tests are hermetic (no docker, no image): they run the SHIPPED probe text (`BINARY_PROBE`) with
real `bash` against real executable files on disk, parse its verdicts with the shipped `parse_probe`,
and decide with the shipped `decide`. Nothing is stubbed — the probe and the decision are the product.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import engine_image as ei  # noqa: E402


def _binary(tmp_path: Path, answers: dict[str, str], default_rc: int = 1) -> Path:
    """A real executable that answers the flags in `answers` and fails the rest.

    `answers` maps a flag to the text it prints (exit 0). Any other flag exits `default_rc` with a
    line on stderr, which is what an engine that dropped the flag actually does.
    """
    cases = "\n".join(
        f'  {flag})\n    echo {_q(text)}\n    exit 0\n    ;;' for flag, text in answers.items())
    path = tmp_path / "engine-binary"
    path.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f"{cases}\n"
        '  *)\n'
        '    echo "unsupported flag: $1" >&2\n'
        f"    exit {default_rc}\n"
        "    ;;\n"
        "esac\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _q(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def _run(tmp_path: Path, answers: dict[str, str], flags: list[str], default_rc: int = 1):
    """Run the SHIPPED probe against a real executable, and parse what it printed."""
    binary = _binary(tmp_path, answers, default_rc)
    r = subprocess.run(["bash", "-c", ei.BINARY_PROBE, "llgenie-binary", str(binary), *flags],
                       capture_output=True, text=True, timeout=120,
                       env={**os.environ, "PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    return r, ei.parse_probe(r.stdout)


VERSION_TEXT = "fake-engine version 1.2.3"
HELP_TEXT = "usage: fake-engine [flags]"

EVERYTHING = {"--version": VERSION_TEXT, "-h": HELP_TEXT, "--help": HELP_TEXT, "-V": VERSION_TEXT}


# ---------------------------------------------------------------------------
# the probe reports every flag instead of stopping at the first
# ---------------------------------------------------------------------------
def test_the_probe_reports_every_flag_instead_of_stopping_at_the_first(tmp_path):
    """The old probe `exit 0`ed on the first answer: that is what masked a dead flag."""

    # Given a binary that answers --version and refuses --help
    r, verdicts = _run(tmp_path, {"--version": VERSION_TEXT}, ["--version", "--help"])

    # When  the probe runs
    # Then  it exits 0 (the verdict belongs to the caller) and reports a verdict for BOTH flags
    assert r.returncode == 0, r.stdout + r.stderr
    assert set(verdicts) == {"--version", "--help"}, verdicts

    # And   the verdicts are the flags' OWN results, not one shared success
    assert verdicts["--version"]["rc"] == 0 and verdicts["--version"]["bytes"] > 0
    assert verdicts["--help"]["rc"] != 0
    print(f"[probe] reported {sorted(verdicts)} — --help exit {verdicts['--help']['rc']}")


def test_the_parser_accepts_a_padded_byte_count(tmp_path):
    """BSD `wc -c` pads its count; a parser that only understands GNU spacing reds macOS (issue #580)."""

    # Given a verdict line whose byte count is padded, as BSD `wc -c` prints it
    text = "\n".join([
        "LG-FLAG --version 0       12",
        "LG-OUT-BEGIN --version",
        "fake-engine 1.2.3",
        "LG-OUT-END --version",
    ])

    # When  it is parsed
    verdicts = ei.parse_probe(text)

    # Then  the flag is recorded with its real numbers
    assert verdicts == {"--version": {"rc": 0, "bytes": 12, "output": "fake-engine 1.2.3"}}, verdicts
    assert ei.decide([], verdicts, "device", engine="mlx", variant="cuda")["ok"]  # an exempt cell
    # (a device verdict without the identity is itself a failure — see test_engine_gate_strict.py)


def test_a_missing_binary_file_is_still_the_probe_failure(tmp_path):
    """The exit-code contract survives: 1 means the file is missing, not 'a flag failed'."""

    # Given a path that is not an executable file anywhere on PATH
    r = subprocess.run(["bash", "-c", ei.BINARY_PROBE, "llgenie-binary",
                        str(tmp_path / "does-not-exist"), "--version"],
                       capture_output=True, text=True, timeout=60)

    # Then  the probe exits 1 and says which file it could not find
    assert r.returncode == 1, r.stdout + r.stderr
    assert "missing binary file" in r.stderr


# ---------------------------------------------------------------------------
# every documented flag must answer, individually
# ---------------------------------------------------------------------------
def test_a_dead_help_flag_reds_naming_the_flag(tmp_path):
    """A documented flag that stopped answering is the regression the bump's CI must catch."""

    # Given a binary that answers --version and exits 1 for the documented --help
    r, verdicts = _run(tmp_path, {"--version": VERSION_TEXT}, ["--version", "--help"])

    # When  the documented flags --version --help are decided
    verdict = ei.decide(["--version", "--help"], verdicts)

    # Then  the check fails and the failure names --help
    assert not verdict["ok"]
    assert any(line.startswith("--help: documented but did not answer") for line in verdict["failures"]), \
        verdict["failures"]
    print(f"[decide] {verdict['failures'][0].splitlines()[0]}")


def test_a_binary_that_answers_every_flag_passes(tmp_path):
    """The pass case, with each flag reported on its own line."""

    # Given a binary that answers every flag
    r, verdicts = _run(tmp_path, EVERYTHING, list(ei.TYPED_FLAGS))

    # When  the documented flags are decided
    verdict = ei.decide(["--version", "--help"], verdicts)

    # Then  it passes and every probed flag is recorded as answered
    assert verdict["ok"], verdict["failures"]
    assert all(verdicts[f]["rc"] == 0 for f in ei.TYPED_FLAGS), verdicts
    print(f"[decide] ok with {len(ei.TYPED_FLAGS)} flags answered")


# ---------------------------------------------------------------------------
# the families: what a user actually types
# ---------------------------------------------------------------------------
def test_no_help_spelling_reds_the_help_family(tmp_path):
    """Six engines document `--help` only: a family failure must name BOTH spellings."""

    # Given a binary that answers the version flags and neither help spelling
    r, verdicts = _run(tmp_path, {"--version": VERSION_TEXT, "-V": VERSION_TEXT},
                       ["--version", "-h", "--help", "-V"])

    # When  the verdicts are decided with no documented flags
    verdict = ei.decide([], verdicts)

    # Then  the help family is the failure, naming -h and --help
    assert not verdict["ok"]
    family = [line for line in verdict["failures"] if "help family" in line]
    assert family, verdict["failures"]
    assert "-h" in family[0] and "--help" in family[0], family[0]


def test_an_empty_manifest_still_requires_one_answer(tmp_path):
    """An engine that documents nothing keeps the old guarantee — said out loud."""

    # Given a manifest with no flags and a binary that answers none
    r, verdicts = _run(tmp_path, {}, list(ei.TYPED_FLAGS))

    # When  the verdicts are decided
    verdict = ei.decide([], verdicts)

    # Then  it fails, naming the probed flags
    assert not verdict["ok"]
    assert any("documents no flags" in line for line in verdict["failures"]), verdict["failures"]


def test_a_help_only_cli_is_not_failed_for_having_no_version_flag():
    """mlx_lm.server is argparse: --help/-h only. `probe: help` requires the help family and
    leaves the version to the image's `detect`, which prints the package version."""

    # Given a CLI that answers help but exits 2 on every version spelling
    verdicts = {"--help": {"rc": 0, "bytes": 40, "output": "usage"},
                "-h": {"rc": 0, "bytes": 40, "output": "usage"},
                "--version": {"rc": 2, "bytes": 10, "output": ""},
                "-V": {"rc": 2, "bytes": 10, "output": ""}}

    # When  the verdict is decided with the help policy, and with the default one
    help_verdict = ei.decide(["--help"], verdicts, policy="help")
    flags_verdict = ei.decide(["--help"], verdicts, policy="flags")

    # Then  help passes (its detect proves the version) while the strict policy still names it
    assert help_verdict["ok"], help_verdict
    assert not flags_verdict["ok"]
    assert "version family" in " ".join(flags_verdict["failures"])


def test_a_device_probe_is_contained_only_for_a_named_cell(tmp_path):
    """vllm cuda/rocm cannot answer without its device — but ONLY because they are named (#625).

    Until #625 any `probe: device` cell passed with every flag at exit 1, which is how four rows went
    green having proved nothing. The containment now has to be earned: the cell is in `DEVICE_ONLY`, and
    the note quotes the reason. An unlisted cell with the same verdicts is red.
    """

    # Given a `probe: device` variant whose flags all fail on this runner
    r, verdicts = _run(tmp_path, {}, list(ei.TYPED_FLAGS))

    # When  the verdicts are decided for a cell that IS on the exemption list
    listed = ei.decide(["--version", "--help"], verdicts, policy="device",
                       engine="vllm", variant="cuda")

    # Then  it passes, and says where the version comes from and why it is exempt
    assert listed["ok"], listed["failures"]
    assert "detect" in listed["note"] and "#625" in listed["note"], listed

    # And  the SAME verdicts on an unlisted cell are red — the policy alone no longer rescues it
    unlisted = ei.decide(["--version", "--help"], verdicts, policy="device",
                         engine="sglang", variant="cuda")
    assert unlisted["ok"] is False, unlisted
    assert any("DEVICE_ONLY" in f for f in unlisted["failures"]), unlisted["failures"]


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
