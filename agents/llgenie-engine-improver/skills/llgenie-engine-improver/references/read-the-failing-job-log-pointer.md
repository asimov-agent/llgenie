# Read the failing job's log first (#1791-AC3 pointer)

On a red bot-gate in this lane, **read the failing job's OWN log before any dispatch or any green/red/reviewable claim** — a conclusion is a verdict, not a cause, and a fix without the actual log is a guess. This lane's SOUL carries the discipline verbatim; the full mandatory sequence (name the run + head, find the failing job, read that job's log verbatim, attribute the root cause to THAT gate via the gate→defect map, report green only off a completed run id and head sha with no `linux/*` or guard/scope row in_progress/cancelled) is the canonical procedure:

- **Canonical reference (merged via #1840, implementer lane):**
  `agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`

Owned by the implementer lane (#791). This pointer exists so the sequence is loadable from this lane's skill surface per #1791-AC3. When this lane's engine-build or engine-install gates red, load the canonical reference above, follow its mandatory sequence, and attribute the cause to the correct gate — never forward a red as "another lane's drift" until the failing leg's own log has been read. The engine-build-specific failing-leg loop (open log → classify per `publish-run-adjudication.md` → fix that cell → re-dispatch the single engine×arch → GHCR-probe confirm) is this lane's own `references/engine-build-proof-dispatch.md` and `references/publish-run-adjudication.md`; the read-the-log-first sequence loads from the canonical reference.
