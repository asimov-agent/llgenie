#!/usr/bin/env python3
"""A green registry-sync PR is reviewed into ONE agent:implement issue (issue #709).

`registry_review.py` has two halves and both are driven here for real: the **selection check**
runs the product's own `trend_list()` / `rank_engines()` over a real store built in a temp dir,
and the **publish step** files an issue with `gh` replaced by a function that records the command
(`gh` is the external system; the report, the marker and the decision are the product).

The one thing the selection check exists to catch — a list that names a server which is NOT the
fastest of its own rank class — is proved by handing the checker an order that is wrong
(`selection(ranker=…)`). The ranking rule itself is not replaced: the checker is the code under
test, the order is its input.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import registry_review as RR  # noqa: E402

#: The engine params a real host reads, narrowed to two engines on one backend — the container
#: facts, not a stand-in for the ranking rule.
IDS = {
    "llama.cpp": {"id": "llama.cpp", "variants": ["cuda", "cpu"], "formats": ["gguf"]},
    "vLLM": {"id": "vllm", "variants": ["cuda"], "formats": ["safetensors", "gguf"]},
}


def _model(id_: str, name: str, vram: str, engines: list[dict]) -> dict:
    return {"id": id_, "name": name, "vram_tier": vram,
            "formats": [{"name": "GGUF", "hf": f"a/{id_}-GGUF"}],
            "engines": engines}


def _registry(*models: dict) -> dict:
    return {"generated_utc": "2026-10-27T05:00:00Z",
            "engines": {"llama.cpp": {"backend": "CUDA"}, "vLLM": {"backend": "CUDA"}},
            "models": list(models)}


#: One card's worth of store: two engines measured on the SAME card, vLLM faster.
STORE = _registry(
    _model("slow-model", "Slow Model", "8GB", [
        {"engine": "llama.cpp", "tps": "40.0", "hardware": "RTX 4090", "backend": "CUDA"},
        {"engine": "vLLM", "tps": "90.0", "hardware": "RTX 4090", "backend": "CUDA"},
    ]),
)


def test_the_selection_names_the_fastest_server_of_its_own_card_class():
    """The list names the server, and it is the fastest one measured on that card class."""
    # Given  a store whose two engines are both proven on the same card, vLLM at 90 t/s
    # When   the selection check runs for one card size
    sel = RR.selection(STORE, archs=("cuda",), vrams=(24,), rams=(32,), ids=IDS)

    # Then   the row names vLLM at its measured figure, with no finding
    case = sel["cases"][0]
    assert case["rows"] == [{"model": "Slow Model", "server": "vLLM", "tps": 90.0,
                             "rank": 0, "measured_on": "CUDA"}], case["rows"]
    assert case["findings"] == []


def test_a_list_that_names_a_slower_server_of_the_same_class_is_a_finding():
    """The defect class the check exists for: the row is not the highest t/s that fits the card."""
    # Given  the same store, and a ranker that hands back the slower engine FIRST
    def wrong_order(model, arch, ids, gb):  # noqa: ARG001
        return [
            {"engine": "llama.cpp", "id": "llama.cpp", "variant": "cuda", "tps": 40.0,
             "engagement": 0, "rank": 0, "measured_on": "CUDA", "same_hw": True},
            {"engine": "vLLM", "id": "vllm", "variant": "cuda", "tps": 90.0,
             "engagement": 0, "rank": 0, "measured_on": "CUDA", "same_hw": True},
        ]

    # When   the selection check runs against that order
    sel = RR.selection(STORE, archs=("cuda",), vrams=(8,), rams=(32,), ids=IDS,
                       ranker=wrong_order)

    # Then   it names both figures, so a reviewer can see which server is missing
    finding = sel["findings"][0]
    assert finding["kind"] == "slower-than-class"
    assert "llama.cpp (40.0 t/s) is named but vLLM measured 90.0 t/s" in finding["detail"]


def test_a_listed_model_no_engine_can_run_is_a_finding():
    """A row llgenie can list but cannot serve is reported, never silently empty."""
    # Given  a store whose only engine has no image for the arch under review
    # When   the selection check runs with an engine set that cannot serve it
    sel = RR.selection(STORE, archs=("cuda",), vrams=(8,), rams=(32,), ids={})

    # Then   the row keeps its name and the finding says why there is no server
    assert sel["cases"][0]["rows"][0]["server"] == ""
    assert sel["findings"][0]["kind"] == "no-engine"
    assert "no cuda engine image can run it" in sel["findings"][0]["detail"]


def test_a_tier_that_lists_nothing_is_a_finding():
    """A card size with no listed model is reported: the list is the product's answer."""
    # Given  a store whose only model needs more VRAM than the case under review
    # When   the selection check runs for a card that fits nothing
    sel = RR.selection(STORE, archs=("cuda",), vrams=(0.5,), rams=(8,), ids=IDS)

    # Then   the empty tier is named instead of rendering a silently blank table
    assert sel["cases"][0]["rows"] == []
    assert sel["findings"][0]["kind"] == "empty-tier"


