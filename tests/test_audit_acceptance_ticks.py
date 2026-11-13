"""The acceptance-tick audit and its supersession sweep (issue #2631, follow-up #2288).

`gh` is a recorded fake (the test must not post to GitHub); every classification,
renderer shape, and idempotence rule is exercised through the real argument
handling and the real JSON plumbing of `scripts/audit_acceptance_ticks.py`.

Scenarios map one-to-one onto
`openspec/changes/audit-tick-supersession/specs/acceptance-evidence/spec.md`.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

from scripts import audit_acceptance_ticks as aat

FAKE_GH = '''#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
fix = json.loads(open(os.environ["GH_FIXTURES"], encoding="utf-8").read())
posts_path = os.environ["GH_POSTS"]
def posts(entry):
    with open(posts_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + chr(10))
if args[:2] == ["api", "graphql"]:
    query = " ".join(args)
    page = fix["pages"][1:] if "after:" in query else fix["pages"][:1]
    last = {"data": {"repository": {"issues": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [n for p in page for n in p["nodes"]]}}}}
    print(json.dumps(last))
    raise SystemExit(0)
if args[:3] == ["api", "-X", "POST"]:
    endpoint = args[3]
    num = int(re.search(r"/issues/(\\d+)/comments", endpoint).group(1))
    body = json.loads(open(args[args.index("--input") + 1], encoding="utf-8").read())["body"]
    posts({"post": num, "body": body})
    print("{}")
    raise SystemExit(0)
endpoint = args[1]
m = re.search(r"/actions/runs/(\\d+)$", endpoint)
if m:
    rid = m.group(1)
    if rid not in fix["runs"]:
        sys.stderr.write("HTTP 404: Not Found" + chr(10))
        raise SystemExit(1)
    print("\\t".join(fix["runs"][rid]))
    raise SystemExit(0)
m = re.search(r"/actions/runs\\?head_sha=([0-9a-f]+)", endpoint)
if m:
    print(json.dumps(fix.get("head_runs", {}).get(m.group(1), [])))
    raise SystemExit(0)
m = re.search(r"/issues/(\\d+)/comments$", endpoint)
if m:
    # The real endpoint returns comment OBJECTS; the fixture stores bodies.
    print(json.dumps([{"body": b} for b in fix["comments"].get(m.group(1), [])]))
    raise SystemExit(0)
sys.stderr.write("unexpected gh call: " + " ".join(args) + chr(10))
raise SystemExit(1)
'''


def _fake_gh(tmp_path: Path, fixtures: dict) -> Path:
    """A recorded fake `gh` on PATH (first on PATH wins) reading a fixture file."""
    scripts = tmp_path / "bin"
    scripts.mkdir(parents=True, exist_ok=True)
    fake = scripts / "gh"
    fake.write_text(FAKE_GH, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    fixture_file = tmp_path / "fixtures.json"
    fixture_file.write_text(json.dumps(fixtures), encoding="utf-8")
    os.environ["GH_FIXTURES"] = str(fixture_file)
    os.environ["PATH"] = f"{scripts}{os.pathsep}{os.environ['PATH']}"
    os.environ["GH_POSTS"] = str(tmp_path / "posts.jsonl")
    return tmp_path


RED_CRIT = "- [x] the ghost mint stops (proven: run=43000000001 failure) closes #2472"
GREEN_CRIT = "- [x] the bump landed (proven: run=43000000002 success)"
UNREAD_CRIT = "- [x] the sweep reported a verdict (proven: run=43000000003)"

HEAD_A = "aaa1111" * 5  # 40 hex chars
HEAD_B = "bbb2222" * 5

# Head AAA… has green runs only for UNRELATED workflows: the cited CI never
# re-proves the criterion there. This is the shape measured on the real corpus.
FIXTURES = {
    "pages": [{"nodes": [
        {"number": 10, "body": f"## Acceptance criteria\n{RED_CRIT}\n{GREEN_CRIT}\n"},
        {"number": 11, "body": f"## Acceptance criteria\n{UNREAD_CRIT}\n"},
    ]}],
    "runs": {"43000000001": ["completed", "failure", HEAD_A, "CI (unit)"],
             "43000000002": ["completed", "success", HEAD_B, "CI (unit)"]},
    "head_runs": {HEAD_A: [{"id": 43111111111, "name": "nightly-sweep"}]},
    "comments": {},
}

RUN_STATES = {
    "43000000001": ["completed", "failure", HEAD_A, "CI (unit)"],
    "43000000003": ["unreadable", "", "", ""],
}


def _fixtures(**over) -> dict:
    f = json.loads(json.dumps(FIXTURES))
    f.update(over)
    return f


def _note(entries, run_states=None, head_green=None):
    return aat.render_supersede_note(
        10, entries,
        run_states if run_states is not None else RUN_STATES,
        head_green if head_green is not None else {HEAD_A: [{"id": 43111111111, "name": "nightly-sweep"}]},
    )


# ------------------------------------------------------------- audit classification


def test_stale_requires_every_cited_run_to_be_non_green(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    _fake_gh(tmp_path, _fixtures())
    roster = tmp_path / "roster.json"
    rc = aat.audit("o/r", roster, quiet=True)
    data = json.loads(roster.read_text())
    assert rc == 1  # stale ticks remain
    stale = {int(k): v for k, v in data["stale"].items()}
    assert sorted(stale) == [10, 11]
    assert [c[1] for c in stale[10]] == [["43000000001"]]  # the green criterion left the set
    assert data["ticked_criteria_citing_runs"] == 3
    assert data["run_states"]["43000000003"] == ["unreadable", "", "", ""]
    # the head survey runs for heads cited by stale criteria only (HEAD_A, not HEAD_B)
    assert list(data["head_green"]) == [HEAD_A]
    assert data["head_green"][HEAD_A] == [{"id": 43111111111, "name": "nightly-sweep"}]
    assert data["counting_method"] == aat.COUNTING_METHOD


def test_a_superseded_criterion_leaves_the_denominator(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    note = _note([(RED_CRIT.strip(), ["43000000001"], ["failure"])])
    _fake_gh(tmp_path, _fixtures(comments={"10": [note]}))
    roster = tmp_path / "roster.json"
    rc = aat.audit("o/r", roster, quiet=True)
    data = json.loads(roster.read_text())
    assert rc == 1  # issue 11 is still unsuperseded
    assert str(10) not in data["stale"]
    assert data["superseded"]["10"][0][0] == RED_CRIT.strip()


def test_all_superseded_audit_reports_zero_and_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    note10 = _note([(RED_CRIT.strip(), ["43000000001"], ["failure"])])
    note11 = _note([(UNREAD_CRIT.strip(), ["43000000003"], ["unreadable"])])
    _fake_gh(tmp_path, _fixtures(comments={"10": [note10], "11": [note11]}))
    roster = tmp_path / "roster.json"
    assert aat.audit("o/r", roster, quiet=True) == 0
    data = json.loads(roster.read_text())
    assert data["stale"] == {}
    assert sum(len(v) for v in data["superseded"].values()) == 2


# ------------------------------------------------------------------ note renderer


def test_the_note_is_marker_first_quoted_and_append_only():
    note = _note([(RED_CRIT.strip(), ["43000000001"], ["failure"])])
    assert note.startswith(aat.SUPERSEDE_MARKER)
    assert "- cited: run=43000000001 (failure)" in note
    assert f"> {RED_CRIT.strip()}" in note
    assert "ticks stay as written" in note
    assert "append-only" in note
    assert "AUDIT-2288" in note


def test_the_note_states_per_head_whether_the_cited_workflow_ever_went_green():
    # greens at the head belong to UNRELATED workflows: never re-proves the tick
    note = _note([(RED_CRIT.strip(), ["43000000001"], ["failure"])])
    headline = next(l for l in note.splitlines() if l.startswith("  head "))
    assert headline.startswith(f"  head {HEAD_A[:10]}")
    assert "CI (unit)) never went green at this head" in headline
    assert "nightly-sweep" in headline

    # no green run at all at the head
    note_none = _note([(RED_CRIT.strip(), ["43000000001"], ["failure"])], head_green={})
    assert f"  head {HEAD_A[:10]}: no completed/success run exists at this head" in note_none

    # the cited workflow itself has a green run at the head: the note names it
    note_same = _note(
        [(RED_CRIT.strip(), ["43000000001"], ["failure"])],
        head_green={HEAD_A: [{"id": 43222222222, "name": "CI (unit)"}]},
    )
    assert "green run(s) of the cited workflow at this head: 43222222222" in note_same

    # an unreadable run contributes no head line (no head recorded)
    note_unread = _note([(UNREAD_CRIT.strip(), ["43000000003"], ["unreadable"])])
    assert "  head " not in note_unread


def test_covered_criteria_only_reads_supersede_notes():
    plain = aat.AUDIT_MARKER + "\n> " + RED_CRIT.strip() + "\n"
    assert aat.covered_criteria([plain]) == set()
    supersede = _note([(RED_CRIT.strip(), ["43000000001"], ["failure"])])
    # head-fact lines sit between `- cited:` and the quoted criterion; the
    # parser must not lose the quote there (regression for the #2631 note shape)
    assert any(l.startswith("  head ") for l in supersede.splitlines())
    assert aat.covered_criteria([supersede]) == {RED_CRIT.strip()}


# ------------------------------------------------------------------- notes + post


def test_post_uses_the_renderer_verbatim_and_is_marker_idempotent(tmp_path):
    _fake_gh(tmp_path, _fixtures())
    roster = tmp_path / "roster.json"
    notes_dir = tmp_path / "notes"
    assert aat.audit("o/r", roster, quiet=True) == 1  # no notes on the issues yet
    assert aat.notes("o/r", roster, notes_dir) == 0
    rendered = {p.name: p.read_text() for p in notes_dir.glob("*.md")}
    assert set(rendered) == {"10.md", "11.md"}
    assert rendered["11.md"].startswith(aat.SUPERSEDE_MARKER)
    assert f"  head {HEAD_A[:10]}" in rendered["10.md"]

    assert aat.post("o/r", roster, notes_dir) == 0
    posts = [json.loads(line) for line in (tmp_path / "posts.jsonl").read_text().splitlines()]
    # Both issues got exactly one comment, each body the rendered note verbatim.
    assert sorted(p["post"] for p in posts) == [10, 11]
    assert {p["post"]: p["body"] for p in posts} == {10: rendered["10.md"], 11: rendered["11.md"]}

    # Second run: both issues now carry the marker — posting is a no-op, not a second comment.
    fixtures_path = Path(os.environ["GH_FIXTURES"])
    data = json.loads(fixtures_path.read_text())
    data["comments"] = {"10": [rendered["10.md"]], "11": [rendered["11.md"]]}
    fixtures_path.write_text(json.dumps(data))
    assert aat.post("o/r", roster, notes_dir) == 0
    posts2 = [json.loads(line) for line in (tmp_path / "posts.jsonl").read_text().splitlines()]
    assert sorted(p["post"] for p in posts2) == [10, 11]  # unchanged: nothing posted twice


def test_the_audit_and_poster_share_the_proc_seam():
    src = (REPO / "scripts" / "audit_acceptance_ticks.py").read_text()
    assert "from proc import" in src
    assert "subprocess.run" not in src  # one subprocess policy, the seam (issue #797)
