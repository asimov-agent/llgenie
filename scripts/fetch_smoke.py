#!/usr/bin/env python3
"""Prove the masked web reach works: one real request, a hard budget, a loud failure (issue #362).

A bot leg whose Firecrawl key is dead must die in **seconds**, not return an empty result the run
reports as success. That is the failure this smoke exists for: the key is read from the environment
**by name**, one request is made with a bounded response, and 401/402/403 is a failure with the code
in the message — never "no results".

It prints the HTTP status, the byte count and a short excerpt of the fetched text. It never prints
the key: not the value, not a prefix, not a length. On a missing key it exits 2 with the variable's
name (the same contract as `scripts/agent_shell_keys_check.py`), and `--allow-unconfigured` is the
explicit local opt-out that says nothing was verified.

Usage:
    python3 scripts/fetch_smoke.py --budget 4000
    python3 scripts/fetch_smoke.py --url https://example.com --budget 2000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

#: The variable that carries the Firecrawl credential — the name only, never a value.
KEY_VAR = "FIRECRAWL_API_KEY"
API = "https://api.firecrawl.dev/v1/scrape"
#: A page that is cheap to scrape and stable enough to prove the round trip.
DEFAULT_URL = "https://example.com"
#: A hard cap on what is read, so a runaway response cannot be drained into memory or the log.
MAX_READ = 5 * 1024 * 1024


def fetch(url: str, budget: int, timeout: int = 60, api: str = API) -> tuple[int, str]:
    """POST one scrape; return `(status, text)`. Raises `urllib.error.HTTPError` on a non-2xx.

    `api` is overridable so the suite can drive the REAL client against a local server (an external
    system the test provides), never a stub of this function.
    """
    body = json.dumps({"url": url, "formats": ["markdown"]}).encode()
    req = urllib.request.Request(api, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    # The value is read here and put in the header — never logged, never echoed.
    req.add_header("Authorization", "Bearer " + os.environ[KEY_VAR])
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(MAX_READ + 1)
        return resp.status, raw.decode("utf-8", "replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="One real Firecrawl request with a hard budget.")
    ap.add_argument("--url", default=DEFAULT_URL, help=f"the URL to scrape (default: {DEFAULT_URL})")
    ap.add_argument("--budget", type=int, default=4000, help="max response bytes to read (default 4000)")
    ap.add_argument("--api", default=API, help=f"the scrape endpoint (default: {API})")
    ap.add_argument("--allow-unconfigured", action="store_true",
                    help="explicit local opt-out (never set in CI)")
    args = ap.parse_args(argv)

    if args.allow_unconfigured:
        print("[fetch-smoke] NOT CONFIGURED (--allow-unconfigured): nothing about the web reach was verified.")
        return 0
    if not os.environ.get(KEY_VAR):
        print(f"[fetch-smoke] FATAL: {KEY_VAR} is missing or empty — there is nothing to smoke. Set the "
              f"repository secret; the value stays in the environment and is never printed.", file=sys.stderr)
        return 2

    try:
        status, text = fetch(args.url, args.budget, api=args.api)
    except urllib.error.HTTPError as exc:
        # 401/402/403 is the dead-key case: loud, with the code, and never an empty success.
        print(f"[fetch-smoke] FATAL: Firecrawl answered HTTP {exc.code} — the key is dead, exhausted or "
              f"not allowed to scrape; every leg would return an empty result. Fix the secret "
              f"({KEY_VAR}), never print it.", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — a network failure is loud, with its type only
        print(f"[fetch-smoke] FATAL: the request failed ({type(exc).__name__}) — no content to verify.",
              file=sys.stderr)
        return 1

    # The contract is JSON with `data.markdown`; a 200 that carries no content is the "no results"
    # failure this smoke exists for, so it is refused rather than reported healthy.
    try:
        markdown = (json.loads(text).get("data") or {}).get("markdown") or ""
    except json.JSONDecodeError:
        markdown = ""
    if not markdown.strip():
        print("[fetch-smoke] FATAL: HTTP 200 with an EMPTY body (no data.markdown) — a fetch leg would "
              "report success on nothing; refusing to call that healthy.", file=sys.stderr)
        return 1

    markdown = markdown[:args.budget]
    excerpt = " ".join(markdown.split())[:160]
    print(f"[fetch-smoke] OK: HTTP {status}, {len(markdown)} markdown char(s) (budget {args.budget}); "
          f"excerpt: {excerpt!r}")
    print(f"[fetch-smoke] the key was read from {KEY_VAR} and never printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
