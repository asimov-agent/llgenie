# Closing the #1646 merge-close scan-evidence round-trip — 2026-11-03

`#1646` (security:high, `dockerfile.security.missing-user` in `openspec/Dockerfile`)
was merge-closed by #1655's `closes #1646` at 06:55:09Z with its scan-evidence
acceptance boxes unchecked. The fix is genuinely on live main (`08f96de5`,
`USER 65532:65532` in `openspec/Dockerfile:32`), so the finding was NOT reopened —
but the honest clearing round-trip belonged to the security line.

**Clearing evidence — a genuine completed scan on fixed main:**

- **Run:** 41601847794 (`security-scan.yml`, workflow_dispatch, `tools=all`,
  `enforce=report` non-gating)
- **Head:** `299e9a7e13` (origin/main at dispatch)
- **Result:** COMPLETED SUCCESS (guard + scan jobs both success)
- **Finding absent:** 0 matches for `semgrep:dockerfile.security.missing-user*`
  — zero `missing-user` / `openspec/Dockerfile` entries in the 29-line semgrep
  finding list (all remaining are unrelated rules in other files).
  `security_issues.py` step reported `created=0 updated=0 cleared=0` (correct:
  #1646 is already CLOSED; the scan-loop only adopts OPEN security issues).

**Box-tick (scan-evidence acceptance, ticked only on a genuine completed run):**

1. `openspec/Dockerfile:30` no longer matches the rule — fixed in source (`[x]`)
2. `make security-scan TOOL=semgrep` no longer reports missing-user for it (`[x]`)
3. the next scan closes this issue with the run that cleared it (`[x]` — names
   run 41601847794 at `299e9a7e13`)

**Guarding lesson re-confirmed on-record:** a finding whose acceptance box is
scan-evidence can be merge-closed by a bare `closes #N` with the evidence unrun.
`make security-verdict` and the fix itself are the clearing proof — a completed
scan at a named head, never the merge reference alone. This record carries the
run id and head sha so the close is auditable, not a claim about a database
snapshot.
