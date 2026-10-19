#!/usr/bin/env python3
"""Redact a captured agent log before any of it reaches a bot job's console.

A bot's agent stream IS the job's console output: `make implement-issue` writes whatever the
agent printed straight into the step log. GitHub masks the secret values it *registers*, and
that is a filter over the stream, not a property of the content — a value that is transformed
(URL-encoded, base64, a slice) sails past it. Nothing bounded how much of the stream was
printed either.

So the stream is captured to a file and this redactor is the only thing that prints:

* every secret VALUE present in the environment is read **by name** (the names live in ONE
  place — `scripts/check_secret_output.py::SECRET_VARS`) and every spelling of it is replaced
  with `***`: the raw value, its URL-encoded form and its base64 form;
* credential SHAPES (`ghp_…`, `github_pat_…`, `hf_…`, `sk-…`, a `Bearer <token>` header) are
  redacted too, so a token that reached the log without ever being in this process's
  environment is caught as well;
* the printed part is bounded to a tail (`--tail N`, default 60) and the REDACTED whole log is
  written to `--out` for the run artifact — the raw file is never uploaded and never printed.

The script never prints a value: it prints the redacted lines and a redaction COUNT. A missing
input is loud (exit 2) rather than an empty log that reads as a clean run.

Usage:
    python3 scripts/scrub_log.py --in hermes-run.log --out hermes-run.scrubbed.log --tail 60
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
#: ONE list of the variables that carry a credential — never a second copy.
from check_secret_output import SECRET_VARS  # noqa: E402

#: What replaces a redacted span. A fixed marker, so the output is greppable and the same in
#: every spelling — never a hint of the value (no first/last characters, no length).
MASK = "***"

#: A value shorter than this is not redacted: replacing a 1–3 character value would shred the
#: log without hiding anything. Real credentials in this repo are far longer.
MIN_VALUE_LEN = 8

#: Credential SHAPES, for a value that never entered this process's environment.
SHAPE_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bev_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{16,}"),
)


def spellings(value: str) -> set[str]:
    """Every form of one secret value that could reach a log.

    A value can arrive as itself, URL-encoded (it travelled in a query string or a header) or
    base64 (it was put in a JSON body by hand). All three are the same secret.
    """
    forms = {value}
    forms.add(urllib.parse.quote(value, safe=""))
    forms.add(urllib.parse.quote_plus(value))
    try:
        forms.add(base64.b64encode(value.encode()).decode())
        forms.add(base64.urlsafe_b64encode(value.encode()).decode())
    except Exception:  # pragma: no cover - encode() of a str cannot really fail
        pass
    return {f for f in forms if len(f) >= MIN_VALUE_LEN}


def environment_values(environ: dict[str, str] | None = None) -> dict[str, str]:
    """The secret values present in the environment, keyed by the spelling to replace."""
    env = os.environ if environ is None else environ
    found: dict[str, str] = {}
    for name in SECRET_VARS:
        value = env.get(name)
        if not value:
            continue
        for form in spellings(value):
            if len(form) >= MIN_VALUE_LEN:
                found[form] = name
    return found


def redact(text: str, environ: dict[str, str] | None = None) -> tuple[str, int]:
    """Return `(redacted_text, redaction_count)`. Never returns or prints a value."""
    values = environment_values(environ)
    count = 0
    # Longest first: a value that is a substring of another form must not be replaced first and
    # leave a fragment of the longer one behind.
    for form in sorted(values, key=len, reverse=True):
        hits = text.count(form)
        if hits:
            text = text.replace(form, MASK)
            count += hits
    for pattern in SHAPE_PATTERNS:
        text, hits = pattern.subn(MASK, text)
        count += hits
    return text, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Redact a captured agent log and print a bounded tail.")
    parser.add_argument("--in", dest="src", required=True, help="the captured log to redact")
    parser.add_argument("--out", dest="dst", default=None,
                        help="write the REDACTED whole log here (the run artifact)")
    parser.add_argument("--tail", type=int, default=60, help="how many of the last lines to print (default 60)")
    args = parser.parse_args(argv)

    src = Path(args.src)
    if not src.is_file():
        print(f"[scrub-log] FATAL: no such log to redact: {src} — a captured stream that cannot be "
              f"read must never look like a clean run.", file=sys.stderr)
        return 2

    raw = src.read_text(errors="replace")
    clean, count = redact(raw)

    if args.dst:
        Path(args.dst).write_text(clean)

    lines = clean.splitlines()
    tail = lines[-args.tail:] if args.tail > 0 else []
    print(f"[scrub-log] {src}: {len(lines)} line(s), {count} redaction(s); "
          f"printing the last {len(tail)} line(s) — redacted, never raw.")
    for line in tail:
        print(f"[agent] {line}")
    if len(lines) > len(tail):
        print(f"[agent] … {len(lines) - len(tail)} earlier line(s) omitted "
              f"(the full REDACTED log is the run artifact: {args.dst or 'not written'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
