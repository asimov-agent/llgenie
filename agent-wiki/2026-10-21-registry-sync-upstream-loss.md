# 2026-10-21 — the weekly registry sync is blocked by a loss in the upstream store (issue #525)

## What was found

While verifying every bot against latest `main`, the `registry-sync` job was found **red on its last
run** (`39240829581`, 2026-10-19) with `make check-registry-keys` refusing the sync:

```
[check-registry-keys] LOSS: qwen3.8-27b: measurement llama.cpp on Strix Halo (Ryzen AI Max APU) 128GB is gone
[check-registry-keys] LOSS: qwen3.8-27b: mlx-serve on M4 Max t/s lowered 146 -> 70
[check-registry-keys] LOSS: qwen3.8-flash-next-125b: measurement Strata on RTX 3090 is gone
[check-registry-keys] FAILED: 23 loss(es) vs HEAD:data/models.json — the registry is additive only
```

The bot is behaving exactly as designed: `data/models.json` is vendored verbatim, and llgenie never
patches upstream data to make a sync pass. A dropped `(engine, hardware)` group removes an engine
from a model's offer and lowers the t/s llgenie ranks on.

## What was done

The loss was reported **upstream**, where the store is written:
[andyholst/trending-local-llms#525](https://github.com/andyholst/trending-local-llms/issues/525)
(the 23 losses, the measured examples, and what "done" means there). No llgenie data was changed and
the guard was not widened.

## Status

Recorded in llgenie by PR #487. Blocked on the upstream fix. Once #525 is resolved, the next Monday `registry-sync` run should open
its PR normally; nothing on the llgenie side needs to change.
