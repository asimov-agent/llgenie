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
    """The fetch contract is the `agent-fetch` skill, which the leg preloads (issue #577)."""

    mk = (REPO / "Makefile").read_text()
    recipe = next(l for l in mk.splitlines() if l.lstrip().startswith("hermes -z")
                  and "-s agent-fetch" in l)
    skill = (REPO / ".hermes" / "skills" / "agent-fetch" / "SKILL.md").read_text()

    # Then the leg preloads the skill, which names the VARIABLE (never a value) and forbids printing
    assert "-s agent-fetch" in recipe, recipe[:300]
    assert "FIRECRAWL_API_KEY" in skill
    assert "never appears anywhere" in skill or "never print" in skill.lower()
    # And one place only: the API shape lives in the skill, in no recipe
    assert mk.count("api.firecrawl.dev") == 0
    assert skill.count("api.firecrawl.dev") == 1


def test_the_leg_is_a_make_target_and_the_smoke_is_reachable():
    mk = (REPO / "Makefile").read_text()

    assert re.search(r"(?m)^agent-fetch:", mk) and re.search(r"(?m)^_agent-fetch:", mk)
    assert re.search(r"(?m)^search-smoke:", mk)
    assert "python3 scripts/fetch_smoke.py" in mk


# ---------------------------------------------------------------------------
# the deployment (issue #381): the smoke runs on the repository secret
# ---------------------------------------------------------------------------
def test_the_smoke_runs_in_a_monitored_job_on_the_repository_secret():
    """A leg nobody schedules is not a check: the smoke runs daily, on the secret, by NAME."""

    # Given the workflow that runs the smoke
    text = (WORKFLOWS / "search-smoke.yml").read_text()

    # When  it is read
    # Then  it is scheduled on its own slot and dispatchable, and it declares its trigger surface
    assert re.search(r'(?m)^\s*- cron: "11 7 \* \* \*"', text), text[:400]
    assert "workflow_dispatch:" in text
    for key in ("# Trigger surface:", "# Flow:", "# Never:"):
        assert key in text, f"{key} missing from the header block"

    # And the key arrives by NAME, never as a value on a command line or in a run block
    assert "FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}" in text, text[:400]
    assert "secrets.FIRECRAWL_API_KEY }}" in text
    assert not re.search(r"-e\s+FIRECRAWL_API_KEY=", text), "the key travels as a value, not a name"
    assert not re.search(r"FIRECRAWL_API_KEY=\$", text), "the key is interpolated into the workflow"

    # And the agent's own shell is proven to see it BEFORE the smoke spends it
    assert "make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY" in text
    assert "make search-smoke" in text
    assert text.index("run: make agent-shell-keys-check") < text.index("run: make search-smoke")


def test_the_host_only_exception_for_the_smoke_is_gone():
    """check-wiring fails a recorded exception CI reaches, so the record is the proof of the wiring."""

    import json

    # Given the dated host-only decisions
    data = json.loads((REPO / "tests" / "fixtures" / "host-only-wiring.json").read_text())

    # Then no entry claims the smoke is human-run any more, and the workflow it names exists
    assert "search-smoke" not in (data.get("targets") or {}), data.get("targets")
    assert (WORKFLOWS / "search-smoke.yml").exists()


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


# ---------------------------------------------------------------------------
# the reach DEPLOYED (issue #380): a bot leg pre-fetches, and the legs' URLs are checked
# ---------------------------------------------------------------------------
def test_a_bot_leg_reaches_agent_fetch():
    """#362 shipped the leg and no bot called it, so the reach was unreachable from a run. The
    assertion is DERIVED from the workflow files and the Makefile's call graph — never a hand list."""

    import check_wiring as cw

    # Given the wiring graph of the real tree
    g = cw.graph(REPO)

    # When  the targets the CI workflows call are closed over the Makefile's own call graph
    seen, frontier = set(g["ci_targets"]), set(g["ci_targets"])
    while frontier:
        frontier = {c for t in frontier for c in g["calls"].get(t, set())} - seen
        seen |= frontier

    # Then  the fetch leg is REACHED by a job, not merely declared ...
    assert "agent-fetch" in seen, (
        "no CI-reached target calls `make agent-fetch` — the masked web reach is unreachable from a "
        f"run again (issue #380). Reached: {sorted(seen)}")

    # ... through the bot leg that pre-fetches evidence, and that leg is itself reached
    assert "issue-evidence" in seen, "the pre-fetch leg is not reached by CI"
    assert "issue-refiner" in g["workflow_targets"].get("issue-refiner.yml", set()), \
        "the refiner leg is not the consumer the workflow runs"


