#!/usr/bin/env python3
"""A changed store opens ONE issue that states what changed (issue #704).

`registry_change_issue.py` compares the committed store/contract/README with the working
tree's and renders the facts. These tests drive the real `compare()`/`render()` over two
real stores built in a temp dir, and the real `open_issue()` with `gh` replaced by a
function that records the command — `gh` is the external system, the script is the product.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import registry_change_issue as RCI  # noqa: E402
import issue_body  # noqa: E402  (the one issue shape, issue #745)


def _store(utc: str, models: list[dict], engines: dict) -> bytes:
    return json.dumps({"generated_utc": utc, "engines": engines, "models": models},
                      indent=2).encode()


def _model(id_: str, name: str, vram: str, formats: list[str]) -> dict:
    return {"id": id_, "name": name, "vram_tier": vram,
            "formats": [{"name": f, "hf": f"a/{id_}-{f.lower()}"} for f in formats],
            "engines": [{"engine": "llama.cpp", "tps": "10"}]}


def _contract(*required: str, backends: list[str] | None = None) -> bytes:
    return json.dumps({
        "type": "object", "required": ["engines", "models"],
        "properties": {
            "engines": {"additionalProperties": {
                "required": ["backend", "note", "url"],
                "properties": {"backend": {"enum": backends or ["CUDA", "Metal", "CPU"]}}}},
            "models": {"items": {"required": list(required),
                                 "properties": {"formats": {"minItems": 1,
                                                            "items": {"required": ["name", "hf"]}}}}},
        },
    }, indent=2).encode()


def _readme(names: list[str]) -> bytes:
    rows = "\n".join(f"| [**{n}**](https://huggingface.co/a/{n}) | **8GB** |" for n in names)
    return f"# Trending\n\n## ❤️ Most loved\n\n| Model | VRAM |\n|---|---|\n{rows}\n\n## Next\n".encode()


def _snapshot(models, engines, required, names, backends=None) -> dict:
    return {
        RCI.STORE: _store("2026-10-26T00:00:00Z", models, engines),
        RCI.CONTRACT: _contract(*required, backends=backends),
        RCI.README: _readme(names),
        RCI.CATALOG: json.dumps({"files": {"m1": {"cuda": {"quants": [{"url": "u1"}]}}}}).encode(),
        RCI.MATRIX: json.dumps({"cases": [{}, {}]}).encode(),
        RCI.GAP: json.dumps({"unresolved": ["NewEngine"]}).encode(),
    }


def test_the_report_names_an_added_model_a_new_engine_and_an_added_contract_key():
    """The three facts an agent needs before it can touch llgenie: a new row, a new engine
    it must decide, and a contract key it does not read yet."""
    # Given  the previous store, and the synced one that added a model, an engine and a key
    prev = _snapshot([_model("m1", "Model One", "16GB", ["GGUF"])],
                     {"llama.cpp": {"backend": "CUDA", "note": "n", "url": "u"}},
                     req_prev := ["id", "name", "vram_tier", "formats", "engines"],
                     ["Model One"])
    cur = _snapshot([_model("m1", "Model One", "16GB", ["GGUF"]),
                     _model("m2", "Model Two", "8GB", ["GGUF", "MLX"])],
                    {"llama.cpp": {"backend": "CUDA", "note": "n", "url": "u"},
                     "NewEngine": {"backend": "Metal", "note": "n", "url": "u"}},
                    req_prev + ["last_seen"], ["Model One", "Model Two"],
                    backends=["CUDA", "Metal", "CPU", "ROCm"])

    # When   the change is compared and rendered
    facts = RCI.compare(prev, cur)
    body = RCI.render(facts)

    # Then   the report names each of them, and says what llgenie must do about it
    assert facts["models_after"] == 2 and facts["engines_after"] == 2
    assert "`m2` — Model Two (VRAM 8GB)" in body
    assert "`NewEngine`" in body
    assert "['last_seen']" in body
    assert "'ROCm'" in body
    assert "#693, #677" in body and "#673/#686" in body
    assert "## Not covered" in body and "#669" in body
    # And the body is the repository's issue shape: the goal first, the diff as `## Technical`
    assert issue_body.missing(body) == [], issue_body.missing(body)
    assert issue_body.headings(body)[-1] == "Technical"
    assert "`m2` — Model Two (VRAM 8GB)" in issue_body.section_body(body, "Technical")


class _Gh:
    """A `gh` stand-in: it records every argv and answers the endpoints the product calls.

    `issue create` stores NO label — that is the measured runner behaviour (#724, issues #710
    and #749), so the only write that makes an issue routable is the REST label endpoint. The
    real `open_issue()`/`set_labels()`/`labels_of()` run against it; only `gh` is a stand-in.
    """

    def __init__(self, open_issues: list | None = None, label_sticks: bool = True,
                 label_refused: bool = False):
        self.calls: list[list[str]] = []
        self.open_issues = open_issues or []
        self.label_sticks = label_sticks
        self.label_refused = label_refused
        self.labels: dict[str, list[str]] = {}
        self._next = 705

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.open_issues)
        if args[:2] == ["issue", "edit"]:
            return ""
        if args[:2] == ["issue", "create"]:
            n, self._next = self._next, self._next + 1
            return f"https://github.com/asimov-agent/llgenie/issues/{n}"
        if args[:1] == ["api"]:
            path = next(a for a in args if a.startswith("repos/"))
            n = path.split("/issues/")[1].split("/")[0]
            if "POST" in args and self.label_refused:
                # The runner's PAT refuses the label write outright (#775): like real gh, it
                # exits non-zero and stderr names the 403, which the product must survive.
                raise RuntimeError(f"gh {' '.join(args)} failed: gh: Resource not "
                                   f"accessible by personal access token (HTTP 403)")
            if "POST" in args and self.label_sticks:
                for i, a in enumerate(args):
                    if a == "-f" and args[i + 1].startswith("labels[]="):
                        want = args[i + 1].split("=", 1)[1]
                        self.labels.setdefault(n, [])
                        if want not in self.labels[n]:
                            self.labels[n].append(want)
                return ""
            return "\n".join(self.labels.get(n, []))
        raise AssertionError(f"unexpected gh call: {args}")


def test_a_second_open_for_the_same_store_updates_instead_of_duplicating(monkeypatch):
    """One issue per store version: the marker is the identity, so a re-run edits it — and
    re-queues it, because the transport may have dropped the label the first time."""
    # Given  gh answering with an open issue that already carries this store's marker,
    #        and carrying no label (the measured #710/#749 state)
    utc = "2026-10-26T00:00:00Z"
    marker = RCI.MARKER.format(utc=utc)
    gh = _Gh(open_issues=[{"number": 704, "body": f"old body\n\n{marker}\n"}])
    monkeypatch.setattr(RCI, "run_gh", gh)

    # When   the report is opened for that same store
    result = RCI.open_issue("new body", utc, "asimov-agent/llgenie")

    # Then   it edits issue 704 rather than creating a second one
    assert result == "updated #704"
    assert ["issue", "edit", "704"] == gh.calls[1][:3]
    assert not any(c[:2] == ["issue", "create"] for c in gh.calls)

    # And    the unlabelled issue is labelled through the REST endpoint, not `--add-label`
    posts = [c for c in gh.calls if c[:1] == ["api"] and "POST" in c]
    assert len(posts) == 1 and "repos/asimov-agent/llgenie/issues/704/labels" in posts[0]
    assert f"labels[]={RCI.LABEL}" in posts[0]
    assert gh.labels["704"] == [RCI.LABEL]


def test_a_store_with_no_open_issue_creates_exactly_one(monkeypatch):
    """The first sync of a store version files one issue, and the label is PROVED."""
    # Given  gh answering with no matching issue
    gh = _Gh()
    monkeypatch.setattr(RCI, "run_gh", gh)

    # When   the report is opened
    result = RCI.open_issue("body", "2026-10-27T00:00:00Z", "asimov-agent/llgenie")

    # Then   exactly one issue is created, and it carries no --label (dropped on the runner)
    assert result.endswith("/issues/705")
    creates = [c for c in gh.calls if c[:2] == ["issue", "create"]]
    assert len(creates) == 1
    assert "--label" not in creates[0]

    # And    the label was written through the API and read back from the tracker
    posts = [c for c in gh.calls if c[:1] == ["api"] and "POST" in c]
    assert len(posts) == 1 and "repos/asimov-agent/llgenie/issues/705/labels" in posts[0]
    assert f"labels[]={RCI.LABEL}" in posts[0]
    reads = [c for c in gh.calls if c[:1] == ["api"] and "--jq" in c]
    assert reads and "repos/asimov-agent/llgenie/issues/705/labels" in reads[-1]
    assert gh.labels["705"] == [RCI.LABEL]


def test_a_change_issue_that_cannot_be_labelled_fails_the_step(monkeypatch):
    """An unlabelled change issue routes the store review to nobody: a red step, never a pass."""
    # Given  a tracker whose label write is accepted but never stored
    gh = _Gh(label_sticks=False)
    monkeypatch.setattr(RCI, "run_gh", gh)

    # When   the report is opened
    try:
        RCI.open_issue("body", "2026-10-27T00:00:00Z", "asimov-agent/llgenie")
    except SystemExit as exc:
        # Then  the step fails, naming the issue and the missing label
        assert "#705" in str(exc) and RCI.LABEL in str(exc), exc
    else:                                            # pragma: no cover - the failure is the assertion
        raise AssertionError("an unlabelled change issue must fail the step")

    # And    the failure is the READ-BACK, not a skipped write
    assert [c for c in gh.calls if c[:1] == ["api"] and "POST" in c]


def test_a_change_issue_survives_a_label_write_the_credential_refuses(monkeypatch, capsys):
    """A refused label write (HTTP 403) must not lose the change issue AND the sync PR: the
    step files the issue, names the refusal, and returns — it never dies on a label it cannot
    apply (#775, the #724/#819 PAT class).
    """
    # Given  a tracker whose label POST is REFUSED by the credential (the runner PAT 403)
    gh = _Gh(label_refused=True)
    monkeypatch.setattr(RCI, "run_gh", gh)

    # When   the report is opened
    result = RCI.open_issue("body", "2026-10-27T00:00:00Z", "asimov-agent/llgenie")

    # Then   the change issue is still filed (the analysis is the artifact), no exception
    assert result.endswith("/issues/705")
    creates = [c for c in gh.calls if c[:2] == ["issue", "create"]]
    assert len(creates) == 1

    # And    the refusal is reported loudly on stderr, never swallowed
    err = capsys.readouterr().err
    assert "#705" in err and "refused by the credential" in err
    assert "Resource not accessible by personal access token" in err or "HTTP 403" in err

    # And    the step returns successfully — the leg survives so the sync PR step still runs
    assert not [c for c in gh.calls if c[:1] == ["api"] and "--jq" in c]


def test_dry_run_mutates_nothing(monkeypatch):
    """`DRY=1` previews the decision, it does not touch GitHub."""
    # Given  a marker-less listing
    gh = _Gh()
    monkeypatch.setattr(RCI, "run_gh", gh)

    # When   the open runs dry
    result = RCI.open_issue("body", "2026-10-27T00:00:00Z", "asimov-agent/llgenie", dry=True)

    # Then   it says what it would do, and neither writes the body nor labels anything
    assert result == "would create one issue"
    assert not any(c[:2] in (["issue", "create"], ["issue", "edit"]) for c in gh.calls)
    assert not any(c[:1] == ["api"] for c in gh.calls)


def test_a_dry_update_of_a_marked_issue_does_not_label_it(monkeypatch):
    """The dry run is inert on the update path too: no edit, no label write."""
    # Given  an open issue carrying this store's marker and no label
    utc = "2026-10-26T00:00:00Z"
    marker = RCI.MARKER.format(utc=utc)
    gh = _Gh(open_issues=[{"number": 704, "body": marker}])
    monkeypatch.setattr(RCI, "run_gh", gh)

    # When   the open runs dry
    result = RCI.open_issue("new body", utc, "asimov-agent/llgenie", dry=True)

    # Then   nothing is written
    assert result == "would update #704"
    assert not any(c[:2] in (["issue", "edit"], ["issue", "create"]) for c in gh.calls)
    assert not any(c[:1] == ["api"] for c in gh.calls)


def test_the_workflow_runs_the_step_even_when_a_gate_is_red():
    """The analysis is most valuable when the store cannot land, so the step must not be
    gated on the check step's success (issue #704)."""
    # Given  the sync workflow, read as text (a strict YAML parse is check-workflows' job)
    import re
    text = (ROOT / ".github" / "workflows" / "registry-sync.yml").read_text()

    # When   the change-issue step is located
    step = re.search(r"- name: State what changed in ONE issue.*?(?=\n      - name: |\Z)", text, re.S)

    # Then   it exists, runs on `always()` when the store changed, and calls the make target
    assert step, "the registry-sync workflow has no change-issue step"
    body = step.group(0)
    assert "always()" in body and "steps.diff.outputs.changed" in body
    assert "make sync-change-issue REPO=" in body
