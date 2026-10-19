#!/usr/bin/env python3
"""Refuse to start a bot leg whose credential is missing (issue #363).

A leg that forwards a key its job never set spends the runner first: it pulls the agent image,
starts a container, and only then fails inside Hermes — a 120-180 minute-timeout job lost to a
plumbing mistake, with a log that reads like a model problem. `make hermes-smoke` already refused
this way; every other agent leg did not.

This guard runs **before** `scripts/ci_images.py ensure agent`, for every leg, with the keys that leg
needs. It prints the variable's NAME only — never a value, never a prefix, never a length of a value
it did not get — and exits 2 so a missing key is a loud failure, not a skipped check.

Usage:
    python3 scripts/require_env.py NOUS_API_KEY
    python3 scripts/require_env.py NOUS_API_KEY TYPESAFE_API_KEY
"""
from __future__ import annotations

import argparse
import os
import re
import sys

NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail when a bot leg's credential is missing.")
    ap.add_argument("names", nargs="+", help="the environment variables this leg needs")
    args = ap.parse_args(argv)

    bad = [n for n in args.names if not NAME.match(n)]
    if bad:
        print(f"[require-env] FATAL: not a variable name: {', '.join(bad)}", file=sys.stderr)
        return 2

    missing = [n for n in args.names if not os.environ.get(n)]
    if missing:
        print(f"[require-env] FATAL: {', '.join(missing)} is missing or empty — refusing to start. "
              f"Set the repository secret (the value stays in the environment and is never printed).",
              file=sys.stderr)
        return 2

    print(f"[require-env] OK: {len(args.names)} credential(s) present: {', '.join(args.names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
