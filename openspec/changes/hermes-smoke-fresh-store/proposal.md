# hermes-smoke-fresh-store — proposal

Issue: [#471](https://github.com/asimov-agent/llgenie/issues/471)

## Why

`make hermes-smoke` is the gate every bot leg runs before it spends 120 minutes of agent time
(issues #238, #358, #407). It fails **before it calls Hermes**:

```python
def run(hermes, alias, reasoning, db, timeout, keep_token=False) -> int:
    if not db.exists():
        print(f"[hermes-smoke] FAIL: no transcript at {db} - Hermes wrote no session, ...")
        return 1
```

`db` is `$HERMES_HOME/state.db`, the store Hermes **creates when it runs**. On a fresh agent image
there is no `state.db` yet (`docker run --rm llgenie/agent:latest …` → `state.db MISSING`), so the
check refuses the run that would have created it. Measured today: the scheduled `issue-bot` run
[39595965983](https://github.com/asimov-agent/llgenie/actions/runs/39595965983) failed 1 second after
the step began:

```
[agent] python3 scripts/hermes_smoke.py run --alias nous-deepseek --reasoning low
[agent] [hermes-smoke] FAIL: no transcript at /root/.hermes/state.db - Hermes wrote no session,
         so there is nothing to prove (check HERMES_HOME)
```

Every leg that runs the smoke — `issue-bot`, `fix-bot`, `issue-refiner`, `rebase-bot` — dies the same
way, so no bot can do any work at all.

The rest of the function already does the right thing: it snapshots the session ids, invokes
`hermes -z <prompt> -m <alias> --reasoning low --yolo`, and judges the **new** session's transcript
(`new_session`, `evaluate`). The pre-flight check contradicts that design instead of supporting it.

## What Changes

- **`scripts/hermes_smoke.py`** no longer refuses a missing store before the call. It snapshots the
  existing ids when the store is there, runs Hermes, and then: a run that leaves **no store** fails
  naming the path it expected (the store is the evidence, so its absence is still loud), a store that
  is present but unreadable fails naming the reason (`no readable sessions store`, as today), and a
  store with no **new** session fails naming that. The proof itself —
  `role='tool'`, `tool_name='terminal'`, the nonce in the result and in the final answer — is
  unchanged.
- **`tests/test_hermes_smoke.py`** replaces the test that pinned the pre-run refusal with two cases
  that pin the real contract: a **fresh `HERMES_HOME` with no store passes** when the run's session
  carries the nonce (the run creates the store), and a run that **writes no store at all** is a named
  failure. A stub `hermes` on disk provides the session (a real fake binary, the repo's allowance for
  an external CLI), so the real `run()` path executes.
- **`agent-wiki/2026-10-21-hermes-smoke-fresh-store.md`** records the change against issue #471.

## Not covered

- The manual dispatch of `issue-bot` without an issue number — #472, which this change unblocks but
  does not implement.
- The three/day cap, the claim protocol and the token/redaction seams are untouched.
