"""The staleness refresh-issue producer (issue #2901) — hermetic.

`scripts/trend_staleness_issue.py` turns a cell drift named by
`scripts/trend_list_matrix.py --staleness` into ONE open refresh issue. The GitHub
delivery seam (`scripts/proc.py`, the one subprocess policy seam, #797) is faked
here: the fetch/POST is scripted, the decision logic (dedupe read, marker, render
path, dry contract) is real. The live pairing of the two scripts is exercised on
`ci-hf-live` (the lane that runs both) and pinned in
`tests/test_trend_list_matrix.py::test_staleness_names_the_disagreeing_cells_and_exits_nonzero`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
from scripts import trend_list_matrix as tlm
from scripts import trend_staleness_issue as tsi

DRIFT = [{
    "case": tlm.case_key("cuda", 16.0, 32.0),
    "added": ["new-model"],
    "dropped": ["gone-model"],
    "changed": [{"model": "kept-model", "fields": {"size_gb": "9.0 -> 13.0"}}],
}]


class FakeGh:
    """Records every `gh api` call the producer makes and scripts the replies."""

    def __init__(self, search_items: list[dict], created: int = 4321):
        self.calls: list[tuple[list[str], dict]] = []
        self.search_items = search_items
        self.created = created

    def __call__(self, cmd, timeout=None, **kwargs):
        self.calls.append((list(cmd), dict(kwargs)))
        joined = " ".join(cmd)
        if "search/issues" in joined:
            # `gh api --jq '[.items[] | …]'` prints the ARRAY, not the wrapper object.
            return json.dumps(self.search_items)
        if "--method" in cmd and "POST" in cmd:
            payload = json.loads(kwargs.get("input") or "{}")
            assert payload.get("labels") == [tsi.LABEL], "the refresh issue must carry the lane label"
            return json.dumps({"number": self.created, "html_url": f"https://x/{self.created}"})
        raise AssertionError(f"unexpected gh call: {joined}")

    def posts(self) -> list[tuple[list[str], dict]]:
        return [c for c in self.calls if "--method" in c[0] and "POST" in c[0]]


@pytest.fixture()
def fake_drift(monkeypatch, tmp_path):
    """A drift is present; the live build itself is NOT what this module tests.

    The patch lands on `tsi.tlm` — the module object the PRODUCER imported. The
    #796 trap: a `from scripts import trend_list_matrix` test alias and the
    producer's own `import trend_list_matrix` can be two module objects, and a
    patch on the wrong one leaves the real live read in place.

    #3057: these fixtures simulate a STANDALONE drift read — no handoff present —
    so a leftover build/trend-staleness-drift.json in the tree can never steer them.
    """
    monkeypatch.setattr(tsi.tlm, "staleness_read", lambda: (1, list(DRIFT)))
    monkeypatch.setattr(tsi.tlm, "DRIFT_REPORT", tmp_path / "no-drift-handoff.json")


@pytest.fixture()
def fake_repo(monkeypatch):
    """The producer's subprocess seam, swapped for the recorder."""
    fake = FakeGh([])
    monkeypatch.setattr(tsi.proc, "run_checked", fake)
    return fake


def test_dry_prints_the_issue_and_files_nothing(monkeypatch, fake_drift):
    fake = FakeGh([])
    monkeypatch.setattr(tsi.proc, "run_checked", fake)
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie", "--dry"])
    assert rc == 0
    assert fake.calls == [], "DRY must not touch GitHub at all"


def test_one_issue_per_drift_and_the_dedupe_read_gates_it(monkeypatch, fake_drift, fake_repo):
    # No open marker issue: exactly one POST lands.
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    assert rc == 0 and len(fake_repo.posts()) == 1, f"expected exactly one filed issue: {fake_repo.calls}"

    # An open marker issue exists: the SAME drift files nothing new (dedupe read ran first).
    fingerprint = tsi.drift_fingerprint(DRIFT)
    marker_body = f"{tsi.MARKER_PREFIX} {fingerprint} -->\n\n## Problem\n…"
    fake2 = FakeGh([{"number": 4321, "title": tsi.TITLE, "body": marker_body}])
    monkeypatch.setattr(tsi.proc, "run_checked", fake2)
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    assert rc == 0
    assert not fake2.posts(), "an open marker issue must suppress a second filing"

    # An issue merely mentioning the words (like the detector issue itself) is NOT "already filed".
    fake3 = FakeGh([{"number": 2901, "title": "trend staleness alarm", "body": "## Problem\nmentions trend-staleness only"}])
    monkeypatch.setattr(tsi.proc, "run_checked", fake3)
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    assert rc == 0 and len(fake3.posts()) == 1, "mentioning the marker words is not holding the marker"


