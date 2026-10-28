"""A plan the live search stops returning is churn, not a failure — but a dead plan still is (#769).

`make check-quant-catalog` is the one gate every PR runs, and it went red on `main` `ea80ab4` for a
reason no PR caused: the generator reads the table from a SEARCH (`sort=downloads`), so once a page
moved, six `SolsticeAI/Nanbeige4.3-33B-mlx-*` plans (HTTP 401, gated) and one still-public plan
(`ToPo-ToPo/Ornith-1.5-35B-A3B-mlx-4bit`, HTTP 200) stopped being generated and `compare()` called
each of them a failure. The only way out was a data commit on a feature branch — and the sync that
produced it DROPPED the still-downloadable plan.

The rule this file locks, through the real `compare()`/`carry_over()` and the real `_probe_status()`:

  * a committed plan the generation dropped whose link still answers (200, or 401/403 gated) is a
    NOTE: kept, and the check exits 0;
  * a committed plan whose link answers 404/410 is a FAILURE: nothing serves it, so dropping it is
    the correct action and the catalog is stale;
  * a sync carries the reachable one over and prints why, and leaves the dead one out.

**No mocks.** `_probe_status()` performs a real ranged GET over a real socket against a real
`http.server` on loopback, which answers 200 / 401 / 404; the classifier under test is the production
one, and `compare()`/`carry_over()` are the functions `make check-quant-catalog` and
`make sync-quant-catalog` call. Hermetic in the only sense that matters here: it never reaches the
live Hub, so it cannot join the suite's network-dependent exclusions.
"""
from __future__ import annotations

import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import gen_trending_quant_catalog as gen  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    """A real HTTP server: /ok answers 200, /gated 401, /dead 404 — the Hub's three answers."""

    def do_GET(self):  # noqa: N802 — the stdlib's name
        if self.path.startswith("/ok"):
            self.send_response(200)
            self.send_header("Content-Length", "1")
            self.end_headers()
            self.wfile.write(b"x")
        elif self.path.startswith("/gated"):
            self.send_error(401, "gated")
        else:
            self.send_error(404, "not found")

    def log_message(self, *args):  # keep the test output clean
        pass


@pytest.fixture()
def server():
    """A live loopback server, so `_probe_status()` runs against real sockets, not a stub."""
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _row(url: str, repo: str) -> dict:
    return {"repo": repo, "revision": "main", "path": url.rsplit("/", 1)[-1],
            "files": [url.rsplit("/", 1)[-1]], "size_gb": 4.0, "url": url}


def _catalog(urls: dict[str, str], *, utc: str = "2026-10-28T00:00:00Z") -> dict:
    """`{repo-name: url}` -> a catalog payload with one (model, engine) cell holding those plans."""
    return {"meta": {"generated_utc": utc},
            "files": {"solstice-33b": {"mlx": {"arch": ["metal"],
                                              "quants": [_row(u, r) for r, u in urls.items()]}}}}


def _probe(url: str) -> str:
    """The production classifier, unpatched."""
    return gen._probe_status(url, timeout=10.0)


def test_a_plan_the_search_dropped_but_the_repo_still_serves_is_a_note_not_a_failure(server):
    """Acceptance 1: a committed plan the live search no longer returns, whose repo answers 200."""

    # Given a committed plan the fresh generation dropped while its link still answers 200
    committed = _catalog({"ToPo-ToPo/Ornith": f"{server}/ok/ornith.gguf",
                          "unsloth/live": f"{server}/ok/live.gguf"})
    generated = _catalog({"unsloth/live": f"{server}/ok/live.gguf"})
    assert _probe(f"{server}/ok/ornith.gguf") == gen.PROBE_OK

    # When  compare() runs — the function `make check-quant-catalog` calls, with the real probe
    failures, notes = gen.compare(committed, generated)

    # Then  nothing fails, and the note says the plan is reachable and kept
    assert failures == []
    assert any("ornith.gguf" in n and "still reachable (ok)" in n for n in notes), notes
    assert any("kept, not a failure" in n for n in notes), notes


