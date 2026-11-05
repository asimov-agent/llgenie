# Host-test cells: the per-cell acceptance harness and the host arch grid

## `make test-engine-host` — the acceptance command for ONE engine×arch cell (#1322)

`make test-engine-host ENGINE=<id> ARCH=<arch>` is the harness that proves a published image
serves on this host: it resolves the published tag → installs/pulls the launcher → serves the
smallest supported model for that engine → reads real timings. It is also the LAST step of
`.github/workflows/engine-build.yml` (the `host-verify` job), run per matrix cell on the runner's
own supported archs — so a green CI host-verify and a local `test-engine-host` exercise the same
path. Run it once per cell, SEQUENTIALLY (one GPU), and never substitute `build-engine*`.

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
