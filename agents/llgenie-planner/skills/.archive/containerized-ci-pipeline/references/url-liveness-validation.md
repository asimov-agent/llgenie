# URL-liveness checks in a validation pipeline: retry, classify, cache separately

Every link/URL gate in a validation pipeline must answer "is this dead?" without turning one transient network failure into a hard CI failure. The class of bug and the durable fix:

## The single-probe flake

When the strict probe already retries retryable statuses with backoff, honours `Retry-After`, treats DNS as dead and an unsettled probe as UNVERIFIED, but a **lenient** path (README / source_post links) is a single HEAD->GET pass under `except Exception: continue`, one timeout or connection-reset returns `False` — and `does not resolve` is reported on a LIVE repo. Signature: a push with zero link changes goes red in the link stage, is green on re-run, and the failing URL resolves in a browser.

## The fix: one probe, classify the verdict by mode

- The lenient verdict comes from the SAME retrying probe as strict. Dead only on a **definitive** status (404/410/401/DNS); 403 (bot-block) stays reachable for lenient kinds; anything still unverifiable after retries is **UNVERIFIED** -> accepted, with the evidence printed (`WARN: link unverified (network: timed out after 4 attempts): <url>`) — never an unstated `False`. The WARN line both explains the acceptance and keeps the log grep-able.
- Keep **separate per-run caches** for the lenient and strict verdicts: they answer the SAME url differently for 403, so a shared cache would return the wrong mode's verdict.

## Red/green on the SAME transient input

Prove the fix, don't assert it: run OLD code and NEW code against an identical timeout/connection-reset input and show the verdict flips. With a mocked `urlopen` raising `URLError(socket.timeout)` and a stubbed backoff sleep:

```
master:  lenient link is DEAD? True     # the flake
this PR: WARN: link unverified (network: timed out after 4 attempts): …
         lenient link is DEAD? False    # accepted, evidence printed
```

## Cache hygiene in the status-loop test

A unit test that loops HTTP statuses (200/403/429/503/404) over the SAME url while clearing only the strict cache leaks the first verdict across iterations (the lenient cache still holds the first status's answer). Clear BOTH caches in the loop, or give each status its own url.
