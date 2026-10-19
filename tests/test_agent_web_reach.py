#!/usr/bin/env python3
"""The agent has a masked web reach, and a dead key fails in seconds (issue #362).

The Hermes CLI ships a bundled `browser-firecrawl` plugin keyed by `FIRECRAWL_API_KEY`, so the
capability is in the agent image; what was missing is a sanctioned way to use it with the key never
printed, and a smoke that dies loudly instead of returning an empty result. This suite proves:

* the key is in the Makefile's ONE `AGENT_SHELL_KEYS` list, so `agent-shell-keys-check` proves the
  AGENT's shell can see it (Hermes strips provider credentials from its terminal tool);
* one leg (`make agent-fetch`) carries it BY NAME, and its prompt reads the value from the
  environment and forbids printing it;
* `scripts/fetch_smoke.py` drives the REAL HTTP client against a local server: 401 is loud with the
  code, HTTP 200 with an empty body is a failure (not "no results"), a real body is success — and
  the key's value appears in no output;
* the wiring: the smoke is a make target, and the bot jobs run it.

NO-SKIP POLICY: the HTTP cases run against a local server the test provides (an external system the
test controls, driven by the real client — never a stub of the code under test).
"""
from __future__ import annotations

import http.server
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SMOKE = REPO / "scripts" / "fetch_smoke.py"
WORKFLOWS = REPO / ".github" / "workflows"

# secret-output: test value — a sentinel, never a credential.
SENTINEL = "SENTINELfirecrawl0123456789"
FORCE = "_HERMES_FORCE_"


def _clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(FORCE) and k not in ("FIRECRAWL_API_KEY", "NOUS_API_KEY", "GH_TOKEN", "HF_TOKEN")}
    env.update(extra)
    return env


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200
    body = b'{"data":{"markdown":"hello from the local scrape"}}'

    def do_POST(self):  # noqa: N802 — the stdlib's name
        self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *a):  # keep the test output clean
        pass


def _serve(handler_cls) -> tuple[str, http.server.ThreadingHTTPServer]:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_port}/v1/scrape", srv


def _smoke(env: dict, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(SMOKE), *args], env=env, capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------------------
# the key: one list, forwarded by name
# ---------------------------------------------------------------------------
def test_firecrawl_is_in_the_one_agent_shell_list():
    mk = (REPO / "Makefile").read_text()

    # Then the key the fetch leg uses travels through the seam #358 built
    line = next(l for l in mk.splitlines() if l.startswith("AGENT_SHELL_KEYS"))
    assert "FIRECRAWL_API_KEY" in line, line

    # And the fetch leg forwards names only (a value never appears on a command line)
    env = _clean_env(FIRECRAWL_API_KEY=SENTINEL, IN_CONTAINER="")
    r = subprocess.run(["make", "-n", "--no-print-directory", "agent-fetch", "URL=https://example.com",
                        "IN_CONTAINER="], cwd=REPO, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert f"-e {FORCE}FIRECRAWL_API_KEY" in out, out[-400:]
    assert SENTINEL not in out, "the key value reached a command line"


def test_the_fetch_prompt_reads_the_key_by_name_and_forbids_printing_it():
    mk = (REPO / "Makefile").read_text()
    recipe = next(l for l in mk.splitlines() if l.lstrip().startswith("hermes -z") and "Firecrawl" in l)

    # Then the prompt names the VARIABLE (never a value) and states the no-print rule
    assert "$$FIRECRAWL_API_KEY" in recipe, recipe[:300]
    assert "never print, echo, write or copy the value" in recipe
    # And one leg only: no second prompt hand-rolls the fetch
    assert mk.count("api.firecrawl.dev") == 1


def test_the_leg_is_a_make_target_and_the_smoke_is_reachable():
    mk = (REPO / "Makefile").read_text()

    assert re.search(r"(?m)^agent-fetch:", mk) and re.search(r"(?m)^_agent-fetch:", mk)
    assert re.search(r"(?m)^search-smoke:", mk)
    assert "python3 scripts/fetch_smoke.py" in mk


# ---------------------------------------------------------------------------
# the smoke: real client, local server
# ---------------------------------------------------------------------------
def test_a_missing_key_is_loud_and_names_the_variable():
    # Given no key in the container
    r = _smoke(_clean_env())

    # Then  it exits 2, names the variable, and prints no value
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "FIRECRAWL_API_KEY" in r.stderr and "FATAL" in r.stderr, r.stderr


def test_the_opt_out_says_nothing_was_verified():
    r = _smoke(_clean_env(), "--allow-unconfigured")
    assert r.returncode == 0 and "NOT CONFIGURED" in r.stdout, (r.returncode, r.stdout)
    for f in WORKFLOWS.glob("*.yml"):
        for line in f.read_text().splitlines():
            assert not ("fetch-smoke" in line and "allow-unconfigured" in line), f"{f.name}: opt-out in CI"


def test_a_dead_key_fails_with_the_code_and_no_empty_success():
    # Given an endpoint that answers 401 for the key
    handler = type("_Unauthorized", (_Handler,), {"status": 401, "body": b'{"error":"bad key"}'})
    api, srv = _serve(handler)
    try:
        # When  the smoke runs with a key set
        r = _smoke(_clean_env(FIRECRAWL_API_KEY=SENTINEL), "--api", api)
    finally:
        srv.shutdown()

    # Then  it fails, names HTTP 401, and never prints the key
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "HTTP 401" in r.stderr, r.stderr
    assert SENTINEL not in (r.stdout + r.stderr), "the key value was printed"


def test_an_empty_body_is_not_healthy():
    handler = type("_Empty", (_Handler,), {"status": 200, "body": b"{}"})
    api, srv = _serve(handler)
    try:
        r = _smoke(_clean_env(FIRECRAWL_API_KEY=SENTINEL), "--api", api)
    finally:
        srv.shutdown()

    # Then  a 200 with nothing in it is refused — a fetch leg must not report success on nothing
    assert r.returncode == 1 and "EMPTY body" in r.stderr, (r.returncode, r.stderr)
    assert SENTINEL not in (r.stdout + r.stderr)


def test_a_real_body_is_success_and_the_key_is_never_shown():
    api, srv = _serve(_Handler)
    try:
        r = _smoke(_clean_env(FIRECRAWL_API_KEY=SENTINEL), "--api", api, "--budget", "2000")
    finally:
        srv.shutdown()

    # Then  it reports the status and a bounded excerpt, and the value appears nowhere
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "HTTP 200" in r.stdout and "hello from the local scrape" in r.stdout, r.stdout
    assert "never printed" in r.stdout
    assert SENTINEL not in (r.stdout + r.stderr), "the key value was printed"


def test_the_budget_bounds_what_is_read():
    big = b'{"data":{"markdown":"' + b"x" * 5000 + b'"}}'
    handler = type("_Big", (_Handler,), {"status": 200, "body": big})
    api, srv = _serve(handler)
    try:
        r = _smoke(_clean_env(FIRECRAWL_API_KEY=SENTINEL), "--api", api, "--budget", "100")
    finally:
        srv.shutdown()

    # Then  the read is bounded by the budget (the reply is not drained into memory or the log)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    m = re.search(r"(\d+) markdown char\(s\) \(budget 100\)", r.stdout)
    assert m and int(m.group(1)) <= 101, r.stdout
