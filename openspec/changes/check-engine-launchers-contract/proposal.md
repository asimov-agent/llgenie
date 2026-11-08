# check-engine-launchers contract

## Why

`make check-engine-launchers` reddened `main` at a green `ci.yml` at `faa1af30` (measured 2026-11-08, run
42521619071 job 128856141997):

```
[launchers] no launcher for vllm (...) - informational: a host may legitimately have none, CI has none
[launchers] 0 ok, 0 stale, 7 missing, 0 not published (arch vulkan)
make: *** [Makefile:1360: check-engine-launchers] Error 1
```

The sweep called every missing launcher informational and then `exit 1` regardless — CI's normal state (no
launchers at all) was reported informational and still reddened the gate. The stated contract and the exit
code disagreed, and the red blocked every merge (ci-verdict reported it as UNJUDGED RED) at a green `ci.yml`.

## What changes

1. A missing launcher stays **informational** on a host with zero launchers (CI, a fresh checkout) and for
   every **on-demand** engine (litert, mlx, ollama, vllm, …) — a host may legitimately serve fewer. Those
   never red the sweep; on a host with no launchers the sweep exits 0.
2. One class is **REQUIRED**: once a host has installed at least one CORE launcher (`make install` always
   writes the llama.cpp / llama.cpp-prism pair), the absent half of that pair is a broken install and reds,
   naming `make engine-launchers ENGINES=<engine>` as the fix.
3. A stale launcher still reds everywhere; `CHECK_REGISTRY=1` still fails a tag no manifest resolves.

## Change-first

Issue #2296 is the surviving tracker. The REQUIRED/informational split is new: previously every missing
launcher was informational and the sweep still reddened, so a host that opted into the default install set
but silently dropped a CORE launcher was indistinguishable from CI. `ci-verdict`'s judging of
`check-engine-launchers` is untouched; the gate just stops reddening on a legitimate state. Branch:
`fix/2296-launcher-contract`.