def test_the_bot_leg_forwards_the_key_by_name_and_gates_first():
    """The leg's first gate proves the AGENT's shell sees the key (#358), and the key travels as a
    NAME — a leg that spends a fetch without that gate is green while doing nothing."""

    mk = (REPO / "Makefile").read_text()
    refiner = mk.split("\nissue-refiner:", 1)[1].split("\n\n", 1)[0]

    # Then the credential is proven visible before anything is fetched ...
    assert "agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY" in refiner, refiner
    assert refiner.index("agent-shell-keys-check") < refiner.index("issue-evidence"), \
        "the fetch leg runs before its credential is proven visible"

    # ... and the workflow forwards the key by NAME only
    wf = (WORKFLOWS / "issue-refiner.yml").read_text()
    assert "FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}" in wf, "the job never sets the key"
    assert "FIRECRAWL_API_KEY" in wf.split("run: make agent-shell-keys-check", 1)[1][:200], \
        "the job's keys check does not cover the new credential"
    assert not re.search(r"-e\s+FIRECRAWL_API_KEY=", wf), "the key travels as a value, not a name"


def test_the_candidates_are_extracted_from_prose():
    """An issue names URLs inside prose; the extractor must find them and drop the noise."""

    import web_evidence as we

    # Given prose that wraps URLs in punctuation and repeats one
    text = ("see https://github.com/ggml-org/llama.cpp, and (https://huggingface.co/models). "
            "again https://github.com/ggml-org/llama.cpp#readme and a dead loop "
            "http://localhost:8080/x .")

    # When  the candidates are extracted
    got = we.candidates(text)

    # Then  each URL appears once, without its trailing punctuation or fragment, and loopback is gone
    assert got == ["https://github.com/ggml-org/llama.cpp", "https://huggingface.co/models"], got


def test_a_dead_url_is_reported_and_fails_the_coverage_check():
    """`make web-coverage` must be loud on a dead link — it is the URL a bot run depends on."""

    import web_evidence as we

    # Given a real server that 404s one path and serves another
    class _H(_Handler):
        def do_GET(self):  # noqa: N802 — the stdlib's name
            self.send_response(200 if self.path.endswith("/ok") else 404)
            self.end_headers()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"

    try:
        # When  both are checked (the real client, a real server)
        rows, dead = we.check([f"{base}/ok", f"{base}/gone"], timeout=10)
    finally:
        srv.shutdown()
        srv.server_close()

    # Then  the dead one is counted and its status is visible
    assert [s for _, s in rows] == [200, 404], rows
    assert dead == 1, rows


def test_the_coverage_fixture_names_urls_and_gated_urls_are_not_dead():
    """The fixture is the declared dependency list, and a credential-gated URL is reachable, not dead."""

    import web_evidence as we

    # Given the checked-in fixture, and a real server that refuses with 403
    urls = we.candidates((REPO / "tests" / "fixtures" / "bot-facing-urls.md").read_text())

    class _Gated(_Handler):
        def do_GET(self):  # noqa: N802 — the stdlib's name
            self.send_response(403)
            self.end_headers()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Gated)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        # When  the fixture and the gated URL are checked
        rows, dead = we.check([f"http://127.0.0.1:{srv.server_port}/gated"], timeout=10)
    finally:
        srv.shutdown()
        srv.server_close()

    # Then  the fixture names real destinations ...
    assert len(urls) >= 3, urls
    assert all(u.startswith("https://") for u in urls), urls

    # ... and a 403 is REACHABLE (the resource exists; the bot simply has no credential for it)
    assert rows == [(f"http://127.0.0.1:{srv.server_port}/gated", 403)], rows
    assert dead == 0, rows
    assert we.is_dead(403) is False and we.is_dead(401) is False
    # ... while a 404, a 500 and a failed read ARE dead
    assert we.is_dead(404) is True and we.is_dead(500) is True
    assert we.is_dead("TimeoutError") is True
    assert we.is_dead(200) is False and we.is_dead(302) is False
