# Acceptance write-back evidence rule

A `check-pr-acceptance` red is cleared **ONLY** with evidence a command can replay:

1. **(1) `run=<id>` at the current head** — a completed run whose `head_sha ==` the judged head.
2. **OR (2) a reproducible `command rc=<n> <sha>`** — a command + exit code + head sha you can re-run.

A **bare tick**, a `(proven: committed at head…)` claim, or a fold/sync hash **reds the gate** (#2288).

## While the run is pending
If the item needs a gates run and it is still pending, the box **stays unticked** — mark it **RUNNING**
with the pending run id. **Never tick on a pending run**: a conclusion-less row is *no verdict*; an in-flight
cell is not green proof, and it cannot be replayed.

## When to write back
Run
```
scripts/acceptance_writeback.py writeback --issue <N> --proven <item> \
  --verdict-ref '<you + comment id + head sha + run id>'
```
**only when the hermetic-unit/gates run at the current head concludes**, then **re-verify green on the wire**
(read the issue body back and re-run `make check-pr-acceptance` at that head — a write-back that goes in but
does not turn the gate green is not a landed write-back).

## Non-negotiable
- Never tick an AC on a pending/still-building run.
- Never submit a fold/sync hash or a bare "committed at head" prose claim as the `proven:` ref — the gate
  parses for `run=<id>` or `command rc=<n> <sha>`.
- After any write-back, the head is re-read **before** and the issue body **after**; if the head moved,
  re-judge and re-anchor, never PATCH a moved head.
