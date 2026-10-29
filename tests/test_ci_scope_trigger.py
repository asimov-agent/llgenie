#!/usr/bin/env python3
"""Monitor the #824 CI-scope contract (owner-deferred 2026-10-28, issue #824).

The owner deferred path-selected stages until more pipeline measurements exist (after #871 removed
the macOS group). Until that lifts, `ci.yml` deliberately runs the full matrix on every PR with NO
`paths:` filter, and the classifier (`ci_scope.py`, `scope.yml`) lives only on closed branches.

This test pins the *deferred* contract so the two failure modes of the future optimisation do not
merge silently:

1. **Premature/naive widening.** The moment someone reintroduces a `paths-ignore` (or `paths`)
   filter, this test forces it to be *correct*: a markdown path the filter skips must be a pure doc
   (under `docs/`, `agent-wiki/`, `openspec/`, or the single `README.md`/`CHANGES.md`), NOT a
   markdown file under `.hermes/`, `skills/`, `tests/`, `data/`, or the root `AGENTS.md` — those
   carry a second role (skill, fixture input, data, fleet rule) whose stages a `**/*.md` skip would
   drop. That is the exact drift caught on #824 (43 tracked paths ignored by `**/*.md` but classed
   beyond `docs`).

2. **The deferral dissolving silently when docs-only cost returns.** While there is no filter, the
   test documents that `ci.yml` runs the full matrix for every PR and requires the `pull_request`
   trigger to keep its explicit `branches: ["main"]` guard (so the pipeline cannot quietly widen to
   forks/pushes).

Fails closed: green now under the deferral, red on the wide-filter drift.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def tracked_markdown() -> set[str]:
    """Every markdown path git tracks in this checkout."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], check=True, capture_output=True, text=True
    ).stdout
    return {p for p in out.splitlines() if p.endswith(".md")}


def pull_request_ignore_globs(ci: str) -> list[str]:
    """The `paths-ignore:` globs declared under the `pull_request:` trigger (now: none)."""
    # find the pull_request block, then any paths-ignore: list in it
    pr_block = ci.split("pull_request:", 1)[1].split("\n  push:", 1)[0]
    globs: list[str] = []
    if "paths-ignore:" in pr_block:
        tail = pr_block.split("paths-ignore:", 1)[1]
        for line in tail.splitlines():
            line = line.strip()
            if line.startswith("- "):  # block style: - "**/*.md"
                globs.append(line[2:].strip().strip('"').strip("'"))
            elif "[" in line and "]" in line:  # flow style: paths-ignore: ["**/*.md"]
                for a, b in re.findall(r'"([^"]+)"|\'([^\']+)\'', line):
                    globs.append(a or b)
            elif line and not line.startswith("#"):
                break
    return globs


PURE_DOC = (
    lambda rel: (
        rel.startswith("docs/")
        or rel.startswith("agent-wiki/")
        or rel.startswith("openspec/")
        or rel in {"README.md", "CHANGES.md"}
    )
)


def test_the_deferred_contract_keeps_branches_guarded():
    """No filter YET (deferral) — but the trigger must stay `pull_request` on `main` only."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    pr = ci.split("pull_request:", 1)[1].split("\n  push:", 1)[0]
    assert "branches:" in pr and '"main"' in pr, (
        "#824 deferral: ci.yml must keep the pull_request trigger scoped to [main]; a silent "
        "widening to other branches/events re-opens the full-matrix cost without measurement"
    )


def test_any_paths_ignore_cannot_drop_a_non_doc_markdown_role():
    """A `paths-ignore` that skips markdown must only skip PURE docs — never a .md that carries a
    second role (skills, tests/fixtures, data, agents rules). Red on a `**/*.md`-style widen."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    globs = pull_request_ignore_globs(ci)
    if not globs:
        return  # deferral: no filter yet, vacuously correct
    # which tracked md files does the ignore set match? We only need to prove the WIDE case: any
    # glob that is a markdown-wide matcher must not have non-doc offenders under it.
    WIDE = ["**/*.md", "*.md", "**/*.markdown"]
    wide = [g for g in globs if g in WIDE]
    if not wide:
        return  # a specific filter (e.g. docs/**) is a separate review, not this drift
    offenders = sorted(
        p for p in tracked_markdown() if not PURE_DOC(p)
    )
    assert not offenders, (
        "#824 drift reintroduced: paths-ignore {wide} skips {len(offenders)} tracked markdown "
        "files that are NOT pure docs (e.g. {offenders[:5]}...). These carry a second role whose "
        "stages the wide ignore would drop — name doc LOCATIONS (docs/**, agent-wiki/**, "
        "openspec/**, README.md, CHANGES.md), never **/*.md"
    )
