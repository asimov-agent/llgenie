# check-engine-launchers: the sweep's exit code now agrees with its stated contract (issue #2296) — 2026-11-08

**Implements:** issue #2296 — `make check-engine-launchers` reddened `main` at `faa1af30` even though every
missing launcher was informational, a red no PR author could clear at a green CI.

## Root cause

Measured 2026-11-08, run 42521619071 job 128856141997 at `faa1af30`:

```
[launchers] no launcher for vllm (...) - informational: a host may legitimately have none, CI has none
[launchers] 0 ok, 0 stale, 7 missing, 0 not published (arch vulkan)
make: *** [Makefile:1360: check-engine-launchers] Error 1
```

The sweep printed "informational" for every missing launcher and then `exit 1` regardless — CI's normal state
(no launchers at all) was reported informational and still reddened the gate. The stated contract and the exit
code disagreed.

(2 unpublished vllm images in the same run are issue #2294, a cancelled producer — not this defect.)

## Fix

State the contract in one place and make the exit code agree:

- A missing launcher stays **informational** on a host with zero launchers (CI, a fresh checkout), and for
  every **on-demand** engine (litert, mlx, ollama, vllm, …) — a host may legitimately serve fewer. Those
  never red the sweep.
- One class is **REQUIRED**: once a host has installed at least one CORE launcher (`make install` always
  writes the llama.cpp / llama.cpp-prism pair), the absent half of that pair is a broken install and reds,
  naming `make engine-launchers ENGINES=<engine>` as the fix.
- A stale launcher still reds everywhere; `CHECK_REGISTRY=1` still fails a tag no manifest resolves.

## Verification

- `tests/test_check_engine_launchers.py` 15 passed (incl 3 new: uninstalled host all-informational → exit 0,
  opted-in host missing a CORE launcher → RED, on-demand missing stays informational on an opted-in host + a
  test-premise fix).
- Files: `scripts/check_engine_launchers.py`, `tests/test_check_engine_launchers.py`, `docs/ENGINES.md`,
  note pair + `CHANGES.md` row.
