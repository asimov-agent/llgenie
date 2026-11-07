"""The gate that stops a pin-bump PR merging before its image is published (#1622).

`ci.yml` builds/publishes no engine since issue #1027 — publishing is the
engine-build PRODUCER's job, and happens only when it is dispatched `push=true`.
Before #1622 nothing else verified the image: the PR's own
`test_every_image_install_pulls_is_published` DEFERS the repinned engine, because
that check was written for the pre-#1027 world where the same CI run published it.
So a bump could merge with its new tag never on GHCR, unseen until a scheduled run
tripped on the 404 (#1365/#1587 recurring class).

`scripts/check_engine_pins_published.py` closes it at the PR: an engine whose
committed params differ from the base is repinned by THIS change, so its exact tag
must resolve a manifest before merge. Hermetic: the repin set and the digest probe
are stubbed (the real diff is exercised against a real git base in one live test);
nothing touches the network.

Mirrors the fake-digest pattern of tests/test_ci_publish_order.py (issue #169).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

import scripts.check_engine_pins_published as cpp  # noqa: E402  (the repo's one import root, issue #796)
import scripts.engine_image as ei  # noqa: E402

REGISTRY = "ghcr.io/asimov-agent"


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _fake_digest(resolve_map: dict[str, str]) -> tuple[object, list[str]]:
    """Digest probe answering from `resolve_map` ('' = 404); logs every lookup."""
    calls: list[str] = []

    def fake(ref: str):
        calls.append(ref)
        d = resolve_map.get(ref, "")
        return (d, "") if d else ("", "404 Not Found")

    return fake, calls


def test_no_engine_repinned_is_green_and_hermetic(monkeypatch):
    """A PR that repins nothing queries nothing: green, zero network."""
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [])
    fake, calls = _fake_digest({})
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 0
    assert calls == [], "nothing repinned must not touch the registry"


def test_a_repinned_engines_exact_tag_must_resolve(monkeypatch):
    """A repinned engine's exact content-address tag is looked up; a 404 reds with the ref named."""
    engine, variant = "mlx", "cpu"
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [engine])
    tag = ei.resolve(engine, None, variant)["tag"]
    ref = f"{REGISTRY}/{tag}"
    fake, calls = _fake_digest({ref: ""})     # 404 for the exact tag
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 1
    assert ref in calls, f"the exact tag {ref} must be looked up"