def test_the_precondition_is_every_check_green_on_an_open_sync_pr(monkeypatch):
    """A pending or failed check is `skip`, not a review of a store that cannot land."""
    # Given  an open sync PR whose checks are one pass and one pending
    answers = {
        "list": [{"number": 12, "url": "https://example/pull/12", "title": "chore(registry): x",
                  "headRefOid": "abc", "mergeStateStatus": "BLOCKED"}],
        "checks": [{"bucket": "pass", "name": "ci-unit", "state": "SUCCESS", "link": "l"},
                   {"bucket": "pending", "name": "engine-image", "state": "IN_PROGRESS", "link": "l"}],
    }

    def fake(args, ok_codes=(0,)):
        return json.dumps(answers["checks"] if args[:2] == ["pr", "checks"] else answers["list"])

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the PR is read
    pr = RR.sync_pr("asimov-agent/llgenie")

    # Then   it is found, and it is not green — the pending check is named
    assert pr["found"] is True and pr["green"] is False
    assert "engine-image=pending" in pr["why"]


def test_no_open_sync_pr_is_a_skip_with_a_reason(monkeypatch):
    """Nothing is reviewed (and no model is spent) when the sync has not opened a PR."""
    # Given  gh answering with no open `chore/registry-sync` PR
    monkeypatch.setattr(RR, "run_gh", lambda args, ok_codes=(0,): "[]")

    # When   the PR is read
    pr = RR.sync_pr("asimov-agent/llgenie")

    # Then   the reason states what would have to exist instead
    assert pr == {"found": False, "green": False,
                  "why": "no open `chore/registry-sync` PR (the sync opens one only when its gates pass)"}


def test_the_brief_says_skip_and_still_renders_the_check(monkeypatch, tmp_path):
    """A skipped run is diagnosable from its own log, and writes `action=skip` for the job."""
    # Given  a real store in a temp dir and no green sync PR
    store = tmp_path / "models.json"
    store.write_text(json.dumps(STORE))
    monkeypatch.setattr(RR, "run_gh", lambda args, ok_codes=(0,): "[]")
    out = tmp_path / "review-in.md"

    # When   the brief is rendered
    code = RR.brief(store, "asimov-agent/llgenie", RR.BRANCH, str(out))

    # Then   it exits 0, writes the precondition, and the selection table is still there
    assert code == 0
    text = out.read_text()
    assert text.startswith("action=skip\nreason=no open")
    assert "## The VRAM selection check" in text
    assert "Slow Model → vLLM (90.0 t/s)" in text


def test_a_store_with_no_issue_yet_creates_exactly_one_labelled_issue(monkeypatch):
    """The green store's review is ONE issue, labelled for the implementer."""
    # Given  an issue listing with no matching marker and no change-issue for this store
    calls: list[list[str]] = []

    def fake(args, ok_codes=(0,)):
        calls.append(args)
        if args[:2] == ["issue", "list"]:
            return "[]"
        return "https://github.com/asimov-agent/llgenie/issues/710"

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published
    result = RR.publish("body", "sync review: x", "2026-10-27T05:00:00Z", "asimov-agent/llgenie")

    # Then   exactly one issue is created, carrying `agent:implement`
    assert result.endswith("/issues/710")
    creates = [c for c in calls if c[:2] == ["issue", "create"]]
    assert len(creates) == 1
    assert "--label" in creates[0] and RR.LABEL in creates[0]


