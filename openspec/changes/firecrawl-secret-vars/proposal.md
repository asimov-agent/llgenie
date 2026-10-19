# The Firecrawl key joins the ONE credential list the guards read

## Why

`FIRECRAWL_API_KEY` became a credential this repo forwards to the agent (#362, merged as #369), but it
never joined `scripts/check_secret_output.py::SECRET_VARS` — the single list both the static
secret-output guard and the transcript redactor (`scripts/scrub_log.py`, #359) read.

Two measured consequences on `main@829c6ec`:

- `make check-secret-output` scans for a *printed* value of every name in that list. A new
  `echo "$FIRECRAWL_API_KEY"`, `-e FIRECRAWL_API_KEY=$VALUE`, or an xtrace around it is a green run.
- `scripts/scrub_log.py::redact` replaces the VALUE of every name in that list. A Firecrawl value
  reaches the printed log in any spelling that does not happen to match a generic credential SHAPE:

  ```
  $ python3 - <<'PY'
  import sys; sys.path.insert(0,'scripts'); import scrub_log
  val = "fc-" + "b"*28
  for text in [f"token={val}", f"key {val} rejected", f"https://x/?k={val}"]:
      out, n = scrub_log.redact(text, {"FIRECRAWL_API_KEY": val})
      print(n, val in out, out)
  PY
  0 True token=fc-bbbb…bbbb
  0 True key fc-bbbb…bbbb rejected
  0 True https://x/?k=fc-bbbb…bbbb
  ```

The sync test that is supposed to keep the list honest derives the roster from `secrets.<NAME>` in
`.github/workflows/*.yml` only. `FIRECRAWL_API_KEY` is not consumed as a workflow `secrets.` expression
yet (the repository secret does not exist — #381), so the Makefile's `AGENT_SHELL_KEYS` — the list that
decides what the agent actually receives — was never compared.

## What Changes

- **`FIRECRAWL_API_KEY` joins `SECRET_VARS`.** One list, one seam: the static guard and the redactor
  both cover it, with no second copy.
- **The roster test compares `AGENT_SHELL_KEYS` too.** A key added to the Makefile's forwarded list but
  not to `SECRET_VARS` reds `make test-unit` instead of shipping silently.
- **Regression tests for the measured leak**: the redactor masks a Firecrawl value in raw,
  URL-encoded and base64 spelling; the static guard names a printed `$FIRECRAWL_API_KEY`.

## Impact

- Affected specs: `secret-output-guard` (new capability in this change).
- Affected code: `scripts/check_secret_output.py`, `tests/test_secret_output.py`,
  and the tests that lock the redactor.
- No behaviour change for any other credential; no workflow gains the key (that is #381).

## Not covered (each its own issue)

- The `FIRECRAWL_API_KEY` repository secret + running `search-smoke` in a monitored job: #381.
- Wiring `make agent-fetch` into a bot prompt, and the coverage report (#362 items 4 and 6): #380.
