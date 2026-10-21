#!/usr/bin/env python3
"""A bot leg's agent transcript is redacted before it prints, and only the redacted copy is published
(issue #359).

`make implement-issue` writes whatever the agent printed straight into the job log. GitHub masks the
secret values it registers, and that is a filter over the stream, not a property of the content — a
transformed one (URL-encoded, base64, a slice) sails past, and nothing is masked in a log a job
uploads itself. The Makefile's ONE `$(call scrubbed_run,…)` seam captures every public agent leg into
`$(HERMES_LOG)`, prints only the redactor's bounded tail, and writes `$(HERMES_LOG_SCRUBBED)` for the
run artifact. This suite proves, with SENTINEL values only:

* `scripts/scrub_log.py` redacts the raw value, its URL-encoded and base64 spellings, and the
  credential SHAPES it never had in its environment — and prints a COUNT, never a value;
* the missing input is loud (exit 2), so a stream that could not be read never reads as clean;
* the REAL macro, run through the real Makefile, keeps the sentinel out of the console while the
  scrubbed file exists and the command's own exit status survives;
* every public agent leg goes through that macro (a leg that prints raw would be the defect), and the
  bot workflows upload the REDACTED file — never the raw one.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "scrub_log.py"
WORKFLOWS = ROOT / ".github" / "workflows"
LOG = "hermes-run.log"
SCRUBBED = "hermes-run.scrubbed.log"

# secret-output: test value — a sentinel, never a credential.
SENTINEL = "SENTINELvalue0123456789abcdef"
#: The credential-shaped value that never enters the environment (a shape the redactor must catch).
SHAPED = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and k not in ("GH_TOKEN", "HF_TOKEN")}
    env.update(extra)
    return env


# ---------------------------------------------------------------------------
# the redactor itself
# ---------------------------------------------------------------------------
def test_every_spelling_of_a_value_is_redacted():
    import base64
    import sys
    import urllib.parse

    sys.path.insert(0, str(ROOT / "scripts"))
    import scrub_log

    # Given a log that contains the value raw, URL-encoded and base64, plus a credential shape
    spellings = [SENTINEL, urllib.parse.quote(SENTINEL, safe=""),
                 base64.b64encode(SENTINEL.encode()).decode()]
    text = "\n".join(f"line {i}: {s}" for i, s in enumerate(spellings)) + f"\nshaped {SHAPED}\nkept 'the name NOUS_API_KEY is fine'\n"

    # When  it is redacted with the value read from the environment BY NAME
    clean, count = scrub_log.redact(text, environ={"NOUS_API_KEY": SENTINEL})

    # Then  no spelling survives, the shape is gone, the name and the prose stay, and a count is returned
    for s in spellings:
        assert s not in clean, f"a spelling of the value survived: {s[:8]}…"
    assert SHAPED not in clean, "a credential shape survived"
    assert "NOUS_API_KEY" in clean and "line 0:" in clean, clean
    assert count >= len(spellings) + 1, count


def test_the_firecrawl_value_is_redacted_in_every_spelling():
    """Issue #379: FIRECRAWL_API_KEY is forwarded to the agent (#362) but was absent from
    SECRET_VARS, so the redactor masked it only when its generic SHAPE happened to match
    (`Bearer …`) and let it through raw, in a URL or in a JSON body."""

    import base64
    import sys
    import urllib.parse

    sys.path.insert(0, str(ROOT / "scripts"))
    import scrub_log

    # Given a Firecrawl-shaped value in the redactor's environment, raw, URL-encoded and base64
    value = "fc-" + "b" * 28
    spellings = [value, urllib.parse.quote(value, safe=""),
                 base64.b64encode(value.encode()).decode()]
    text = "\n".join(f"line {i}: {s}" for i, s in enumerate(spellings))

    # When  the stream is redacted
    clean, count = scrub_log.redact(text, environ={"FIRECRAWL_API_KEY": value})

    # Then  no spelling survives and the count reports what was replaced
    for s in spellings:
        assert s not in clean, f"a spelling of the Firecrawl value survived: {s[:8]}…"
    assert count >= len(spellings), count


def test_a_short_value_is_left_alone():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import scrub_log

    # Given a value too short to be a credential
    clean, count = scrub_log.redact("port 8080", environ={"NOUS_API_KEY": "8080"})

    # Then  the log is not shredded
    assert clean == "port 8080" and count == 0, (clean, count)


def test_a_missing_log_is_loud():
    # Given no captured log
    with tempfile.TemporaryDirectory() as d:
        missing = Path(d) / "nope.log"

        # When  the redactor runs on it
        r = subprocess.run(["python3", str(SCRIPT), "--in", str(missing)], capture_output=True, text=True)

    # Then  it exits 2 and says why — a stream that cannot be read never looks like a clean run
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "FATAL" in r.stderr and "no such log" in r.stderr, r.stderr


def test_the_cli_prints_only_a_bounded_tail():
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / LOG
        src.write_text("\n".join(f"line {i}" + (f" {SENTINEL}" if i == 3 else "") for i in range(200)))

        # When  the redactor prints a tail of 5 lines
        r = subprocess.run(["python3", str(SCRIPT), "--in", str(src), "--out", str(Path(d) / SCRUBBED),
                            "--tail", "5"], env=_clean_env(NOUS_API_KEY=SENTINEL),
                           capture_output=True, text=True)

    # Then  only the tail is printed, the sentinel is nowhere in the output, and it says how many
    assert r.returncode == 0, r.stderr
    assert SENTINEL not in r.stdout, "the value reached the console"
    assert r.stdout.count("[agent] line ") == 5, r.stdout
    assert "redaction(s)" in r.stdout and "earlier line(s) omitted" in r.stdout, r.stdout


def test_the_scrubbed_file_is_written_and_redacted():
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / LOG
        src.write_text(f"agent said {SENTINEL}\n")
        out = Path(d) / SCRUBBED

        # When  the redactor writes the redacted copy
        subprocess.run(["python3", str(SCRIPT), "--in", str(src), "--out", str(out), "--tail", "0"],
                       env=_clean_env(NOUS_API_KEY=SENTINEL), capture_output=True, text=True, check=True)

        # Then  the artifact exists, holds the marker, and holds no value
        text = out.read_text()
    assert "***" in text and SENTINEL not in text, text


# ---------------------------------------------------------------------------
# the REAL macro, through the real Makefile
# ---------------------------------------------------------------------------
def test_the_macro_redacts_the_stream_and_keeps_the_exit_status():
    """The seam itself: a fixture target that calls the macro exactly as the legs do."""

    # Given a fixture target whose command prints a sentinel and exits 3
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        fixture = f"""
_inject:
\t$(call scrubbed_run,printf '%s\\n' 'agent printed {SENTINEL}' >&2; exit 3)
"""
        env = _clean_env(NOUS_API_KEY=SENTINEL)

        # When  it runs through the REAL Makefile
        r = subprocess.run(["make", "-s", "--no-print-directory", "-f", "Makefile", "-f", "-", "_inject"],
                           cwd=ROOT, input=fixture, env=env, capture_output=True, text=True)
        scrubbed = ROOT / SCRUBBED
        scrubbed_text = scrubbed.read_text() if scrubbed.is_file() else ""
        if scrubbed.is_file():
            scrubbed.unlink()
        for name in (LOG, SCRUBBED):
            (ROOT / name).unlink(missing_ok=True)

    # Then  the sentinel is nowhere in the console, the REDACTED artifact has it masked,
    #       and the command's own exit status survived (make reports `Error 3`, and the run is red)
    assert SENTINEL not in (r.stdout + r.stderr), "the value reached the console"
    assert "***" in scrubbed_text and SENTINEL not in scrubbed_text, scrubbed_text
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert "Error 3" in r.stderr, "the command's own exit status did not survive the seam: " + r.stderr
    assert "redaction(s)" in r.stdout or "redaction(s)" in r.stderr, (r.stdout, r.stderr)


# ---------------------------------------------------------------------------
# the wiring: every public agent leg uses the macro, and only the redacted log is published
# ---------------------------------------------------------------------------
def _public_agent_legs() -> list[tuple[str, str]]:
    mk = (ROOT / "Makefile").read_text()
    legs = []
    for m in re.finditer(r"(?m)^([a-z0-9][a-z0-9._-]*):.*?$", mk):
        start = m.end()
        nxt = re.search(r"(?m)^[a-z0-9][a-z0-9._-]*:", mk[start:])
        body = mk[start:start + (nxt.start() if nxt else len(mk) - start)]
        if "$(AGENT_IMAGE)" in body:
            legs.append((m.group(1), body))
    return legs


def test_every_public_agent_leg_goes_through_the_macro():
    legs = _public_agent_legs()

    # Then every leg that starts the agent image prints through the ONE redaction seam
    assert legs, "no make target starts the agent image — the Makefile changed shape"
    for target, body in legs:
        assert "$(call scrubbed_run," in body, f"{target} prints the agent stream raw"


def test_the_internal_hermes_calls_are_inside_a_leg_that_redacts():
    mk = (ROOT / "Makefile").read_text()

    # Then the macro is defined ONCE, with the redactor and the gitignored paths
    assert "define scrubbed_run" in mk and mk.count("define scrubbed_run") == 1
    assert "python3 scripts/scrub_log.py --in $(HERMES_LOG) --out $(HERMES_LOG_SCRUBBED)" in mk
    assert "exit $$rc" in mk, "the macro must keep the command's exit status"

    # And every internal recipe that calls hermes is reached by a public leg that redacts
    bodies = {}
    for m in re.finditer(r"(?m)^([a-z0-9_][a-z0-9._-]*):.*?$", mk):
        start = m.end()
        nxt = re.search(r"(?m)^[a-z0-9_][a-z0-9._-]*:", mk[start:])
        bodies[m.group(1)] = mk[start:start + (nxt.start() if nxt else len(mk) - start)]
    hermes_inside = [name for name, body in bodies.items()
                     if "hermes -z" in body or "scripts/hermes_smoke.py" in body]
    for name in ("_rebase-bot-agent", "_issue-refiner", "_issue-bot-triage", "_implement-issue", "_hermes-smoke"):
        assert name in hermes_inside, f"{name} no longer runs hermes — the roster changed"

    # …and every one of them runs under a public leg that goes through the macro
    public = {t for t, _ in _public_agent_legs()}
    for name in hermes_inside:
        assert public, f"the public legs disappeared while {name} still calls hermes"


def test_the_workflows_publish_only_the_redacted_log():
    for workflow in ("fix-bot.yml", "issue-bot.yml", "issue-refiner.yml", "rebase-bot.yml"):
        text = (WORKFLOWS / workflow).read_text()

        # Then each bot job uploads the REDACTED log …
        assert SCRUBBED in text, f"{workflow} publishes no redacted transcript"
        assert re.search(rf"(?m)^\s+name: .*redacted", text, re.I), f"{workflow}: the artifact is not named for what it is"

        # … and never the raw one (which holds the unredacted stream by construction)
        for line in text.splitlines():
            assert not re.search(rf"path:.*(?<!scrubbed\.){re.escape(LOG)}\b(?!\.scrubbed)", line), \
                f"{workflow} uploads the RAW log: {line}"
