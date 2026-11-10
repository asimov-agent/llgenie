# Host-test cells: the per-cell acceptance harness and the host arch grid

## `make test-engine-host` — the acceptance command for ONE engine×arch cell (#1322)

`make test-engine-host ENGINE=<id> ARCH=<arch>` is the harness that proves a published image
serves on this host: it resolves the published tag → installs/pulls the launcher → serves the
smallest supported model for that engine → reads real timings. It is also the LAST step of
`.github/workflows/engine-build.yml` (the `host-verify` job), run per matrix cell on the runner's
own supported archs — so a green CI host-verify and a local `test-engine-host` exercise the same
path. Run it once per cell, SEQUENTIALLY (one GPU), and never substitute `build-engine*`.

## `test-engine-host` red = a SERVE/readiness divergence, not the install-leg

A `test-engine-host` red (Makefile:1378, `[host] --- serve …`) is a DIFFERENT failure class from a
`test-engine-install` red — classify by the failing STEP name, never the run conclusion. The common shape:
the published image DOES start and print `[engine-image] READY <id>/<arch> base_url=http://127.0.0.1:<port>/v1`
(the container came up, model mounted), but the host-verify chat probe — `serve_published` → `_chat`
(`engine_host_test.py`, `urlopen(req, timeout=…)`, `retries=2`) — raises `TimeoutError: timed out`, so the
step exits `Makefile:1378: test-engine-host Error 1`. The tell is a READY line followed immediately by a
`TimeoutError` traceback through `serve_published`/`_chat` — i.e. **READY (port/listen up) and first inference
that answers are not the same event**, especially for a 4-bit model doing its first load on a CPU-only runner.
This is a serve/readiness-timing divergence at host-verify, NOT the cuda #1240 install-leg skip bug; give it
its own tracker and look at a first-token readiness wait or a longer chat probe. Never fold it into the
CDI/skip fix, and never read `READY` in the log as "the serve verified green" when the probe still timed out.

## The host arch grid is DERIVED, not a roster

`host_supported_archs()` yields the archs THIS host can run, and it adds `vulkan` ONLY when NO GPU
backend is detected. Measured here: NVIDIA RTX 4090 Laptop (CUDA compute 8.9, 16376 MiB),
`/dev/dri/renderD128`+`renderD129` present, no rocm, no Metal → grid = **['cuda','cpu']** —
`vulkan` is NOT a leg despite the render nodes, because cuda is present.

When you enumerate testable cells, cross the committed `containers/engines/params/*.json`
`variants` against the host grid, and treat the result as a SUBSET check (`expected <= set(actual)`),
never an exact list — a new engine or variant must not red the check. (At 2026-11 the grid-∩-params
cross produced 18 cells: 11 cuda + 7 cpu; do not hard-code that number anywhere.)

## `message_agent` queue-full is NOT delivery

`message_agent` can return `ambiguous` / `queue_full` with "Do not resend". That DM was NOT
delivered. Do not resend: post the same request/claim on the issue or PR thread with the `@lane`
mention, and state that the DM channel was queue-full. The issue thread is the durable record;
a queue-full DM leaves no trace the next reader can find.
