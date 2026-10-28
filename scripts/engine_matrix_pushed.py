#!/usr/bin/env python3
"""Does this run push an engine image? The one decision `ci.yml` asks about a matrix (#844).

`install-published-*` installs PUBLISHED images from GHCR, so it only proves something when this run
actually pushed one. That fact is decided once, here, from the two things that make `engine-image`'s
push step run:

* the event is a `push` — a `pull_request` never publishes (`engine-image`'s `PUBLISH` is empty there), so
  the four install rows on a PR re-prove the registry instead of the diff; and
* the resolved engine matrix has at least one real row — the `none` placeholder (#828) skips every step
  in `engine-image`, so it pushes nothing.

It lives in a script rather than inline in YAML because a decision inside a workflow step can only be
tested by reading the YAML as text, and this is the decision that makes four jobs run or not run: the
bug it prevents (#844) is a green check whose subject could not have changed.

Usage::

    python3 scripts/engine_matrix_pushed.py --event push --matrix '{"include":[{"engine":"vllm"}]}'
    true
"""

from __future__ import annotations

import argparse
import json
import sys


def rows_that_build(matrix_json: str) -> list[str]:
    """The engine names in a resolved matrix that are not the `none` placeholder."""
    try:
        doc = json.loads(matrix_json or "{}")
    except json.JSONDecodeError:
        # An unreadable matrix is not evidence that nothing will be built: fail closed (True), so the
        # install rows run rather than being skipped by a parse error.
        return ["<unreadable matrix>"]
    include = doc.get("include") if isinstance(doc, dict) else None
    if include is None:
        # A legacy `{"engine": [...]}`-shaped matrix (no `include`) still builds its rows.
        include = [doc] if isinstance(doc, dict) else []
    names = []
    for row in include or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("engine") or "none")
        if name != "none":
            names.append(name)
    return names


def pushed(event_name: str, matrix_json: str) -> bool:
    """True only when this run pushes: a push event AND at least one real image row."""
    if (event_name or "").strip().lower() != "push":
        return False
    return bool(rows_that_build(matrix_json))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="does this CI run push an engine image? (issue #844)")
    ap.add_argument("--event", required=True, help="github.event_name")
    ap.add_argument("--matrix", required=True, help="the resolved engine-image matrix, as JSON")
    a = ap.parse_args(argv)
    verdict = pushed(a.event, a.matrix)
    # `ci.yml` writes this straight into $GITHUB_OUTPUT, and published.yml compares it to 'true'.
    print("true" if verdict else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
