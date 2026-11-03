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


def test_the_gate_is_wired_into_ci_unit_and_phony():
    """The gate runs in the PR pipeline (ci-unit) and is .PHONY, else it is a defect."""
    mk = (REPO / "Makefile").read_text()
    assert "$(MAKE) check-engine-pins-published" in mk, "ci-unit must run the gate"
    # .PHONY spans backslash-continuation lines (issue #883): read the whole block
    phony = re.search(r"^\.PHONY:.*?^\S", mk, re.MULTILINE | re.DOTALL)
    assert phony and re.search(r"\bcheck-engine-pins-published\b", phony.group(0)), \
        "check-engine-pins-published is not .PHONY"
    assert re.search(r"\bengine-pins-published-report\b", phony.group(0)), \
        "engine-pins-published-report is not .PHONY"
    target = re.search(r"^check-engine-pins-published:.*(?=^\S)", mk, re.MULTILINE | re.DOTALL)
    assert target and "python3 scripts/check_engine_pins_published.py check" in target.group(0)
    assert target and "--base" in target.group(0), "the gate must diff against the base"
