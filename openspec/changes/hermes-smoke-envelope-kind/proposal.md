# `hermes_smoke` names a lost or truncated tool-result envelope instead of an un-tracked empty success

## Why

A lane's `terminal` call can return an EMPTY SUCCESS while the host tool-output channel is degraded: the
result envelope never arrives (lost) or arrives cut short (truncated), yet the command still exits 0.
`scripts/hermes_smoke.py::evaluate` collapsed every terminal result that did not carry the expected
marker — a missing envelope, a cut-off envelope, and a genuinely empty command's output — into one
generic `no terminal tool result carried <marker>` message. A lane therefore could not tell "the command
produced nothing" from "the output channel dropped the result", so the only safe action was to block,
costing a lane turn and a queue slot (issue #2269). Measured 2026-11-08: four lanes that read `running`
on the board were all dead workers, each reporting the tool-output channel degraded mid-run.

## What Changes

`scripts/hermes_smoke.py::evaluate` classifies each terminal tool-result body through a new
`envelope_kind(body)` helper instead of the single generic message:

- `lost` — the body never arrived at all (`None` / blank): a transport failure, reported as
  `` `terminal` result envelope LOST``, so a lane knows a write may have landed without being readable;
- `truncated` — a body arrived but is not a complete parseable output envelope (cut off mid-JSON):
  reported as `` `terminal` result envelope TRUNCATED``, so a partial result is never read as a clean empty;
- `empty` — a well-formed envelope whose output is genuinely empty (e.g. `true`): still read as a real
  empty command, NOT as suppression (the negative control);
- `ok` — a well-formed envelope carrying output.

Each of the two failing forms (lost, truncated) is covered by a test that reds on the pre-fix code and
passes after; a negative-control test asserts a genuinely empty result is never reported as suppression.

## Not Covered

Host process supervision, gateway CPU saturation, and the `kanban reclaim`/stuck-card defect (leaves the
card `running` after freeing the slot) — separate tracker (issue #2155). This change is the
transmission-layer half: making an empty-success distinguishable from a lost/truncated result.
