# `hermes-smoke` runs first and judges the store it created

Issue #471. OpenSpec change: `hermes-smoke-fresh-store`.

## What was wrong

`scripts/hermes_smoke.py::run()` opened with

```python
if not db.exists():
    print(f"[hermes-smoke] FAIL: no transcript at {db} - Hermes wrote no session, ...")
    return 1
```

`db` is `$HERMES_HOME/state.db` — the store Hermes **creates when it runs** — so a first run could
never pass. The agent image ships without one:

```
$ docker run --rm llgenie/agent:latest sh -c 'test -f /root/.hermes/state.db && echo EXISTS || echo MISSING'
MISSING
```

Measured on the scheduled bot run [39595965983](https://github.com/asimov-agent/llgenie/actions/runs/39595965983)
(2026-10-21 11:58Z): the `implement` job died **one second** into `make hermes-smoke`:

```
[agent] python3 scripts/hermes_smoke.py run --alias nous-deepseek --reasoning low
[agent] [hermes-smoke] FAIL: no transcript at /root/.hermes/state.db - Hermes wrote no session, ...
make: *** [Makefile:636: _hermes-smoke] Error 1
```

Because every bot leg runs the smoke before it spends agent time, no bot could do any work at all.

## What changed

- `run()` no longer refuses a missing store. It snapshots the session ids when the store is present
  (empty on a fresh home), invokes `hermes -z … -m <alias> --reasoning low --yolo`, and then judges
  what the run left: **no store** → fail naming the path (`hermes exited 0 but wrote no transcript
  at …`), **unreadable store** → fail saying `no readable sessions store`, **no new session** → fail
  naming that. The proof itself (a `role='tool'`, `tool_name='terminal'` result carrying
  `smoke-ok:<nonce>`, and a final answer carrying it) is untouched.
- `tests/test_hermes_smoke.py` replaces the case that pinned the pre-run refusal with two real ones:
  a fresh `HERMES_HOME` with **no** `state.db` passes when the run's session proves the call (the run
  creates the store), and a run that writes **no** store is a named failure. Both drive a stub
  `hermes` executable that reads the nonce from the token file the prompt names, so the real `run()`
  path executes.

## Verified

- `tests/test_hermes_smoke.py` — 10 passed in `llgenie/test:latest`.
- Real fresh image, real script: `db MISSING (fresh)` and then the smoke proceeds into the agent
  (`FAIL: hermes exited 2` — this sandbox does not carry `NOUS_API_KEY`), where before the same run
  stopped at `no transcript at /root/.hermes/state.db`.
- Gates for this change, all exit 0: `make check-wiring`, `make check-docs`, `make lint`,
  `make openspec-validate NAME=hermes-smoke-fresh-store`, `make openspec-tasks-check`,
  `make check-pr-hygiene`, `make check-pr-authors`, `make test-unit` (**4966 passed, 6 deselected, 1015 s**).

## Related

- #472 — a manual `issue-bot` dispatch with no issue number picks one issue itself; this change is
  what lets that run survive its first gate.
- The token/redaction seams (#358, #359) and the 3/day cap are unchanged.
