"""The engine gate must be falsifiable: no flag answered = red, and a version must look like one (#625).

Audited from run 40204145334 (29/29 green):

  * `vllm/cuda`, `vllm/rocm`, `tensorrt-llm/cuda` and `mlx/cuda` had EVERY probe at exit 1 and were still
    green, because `decide()` returned ok for any `probe: device` cell;
  * `llama.cpp-laurentzuijdwijk` reported `installed 0.00.000.272 I srv  llama_server: initializing ...` and
    `sglang/rocm` reported `installed 0.0.0`, and `test_image()`'s `\\d+\\.\\d+` search accepted both.

These tests pin both halves: the exemption is a NAMED list with a reason, and a version must be a version.
No docker, no mocks of the product — `decide` and `version_proof` are the product's own pure functions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
from scripts import engine_image as ei


def _verdicts(**flags: int) -> dict:
    """Per-flag probe results: exit code per flag, one byte of output so 'answered' means exit 0."""
    return {f: {"rc": rc, "bytes": 1, "output": ("x" if rc == 0 else "boom")} for f, rc in flags.items()}


# --- the version half -------------------------------------------------------------------------------

def test_a_version_must_look_like_a_version():
    """A semver or a declared pin is a version; a log timestamp and `0.0.0` are not (issue #625)."""

    # Given the shapes measured in run 40204145334
    accepted = {
        "sglang 0.5.21": "0.5.21",
        "vllm/cpu: installed 0.32.0+cpu": "0.32.0",
        "llama.cpp/cpu: installed version: 0.7.0-dev (build 11870, commit 39febd2a0)": "0.7.0",
        "installed pin 3c75be02f450": "pin 3c75be02f450",
        "tensorfold-native 1.1.8": "1.1.8",
        # measured on the published laurentzuijdwijk/cpu image: a log line, THEN the real version
        "0.00.000.331 I srv  llama_server: initializing ...\n"
        "version: 0.5.0-dev (build 11364, commit 3c75be02f)\n"
        "built with GNU 13.3.0 for Linux x86_64": "0.5.0",
    }
    rejected = {
        "installed 0.00.000.272 I srv  llama_server: initializing ...": "",
        "installed 0.0.0": "",
        "": "",
        "installed": "",
    }

    # When  each line is read for a version
    # Then  only the real version shapes are accepted, and the token that proves it is returned
    for line, want in accepted.items():
        assert ei.version_proof(line) == want, (line, ei.version_proof(line))
    for line, want in rejected.items():
        assert ei.version_proof(line) == want, (line, ei.version_proof(line))


def test_the_log_stamp_and_the_placeholder_are_named_in_the_rule():
    """The two measured false positives are rejected BY NAME, so a new spelling cannot sneak past."""

    # Given the exact strings the old `\\d+\\.\\d+` search accepted
    log_stamp = "installed 0.00.000.406 I srv  llama_server: initializing ..."
    placeholder = "installed 0.0.0"

    # Then  both are refused, and neither is mistaken for a pin
    assert ei.version_proof(log_stamp) == ""
    assert ei.version_proof(placeholder) == ""


# --- the flag half ----------------------------------------------------------------------------------

def test_a_device_policy_cell_that_answers_nothing_is_red_unless_it_is_listed():
    """`probe: device` alone is not an exemption any more (issue #625)."""

    # Given every documented flag failing on a cell that is NOT on the exemption list
    documented = ["--version", "--help"]
    failed = _verdicts(**{"--version": 1, "--help": 1, "-h": 1, "-V": 1})

    # When  the verdict is taken for an unlisted cell
    verdict = ei.decide(documented, failed, "device", engine="sglang", variant="cuda")

    # Then  it is red, and the message says what to do about it
    assert verdict["ok"] is False, verdict
    assert any("DEVICE_ONLY" in f and "#625" in f for f in verdict["failures"]), verdict["failures"]


def test_a_listed_cell_is_exempt_but_says_why():
    """The four measured cells pass, and the log carries the exempting reason."""

    # Given the same all-failing probes on a cell that IS listed
    failed = _verdicts(**{"--version": 1, "--help": 1, "-h": 1, "-V": 1})
    engine, variant = "vllm", "cuda"
    assert (engine, variant) in ei.DEVICE_ONLY, "the measured cell must be on the exemption list"

    # When  the verdict is taken
    verdict = ei.decide(["--version", "--help"], failed, "device", engine=engine, variant=variant)

    # Then  it passes and the note quotes the reason instead of a generic "needs its device"
    assert verdict["ok"] is True, verdict
    assert "#625" in verdict["note"], verdict["note"]


def test_the_exemption_never_applies_to_a_flags_policy_cell():
    """An engine that declares `probe: flags` must answer a flag, listed or not."""

    # Given a listed cell, but the manifest says the flags policy
    failed = _verdicts(**{"--help": 1, "-h": 1})

    # When  the verdict is taken with policy=flags
    verdict = ei.decide(["--help"], failed, "flags", engine="vllm", variant="cuda")

    # Then  the exemption does not rescue it
    assert verdict["ok"] is False, verdict


def test_the_exemption_list_is_exactly_the_measured_cells():
    """Adding a cell to DEVICE_ONLY is a reviewed decision: the list is pinned, with a reason each."""

    # Given the exemption list as committed
    # Then  it is the four cells run 40204145334 measured, each with a reasoned, issue-tagged string
    assert set(ei.DEVICE_ONLY) == {("vllm", "cuda"), ("vllm", "rocm"),
                                   ("tensorrt-llm", "cuda"), ("mlx", "cuda")}, sorted(ei.DEVICE_ONLY)
    for cell, reason in ei.DEVICE_ONLY.items():
        assert "#625" in reason and len(reason) > 30, (cell, reason)


# --- the two broken detections this change fixes -----------------------------------------------------

def test_the_two_broken_detects_no_longer_produce_a_false_version():
    """`sglang` reports the installed distribution; the laurentzuijdwijk fork reports its pin."""

    # Given the committed params for both engines
    sglang = json.loads((REPO / "containers" / "engines" / "params" / "sglang.json").read_text())
    laurent = json.loads((REPO / "containers" / "engines" / "params"
                          / "llama.cpp-laurentzuijdwijk.json").read_text())

    # When  their detect commands are read
    # Then  sglang no longer trusts `sglang.__version__` (0.0.0 in the rocm wheel) …
    for variant, spec in sglang["variants"].items():
        assert "importlib.metadata" in spec["detect"], (variant, spec["detect"])
        assert "sglang.__version__" not in spec["detect"], (variant, spec["detect"])

    # And  the fork's `--version` (which DOES answer, exit 0) is still documented, while its detect greps
    #      the `version:` line instead of the log stamp that precedes it
    binaries = json.loads((REPO / "containers" / "engines" / "binaries.json").read_text())
    laurent_binaries = binaries["engines"]["llama.cpp-laurentzuijdwijk"]
    for variant, entry in laurent_binaries.items():
        assert entry["flags"] == ["--version", "--help"], (variant, entry)
    for variant, spec in laurent["variants"].items():
        assert "grep -E '^version:'" in spec["detect"], (variant, spec["detect"])


def test_the_gate_report_separates_what_each_row_proves():
    """`make engine-gate-report` is the census a reviewer reads instead of 27 logs (issue #625)."""

    import engine_gate_report as report  # noqa: PLC0415 (scripts/ is on sys.path above)

    # Given the committed params + manifest
    table = report.rows()

    # When  the census is taken
    by_verdict = {}
    for row in table:
        by_verdict.setdefault(row["verdict"], []).append((row["engine"], row["variant"]))

    # Then  every cell is classified, and the exempt ones are exactly the measured DEVICE_ONLY cells
    assert set(by_verdict) <= {"flag-proven", "device-exempt", "disabled"}, by_verdict
    assert sorted(by_verdict.get("device-exempt", [])) == sorted(ei.DEVICE_ONLY), by_verdict
    # And  the sweep's row count is reproduced: proven + exempt (disabled cells are not built)
    assert len(by_verdict["flag-proven"]) + len(by_verdict["device-exempt"]) == 28, \
        {k: len(v) for k, v in by_verdict.items()}


def test_sglang_reports_the_pinned_version_when_its_own_metadata_is_a_placeholder():
    """The rocm wheel's distribution version is `0.0.0`, so the detect must fall back to the PINNED
    VERSION (#625), never to the commit sha (#636).

    This is the regression the CI run after my first attempt caught (`FAIL sglang/rocm: entrypoint detect
    proves no version (… installed sglang 0.0.0)`) — the earlier test only checked that the detect mentioned
    `importlib.metadata`, which was not enough to keep a placeholder out of the gate. The fallback was then
    `pin <sha>`, which `make test-built-engine` rejects in turn (`installed sglang pin 35ce31329305`), so the
    fallback is now the skill's `version:`.
    """

    # Given sglang's committed params for both backends
    sglang = json.loads((REPO / "containers" / "engines" / "params" / "sglang.json").read_text())
    version = sglang["ref"].lstrip("v")   # v0.5.22 -> 0.5.22: the tag the image is built at

    # When  each detect command is read
    # Then  it falls back to the pinned version, not to the sha, and keeps the placeholder guarded
    for variant, spec in sglang["variants"].items():
        detect = spec["detect"]
        assert "importlib.metadata" in detect, (variant, detect)
        assert 'not in ("0.0.0", "")' in detect, \
            f"{variant}: the detect must treat 0.0.0 as a placeholder, not a version: {detect}"
        assert f'"{version}"' in detect, \
            f"{variant}: the fallback must be the pinned version {version}: {detect}"
        assert "pin " not in detect, f"{variant}: a commit sha is not a version (#636): {detect}"

    # And  the shapes it can print are accepted by the gate, while the placeholder is not
    assert ei.version_proof(f"sglang {version}") == version
    assert ei.version_proof("sglang pin e00930c54890") == "pin e00930c54890", \
        "an engine with no upstream version reports its pin — sglang just must not be one"
    assert ei.version_proof("sglang 0.0.0") == ""


def test_the_gate_report_shows_the_detect_that_will_prove_the_version():
    """The census must print each cell's `detect`, because that is what the gate judges (#625)."""

    import engine_gate_report as report  # noqa: PLC0415

    # Given the committed params, every cell the sweep would build has a detect
    for row in report.rows():
        if row["verdict"] == "disabled":
            continue
        assert row["detect"], row

    # And  the printed census carries it (a placeholder detect would be visible before any image job)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        report.main()
    out = buf.getvalue()
    assert "detect:" in out
    assert "importlib.metadata" in out or 'grep -E' in out  # the two fixed detects are on screen


def test_a_device_verdict_needs_the_cell_identity():
    """`decide(policy='device')` without engine/variant is unanswerable, not "not exempt" (#625).

    The engine-build `mlx/cuda` row failed on this: `tests/test_engine_version.py` called `decide()` with
    three arguments, so the identity defaulted to empty, the `DEVICE_ONLY` lookup missed, and a cell that
    `test_image` had just accepted was reported red (run 40215905868, job 121236921730).
    """

    # Given every probed flag failing, as on a GPU-less runner
    failed = _verdicts(**{"--help": 1, "-h": 1})

    # When  the verdict is taken with policy=device but no identity
    verdict = ei.decide(["--help"], failed, "device")

    # Then  it is red, and the message says the identity is what is missing (not that the cell is exempt)
    assert verdict["ok"] is False, verdict
    assert any("engine" in f and "variant" in f for f in verdict["failures"]), verdict["failures"]

    # And  the same call WITH the identity of a listed cell is green
    listed = ei.decide(["--help"], failed, "device", engine="mlx", variant="cuda")
    assert listed["ok"] is True, listed
