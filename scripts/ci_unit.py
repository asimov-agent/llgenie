#!/usr/bin/env python3
"""`make ci-unit` as a scripts/ entry point (issue #2675, #800 criterion 5).

The 51-line `$(MAKE)` recipe of the `ci-unit` target (mk/ci.mk at the PR base
origin/main@dcfb96b7df) moves here unchanged, as an ordered sequence of `make ...`
command strings: same sub-targets, same order, same fail-fast, same exit code. The
thin target recipe (`@python3 scripts/ci_unit.py`) keeps the `bash-check` prerequisite,
the `##` help line and the target declaration in place — no inventory delta.

Each entry runs through the make binary make itself sets (`MAKE` env, fallback `make`),
so CI flags in `MAKEFLAGS` reach the sub-targets exactly as `$(MAKE)` did.

scripts/issue_bot_gates.py and scripts/check_wiring.py read the gate roster FROM this
file (the #393 aggregator-seam extended to entry points: a recipe that names an entry
point inherits the `make <target>` sequence the entry point executes), which keeps the
#475 gate classification and the CI target closure green across the move.
tests/test_ci_unit_stage.py pins the exact 51 entries and order byte-for-byte against
the base capture recorded in the PR body and this docstring.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Byte-parity with the 51 `$(MAKE)` recipe lines of `ci-unit` at origin/main@dcfb96b7df.
MAKE_SEQUENCE: tuple[str, ...] = (
    "make test-unit",
    "make skills-validate",
    "make check-registry",
    "make check-strata-models",
    "make check-quant-catalog",
    "make check-trend-list-matrix",
    "make check-vram-scope-view",
    "make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json",
    "make check-engine-skill-gap",
    "make check-engine-params",
    "make check-engine-coverage",
    "make check-engine-source",
    "make check-engine-capabilities",
    "make check-engine-launchers",
    "make check-engine-pins-published",
    "make check-model-links",
    "make check-wiring",
    "make check-secret-output",
    "make check-docs",
    "make check-file-hygiene",
    "make check-architecture-census",
    "make check-dispatch-forms",
    "make check-pr-hygiene",
    "make check-report-hygiene",
    "make check-report-header",
    "make check-proc-gate",
    "make proc-gate-report",
    "make check-issue-bodies",
    "make check-skill-code-parity",
    "make check-pr-authors",
    "make check-pr-closing",
    "make check-pr-commit-checkboxes",
    "make check-pr-base",
    "make check-workflows",
    "make check-module-names",
    "make check-claim-reader",
    "make check-scanner-images",
    "make check-security-scan",
    "make check-security-issues",
    "make check-security-bumps",
    "make check-security-bot",
    "make check-actions",
    "make check-renovate",
    "make check-agent-skills",
    "make check-agent-profiles",
    "make check-agent-model",
    "make issue-bot-gates",
    "make issue-bot-gates-check",
    "make check-import-roots",
    "make check-package-layers",
    "make check-agent-profiles-ratchet",
)


def sequence_targets() -> list[str]:
    """Sub-target names in execution order (what the gate-classification consumers read)."""
    return [entry.split()[1] for entry in MAKE_SEQUENCE]


def planned_commands(make_bin: str | None = None) -> list[list[str]]:
    make = make_bin or os.environ.get("MAKE") or "make"
    return [[make, *shlex.split(entry)[1:]] for entry in MAKE_SEQUENCE]


def run(make_bin: str | None = None, dry: bool = False, cwd: str | None = None) -> int:
    """Run the sequence sequentially, fail-fast, preserving the failing step's exit code."""
    workdir = str(cwd or REPO)
    total = len(MAKE_SEQUENCE)
    for i, argv in enumerate(planned_commands(make_bin), 1):
        if dry:
            print(" ".join(argv))
            continue
        rc = subprocess.run(argv, cwd=workdir).returncode  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        if rc != 0:
            print(f"[ci_unit] FAILED step {i}/{total}: {MAKE_SEQUENCE[i - 1]} (rc={rc})",
                  file=sys.stderr)
            return rc
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the ci-unit gate sequence (issue #2675).")
    ap.add_argument("--dry-run", action="store_true", help="print the planned make commands only")
    ap.add_argument("--make", default=None, help="make binary to run (default: $MAKE or `make`)")
    ap.add_argument("--cwd", default=None, help="working directory for the sub-makes (default: repo root)")
    a = ap.parse_args(argv)
    return run(make_bin=a.make, dry=a.dry_run, cwd=a.cwd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
