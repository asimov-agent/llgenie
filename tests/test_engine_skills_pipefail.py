"""Engine skills must survive `set -o pipefail`, which `engine_runner` uses for every step.

`grep -q` exits at the first match; the command writing into the pipe then takes SIGPIPE and
`pipefail` reports 141. That made `strata/rocm`'s `version` exit 1 while its binary was
perfectly fine — found by the dispatch sweep (issue #614).
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_no_engine_skill_pipes_into_grep_q():
    """No skill's detect/install pipes into `grep -q`."""

    # Given every engine skill
    skills = sorted((REPO / "skills" / "engines").glob("*/SKILL.md"))

    # When  their lines are read
    offenders = [str(p.relative_to(REPO)) for p in skills if "grep -q" in p.read_text()]

    # Then  none of them pipes into `grep -q`, which would die on SIGPIPE under pipefail
    assert skills, "no engine skills found"
    assert offenders == [], f"pipe into `grep -q` breaks under `set -o pipefail`: {offenders}"


def test_strata_detect_uses_a_full_read():
    """The fixed strata detect keeps the version line and does not short-circuit the pipe."""

    # Given strata's committed params (what the image runs)
    import json

    params = json.loads((REPO / "containers/engines/params/strata.json").read_text())

    # When  each variant's detect is read
    detects = {a: v["detect"] for a, v in params["variants"].items()}

    # Then  every one reads no pipe at all: the CLI answers --version itself (v0.2.4), so the read
    #       cannot die of SIGPIPE and no early-exiting reader (`grep -q`) can creep back in
    for arch, detect in detects.items():
        assert "grep -q" not in detect, (arch, detect)
        assert "|" not in detect, (arch, detect)
        assert detect.endswith("--version"), (arch, detect)
