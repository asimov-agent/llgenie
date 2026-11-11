# Diagnosing llgenie CI failures that hit the Hub

Most llgenie CI jobs run `docker run --rm -u root -e HOME=/root` (Makefile `TEST_OPTS`)
and the install/health stages run `-e HOME="$(CI_HOME)"` (a fresh `.ci-home` each run).
Both mean any on-disk HTTP cache lives INSIDE the throwaway container/`.ci-home` and is
scrubbed when the job ends — so every CI run fetches Hub data cold once.

## Root cause when a job spams 429 / 5xx

The shared auth path is `scripts/hf_auth.py`: `hf_token()` (env `HF_TOKEN`, then
`HUGGING_FACE_HUB_TOKEN`, then the `HF_TOKEN=` line in `~/.zshrc`/`~/.bashrc`) and
`authorize()` which attaches `Authorization: Bearer <tok>` to every `huggingface.co`
request. Both `_hub_json()` (model_engine_pick) and `_hf_get()` (llama_serve) route
through it and add retry/backoff (`HUB_CACHE_TTL`, `HF_GET_MAX_ATTEMPTS`).

The Hub bounds each token to ~1000 req / 5-min window (anon ~500). A job whose cache is
cold (every CI run) and whose code asks the Hub for each model per format (11 models x
formats in the pick path) can exhaust the window in one run; the retries are exponential
and short, so they fail fast once 429s arrive continuously.

## Diagnostic sequence (in order)

1. **Confirm auth is even wired before blaming rate limit.** Is `HF_TOKEN` present in
   the step env (masked `***` is fine) and passed on the `docker run` via `-e HF_TOKEN`
   (Makefile `TEST_OPTS` / `ENGINE_TEST_ARGS`)? Does the failing call go through
   `authorize()`? If auth is missing in a specific job, that is a pipeline wiring bug.
2. **Same commit, same secret, sibling jobs diverge?** Linux green / macOS red on the
   same run = the rate window, not missing auth — both would fail missing a secret.
3. **Read the live quota** to confirm: probe `https://huggingface.co/api/whoami-v2` with
   the token and read the `ratelimit` / `RateLimit` response header (remaining + reset)
   versus the anon header on a no-auth `GET`. A token sitting at its window ceiling is
   the proof.
4. **A 429 waits for the window, it does not backoff inside it.** The wait is
   `scripts/hf_auth.rate_limit_wait`: the `t` seconds from the `RateLimit` header
   (the Hub sends that, not `Retry-After`), else 300, capped at 600. A 429 is
   retried twice and a non-429 resets the consecutive count. Do not add a
   1/3/5/7 minute ladder: an attempt before `t` is another 429.
5. **A download does not call `urlopen` on a Hub URL.** The size lookup, the
   ranged chunk and the preflight probe go through `scripts/hf_auth.hub_open`,
   which applies that wait. A new Hub GET belongs there too, and its test asserts
   the sleep against `rate_limit_wait` rather than a copied number. Persisting
   the Hub cache still cuts how often the window fills. The wait only covers the
   case where it already has.

## A read-phase Hub timeout is `TimeoutError`, not `URLError`

A retry loop that catches `urllib.error.URLError` looks complete and is not: a
**connect**-phase failure arrives wrapped in `URLError`, but a **read**-phase socket
timeout arrives as the builtin `TimeoutError` (`socket.timeout` since 3.10), raised from
inside `http.client`/`ssl` after the connection exists. `issubclass(TimeoutError,
urllib.error.URLError)` is `False`, so one stalled read escapes the loop entirely: no
`transient error … retrying` line, no retry, and the CLI dies with an `ssl.py` traceback
and exit 1 — which an acceptance test then reports as "must exit 0" (a `macos / top-tier`
red that looks like a regression in whatever commit happened to be pushed).

- Catch BOTH in every Hub GET seam: `except (urllib.error.URLError, TimeoutError)`.
  `hf_auth.hub_open` already does; when a seam such as `llgenie_serve._hf_get` is added
  or audited, compare its transport arm against that one.
- Prove it with a REAL server, not a patched transport: a `ThreadingHTTPServer` that
  accepts and answers nothing, `_hf_get(url, timeout=1)`, module attrs
  `HF_GET_MAX_ATTEMPTS=2` / `HF_GET_BASE_PAUSE=0.0`. Assert the stall is retried, the
  retry's payload is returned, and an exhausted budget raises `SystemExit` naming the
  attempt count with no `TimeoutError` in the message.
- **Falsify before claiming the fix:** `git stash push scripts/<file>.py`, run the new
  test (it must fail with the same `TimeoutError` the CI log shows), `git stash pop`.
  A test that only passes on the fixed tree proves nothing about the mechanism.
- Un-retried `ConnectionResetError` / `http.client.RemoteDisconnected` are a separate,
  unmeasured class — do not silently widen the tuple to `OSError` to "cover" them.

## Don't

- Do not "fix" auth that is already wired — reproduces the same red job.
- Do not treat a cold-cache run's 429 as a transient blip to retry past; the window is
  the constraint.
