#!/usr/bin/env python3
"""The orchestrator's STEP 2 recall now carries a shell fallback that must actually work (issue #2186).

Step 2 of the versioned procedure (`agents/llgenie-planner/skills/llgenie-bot-orchestration/
references/orchestrator-tick-contract.md`) names an agent tool when the turn has it and otherwise
falls back to a pinned `curl` to the hindsight daemon on **127.0.0.1:9177** — never the CLI's
default 8888. Measured 2026-11-08: a pass probed `http://localhost:8888`, nothing listened there,
and the run reported *"the API is down"* while the daemon was healthy on 9177 the whole time. The
two bugs compounded — a step naming an unavailable tool, and a substitute's default nobody chose.

These tests drive the REAL fallback against the live daemon the same way a tick turn would:

1. **Positive** — the fallback command returns a non-empty `results` array for a known failure
   class (`check-pr-acceptance write-back`). This is the memory the step exists to recall.
2. **Negative control** — with the port set to 8888 (the default that caused the false negative),
   the fallback FAILS **while** the 9177 `/health` probe SUCCEEDS, proving the check distinguishes
   a *wrong command* from a *dead daemon*. That is the exact misdiagnosis the issue fixes.

They need the live hindsight daemon on 127.0.0.1:9177, so the hermetic gate keeps the file out
(`tests/fixtures/unit-suite.json`, decision #2186) and `make test-recall-step` runs it on the tick
host where the daemon lives — a host without it FAILS LOUDLY (no skips anywhere in this repo, #1110).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

HOST = "127.0.0.1"
LIVE_PORT = 9177          # HINDSIGHT_API_PORT in $HOME/.hindsight/profiles/hermes.env
WRONG_PORT = 8888         # the CLI default that appears only commented-out in hermes.env
BANK = "llgenie-planner"  # the lane's own bank id, never a placeholder that 404s
KNOWN_CLASS = "check-pr-acceptance write-back"


def _post_json(path: str, port: int, payload: dict) -> dict:
    """POST a JSON body to a path and return the parsed response, or raise on any failure."""
    url = f"http://{HOST}:{port}{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(path: str, port: int, timeout: int = 3) -> dict | None:
    """GET a path; return parsed JSON, or None when nothing/not-hindsight answers."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _health_ok(port: int) -> bool:
    """True when the port serves the hindsight health payload (not merely *a* 200)."""
    data = _get("/health", port)
    return isinstance(data, dict) and data.get("status") == "healthy"


def _recall_ok(port: int) -> int:
    """Run the STEP 2 fallback on `port`; return the number of `results` (raises on failure)."""
    data = _post_json(
        f"/v1/default/banks/{BANK}/memories/recall",
        port,
        {"query": KNOWN_CLASS, "limit": 2},
    )
    results = data.get("results")
    assert isinstance(results, list), f"recall response has no 'results' list: {data!r:.200}"
    return len(results)


def test_recall_fallback_returns_nonempty_results() -> None:
    """The STEP 2 shell fallback answers and returns the known failure class from the lane's bank."""
    n = _recall_ok(LIVE_PORT)
    assert n >= 1, f"expected a non-empty results array, got {n}"


def test_wrong_port_fails_while_health_probe_succeeds() -> None:
    """Negative control: 9177/health succeeds while the 8888 fallback fails — a wrong COMMAND,
    not a dead daemon, is what a failed recall on a healthy subsystem means."""
    # The instrument is up — the premise the old 8888 misdiagnosis violated.
    assert _health_ok(LIVE_PORT), (
        f"the recall daemon is not answering on 127.0.0.1:{LIVE_PORT} — run "
        f"`systemctl --user start llgenie-hindsight` and retry; no skips are allowed (#1110)"
    )
    # The wrong default port carries neither the health payload nor the recall endpoint.
    assert not _health_ok(WRONG_PORT), "8888 must not serve a hindsight health payload"
    with pytest.raises(Exception):
        _recall_ok(WRONG_PORT)
    # Proof of the distinction the probe exists to make:
    assert _health_ok(LIVE_PORT) and not _health_ok(WRONG_PORT)
