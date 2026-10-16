"""The shared live-Hub link probe (issue #256): retry, budget, and a legible cause.

The probe is the test-side liveness check for the links a pick hands a user, so its retry and its
failure message are behaviour a red `unit` lane depends on. Each case drives the REAL probe — the
real `urllib` client, the real `Request` the probe builds — against a REAL loopback HTTP server
that scripts the statuses the Hub answers. Nothing about the probe is stubbed: the server is the
external stand-in, its request log proves how many attempts were made and the sleeper records the
ladder actually waited.
"""
from __future__ import annotations

import contextlib
import http.server
import socket
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
import hub_probe  # noqa: E402


class _Hub(http.server.BaseHTTPRequestHandler):
    """A scripted Hub: answers `script[0]` per request (the last entry repeats)."""

    script: list[int] = [206]
    log: list[str] = []

    def do_GET(self):  # noqa: N802 (http.server's own spelling)
        type(self).log.append(self.headers.get("Range") or "")
        code = self.script[0] if len(self.script) == 1 else self.script.pop(0)
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 (http.server's own signature)
        pass  # keep the pytest output clean


@contextlib.contextmanager
def hub(script):
    """A real HTTP server on a loopback port, answering `script`; yields (url, request log)."""
    _Hub.script = list(script)
    _Hub.log = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Hub)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/model.gguf", _Hub.log
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _closed_port() -> int:
    """A port nothing listens on: bound, then released."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(autouse=True)
def _clean_breaker():
    """Each case starts with a clean outage count (the breaker is process-global)."""
    hub_probe.reset()
    yield
    hub_probe.reset()


def test_a_present_file_is_one_request_and_reports_the_status():
    """A served file costs one ranged GET and the answer carries the status."""
    waits: list[int] = []

    # Given a Hub that answers 206 to a ranged GET
    with hub([206]) as (url, log):

        # When  the shared probe verifies the link
        hit = hub_probe.probe(url, sleeper=waits.append)

    # Then  it exists, the status is in the answer, and nothing was retried
    assert hit.exists and hit.detail == "HTTP 206"
    assert hit.attempts == 1
    assert log == ["bytes=0-0"], "the probe must send the ranged GET, exactly once"
    assert waits == [], "a served file must not wait"


def test_a_missing_file_is_one_request_and_says_404():
    """A definitive answer is never retried, and its status is what the test prints."""
    waits: list[int] = []

    # Given a Hub that answers 404 (the file is genuinely absent)
    with hub([404]) as (url, log):

        # When  the shared probe verifies the link
        hit = hub_probe.probe(url, sleeper=waits.append)

    # Then  it is missing, the status is the answer, and it cost ONE request
    assert not hit.exists and hit.detail == "HTTP 404"
    assert hit.attempts == 1
    assert len(log) == 1, "a 404 must not be retried"
    assert waits == [], "a definitive answer must not spend the backoff budget"


def test_a_definitive_non_404_status_is_not_retried_and_reports_its_own_attempt_count():
    """A status the Hub answered with but that is not the served pair is definitive, not transient."""
    waits: list[int] = []

    # Given a Hub that answers 204 (answered, nothing to serve)
    with hub([204]) as (url, log):

        # When  the shared probe verifies the link
        hit = hub_probe.probe(url, sleeper=waits.append)

    # Then  it is one request, the answer names the status, and no backoff is claimed
    assert not hit.exists and hit.detail == "HTTP 204"
    assert hit.attempts == 1, "a definitive answer must not report the retry budget it never spent"
    assert len(log) == 1
    assert waits == []


def test_a_transient_5xx_is_retried_before_the_link_is_called_missing():
    """One Hub 503 must not redden a lane: the link verifies on the retry."""
    waits: list[int] = []

    # Given a Hub that answers 503 once and 206 afterwards
    with hub([503, 206]) as (url, log):

        # When  the shared probe verifies the link
        hit = hub_probe.probe(url, sleeper=waits.append)

    # Then  the retry served the file, and exactly one backoff step was waited
    assert hit.exists and hit.detail == "HTTP 206"
    assert hit.attempts == 2
    assert len(log) == 2
    assert waits == [1], "the first retry waits one second"


def test_a_sustained_5xx_stops_at_the_budget_and_reports_the_ladder():
    """A sustained Hub failure stops at the bounded budget, and names what it waited."""
    waits: list[int] = []

    # Given a Hub that answers 503 on every attempt
    with hub([503]) as (url, log):

        # When  the shared probe verifies the link
        hit = hub_probe.probe(url, sleeper=waits.append)

    # Then  it fails loudly with the status, the attempt count and the real ladder
    assert not hit.exists
    assert "HTTP 503" in hit.detail and "after 5 attempts" in hit.detail
    assert hit.attempts == 5
    assert len(log) == 5, "the attempts are bounded, never unbounded"
    assert waits == [1, 2, 4, 8], "the backoff ladder is bounded at ~15s"


def test_a_transport_failure_is_reported_as_the_transport_error():
    """A stalled/refused connection is NOT an absent file: the cause must differ."""
    port = _closed_port()

    # Given a port where nothing listens
    # When  the shared probe verifies a link on it
    hit = hub_probe.probe(f"http://127.0.0.1:{port}/model.gguf", sleeper=lambda _s: None)

    # Then  the answer names the transport error and never claims a missing file
    assert not hit.exists
    assert hit.detail.startswith(("URLError:", "OSError:", "TimeoutError:"))
    assert "HTTP" not in hit.detail, "a transport failure must not read as an HTTP status"


def test_the_outage_breaker_caps_the_attempts_after_the_limit():
    """A sustained outage cannot multiply the budget across thousands of links."""
    # Given a Hub that answers 503 forever and OUTAGE_LIMIT probes that spent the budget
    with hub([503]) as (url, log):

        # When  one more link is probed after the limit
        for _ in range(hub_probe.OUTAGE_LIMIT):
            hub_probe.probe(url, sleeper=lambda _s: None)
        spent = len(log)
        hit = hub_probe.probe(url, sleeper=lambda _s: None)

    # Then  the probe took one attempt, said the Hub is degraded, and still failed loudly
    assert hub_probe.OUTAGE_LIMIT * hub_probe.ATTEMPTS == spent
    assert len(log) == spent + 1, "a degraded Hub costs one attempt per link, not five"
    assert not hit.exists and hit.attempts == 1
    assert "degraded window" in hit.detail


def test_every_live_link_probe_in_the_suite_is_the_shared_one():
    """The copy-per-file shape #256 found must not come back."""
    # Given every committed test file (this one carries the search pattern itself)
    files = [p for p in sorted((REPO / "tests").glob("*.py")) if p.name != Path(__file__).name]

    # When  we look for a file carrying its own link probe
    copies = [p.name for p in files if "def _url_exists" in p.read_text()]

    # Then  none does, and both live-Hub suites call the shared one
    assert copies == [], f"these files carry their own probe again: {copies}"
    for name in ("test_pick_full_registry.py", "test_trending_quant_catalog.py"):
        src = (REPO / "tests" / name).read_text()
        assert "hub_probe.probe(" in src, f"{name} does not use the shared probe"
        assert "hub_probe" in src.split("def ", 1)[0], \
            f"{name} must import the shared probe at module level"
