# hermes_smoke names a lost or truncated tool-result envelope instead of an un-tracked empty success (issue #2269)

A lane's terminal call can return an EMPTY SUCCESS while the host tool-output channel is degraded: the
result envelope never arrives (lost) or arrives cut short (truncated), yet the command still exits 0.
Before this change `scripts/hermes_smoke.py::evaluate` collapsed every terminal result that did not
carry the expected marker — a missing envelope, a cut-off envelope, and a genuinely empty command's
output — into one generic `no terminal tool result carried <marker>` message. A lane therefore could
not tell "the command produced nothing" from "the output channel dropped the result", so the only safe
action was to block, costing a lane turn and a queue slot.

`evaluate` now classifies each terminal tool-result body through a new `envelope_kind` helper:

- `lost` — the body never arrived at all (`None` / blank): a transport failure, reported as `` `terminal` result
  envelope LOST``, so the lane knows a write may have landed without being readable;
- `truncated` — a body arrived but is not a complete parseable output envelope: reported as `` `terminal`
  result envelope TRUNCATED``, so a partial result is never read as a clean empty;
- `empty` — a well-formed envelope whose output is genuinely empty (e.g. `true`): still read as a real
  empty command, NOT as suppression (the negative control);
- `ok` — a well-formed envelope carrying output.

Each of the two failing forms (lost, truncated) is covered by a test that reds on the pre-fix code and
passes after; a negative-control test asserts a genuinely empty result is never reported as suppression.
The per-run nonce contract and the 10 existing `test_hermes_smoke.py` cases are unchanged.

#2269