def test_a_second_publish_for_the_same_store_updates_instead_of_duplicating(monkeypatch):
    """One issue per store: the marker is the identity, so a re-run edits it — over REST."""
    # Given  an open issue that already carries this store's review marker
    calls: list[list[str]] = []
    utc = "2026-10-27T05:00:00Z"
    marker = RR.MARKER.format(utc=utc)
    bodies = {"710": f"old\n\n{marker}\n"}

    def fake(args, ok_codes=(0,)):
        calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 710, "title": "t", "body": bodies["710"]}])
        if args[:2] == ["issue", "edit"]:
            # #2691: the product must not reach the GraphQL body transport at all — real gh
            # answers it with "GraphQL: Resource not accessible by personal access token
            # (updateIssue)" for registry-lane runner credentials (#2673), and the fake
            # refusing is what pins the REST-only rule.
            raise AssertionError(f"unexpected gh call: {args}")
        if args[:1] == ["api"]:
            if args[1:3] == ["-X", "PATCH"]:
                new = next(args[i + 1][5:] for i, a in enumerate(args)
                           if a == "-f" and args[i + 1].startswith("body="))
                bodies["710"] = new
                return ""
            return bodies["710"]
        return ""

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published for the same store
    result = RR.publish("new body", "t", utc, "asimov-agent/llgenie")

    # Then   it edits #710 over REST PATCH and creates nothing
    assert result == "updated #710"
    patches = [c for c in calls if c[:3] == ["api", "-X", "PATCH"]]
    assert len(patches) == 1 and "repos/asimov-agent/llgenie/issues/710" in patches[0]
    assert not any(c[:2] == ["issue", "edit"] for c in calls)
    assert not any(c[:2] == ["issue", "create"] for c in calls)

    # And    the write is PROVEN by a read-back of the body over the same transport
    reads = [c for c in calls if c[:1] == ["api"] and c[-1] == ".body"]
    assert reads and "repos/asimov-agent/llgenie/issues/710" in reads[0]
    assert bodies["710"] == f"new body\n\n{marker}\n"


def test_a_review_body_write_that_claims_success_but_never_sticks_fails_the_step(monkeypatch):
    """The read-back is the verdict: a PATCH that exits 0 but leaves the old body must red."""
    # Given  gh accepting the PATCH but never storing the new body (the #819 silent drop)
    utc = "2026-10-27T05:00:00Z"
    marker = RR.MARKER.format(utc=utc)
    bodies = {"710": f"old\n\n{marker}\n"}

    def fake(args, ok_codes=(0,)):
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 710, "title": "t", "body": bodies["710"]}])
        if args[:1] == ["api"] and args[1:3] == ["-X", "PATCH"]:
            return ""                                   # claims success, stores nothing
        if args[:1] == ["api"]:
            return bodies["710"]
        return ""

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published for that same store
    try:
        RR.publish("new body", "t", utc, "asimov-agent/llgenie")
    except SystemExit as exc:
        # Then  the step fails, naming the issue whose body never changed
        assert "#710" in str(exc), exc
    else:                                            # pragma: no cover - the failure is the assertion
        raise AssertionError("a body write that never stuck must fail the step")


