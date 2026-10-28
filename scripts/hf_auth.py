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
import sys
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


#: The Hub endpoint paths that authenticate a token: the API (`/api/...`) and a file
#: fetch (`/<repo>/resolve/...`). A Hub WEB PAGE is not one of them: measured
#: 2026-10-26, the same model page answers 200 WITHOUT the token and 429 WITH it
#: ("we had to rate limit your IP ... make sure you pass a HF_TOKEN"), because a
#: token-bearing web-page GET is accounted against the API rate limit (issue #690).
_HUB_ENDPOINT = re.compile(r"^/(?:api(?:/|$)|.*/resolve/)")


def _hub_endpoint(url: str) -> bool:
    """True when the URL is a Hub endpoint that authenticates a token, not a web page."""
    return _hub_host(url) and bool(_HUB_ENDPOINT.match(urllib.parse.urlparse(url).path or "/"))


def authorize(req: urllib.request.Request) -> urllib.request.Request:
    """Attach `Authorization: *** when the URL is a Hub ENDPOINT and a token exists.

    Never a Hub web page: the token there is what the Hub answers with a 429 (issue #690).
    """
    if _hub_endpoint(req.full_url):
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

#: The transient outcomes every Hub GET retries (issue #339): the Hub's rate limit, the
#: 5xx it actually returns, and a transport failure. Everything else is definitive.
TRANSIENT_HTTP = frozenset({429, 500, 502, 503, 504})
#: Total tries for one GET, and the doubling ladder the non-429 transients wait on.
HUB_MAX_ATTEMPTS = int(os.environ.get("HUB_MAX_ATTEMPTS", "8"))
HUB_BASE_PAUSE = float(os.environ.get("HUB_BASE_PAUSE", "1.5"))
#: How many rate-limit windows one GET may wait out (each up to RATE_LIMIT_WAIT_CAP).
RATE_LIMIT_WAITS = int(os.environ.get("HUB_RATE_LIMIT_WAITS", "2"))


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

# The `hf` CLI speaks the Hub's own answer on a throttle, in text rather than in a
# header ("429 Too Many Requests ... Retry after 202 seconds"). Same policy as the
# header form: the stated seconds, else the 5-minute window, capped at 10 minutes.
_THROTTLE_SAYS = re.compile(r"Retry after\s+(\d+)\s*second", re.I)
_THROTTLE_TEXT = re.compile(r"\b429\b|Too Many Requests", re.I)


def throttle_wait(text: str) -> int:
    """Seconds to wait when a failed attempt's OUTPUT names a Hub throttle, else 0.

    0 means the text names no throttle, so the caller keeps its own (short) pause.
    """
    if not text or not _THROTTLE_TEXT.search(text):
        return 0
    match = _THROTTLE_SAYS.search(text)
    seconds = int(match.group(1)) if match else RATE_LIMIT_WINDOW
    return min(RATE_LIMIT_WAIT_CAP, max(0, seconds))


def hub_open(req: urllib.request.Request, timeout: float = 30, opener=None):
    """Open a Hub URL: ONE GET with ONE bounded, stated transient budget.

    The transient set is the Hub's rate limit (429), the 5xx it actually returns
    (500/502/503/504) and a transport failure (URLError, a timeout). It is retried
    on two stated budgets, and the error that breaks it names the status and the
    attempts spent:

    - a 429 waits the Hub's own window (`rate_limit_wait`: the `RateLimit` header's
      `t`, else 5 minutes, capped at 10) and may spend at most TWO such waits; a
      third consecutive 429 raises. Waiting less spends the next window on another
      429, and an unbounded wait would park a CI job for hours.
    - every other transient outcome retries on a 1.5s doubling ladder (1.5, 3, 6,
      12, 24, 48, 96) up to `HUB_MAX_ATTEMPTS` tries in total.
    - a definitive answer (401/403/404, any other status) is raised on the FIRST
      attempt, so a missing repo cannot hide behind the budget.

    `opener` is the transport, defaulting to `urllib.request.urlopen`; a caller with a
    transport quirk (model_engine_pick prefers IPv4 on macOS runners) passes its own
    and still gets THIS policy, so no caller carries a second retry ladder (issue
    #339).
    """
    global _rate_limited
    authorize(req)
    open_fn = opener or urllib.request.urlopen
    attempts = 0
    while True:
        attempts += 1
        try:
            resp = open_fn(req, timeout=timeout)  # noqa: S310
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _rate_limited += 1
                if _rate_limited > RATE_LIMIT_WAITS:
                    raise
                wait = rate_limit_wait(e)
                # Say it out loud: an unannounced multi-minute sleep is indistinguishable
                # from a hang, and `llgenie` fans out one Hub tree call per model x format.
                print(f"[hf] rate limited (429) on {req.full_url.split('?')[0]}: waiting {wait}s "
                      f"(wait {_rate_limited}/{RATE_LIMIT_WAITS})", file=sys.stderr, flush=True)
                time.sleep(wait)
            elif e.code in TRANSIENT_HTTP:
                _rate_limited = 0
                if attempts >= HUB_MAX_ATTEMPTS:
                    raise
                time.sleep(HUB_BASE_PAUSE * 2 ** (attempts - 1))
            else:
                _rate_limited = 0
                raise
            req = urllib.request.Request(req.full_url, headers=dict(req.header_items()))
            continue
        except (urllib.error.URLError, TimeoutError):
            _rate_limited = 0
            if attempts >= HUB_MAX_ATTEMPTS:
                raise
            time.sleep(HUB_BASE_PAUSE * 2 ** (attempts - 1))
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
