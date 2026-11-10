#!/usr/bin/env python3
"""The `ci-unit` gate sequence, as a tested module (issue #800).

The 2,083-line Makefile's longest recipe was `ci-unit` — 49 lines of `$(MAKE) <gate>` in a fixed
order, the decision of what the whole hermetic unit gate runs. Inline in a recipe that sequencing
was untestable shell text; this module names the SAME sequence in order and runs each step exactly
like the recipe did — `make <target>`, stopping at the FIRST failure and exiting with that step's
status. The recipe became `python3 scripts/ci_unit.py`, one line; the sequence is the tested module.

The list is a SUBSEQUENCE of what CI must gate, not a hand-kept roster to extend blindly: it is the
exact ordered list the old recipe carried, so a gate added to ci-unit is deliberately added here,
not silently skipped. `make ci-unit` still runs `bash-check` (its prerequisite) before this script.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run as `python3 scripts/ci_unit.py`

import proc  # noqa: E402  (the subprocess policy seam, same dir; sibling scripts import it bare)

#: The exact ordered list the old 49-line `ci-unit` recipe ran, one `make <target>` per line.
STEPS = [
    "test-unit",
    "skills-validate",
    "check-registry",
    "check-strata-models",
    "check-quant-catalog",
    "check-trend-list-matrix",
    "check-vram-scope-view",
    "skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json",
    "check-engine-skill-gap",
    "check-engine-params",
    "check-engine-coverage",
    "check-engine-source",
    "check-engine-capabilities",
    "check-engine-launchers",
    "check-engine-pins-published",
    "check-model-links",
    "check-wiring",
    "check-secret-output",
    "check-docs",
    "check-architecture-census",
    "check-dispatch-forms",
    "check-pr-hygiene",
    "check-report-hygiene",
    "check-report-header",
    "check-proc-gate",
    "proc-gate-report",
    "check-issue-bodies",
    "check-skill-code-parity",
    "check-pr-authors",
    "check-pr-closing",
    "check-pr-base",
    "check-workflows",
    "check-module-names",
    "check-claim-reader",
    "check-scanner-images",
    "check-security-scan",
    "check-security-issues",
    "check-security-bumps",
    "check-security-bot",
    "check-actions",
    "check-renovate",
    "check-agent-skills",
    "check-agent-profiles",
    "check-agent-model",
    "issue-bot-gates",
    "issue-bot-gates-check",
    "check-import-roots",
    "check-package-layers",
    "check-agent-profiles-ratchet",
]


def run(steps: list[str] | None = None, root: Path | None = None,
        env: dict[str, str] | None = None) -> int:
    """Run `make <step>` for each step in order, stopping at the first failure.

    Returns 0 when every step passed, else the first failing step's exit code — exactly what the
    old recipe did (a `$(MAKE)` line that fails aborts the recipe with that status). `env` is
    forwarded to each `make` call (tests inject a stub `make` on PATH via it).
    """
    for step in steps or STEPS:
        cmd = ["make", *step.split()]
        if root:
            cwd = str(root)
        else:
            cwd = None
        r = proc.run_ok(cmd, cwd=cwd, env=env)
        if r.returncode != 0:
            print(f"[ci-unit] {step!r} failed (exit {r.returncode})", file=sys.stderr)
            return r.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = __import__("argparse").ArgumentParser(description="Run the ci-unit gate sequence (issue #800)")
    ap.add_argument("--root", default=None, help="makefile root (default: this checkout)")
    a = ap.parse_args(argv)
    return run(root=Path(a.root) if a.root else None)


if __name__ == "__main__":
    raise SystemExit(main())
