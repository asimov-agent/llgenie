"""File the refresh issue for a trend-matrix drift (issue #2901).

`scripts/trend_list_matrix.py --staleness` reads whether the committed
tests/fixtures/trend-list-matrix.json still agrees with the LIVE trending, cell by
cell. This module turns a disagreement into a tracked work item: it files ONE open
refresh issue naming the disagreeing cells and ordering the re-render
(`make render-trend-list-matrix`). The body is rendered ONLY through
`issue_body.render` (AGENTS.md: one renderer, never a hand-built body), and the
dedupe marker — `<!-- trend-staleness: … -->` — is the body's first line, so the
producer remembers what it already filed.

Dedupe steady state: at most ONE open staleness issue exists at a time. A drift
that keeps moving under an already-open issue does not file a new one every lane
tick; the open issue is what a re-render closes.

Exit codes: 0 = fresh, or filed, or already filed; 2 = the staleness read could not
run; 3 = the read disagreed but the issue did not land (a loud failure, mirroring
the queued-run alarm's delivery contract — an alarm whose report did not land is
never green).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import issue_body  # noqa: E402  (the one issue shape, #745)
import proc  # noqa: E402  (the ONE subprocess policy seam, issue #797)
import trend_list_matrix as tlm  # noqa: E402  (the one trend-matrix implementation; the staleness read is its own)

MARKER_PREFIX = "<!-- trend-staleness:"
TITLE = "chore(trend-list): the committed trend matrix disagrees with the live trending — re-render it"
LABEL = "agent:ready"


def drift_fingerprint(cells: list[dict]) -> str:
    """A stable id for the CURRENT disagreement (sorted cells, hashed)."""
    blob = json.dumps(cells, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def cells_summary(cells: list[dict]) -> list[str]:
    out = []
    for c in cells:
        bits = []
        if c["added"]:
            bits.append("added " + ", ".join(c["added"]))
        if c["dropped"]:
            bits.append("dropped " + ", ".join(c["dropped"]))
        for ch in c["changed"]:
            bits.append("changed " + ch["model"] + " ("
                        + "; ".join(f"{k}: {v}" for k, v in sorted(ch["fields"].items())) + ")")
        out.append(f"`{c['case']}`: " + "; ".join(bits))
    return out


def render_issue(cells: list[dict], fingerprint: str) -> str:
    """The refresh issue, rendered through the ONE renderer with the marker first."""
    marker = f"{MARKER_PREFIX} {fingerprint} -->"
    return issue_body.render(
        marker=marker,
        problem=(
            "The committed trend matrix `tests/fixtures/trend-list-matrix.json` no longer agrees "
            "with the LIVE Hugging Face trending the pick reads. The staleness read "
            "(`python3 scripts/trend_list_matrix.py --staleness`, issue #2901) found "
            f"{len(cells)} cell(s) disagree:\n\n"
            + "\n".join(f"- {line}" for line in cells_summary(cells))
        ),
        why=(
            "The hermetic contract check replays the recorded Hub answers, so a fixture that "
            "matches its own recording stays green even after the live trending moved under it. "
            "That drift window is what burned six consecutive `ci-hf-live` runs before the "
            "re-pin landed (#2900): the matrix pinned models at sizes the live builds no longer "
            "produce, and every serving assertion built on it failed downstream."
        ),
        how=[
            "Re-render the trend matrix from the live trending with `make render-trend-list-matrix` "
            "— this rewrites `tests/fixtures/trend-list-matrix.json` and the Hub answers it read "
            "into `tests/fixtures/hub-snapshot.json`, so the hermetic check and the live read agree "
            "again on the same commit.",
            "Open the re-render as its own feature branch + PR so the fixture delta is reviewable; "
            "the PR references this issue.",
            "After the re-render merges, the `ci-hf-live` staleness step reads green again and this "
            "issue closes.",
        ],
        benefit=(
            "The pick, the matrix, and every network assertion built on the committed list match "
            "what the trending store actually offers again — and the drift was CAUGHT: a dated, "
            "linked issue named it before it could burn battery runs."
        ),
        acceptance=[
            "`make render-trend-list-matrix` produces a new fixture+snapshot pair and "
            "`make -s check-trend-list-matrix` exits 0 against it.",
            "`make -s check-trend-list-fresh` exits 0 on `main` after the re-render lands "
            "(the live read agrees in every cell).",
        ],
        not_covered=[
            "Nothing else. The detection itself already shipped in the #2901 lane "
            "(issue #2901); this issue carries only the re-render of the cells named above.",
        ],
        technical=[
            "Produced by `scripts/trend_staleness_issue.py` from the `ci-hf-live` staleness step "
            "(`make check-trend-list-fresh`, issue #2901).",
            f"Drift fingerprint: `{fingerprint}` (hashed cell diff; the marker dedupes this producer).",
            "Cells (fixture -> live): " + "; ".join(cells_summary(cells)),
            "Read replayable with: `make -s check-trend-list-fresh`",
        ],
    )


def _gh_json(args: list[str]) -> Any:
    """One `gh api` call through the subprocess seam; a failure is loud, not empty."""
    out = proc.run_checked(["gh", "api", *args], timeout=60)
    return json.loads(out) if out.strip() else {}


def open_drift_issues(repo: str) -> list[dict]:
    """OPEN issues this producer already filed (marker read — the body's first line)."""
    found = _gh_json([
        "search/issues",
        "-X", "GET",
        # The marker term, NOT a GitHub qualifier phrase: `in:body "trend-staleness:"`
        # 422s on the colon. The python side then requires the FULL marker in the
        # body's first lines, so an issue merely mentioning the word (like #2901
        # itself) is not counted as "already filed".
        "-f", f'q=repo:{repo} is:issue is:open "trend-staleness"',
        "--jq", '[.items[] | {number, title, body}]',
    ]) or []
    return [i for i in found if any(MARKER_PREFIX in line for line in str(i.get("body") or "").splitlines()[:3])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["report", "open"])
    ap.add_argument("--repo", default="asimov-agent/llgenie")
    ap.add_argument("--dry", action="store_true", help="print the issue that would be filed; file nothing")
    ns = ap.parse_args(argv)

    rc, cells = tlm.staleness_read()
    if rc == 2:
        return 2
    if rc == 0:
        print("[trend-staleness-issue] nothing to file: the fixture agrees with the live trending.")
        return 0

    fingerprint = drift_fingerprint(cells)
    body = render_issue(cells, fingerprint)
    if ns.dry or ns.mode == "report":
        # A print-only pass touches GitHub in NO way — not even the dedupe read.
        print(f"[trend-staleness-issue] {'DRY' if ns.dry else 'REPORT'} — would file in {ns.repo}:\n"
              f"TITLE: {TITLE}\nLABEL: {LABEL}\n{body}")
        return 0
    try:
        existing = open_drift_issues(ns.repo)
    except Exception as exc:
        # A dedupe read that cannot run must not file blind (a duplicate is the defect
        # the marker exists to prevent) and must not look green either: loud exit 3.
        print(f"[trend-staleness-issue] FAIL dedupe read failed: {exc}. "
              "Refusing to file; no issue landed.", file=sys.stderr)
        return 3
    if existing:
        nums = ", ".join(f"#{i['number']}" for i in existing)
        print(f"[trend-staleness-issue] already open for this producer: {nums}; no new issue filed "
              f"(drift fingerprint {fingerprint}).")
        return 0

    payload = json.dumps({"title": TITLE, "body": body, "labels": [LABEL]})
    try:
        out = proc.run_checked(["gh", "api", "--method", "POST", f"repos/{ns.repo}/issues",
                                "--input", "-"], input=payload, timeout=60)
        made = json.loads(out)
    except Exception as exc:
        print(f"[trend-staleness-issue] DELIVERY FAILED: refresh issue did not land: {exc}",
              file=sys.stderr)
        return 3
    print(f"[trend-staleness-issue] filed refresh issue #{made.get('number')} "
          f"({made.get('html_url')}) for drift fingerprint {fingerprint}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