def test_a_refused_review_body_write_names_the_issue_the_endpoint_and_the_capability(monkeypatch,
                                                                                      capsys):
    """A 403 on the body PATCH is a credential fact (#775 rule): REPORTED, naming issue +
    endpoint + capability, and the leg survives so the review lane still finishes."""
    # Given  gh refusing the body PATCH with the refusal #2673 measured on the sibling leg
    utc = "2026-10-27T05:00:00Z"
    marker = RR.MARKER.format(utc=utc)
    bodies = {"710": f"old\n\n{marker}\n"}
    calls: list[list[str]] = []

    def fake(args, ok_codes=(0,)):
        calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 710, "title": "t", "body": bodies["710"]}])
        if args[:1] == ["api"] and args[1:3] == ["-X", "PATCH"]:
            raise RuntimeError(f"gh {' '.join(args)} failed: gh: Resource not accessible by "
                               "personal access token (HTTP 403)")
        return bodies.get("710", "")

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published for that same store
    result = RR.publish("new body", "t", utc, "asimov-agent/llgenie")

    # Then   no traceback: the leg returns a named outcome instead of an updated one
    assert result == "update refused for #710"

    # And    stderr names the issue, the exact endpoint, and the missing capability
    err = capsys.readouterr().err
    assert "#710" in err
    assert "repos/asimov-agent/llgenie/issues/710" in err
    assert "issues write" in err
    assert "Resource not accessible by personal access token" in err

    # And    no GraphQL transport was attempted, and no read-back followed the refusal
    assert not any(c[:2] == ["issue", "edit"] for c in calls)
    assert not [c for c in calls if c[:1] == ["api"] and c[-1] == ".body"]


def test_the_review_names_the_store_change_report_instead_of_repeating_it(monkeypatch):
    """The diff index (#704) is linked, not restated: one issue, one objective."""
    # Given  an open change issue carrying the store's change marker
    utc = "2026-10-27T05:00:00Z"
    calls: list[list[str]] = []

    def fake(args, ok_codes=(0,)):
        calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 706, "title": "sync: review",
                                "body": RR.CHANGE_MARKER.format(utc=utc)}])
        return "https://github.com/asimov-agent/llgenie/issues/711"

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published
    RR.publish("body", "t", utc, "asimov-agent/llgenie")

    # Then   the created body links #706
    created = [c for c in calls if c[:2] == ["issue", "create"]][0]
    assert "The store's change report is #706." in created[created.index("--body") + 1]


def test_a_clear_verdict_files_nothing(tmp_path, capsys):
    """The leg's `clear` is an answer, not a skipped run: publish exits 0 and creates none."""
    # Given  a verdict file that says the list and its servers are right
    leg = tmp_path / "registry-review.md"
    leg.write_text("VERDICT: clear\nREASON: every row names the fastest server of its class\n")

    # When   publish runs on it
    code = RR.main(["publish", "--in", str(leg), "--utc", "2026-10-27T05:00:00Z"])

    # Then   it exits 0, reports the reason, and never touches GitHub
    assert code == 0
    assert "nothing to file" in capsys.readouterr().out


def test_the_workflow_only_runs_the_review_behind_a_green_brief():
    """Every secret-spending step is gated on the brief's `review`, and only make targets run."""
    # Given  the workflow text (a strict YAML parse is check-workflows' job)
    text = (ROOT / ".github" / "workflows" / "registry-sync-review.yml").read_text()

    # When   the steps after the brief are read
    tail = text.split("Brief — the sync PR's checks", 1)[1]

    # Then   each one is gated on `action == 'review'` and calls a make target
    for block in tail.split("- name:")[1:]:
        if "run: make" not in block:
            continue
        assert "steps.brief.outputs.action == 'review'" in block, block[:80]
    assert "make registry-review-brief REPO=" in text
    assert "make registry-sync-review AGENT_IMAGE=" in text
    assert "make registry-review-publish REPO=" in text
    assert _Agent_no_direct_script(text)
    # The store the brief reads is the one that would land: the PR's head, checked out first.
    assert text.index("gh pr checkout") < text.index("make registry-review-brief REPO=")


def _Agent_no_direct_script(text: str) -> bool:
    """A workflow never calls `python3 scripts/…` directly (AGENTS.md: every step is a target)."""
    return "python3 scripts/" not in text


def test_the_skill_is_the_legs_contract():
    """The leg preloads ONE skill that states its Inputs, its ONE output and its rules."""
    # Given  the skill file the make leg names
    skill = (ROOT / ".hermes" / "skills" / "registry-sync-review" / "SKILL.md").read_text()

    # When   its frontmatter and contract sections are read
    # Then   the name matches its directory and every section a bot skill must carry is there
    assert "name: registry-sync-review" in skill
    for section in ("## Inputs", "## Output", "## Rules"):
        assert section in skill
    assert "registry-review.md" in skill
