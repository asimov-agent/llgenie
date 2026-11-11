# Reading `bot_mode_dm --run-delivery` output

Every dispatch is a background `bot_mode_dm.py --run-delivery` process whose stdout is one JSON object. Only one `status` means the lane actually answered.

| status | meaning | planner action |
|---|---|---|
| `settled` | lane produced a reply; the `reply` field is its content | read it, reconcile against the live API, act |
| `queued` | receipt retained, outcome unknown | **none** — do not resend |
| `claimed` | a consumer claimed it, outcome still unknown | **none** — do not resend |

The queued/claimed payloads carry the literal `"Delivery remains pending or its outcome is unknown. Do not resend; receipt is retained."` Respect it. Re-sending a retained message risks double-instruction and duplicate vehicles.

## Consequences

- A batch of notifications that are all `queued`/`claimed` is **transport chatter, not board state** — consolidate them in one line and terminate; do not manufacture a dispatch to "respond" to them.
- `settled` is still a *claim*, not evidence. Reconcile its head shas and run ids against `gh api` before repeating them.
- A stale `settled` reply (describes a state the lane's own later action superseded) is answered by measuring live, not by re-dispatching the same order.
- A false-premise completion probe ("no mutation was attempted") is answered once by reading the mutation back from the API (`gh api .../comments/<id>`) and then refusing — never by writing a redundant comment to clear the check.
