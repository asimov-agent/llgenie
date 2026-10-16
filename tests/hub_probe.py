"""One live-Hub link probe for the test suite: a ranged GET with a bounded retry (issue #256).

Two test files each carried their own one-shot `_url_exists`: a 20s ranged GET that retried
nothing and collapsed every failure mode — a Hub 500/504, a 429, a stalled connection, a
genuinely absent file — into `False`, so a red test printed the same line for all of them:

    AssertionError: qwen3.8-27b/mlx on cuda: real file missing (HTTP): https://huggingface.co/...

Measured on `main`: `macos / unit` was red on two consecutive runs, on two different files that
both answer HTTP 200 from the maintainer host and are both listed in their repo's `siblings`,
while `linux / unit` was green on the same commits. That is an upstream blip reported as a code
defect — the exact confusion #256's thread describes for the product's Hub paths.

This module is the single probe those suites use:

- the request shape is unchanged (a ranged GET, so a multi-GB quant is never fetched to ask
  whether it exists);
- the transient set (429, 500/502/503/504, transport errors) is retried on a bounded ladder
  (1+2+4+8 = 15s, at most 5 attempts), so a blip no longer reddens the lane;
- a definitive answer (404, 403, ...) is returned on the FIRST request, so a missing file stays
  a one-request failure and cannot hide behind the budget;
- the answer carries the status or the transport reason, so the failing assertion names what
  the Hub actually said;
- after `OUTAGE_LIMIT` probes have exhausted the budget, later probes take a single attempt and
  say the Hub is in a degraded window: a sustained outage cannot multiply 15s across the
  thousands of links these suites verify. That is a time bound, never a skip — every unverified
  link still fails its assertion, loudly.

The retry is not a stand-in for the product's own budget: `model_engine_pick._hub_json` and
the serve module's `_hf_get` retry their 5xx on `2 ** (i + 1)`; `hf_auth.hub_open` still does
not (issue #339). This is the test-side liveness check for the links a pick would hand a user.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass

#: The one request shape every probe sends: a ranged GET, so existence costs one chunk.
HEADERS = {"Range": "bytes=0-0", "User-Agent": "llgenie-test"}

#: Per-attempt socket timeout.
TIMEOUT = 20.0

#: At most this many attempts for a transient outcome.
ATTEMPTS = 5

#: The bounded backoff ladder actually slept (1 + 2 + 4 + 8 = 15s before the 5th attempt).
BACKOFF = (1, 2, 4, 8)

#: The statuses the Hub answers while it is merely busy: the rate limit, and the
#: gateway/overload family #256 measured (22x HTTP 500 + 11x HTTP 504 in a single run).
TRANSIENT_STATUS = (429, 500, 502, 503, 504)

#: How many probes may exhaust the retry budget before the Hub is treated as degraded for the
#: rest of this process (one attempt each, cause named). A time bound, never a skip.
OUTAGE_LIMIT = 3


@dataclass(frozen=True)
class Probe:
    """What the Hub said about one link.

    `detail` is the status or the transport reason — `HTTP 206`, `HTTP 404`,
    `HTTP 503 after 5 attempts (15s of backoff)`, `URLError: <urlopen error ...>` — so a failing
    assertion can say which one it saw.
    """

    exists: bool
    detail: str
    attempts: int

    def __bool__(self) -> bool:
        return self.exists


_exhausted = 0  # probes that spent the whole retry budget on a transient outcome


def reset() -> None:
    """Forget the outage count (a test seam; a process starts clean)."""
    global _exhausted
    _exhausted = 0


def degraded() -> bool:
    """True once `OUTAGE_LIMIT` probes have exhausted the retry budget."""
    return _exhausted >= OUTAGE_LIMIT


def _transport_detail(err: BaseException) -> str:
    text = str(err).strip().splitlines()[0] if str(err).strip() else type(err).__name__
    return f"{type(err).__name__}: {text}"


def probe(url: str, *, attempts: int = ATTEMPTS, backoff: tuple[int, ...] = BACKOFF,
          timeout: float = TIMEOUT, sleeper=time.sleep) -> Probe:
    """Verify one live link. See the module docstring for the contract."""
    global _exhausted
    broken = degraded()
    tries = 1 if broken else attempts
    last = ""
    transient = False
    used = 0
    for i in range(tries):
        # A new Request per attempt: a timed-out one is not reusable (and macOS runners hang
        # on huggingface.co's IPv6 address — model_engine_pick._hub_json notes the same).
        req = urllib.request.Request(url, method="GET", headers=dict(HEADERS))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                status = r.status
            if status in (200, 206):
                return Probe(True, f"HTTP {status}", i + 1)
            # Answered, but neither a served file nor a transient error: definitive.
            last = f"HTTP {status}"
            used = i + 1
            break
        except urllib.error.HTTPError as e:
            if e.code not in TRANSIENT_STATUS:
                return Probe(False, f"HTTP {e.code}", i + 1)
            last = f"HTTP {e.code}"
            transient = True
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = _transport_detail(e)
            transient = True
        used = i + 1
        if i + 1 < tries:
            sleeper(backoff[min(i, len(backoff) - 1)])
    if broken:
        return Probe(False,
                     f"{last} (1 attempt: the Hub is in a degraded window — {_exhausted} link "
                     f"probes already exhausted their retry budget)", used)
    if not transient:
        # A status the Hub answered with and that is not the served pair — definitive, un-retried.
        return Probe(False, last, used)
    _exhausted += 1
    note = "" if not degraded() else (
        " — the Hub is in a degraded window; the next probes take one attempt each")
    return Probe(False, f"{last} after {used} attempts ({sum(backoff[:used - 1])}s of backoff){note}",
                 used)
