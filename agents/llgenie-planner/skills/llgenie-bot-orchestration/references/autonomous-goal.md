# Autonomous goal (owner, 2026-11-01)

The analyst, the product manager, and the planner do not wait to be asked for the
next improvement. The experience they steer toward: a person loads a trending
local model on the trending inference server they chose, that server fits
their hardware, and among the servers that fit it has the highest measured
tokens per second. Card RAM and Metal, CUDA, or CPU are the fit in
`scripts/detect_server.py`. A tokens-per-second number that was not measured
is not a claim. The living statement is `docs/VISION.md`. The planner does not
edit it. When the analyst and the product manager agree a sharper sentence on
an issue, the analyst opens one pull request that changes only that file, its
`agent-wiki` note, and its `docs/changes.d` row. The planner checks it and
does not merge it. The page is on `main`. It landed in pull request #1350, which closed issue #1349.

Mechanics that stay: planning happens on a parked initiative; nobody removes
`parked` or adds `ready-to-go`/`agent:implement` until the owner adds
`ready-to-go`; no dispatch, no branch, no PR without it. The planner remains the
inbox; he tracks who has commented and what is still open. Issue #1341 is the
record; #1343/#1345/#1346 stay parked. Cron cc5d2bd4083a carries the same
sentence.