def test_a_gated_plan_the_search_dropped_is_also_kept(server):
    """401/403 means the file exists and this token may not read it — reachable, never dead (#418)."""

    # Given a committed plan whose repo now answers 401
    committed = _catalog({"SolsticeAI/Nanbeige4.3-33B-mlx-4bit": f"{server}/gated/nanbeige.gguf",
                          "unsloth/live": f"{server}/ok/live.gguf"})
    generated = _catalog({"unsloth/live": f"{server}/ok/live.gguf"})
    assert _probe(f"{server}/gated/nanbeige.gguf") == gen.PROBE_GATED

    # When  compare() runs
    failures, notes = gen.compare(committed, generated)

    # Then  it is a note naming the gated status, not a failure
    assert failures == []
    assert any("still reachable (gated)" in n for n in notes), notes


def test_a_plan_whose_repo_answers_404_is_still_a_failure(server):
    """Acceptance 2: the gate must not be weakened into "whatever the search dropped is fine"."""

    # Given a committed plan whose repository is gone
    committed = _catalog({"dead/repo": f"{server}/dead/gone.gguf",
                          "unsloth/live": f"{server}/ok/live.gguf"})
    generated = _catalog({"unsloth/live": f"{server}/ok/live.gguf"})
    assert _probe(f"{server}/dead/gone.gguf") == gen.PROBE_DEAD

    # When  compare() runs
    failures, notes = gen.compare(committed, generated)

    # Then  the gate is red, and the line says why the plan may be dropped
    assert len(failures) == 1, failures
    assert "gone.gguf" in failures[0] and "404/410" in failures[0]
    assert not any("gone.gguf" in n for n in notes), notes


def test_the_sync_carries_the_reachable_plan_over_and_leaves_the_dead_one_out(server):
    """Acceptance 3: `make sync-quant-catalog` keeps a still-reachable plan and prints why."""

    # Given a committed table with one reachable and one dead plan the generation dropped
    committed = _catalog({"ToPo-ToPo/Ornith": f"{server}/ok/ornith.gguf",
                          "dead/repo": f"{server}/dead/gone.gguf",
                          "unsloth/live": f"{server}/ok/live.gguf"})
    generated = _catalog({"unsloth/live": f"{server}/ok/live.gguf"})

    # When  the sync's carry-over runs
    payload, kept, dropped = gen.carry_over(committed, generated)

    # Then  the reachable plan is back in its own cell, the dead one is not, and both are reported
    urls = {q["url"] for q in payload["files"]["solstice-33b"]["mlx"]["quants"]}
    assert f"{server}/ok/ornith.gguf" in urls
    assert f"{server}/dead/gone.gguf" not in urls
    assert f"{server}/ok/live.gguf" in urls
    assert any("ornith.gguf" in line and "still reachable: ok" in line for line in kept), kept
    assert any("gone.gguf" in line and "404/410" in line for line in dropped), dropped

    # And the carried-over table passes the gate it was written for
    failures, _ = gen.compare(payload, generated)
    assert failures == [], failures


def test_a_clean_catalog_costs_no_probe(server):
    """The gate probes only what a generation DROPPED: an unchanged table makes no request."""

    # Given a committed table identical to the generation, and a probe that must not be called
    committed = _catalog({"unsloth/live": f"{server}/ok/live.gguf"})
    calls: list[str] = []

    def counted(url, timeout=20.0):
        calls.append(url)
        return gen.PROBE_OK

    # When  compare() runs
    failures, notes = gen.compare(committed, committed, probe=counted)

    # Then  it is green, silent, and probed nothing
    assert (failures, notes, calls) == ([], [], [])


def test_the_committed_catalog_the_gate_reads_is_a_real_table():
    """The payload shape this file builds is the committed one's: a drift here would hide a break."""

    catalog = json.loads((REPO / "data" / "trending-quant-catalog.json").read_text())
    assert set(catalog) == {"meta", "files"}
    assert set(catalog["meta"]) >= {"generated_utc"}
    model = next(iter(catalog["files"].values()))
    cell = next(iter(model.values()))
    assert set(cell) >= {"arch", "quants"}
    assert set(cell["quants"][0]) >= {"repo", "revision", "path", "files", "size_gb", "url"}
