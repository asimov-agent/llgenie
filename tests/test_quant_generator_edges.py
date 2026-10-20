"""trending-quant-catalog generator edge cases (issue #122): the 'validate the NEW
links vs the old generated file / all on first run' contract, and the regression the
catalog is sensitive to — a fresh sync must probe new links, a refresh must probe only
the ones that changed, and a change (new / removed / renamed link or missing section)
bites, never silently ships.

Hermetic: mp.load_registry, gen._model_catalog and the network _probe_exists are
monkeypatched, so no live Hub and no real registry is touched. The generator's own
decision logic (links_to_validate) and its --check drift gate are exercised directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import gen_trending_quant_catalog as gen  # noqa: E402
import model_engine_pick as mp  # noqa: E402

_A = "https://huggingface.co/unsloth/A/resolve/main/a.gguf"
_B = "https://huggingface.co/unsloth/A/resolve/main/b.gguf"
_C = "https://huggingface.co/unsloth/B/resolve/main/c.gguf"


def _row(url):
    return {"repo": url.split("/resolve/")[0].replace("https://huggingface.co/", "", 1),
            "revision": "main", "path": url.rsplit("/", 1)[-1],
            "files": [url.rsplit("/", 1)[-1]], "size_gb": 1.0, "url": url}


def _payload(urls, utc="2026-10-10T00:00:00Z"):
    """A full {meta, files:{model:{engine:{arch,quants}}}} table payload."""
    eng = {"arch": ["cuda", "cpu"], "quants": [_row(u) for u in urls]}
    return {"meta": {"generated_utc": utc},
            "files": {"qwen3.8-27b": {"llama.cpp": eng}}}


def _engine(urls):
    """The engine-level cell: {arch, quants}."""
    return {"arch": ["cuda", "cpu"], "quants": [_row(u) for u in urls]}


def _stub_generator(monkeypatch, urls):
    """Make gen.main() build a payload for model 'qwen3.8-27b' with the given URLs.
    _model_catalog(m) returns the ENGINE map for that one model: {llama.cpp: {arch, quants}}.
    The stub registry carries the same generated_utc as _payload so --check only compares
    the model table (the drift we care about), not the timestamp."""
    monkeypatch.setattr(mp, "load_registry",
                        lambda *a, **k: {"generated_utc": "2026-10-10T00:00:00Z",
                                         "models": [{"id": "qwen3.8-27b"}]})
    monkeypatch.setattr(gen, "_model_catalog", lambda m: {"llama.cpp": _engine(urls)})


def _row_urls(payload_text):
    return {r["url"] for r in
            json.loads(payload_text)["files"]["qwen3.8-27b"]["llama.cpp"]["quants"]}


# ---- edge case 1: links_to_validate returns ALL on a first run -------------------
def test_first_run_probes_every_link():
    # Given a brand-new table (no prior generated file)
    new = {_A, _B, _C}
    # When the sync decides which links to validate
    probes = gen.links_to_validate(new, None)
    # Then it validates ALL of them (a first generation has no old file to diff against)
    assert set(probes) == new and len(probes) == 3


# ---- edge case 2: an update probes ONLY the newly-added links -------------------
def test_update_probes_only_new_links():
    # Given a mature table (A, B already committed) and a refresh that adds C
    old = _payload([_A, _B])
    new = {_A, _B, _C}
    # When the sync decides which links to validate
    probes = gen.links_to_validate(new, old)
    # Then it probes ONLY the newly-added link C, not the unchanged A/B
    assert probes == [_C]


def test_update_with_only_a_removed_link_probes_nothing():
    # Given a table (A, B, C) and a refresh that DROPS C (a link disappeared upstream)
    old = _payload([_A, _B, _C])
    new = {_A, _B}
    # When the sync decides which links to validate against the old file
    probes = gen.links_to_validate(new, old)
    # Then there is nothing newly-added to probe (the drop is an existing-link loss,
    # surfaced separately by the fixture-vs-canonical regression test)
    assert probes == []


# ---- edge case 3: a change that renders the catalog STALE is caught by --check ----
def test_check_fails_when_generated_differs_from_committed(monkeypatch, tmp_path):
    # Given a committed catalog (A, B) and a generator that now produces (A, B, C)
    _stub_generator(monkeypatch, [_A, _B, _C])
    dst = tmp_path / "trending-quant-catalog.json"
    dst.write_text(json.dumps(_payload([_A, _B]), indent=2) + "\n")
    monkeypatch.setattr(sys, "argv", ["gen_trending_quant_catalog.py", "--check", "-o", str(dst)])

    # When check-quant-catalog runs (the drift gate)
    rc = gen.main()

    # Then it FAILS: the committed artifact no longer matches the generator (the
    #   catalog is sensitive to the change — a new link appeared and must be reviewed)
    assert rc == 1


def test_check_passes_when_committed_matches_generated(monkeypatch, tmp_path):
    # Given a committed catalog produced by the generator itself (so meta matches)
    _stub_generator(monkeypatch, [_A, _B])
    dst = tmp_path / "trending-quant-catalog.json"
    monkeypatch.setattr(sys, "argv", ["gen_trending_quant_catalog.py", "-o", str(dst)])
    monkeypatch.setattr(gen, "_probe_status", lambda u, timeout=20.0: gen.PROBE_OK)
    assert gen.main() == 0                      # writes the committed table (healthy)

    # When check-quant-catalog runs against the identical generator + committed file
    monkeypatch.setattr(sys, "argv", ["gen_trending_quant_catalog.py", "--check", "-o", str(dst)])
    rc = gen.main()

    # Then it passes (no drift)
    assert rc == 0


# ---- edge case 4: a sync with a dead new link fails loudly -----------------------
def test_sync_fails_when_a_new_link_is_dead(monkeypatch, tmp_path):
    # Given a committed table (A) and a refresh whose NEW link B is dead (404)
    _stub_generator(monkeypatch, [_A, _B])
    dst = tmp_path / "trending-quant-catalog.json"
    dst.write_text(json.dumps(_payload([_A]), indent=2) + "\n")
    monkeypatch.setattr(sys, "argv", ["gen_trending_quant_catalog.py", "-o", str(dst)])
    monkeypatch.setattr(gen, "_probe_status",
                        lambda u, timeout=20.0: gen.PROBE_OK if u != _B else gen.PROBE_DEAD)

    # When the sync runs and the newly-added link does not resolve
    rc = gen.main()

    # Then it FAILS loudly and does NOT write the table (a fabricated link is never
    # shipped): the destination still holds the OLD committed table (A)
    assert rc == 1
    assert _row_urls(dst.read_text()) == {_A}


# ---- edge case 5: a sync writes canonical + fixture together ----------------------
def test_sync_writes_canonical_and_fixture_together(monkeypatch, tmp_path):
    # Given a first run with all links healthy (canonical OUT + fixture both tmp dirs,
    # so the sync writes both to the "canonical" location)
    _stub_generator(monkeypatch, [_A, _B])
    dst = tmp_path / "trending-quant-catalog.json"
    fx = tmp_path / "fixture.json"
    monkeypatch.setattr(gen, "OUT", dst)
    monkeypatch.setattr(gen, "FIXTURE", fx)
    monkeypatch.setattr(sys, "argv", ["gen_trending_quant_catalog.py"])  # default -o = OUT
    monkeypatch.setattr(gen, "_probe_status", lambda u, timeout=20.0: gen.PROBE_OK)

    # When the sync runs
    rc = gen.main()

    # Then it writes both the canonical table and its test fixture, in lock-step
    assert rc == 0
    assert dst.exists() and fx.exists()
    assert dst.read_text() == fx.read_text()
    assert _row_urls(dst.read_text()) == {_A, _B}


# ---- edge case 8: a gated file exists — it is not a dead link (issue #418) -------
def test_probe_status_classifies_gated_apart_from_dead(monkeypatch):
    """200/206 readable, 401/403 gated (present, not readable), 404 dead — measured shapes."""
    import io
    import urllib.error

    class Response:
        """The two attributes the probe reads: `status`, and the context-manager protocol."""
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def answer(code):
        def urlopen(req, timeout=20.0):
            if code in (200, 206):
                return Response(200)
            raise urllib.error.HTTPError(req.full_url, code, "no", {}, io.BytesIO(b""))
        monkeypatch.setattr("urllib.request.urlopen", urlopen)
        monkeypatch.setattr("urllib.request.Request", lambda *a, **k: type("R", (), {"full_url": "u"})())
        return gen._probe_status("https://huggingface.co/x/resolve/main/y.gguf")

    # Given the statuses a Hub link can answer with
    # When  each is probed
    # Then  only 404 is dead, and a gated file is reported as such
    assert answer(200) == gen.PROBE_OK
    assert answer(401) == gen.PROBE_GATED
    assert answer(403) == gen.PROBE_GATED
    assert answer(404) == gen.PROBE_DEAD


def test_a_gated_new_link_does_not_red_the_sync(monkeypatch, tmp_path, capsys):
    """The Meta gated file that failed run 39240829581 must not block the whole refresh."""
    # Given a committed table (A) and a refresh whose NEW link B is gated (401)
    _stub_generator(monkeypatch, [_A, _B])
    dst = tmp_path / "trending-quant-catalog.json"
    dst.write_text(json.dumps(_payload([_A]), indent=2) + "\n")
    monkeypatch.setattr(sys, "argv", ["gen_trending_quant_catalog.py", "-o", str(dst)])
    monkeypatch.setattr(gen, "_probe_status",
                        lambda u, timeout=20.0: gen.PROBE_OK if u != _B else gen.PROBE_GATED)

    # When the sync runs
    rc = gen.main()

    # Then it succeeds, writes the table, and says the link was gated (visible, not fatal)
    assert rc == 0
    assert _row_urls(dst.read_text()) == {_A, _B}
    out = capsys.readouterr()
    assert "gated=1" in out.out or "gated (exists" in out.out
