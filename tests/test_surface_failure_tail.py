"""The live-step failure-tail helper must be executable, parse, and surface the real cause.

Why this exists (issue #1714): a main-only live step (ci-hf-live's check-model-links /
check-registry / check-quant-catalog / test-unit-network, and pipeline's ci-top-tier) fails
with `make ... Error 2` whose real cause lives in the target's OWN log tail (e.g.
`... is gone`, an AssertionError, `make: *** [...] Error 1`), but the Actions check-run
annotation shows only the generic runner wrapper — the Node 20 deprecation warning and
`##[error]Process completed with exit code 2.` — with no trace. `scripts/surface_failure_tail.sh`
runs the command with combined output teed to a logfile and, on non-zero exit, emits the
ANSI-stripped tail of that logfile as `::error::` workflow commands, which GitHub renders as
the check-run annotation. These tests pin that behaviour so flake-vs-drift is decidable from
the check run, not a manual log fetch.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "scripts" / "surface_failure_tail.sh"


def _run(logfile: Path, argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(HELPER), str(logfile), "--", *argv],
                          capture_output=True, text=True)


def test_helper_is_executable():
    assert os.access(HELPER, os.X_OK), "scripts/surface_failure_tail.sh must be executable"


def test_helper_parses():
    r = subprocess.run(["bash", "-n", str(HELPER)], capture_output=True, text=True)
    assert r.returncode == 0, f"surface_failure_tail.sh has a syntax error:\n{r.stderr}"


def test_success_passthrough_emits_no_error_annotation(tmp_path):
    """A successful command must exit 0 and emit no ::error:: annotation."""
    log = tmp_path / "ok.log"
    r = _run(log, ["bash", "-c", "printf 'all good\\n'; exit 0"])
    assert r.returncode == 0, r.stderr
    assert "all good" in r.stdout
    assert "::error" not in r.stdout, r.stdout


def test_failure_preserves_rc_and_surfaces_real_tail_as_error_annotation(tmp_path):
    """A failing command must keep its exit code and surface the real tail lines
    (the ones the target's log already carries: the assertion, the file:line, the
    make Error) as ::error:: annotations — not the generic wrapper."""
    log = tmp_path / "fail.log"
    r = _run(log, ["bash", "-c",
                   "printf 'E AssertionError: ccore picks must be high->lower\\n"
                   "E assert [4482402816, 4482402848] == [4482402848, 4482402816]\\n"
                   "tests/test_top_tier_acceptance.py:321: AssertionError\\n"
                   "make: *** [Makefile:1830: ci-top-tier] Error 2\\n'; exit 77"])
    assert r.returncode == 77, r.stderr
    assert "::error::E AssertionError: ccore picks must be high->lower" in r.stdout, r.stdout
    assert "::error::tests/test_top_tier_acceptance.py:321: AssertionError" in r.stdout, r.stdout
    assert "::error::make: *** [Makefile:1830: ci-top-tier] Error 2" in r.stdout, r.stdout
