#!/usr/bin/env python3
"""The token every Hugging Face call sends.

`HF_TOKEN` in the environment wins, then `HUGGING_FACE_HUB_TOKEN`, then the
`HF_TOKEN=` line in `~/.zshrc` or `~/.bashrc`. CI sets the environment from
the `HF_TOKEN` Actions secret. The value is never printed and never written
into the repo.
"""
from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_LINE = re.compile(
    r"(?m)^[ \t]*(?:export[ \t]+)?HF_TOKEN=[\"']?(hf_[A-Za-z0-9]+)[\"']?[ \t]*$"
)


def hf_token() -> str:
    """The Hub token, or '' when none is configured."""
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        val = os.environ.get(key, "").strip().strip("\"'")
        if val:
            return val
    for name in (".zshrc", ".bashrc"):
        path = os.path.expanduser(f"~/{name}")
        try:
            text = open(path).read()
        except OSError:
            continue
        match = _LINE.search(text)
        if match:
            return match.group(1)
    return ""


def _hub_host(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host == "huggingface.co" or host.endswith(".huggingface.co")


def authorize(req: urllib.request.Request) -> urllib.request.Request:
    """Attach `Authorization: Bearer` when the URL is the Hub and a token exists."""
    if _hub_host(req.full_url):
        tok = hf_token()
        if tok:
            req.add_header("Authorization", f"Bearer {tok}")
    return req


# Hub API quota is a fixed 5-minute window (https://huggingface.co/docs/hub/en/rate-limits).
# A 429 carries the seconds left in that window as RateLimit: "api";r=0;t=<seconds>.
# The Hub does not send Retry-After. Waiting less than t spends the next window on
# another 429. 10 minutes is the longest a caller holds before it fails.
RATE_LIMIT_WINDOW = 300
RATE_LIMIT_WAIT_CAP = 600
# One capped 429 sleep, then the 180s the detailed dry run already had for
# discovery. A limit equal to the cap expires as that sleep ends.
TOP_TIER_DRY_RUN_TIMEOUT = RATE_LIMIT_WAIT_CAP + 180
_RATE_LIMIT_T = re.compile(r"(?:^|[;,])t=(\d+)")


def rate_limit_wait(err: urllib.error.HTTPError) -> int:
    """Seconds to wait after a Hub 429, from the RateLimit header.

    The `t` value is the seconds left in the fixed window. Absent, the wait is
    the 5-minute window. Never more than 10 minutes. Every Hub caller and every
    test that asserts this wait uses this function.
    """
    raw = ""
    if err.headers:
        raw = err.headers.get("RateLimit") or err.headers.get("Retry-After") or ""
    match = _RATE_LIMIT_T.search(raw)
    seconds = int(match.group(1)) if match else RATE_LIMIT_WINDOW
    if not match and raw.strip().isdigit():
        seconds = int(raw.strip())
    return min(RATE_LIMIT_WAIT_CAP, max(0, seconds))


_rate_limited = 0  # consecutive Hub 429s across calls; a non-429 resets it


def hub_open(req: urllib.request.Request, timeout: float = 30):
    """Open a Hub URL. A 429 waits `rate_limit_wait` and is retried twice.

    Any response that is not a 429 resets the consecutive count, so the next
    429 gets the full budget again. A third consecutive 429 raises. This is the
    GET every Hub download uses; a caller does not call urlopen on a Hub URL.
    """
    global _rate_limited
    authorize(req)
    while True:
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
        except urllib.error.HTTPError as e:
            if e.code != 429:
                _rate_limited = 0
                raise
            _rate_limited += 1
            if _rate_limited > 2:
                raise
            time.sleep(rate_limit_wait(e))
            req = urllib.request.Request(req.full_url, headers=dict(req.header_items()))
            continue
        _rate_limited = 0
        return resp


def apply_env(env: dict) -> dict:
    """Put the token on `env` for the `hf` CLI. Leave an explicit value in place."""
    tok = hf_token()
    if tok:
        env["HF_TOKEN"] = tok
        env.setdefault("HUGGING_FACE_HUB_TOKEN", tok)
    return env
