# Bot outcome changed-path backstop (#3124)

Bot workflows repeatedly report `completed success` and write `bot-done … fixed`
when nothing changed. This change adds one shared, reusable backstop helper and
wires it into every bot outcome step that writes a success/fixed marker, BEFORE
that marker is written. A run with no durable changed artifact ends non-success
and writes no success marker. It adds a failure mode only; no existing gate is
weakened. Per-bot root causes (#3121, #3123, #3120) stay separate.
