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
#: Total seconds ONE `hub_open` lookup may spend sleeping on Hub 429s (issue #872).
#: The count above bounds the NUMBER of waits, never their sum: two capped waits are
#: 1200 seconds, and a probe that spends them holds a shared CI runner for 20 minutes
#: while `pytest`'s 300 s faulthandler only prints a traceback. So the waits are bounded
#: by a TOTAL: `RATE_LIMIT_TOTAL_BUDGET` is sized to the Hub's REAL 5-minute window
#: (300 s) so a transient 429's window fits and is waited out, yet a probe still cannot
#: hold a shared CI runner for the 10-minute cap. A 429 whose window (the Hub's `t`, up to
#: the 600 s CAP when the header is absent) exceeds this total still raises at once (issue
#: #872: the 20-minute hop stays impossible). The raised message states the attempts and
#: the seconds spent, so the lookup never fails silently.
RATE_LIMIT_TOTAL_BUDGET = float(os.environ.get("HUB_RATE_LIMIT_BUDGET", "300"))


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


def _rate_limited_error(err: urllib.error.HTTPError, attempts: int, waits: int,
                        slept: float) -> urllib.error.HTTPError:
    """The same 429, with the budget it was allowed spelled out in its message.

    The status and headers are the Hub's, unchanged, so a caller that reads
    `e.code`/`e.headers` behaves exactly as before; only `msg` (what the traceback
    and every `str(err)` show) now says how many attempts and 429 waits were spent
    out of what budget — a rate-limited lookup must be diagnosable from its own
    failure, not from a stopwatch (issue #872).
    """
    return urllib.error.HTTPError(
        err.url, err.code,
        f"{err.msg} [hf_auth] {attempts} attempt(s), {waits} 429 wait(s) totalling "
        f"{slept:.0f}s of the {RATE_LIMIT_TOTAL_BUDGET:.0f}s budget "
        f"(HUB_RATE_LIMIT_BUDGET) over at most {RATE_LIMIT_WAITS} window(s)",
        err.headers, None)


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
    - the waits are ALSO bounded by a total, `RATE_LIMIT_TOTAL_BUDGET` (300 s, the Hub's
      real 5-minute window): a wait
      that does not fit what is left of it raises immediately instead of sleeping, so
      a single lookup's wall clock is a small constant rather than 2 x 600 s. The
      raised 429 names the attempts and the seconds spent (issue #872).
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
    waits = 0     # 429 waits THIS lookup has spent (the count rule caps them)
    slept = 0.0   # seconds THIS lookup has slept on them (the total rule caps them)
    while True:
        attempts += 1
        try:
            resp = open_fn(req, timeout=timeout)  # noqa: S310
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _rate_limited += 1
                wait = rate_limit_wait(e)
                # The total is sized to the Hub's REAL window (300 s), not 60 s: a
                # transient 429 whose window is the Hub's 5-minute default used to raise at
                # 0 s spent and 1 attempt — a fail-fast that never waits, which turned a
                # transient 429 into a suite failure (#932). The 600 s CAP stays refused
                # (issue #872), so the 20-minute hop is still impossible.
                if _rate_limited > RATE_LIMIT_WAITS or slept + wait > RATE_LIMIT_TOTAL_BUDGET:
                    # Two ceilings, and either one ends the lookup: too many windows, or
                    # the next window does not fit what is left of the total budget.
                    raise _rate_limited_error(e, attempts, waits, slept) from None
                # Say it out loud: an unannounced multi-minute sleep is indistinguishable
                # from a hang, and `llgenie` fans out one Hub tree call per model x format.
                print(f"[hf] rate limited (429) on {req.full_url.split('?')[0]}: waiting {wait}s "
                      f"(wait {_rate_limited}/{RATE_LIMIT_WAITS})", file=sys.stderr, flush=True)
                time.sleep(wait)
                waits += 1
                slept += wait
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
