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
def fake_drift(monkeypatch):
    """A drift is present; the live build itself is NOT what this module tests.

    The patch lands on `tsi.tlm` — the module object the PRODUCER imported. The
    #796 trap: a `from scripts import trend_list_matrix` test alias and the
    producer's own `import trend_list_matrix` can be two module objects, and a
    patch on the wrong one leaves the real live read in place.
    """
    monkeypatch.setattr(tsi.tlm, "staleness_read", lambda: (1, list(DRIFT)))


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
