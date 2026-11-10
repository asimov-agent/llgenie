# Refreshing docs/ARCHITECTURE.md for the tree at 20261110T2017 (issue #2473)

## What changed

`docs/ARCHITECTURE.md` lagged the tree again after the 2026-11-09 merge burst (#2343,
#2449, the profile-fold notes): the architecture bot re-derived the surface and the drift
from real `git` state and rewrote only the doc. This is the continuous-refresh pass that
follows the 20261109T0732 census shipped via #2363; PR #2474 carries it.

The refresh carries the one file `docs/ARCHITECTURE.md` on `agent/architecture-20261110T2017`
(measured at `caf0002f4148f53782028b4c173af9e969a25106`). Notable deltas in the re-derivation:

- Repository-layout census re-measured: 4107 -> 4331 tracked files; the nine named content
  dirs now sum to 4250; `agent-wiki/` 717 -> 755, `docs/` 726 -> 765, `tests/` 290 -> 296,
  `agents/` 458 (13 profile dirs plus `manifest.json`, `README.md`, `standing-rules.md`,
  `fleet-block-exemptions.json`).
- The structural-gates row is re-derived against the current `scripts/` census (174 files),
  including the newer gates the 11-09 window added: `check_cron_drift.py` (issue #2359),
  `check_gitleaks_pin.py` (issue #2235), `verify_lane_contract.py` / `agent_lanes_check.py`
  (issue #2260), `check_task_shape.py` (issue #2123), `check_package_layers.py` (issue #795).
- The bots-and-automation row is re-listed from the shipped workflow set (workflow_dispatch
  contracts per directive #2293).

## Current status

Only `docs/ARCHITECTURE.md` is committed on the branch (as `Asimov Agent <support@docondee.com>`);
no workflow, make target, or script changed. The bot never merges and never pushes to `main` —
PR #2474 is for human review. This change-note trio (`agent-wiki/2026-11-10-architecture-refresh-2473.md`,
`docs/changes.d/2026-11-10-architecture-refresh-2473.md`, and its `CHANGES.md` index row) is the docs obligation the
refresh owed (`make check-docs`, issue #1123); issue #2473 is closed by PR #2474.
