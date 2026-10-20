"""One Hub GET, one bounded transient budget (issue #339).

Drives the REAL `hf_auth.hub_open` — and the real pick stack on top of it
(`model_engine_pick._tree` -> `_hub_json` -> `_hub_open` -> `hub_open`) — against a REAL
loopback HTTP server. The retries are proved by the server's own request count, not by a
patched `urlopen`: a fake response object would pass even if the budget never ran.

The ladder is shrunk through the module's own env-tunable attributes
(`HUB_BASE_PAUSE`, `HUB_MAX_ATTEMPTS`) so the suite stays fast; production keeps 1.5s /
8 tries. No test is skipped: the server is started in-process on 127.0.0.1.
"""
from __future__ import annotations

import http.server
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import hf_auth  # noqa: E402
import model_engine_pick as mp  # noqa: E402


class _Scripted(http.server.BaseHTTPRequestHandler):
    """Answer `script` (a list of statuses) in order; the last one repeats."""

    script: list[int] = [200]
    calls = 0

    def do_GET(self):  # noqa: N802 (http.server's API)
        type(self).calls += 1
        code = self.script[min(type(self).calls - 1, len(self.script) - 1)]
        body = b"{}"
        if code == 200:
            body = json.dumps([{"path": "model.gguf", "type": "file", "size": 1}]).encode()
        self.send_response(code)
        if code == 429:
            self.send_header("RateLimit", '"api";r=0;t=1')
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the test output clean
        return


@pytest.fixture
def hub(monkeypatch):
    """A loopback Hub whose answers the test scripts; `(base_url, request_count)`."""
    servers = []

    def serve(script):
        _Scripted.script, _Scripted.calls = list(script), 0
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Scripted)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    # No real sleeping, and a 3-try budget so "bounded" is cheap to prove
    monkeypatch.setattr(hf_auth, "HUB_BASE_PAUSE", 0.0)
    monkeypatch.setattr(hf_auth, "HUB_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(hf_auth, "RATE_LIMIT_WAITS", 2)
    monkeypatch.setattr(hf_auth, "_rate_limited", 0)
    yield serve
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def test_hub_open_retries_a_503_then_reads_the_answer(hub):
    """A 5xx is transient: the SAME GET is retried until the Hub answers."""

    # Given a Hub that fails twice with 503, then answers 200
    base = hub([503, 503, 200])

    # When the real shared seam opens that URL
    req = urllib.request.Request(f"{base}/api/models/org/repo/tree/main")
    with hf_auth.hub_open(req) as r:
        body = r.read()

    # Then the answer was read, on the third request the server actually saw
    assert r.status == 200
    assert [f["path"] for f in json.loads(body)] == ["model.gguf"]
    assert _Scripted.calls == 3


def test_an_eternal_503_fails_loudly_on_the_bounded_budget(hub):
    """A sustained 5xx is bounded: the stated number of tries, then the status raises."""

    # Given a Hub that answers 503 forever, and a 3-try budget
    base = hub([503])

    # When the seam opens that URL
    with pytest.raises(urllib.error.HTTPError) as raised:
        hf_auth.hub_open(urllib.request.Request(f"{base}/api/models/org/repo/tree/main"))

    # Then it raised the status, after exactly the budget's requests
    assert raised.value.code == 503
    assert _Scripted.calls == 3


def test_a_definitive_status_is_not_retried(hub):
    """404 is an answer, not a blip: one request, straight out."""

    # Given a Hub that answers 404
    base = hub([404])

    # When the seam opens that URL
    with pytest.raises(urllib.error.HTTPError) as raised:
        hf_auth.hub_open(urllib.request.Request(f"{base}/api/models/org/absent/tree/main"))

    # Then no retry was made
    assert raised.value.code == 404
    assert _Scripted.calls == 1


def test_an_eternal_429_stops_after_the_stated_window_waits(hub, monkeypatch):
    """The rate limit waits the Hub's window, at most the stated number of times."""

    # Given a Hub that is rate-limited forever, and the waits recorded instead of slept
    base = hub([429])
    slept: list[int] = []
    monkeypatch.setattr(hf_auth.time, "sleep", lambda s: slept.append(s))

    # When the seam opens that URL
    with pytest.raises(urllib.error.HTTPError) as raised:
        hf_auth.hub_open(urllib.request.Request(f"{base}/api/models/org/repo/tree/main"))

    # Then it waited the window twice (t=1 each) and stopped: two waits, three requests
    assert raised.value.code == 429
    assert _Scripted.calls == 3
    assert slept == [1, 1]


def test_the_pick_tree_retries_a_503_instead_of_reporting_an_empty_repo(hub, monkeypatch):
    """The regression: one transient answer must not become 'this repo has no files'."""

    # Given the pick's Hub base pointed at a Hub that 503s once, then lists the file
    base = hub([503, 200])
    monkeypatch.setattr(mp, "HF", base)
    monkeypatch.setattr(mp, "_TREE_CACHE", {})

    # When the pick resolves that repo's tree
    files = mp._tree("org/repo")

    # Then it has the file, and it took the retry to get it
    assert [f["path"] for f in files] == ["model.gguf"]
    assert _Scripted.calls == 2


def test_the_pick_tree_does_not_cache_a_transient_failure(hub, monkeypatch):
    """A sustained throttle is not cached as an empty tree; the next call asks again."""

    # Given a Hub that 429s forever, and the pick's cache empty
    base = hub([429])
    monkeypatch.setattr(mp, "HF", base)
    monkeypatch.setattr(mp, "_TREE_CACHE", {})

    # When the tree is resolved twice
    first, second = mp._tree("org/repo"), mp._tree("org/repo")

    # Then both answers are empty, and BOTH asked the Hub: no poisoned cache entry.
    # The first call spends the whole budget (3 requests). The second still asks — it
    # is not served from a cached empty tree — but the shared consecutive-429 counter
    # is already spent, so its first answer raises: 1 more request, 4 in total.
    assert first == [] and second == []
    assert _Scripted.calls == 4, "the second call must reach the Hub, not a cached empty tree"
    assert mp._TREE_CACHE == {}, "a transient failure must not be cached as an empty repo"
