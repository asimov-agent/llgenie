# Read the failing job's log first (#1791-AC3 pointer)

On a red bot-gate in this lane, **read the failing job's OWN log before any dispatch and before any
green/red/reviewable/mergeable claim** — a `conclusion` is a verdict, not a cause, and a fix without the
actual log is a guess (owner standing rule, versioned in the implementer SOUL). This lane's SOUL carries the
discipline verbatim; the full mandatory sequence (name the run + head, find the failing job, read that job's
log verbatim, attribute the root cause to THAT gate via the gate→defect map, report green only off a completed
run id + head sha with no `linux/*` or guard/scope row `in_progress`/`cancelled`) is the canonical procedure:

- **Canonical reference (merged via #1840, implementer lane):**
  `agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`

Owned by the implementer lane (#791). This pointer exists so the sequence is loadable from this lane's skill
surface per #1791-AC3. When a security scan guard/scope/verdict gate reds, load the canonical reference above,
follow its mandatory sequence, and attribute the cause to the correct gate — never forward a red as "another
lane's drift" until the failing leg's own log has been read. The security-scan-specific detail (a red whose
LAST step failed is the intended finding-filing red; `enforce=report` disables the verdict gate, not the
reporting steps; a red at `security-issues`/`security-bumps` is a pipeline defect to file, not a finding
signal; a stale `ci-verdict` recomputes only when its run concludes) is this lane's own
`references/scan-verification.md` and `references/ci-run-rollup.md`; the read-the-log-first sequence loads
from the canonical reference.