def test_filing_reuses_the_named_drift_handoff_without_a_second_live_read(monkeypatch, tmp_path, fake_repo):
    """#3057 AC1: `make check-trend-list-fresh` ran first and named the drift; the filing
    path consumes its cells from the handoff and must NOT reach the live trending build again
    — the second read is what returned the unreadable exit 2 and erased the ticket."""
    report = tmp_path / "trend-staleness-drift.json"
    report.write_text(json.dumps({"written_by": "make check-trend-list-fresh", "cells": list(DRIFT)}),
                      encoding="utf-8")
    monkeypatch.setattr(tsi.tlm, "DRIFT_REPORT", report)

    def _second_live_read_forbidden():
        raise AssertionError("the filing path must not re-read the live trending (#3057)")
    monkeypatch.setattr(tsi.tlm, "staleness_read", _second_live_read_forbidden)

    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    assert rc == 0, f"filing from the handoff failed: {fake_repo.calls}"
    posts = fake_repo.posts()
    assert len(posts) == 1, f"expected exactly one filed issue: {fake_repo.calls}"
    body = json.loads(posts[0][1]["input"])["body"]
    first_line = body.splitlines()[0]
    assert first_line.startswith(tsi.MARKER_PREFIX), "the dedupe marker must stay the body's first line"
    assert tsi.drift_fingerprint(DRIFT) in first_line, "the marker must fingerprint the handed-off cells"


def test_unreadable_standalone_read_is_named_before_the_exit_code(monkeypatch, tmp_path, fake_repo, capsys):
    """#3057 AC3: with no named drift to file, the producer's own re-read failing prints
    the failure BY NAME before returning 2 — a lost read is loud, never silent."""
    monkeypatch.setattr(tsi.tlm, "DRIFT_REPORT", tmp_path / "no-drift-handoff.json")
    monkeypatch.setattr(tsi.tlm, "staleness_read", lambda: (2, []))
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "[trend-staleness-issue] FAIL" in err, "the failure must carry the producer's FAIL line"
    assert "staleness re-read could not run" in err, "the log must name WHICH leg failed"
    assert not fake_repo.posts(), "a lost read must file nothing"


def test_corrupt_handoff_is_named_and_falls_back_to_the_producer_read(monkeypatch, tmp_path, fake_repo, capsys):
    """A handoff the producer cannot trust is reported by name, not silently skipped:
    filing still happens via the producer's own read."""
    bad = tmp_path / "trend-staleness-drift.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(tsi.tlm, "DRIFT_REPORT", bad)
    monkeypatch.setattr(tsi.tlm, "staleness_read", lambda: (1, list(DRIFT)))
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    err = capsys.readouterr().err
    assert "[trend-staleness-issue] FAIL named-drift file" in err, "the corrupt handoff must be named"
    assert rc == 0 and len(fake_repo.posts()) == 1, "a corrupt handoff must not silently skip filing"


def test_body_is_rendered_through_the_one_renderer_with_the_marker_first(monkeypatch, fake_drift, fake_repo):
    rc = tsi.main(["open", "--repo", "asimov-agent/llgenie"])
    assert rc == 0
    post, kwargs = fake_repo.posts()[0]
    assert "--input" in post, "the body must travel on stdin (--input -), never in argv"
    payload = json.loads(kwargs["input"])
    body = payload["body"]
    fingerprint = tsi.drift_fingerprint(DRIFT)
    assert body.splitlines()[0] == f"{tsi.MARKER_PREFIX} {fingerprint} -->"
    for section in ("## Problem", "## Why it matters", "## How we fix it", "## Benefit",
                    "## Acceptance criteria", "## Technical"):
        assert section in body, f"the six-section shape lost {section}"
    assert body.index("## Technical") > body.index("## Acceptance criteria"), "## Technical must stay last"
    assert "render-trend-list-matrix" in body, "the refresh issue must order its own remedy"


def test_a_failed_delivery_is_exit_3_not_green(monkeypatch, fake_drift):
    class Boom(FakeGh):
        def __call__(self, cmd, timeout=None, **kwargs):
            super().__call__(cmd, timeout=timeout, **kwargs)
            if "--method" in cmd:
                raise RuntimeError("gh api POST failed")
            return json.dumps({"items": []})

    monkeypatch.setattr(tsi.proc, "run_checked", Boom([]))
    assert tsi.main(["open", "--repo", "asimov-agent/llgenie"]) == 3


def test_a_failed_dedupe_read_refuses_to_file(monkeypatch, fake_drift):
    class NoSearch(FakeGh):
        def __call__(self, cmd, timeout=None, **kwargs):
            if "search/issues" in " ".join(cmd):
                raise RuntimeError("gh api search failed")
            return super().__call__(cmd, timeout=timeout, **kwargs)

    fake = NoSearch([])
    monkeypatch.setattr(tsi.proc, "run_checked", fake)
    assert tsi.main(["open", "--repo", "asimov-agent/llgenie"]) == 3
    assert not fake.posts(), "a blind filing after a dead dedupe read is the defect"


def test_fresh_read_files_nothing_even_without_dry(monkeypatch, fake_repo):
    monkeypatch.setattr(tsi.tlm, "staleness_read", lambda: (0, []))
    assert tsi.main(["open", "--repo", "asimov-agent/llgenie"]) == 0
    assert fake_repo.calls == [], "fresh means GitHub is not touched at all"
