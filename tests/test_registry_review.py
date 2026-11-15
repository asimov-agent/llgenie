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


def test_a_second_publish_edits_over_rest_and_reads_the_body_back(monkeypatch):
    """One issue per store: the marker is the identity, so a re-run edits it over REST and reads it back."""
    # Given  an open issue that already carries this store's review marker
    calls: list[list[str]] = []
    utc = "2026-10-27T05:00:00Z"
    marker = RR.MARKER.format(utc=utc)
    written: dict[int, str] = {}
    patched: list[list[str]] = []

    def fake(args, ok_codes=(0,)):
        calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 710, "title": "t", "body": f"old\n\n{marker}\n"}])
        if args[0] == "api" and "-X" in args:
            # the REST PATCH records the body it is sent
            patched.append(args)
            i = args.index("-f")
            field = args[i + 1]
            key, val = field.split("=", 1)
            assert key == "body"
            assert "new body\n\n" in val and marker in val
            written[710] = val
            return ""
        # the read-back (`--jq .body`) over the same transport returns exactly the stored body
        return written.get(710, "")

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published for the same store
    result = RR.publish("new body", "t", utc, "asimov-agent/llgenie")

    # Then   it edits #710 through the REST PATCH (no GraphQL `issue edit`) and reads it back
    assert result == "updated #710"
    assert not any(c[:2] == ["issue", "edit"] for c in calls)
    assert patched and any(f"repos/asimov-agent/llgenie/issues/710" in a for a in patched)
    assert any("api" in a and "PATCH" in a for a in patched)
    assert any("api" in a and "--jq" in a and ".body" in a for a in calls)
    assert not any(c[:2] == ["issue", "create"] for c in calls)


def test_an_update_whose_body_did_not_stick_fails_naming_the_issue(monkeypatch):
    """A 0-exit write that never stores the body is a red step, not a green one (#819)."""
    # Given  an open review issue, and a read-back whose stored body is NOT the write sent
    utc = "2026-10-27T05:00:00Z"
    marker = RR.MARKER.format(utc=utc)

    def fake(args, ok_codes=(0,)):
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 710, "title": "t", "body": f"old\n\n{marker}\n"}])
        # the PATCH "succeeds" (returns 0) but the read-back returns the stale body
        return json.dumps({"number": 710, "body": "old\n\n" + marker + "\n"})

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published for the same store
    import pytest  # noqa: PLC0415

    with pytest.raises(SystemExit) as ei:
        RR.publish("new body", "t", utc, "asimov-agent/llgenie")

    # Then   the step fails naming the issue — a stored body mismatch is never silent
    assert "710" in str(ei.value)
    assert "body" in str(ei.value)


def test_a_refused_body_write_reports_and_survives(monkeypatch, capsys):
    """A 403 refusal is a credential fact (#775): print it loudly and do not raise."""
    # Given  an open review issue, and a REST write GitHub refuses with a PAT 403
    utc = "2026-10-27T05:00:00Z"
    marker = RR.MARKER.format(utc=utc)

    def fake(args, ok_codes=(0,)):
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 710, "title": "t", "body": f"old\n\n{marker}\n"}])
        raise RuntimeError("gh api -X PATCH repos/asimov-agent/llgenie/issues/710 "
                           "-f body=... failed (1): GraphQL: Resource not accessible by "
                           "personal access token (HTTP 403)")

    monkeypatch.setattr(RR, "run_gh", fake)

    # When   the review is published for the same store
    result = RR.publish("new body", "t", utc, "asimov-agent/llgenie")

    # Then   the run survives with a result, and one loud line names issue + endpoint + capability
    assert result == "updated #710"
    err = capsys.readouterr().err
    assert "710" in err
    assert "refused" in err
    assert "body" in err


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
