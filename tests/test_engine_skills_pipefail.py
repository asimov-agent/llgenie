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

    # Then  every one reads no pipe at all: the CLI answers --version itself (v0.2.7), so the read
    #       cannot die of SIGPIPE and no early-exiting reader (`grep -q`) can creep back in
    for arch, detect in detects.items():
        assert "grep -q" not in detect, (arch, detect)
        assert "|" not in detect, (arch, detect)
        assert detect.endswith("--version"), (arch, detect)


def test_no_engine_reports_a_commit_sha_as_its_version():
    """`pin <sha>` is not a version (issue #636): a sha has no dots, so `make test-built-engine`
    rejects it and the published-image stage goes red for an engine that is perfectly fine.

    A `detect` may fall back to the PINNED VERSION (the skill's tag, e.g. `0.5.22`), never to the
    commit sha.
    """

    # Given every engine skill
    skills = sorted((REPO / "skills" / "engines").glob("*/SKILL.md"))

    # When  their detect lines are read
    offenders = {str(p.relative_to(REPO)): [l for l in p.read_text().splitlines()
                                            if l.startswith("detect:") and "{pinned_short}" in l]
                 for p in skills}
    offenders = {k: v for k, v in offenders.items() if v}

    # Then  none of them prints the sha as its version
    assert skills and offenders == {}, offenders