def test_green_only_when_the_exact_tag_resolves(monkeypatch):
    """Once the same tag resolves, the identical check is green."""
    engine = "mlx"
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [engine])
    # mlx declares cuda + cpu — every non-disabled variant must resolve for green
    import json as _json
    params = _json.loads(
        (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    variants = [v for v in params["variants"] if not ei.disabled(engine, v)]
    resolve_map = {}
    for v in variants:
        ref = f"{REGISTRY}/{ei.resolve(engine, None, v)['tag']}"
        resolve_map[ref] = "sha256:" + "0" * 64
    fake, calls = _fake_digest(resolve_map)
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 0
    assert len(calls) == len(variants), f"every variant queried, got {calls}"


def test_every_variant_of_a_repinned_engine_must_resolve(monkeypatch):
    """A repinned engine's whole published set reds if ANY variant is absent, not just cpu."""
    engine = "llama.cpp"
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [engine])
    # resolve every non-disabled variant the committed params declare
    import json as _json
    params = _json.loads(
        (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    variants = [v for v in params["variants"] if not ei.disabled(engine, v)]
    assert len(variants) >= 2, f"{engine} should declare more than one buildable variant"
    resolve_map = {}
    for v in variants:
        ref = f"{REGISTRY}/{ei.resolve(engine, None, v)['tag']}"
        # all but the LAST variant resolve; the last 404s -> the gate must red
        resolve_map[ref] = "sha256:" + "0" * 64
    last_ref = f"{REGISTRY}/{ei.resolve(engine, None, variants[-1])['tag']}"
    resolve_map[last_ref] = ""
    fake, calls = _fake_digest(resolve_map)
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 1, "an unresolved variant of a repinned engine must red the PR"
    assert last_ref in calls
    # and every variant was checked, not just cpu
    assert len(calls) == len(variants), f"looked up {calls}, expected one per variant"


def test_the_real_diff_detects_a_repin_and_checks_the_registry():
    """Live: with the tree at its own base (nothing repinned) the gate is green and
    probes nothing beyond the diff. A params file that differs from the base is named.
    Genuinely runs (no skip) exactly as the live registry tests of
    tests/test_ci_publish_order.py do — CI is always a full clone, so git resolves."""
    engine = "mlx"
    base = _head()
    assert base, f"git must resolve the base (full clone): got {base!r}"
    orig = (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text()
    ids = cpp.repinned_engine_ids(base)
    assert engine not in ids, f"{engine} should be at its base pin (repinned: {ids})"
    assert not ids, f"a clean branch repins nothing, got {ids}"
    assert (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text() == orig


def test_a_404_is_polled_until_the_producer_publishes(monkeypatch, capsys):
    """CI waits. A tag that 404s on the first look and resolves on the next is green."""
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: ["mlx"])
    seen: dict[str, int] = {}

    def digest(ref: str):
        seen[ref] = seen.get(ref, 0) + 1
        if seen[ref] == 1:
            return "", "HTTP Error 404: Not Found"
        return "sha256:" + "b" * 64, ""

    monkeypatch.setattr(cpp.time, "sleep", lambda _seconds: None)
    rc = cpp.check(_head(), digest=digest, registry=REGISTRY, wait_min=5)
    assert rc == 0
    assert seen and all(n >= 2 for n in seen.values())
    assert "waiting for" in capsys.readouterr().out


def test_the_gate_is_wired_into_ci_unit_and_phony():
    """The gate runs in the PR pipeline and is .PHONY, else it is a defect.

    It is not a step of ci-unit. That job's ceiling is 120 minutes and the
    producer is allowed 240, so a one-shot 404 redded the PR while the image
    was still building (PR #1696). ci.yml's engine-pins job polls instead.
    """
    mk = (REPO / "Makefile").read_text()
    ci_unit = mk.split("\nci-unit:", 1)[1].split("\n\n", 1)[0]
    assert "check-engine-pins-published" not in ci_unit, "unit must not 404 while the producer runs"
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "make check-engine-pins-published WAIT=" in workflow
    # .PHONY spans backslash-continuation lines (issue #883): read the whole block
    phony = re.search(r"^\.PHONY:.*?^\S", mk, re.MULTILINE | re.DOTALL)
    assert phony and re.search(r"\bcheck-engine-pins-published\b", phony.group(0)), \
        "check-engine-pins-published is not .PHONY"
    assert re.search(r"\bengine-pins-published-report\b", phony.group(0)), \
        "engine-pins-published-report is not .PHONY"
    target = re.search(r"^check-engine-pins-published:.*(?=^\S)", mk, re.MULTILINE | re.DOTALL)
    assert target and "python3 scripts/check_engine_pins_published.py check" in target.group(0)
    assert target and "--base" in target.group(0), "the gate must diff against the base"
    assert target and "--wait-min" in target.group(0), "CI must be able to poll"



def test_red_pin_producing_cell_skips_instead_of_waiting(monkeypatch, capsys):
    """AC1 (issue #1844): a pin-producing engine-build cell that ALREADY concluded red
    concludes the gate immediately with a recorded SKIPPED decision — not a 290-minute
    wait. The reproducing cell is the truthful red; the pin gate owes no timer on top."""
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: ["mlx"])

    def digest(_ref):
        raise AssertionError("evidence-aware pre-poll must skip BEFORE any registry probe")

    cell = lambda _engine: ("42180155067", "failure")
    rc = cpp.check(_head(), digest=digest, registry=REGISTRY, wait_min=290,
                   producer=cell, repo="asimov-agent/llgenie", branch="fix/whatever")
    assert rc == 0, "a red producing cell skips the gate (the red belongs to the cell)"
    err = capsys.readouterr().err
    assert "SKIPPED" in err and "engine=mlx" in err and "42180155067" in err and "failure" in err


def test_non_success_cell_skips_a_success_red_and_no_conclusion_wait(monkeypatch):
    """Every non-success producer cell (failure, cancelled, timed_out) skips immediately;
    a success pairing with a 404 tag is a REAL publish gap (red, gate not weakened); an
    in-progress (no conclusion) cell still owes the wait and a late publish passes."""
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: ["mlx"])
    for conc in ("failure", "cancelled", "timed_out"):
        rc = cpp.check(_head(), digest=lambda _r: ("", "404"), registry=REGISTRY,
                       wait_min=5, producer=lambda _e: ("999", conc))
        assert rc == 0, f"{conc} must skip immediately, not wait"
    rc = cpp.check(_head(), digest=lambda _r: ("", "404"), registry=REGISTRY,
                   wait_min=0, producer=lambda _e: ("999", "success"))
    assert rc == 1, "a success producer cell + a 404 tag is a genuine publish gap and red"
    seen = {}

    def digest(ref):
        seen[ref] = seen.get(ref, 0) + 1
        return ("", "404") if seen[ref] == 1 else ("sha256:" + "0" * 64, "")

    monkeypatch.setattr(cpp.time, "sleep", lambda _s: None)
    rc = cpp.check(_head(), digest=digest, registry=REGISTRY, wait_min=5,
                   producer=lambda _e: None)
    assert rc == 0, "a not-yet-concluded producer cell still waits for the publish (gate intact)"


def test_evidence_pre_poll_off_without_wait_or_repo_branch(monkeypatch):
    """The evidence pre-poll runs ONLY when CI asks for a wait AND names repo+branch;
    a one-shot local check must stay a pure registry probe (hermetic)."""
    called = []

    def producer(e):
        called.append(e)
        return ("1", "failure")

    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: ["mlx"])
    rc = cpp.check(_head(), digest=lambda _r: ("", "404"), registry=REGISTRY,
                   producer=producer, repo="r", branch="b")
    assert rc == 1 and called == [], "a one-shot (no wait) check must be a pure registry probe"
    seen = {}
    def digest2(ref):
        seen[ref] = seen.get(ref, 0) + 1
        return ("", "404") if seen[ref] == 1 else ("sha256:" + "0" * 64, "")
    monkeypatch.setattr(cpp.time, "sleep", lambda _s: None)
    rc = cpp.check(_head(), digest=digest2, registry=REGISTRY,
                   wait_min=5, producer=None, repo="")
    assert rc == 0 and seen, "without repo/branch the pre-poll stays off and the wait resolves"


def test_wiring_passes_repo_and_branch_into_the_ci_job():
    """The evidence-aware pre-poll is on in the CI job: ci.yml must name REPO+BRANCH and
    grant actions:read (the right to read the producer's cell job state, issue #893)."""
    wf = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    pins = re.search(r"^  engine-pins:.*?(?=\n  [a-z])", wf, re.MULTILINE | re.DOTALL)
    assert pins, "engine-pins job not found in ci.yml"
    block = pins.group(0)
    assert "actions: read" in block, "engine-pins must read the producer cell state (actions:read)"
    assert "REPO=${{ github.repository }}" in block
    assert "BRANCH=${{ github.head_ref || github.ref_name }}" in block
