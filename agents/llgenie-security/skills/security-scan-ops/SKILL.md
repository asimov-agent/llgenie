---
name: security-scan-ops
description: "Use when the security scan reds, files nothing, or must be proven clean."
version: 1.0.0
author: LLGenie Security Officer
license: MIT
metadata:
  hermes:
    tags: [security, ci, github-actions, llgenie]
    related_skills: [github-workflow-admission, github, containerized-repo-verification]
---

# Keep the llgenie security pipeline reporting

## Inputs

`$REPO` (owner/name), the scan reports on disk (`security-reports/`), `containers/scanners/digests.json`
for the scanner refs, and `data/security-policy.json` for the severity policy.

## Output

Nothing but a report. This lane reads the scan, names exposures, and files/clears issues — it does not
implement the remediation. The one file it may write is its own `agents/llgenie-security/SOUL.md`.

## Rules

1. **A deliberate weakening is never the fix.** A red is the code or the rule, not the gate: no allowlist
   entry, no widened severity set, no `require_fix: false`, no emptied `fail_on`.
2. **Report scope, not remediation-by-patch.** What is exposed, the measurement (command + output + sha),
   who decides, the smallest fix that closes it.
3. **Secrets and identity are verified, never asserted absent.** Name the command and its answer —
   `gh auth status`, `gh secret list`, keyring, env *names* — and never print a value while checking.
4. **A scan result nobody can see is not a finding.** Publish on the issue with the sha it was measured at;
   sensitive detail goes private first, the existence and the reference never do. A scan that touches
   `scripts/` or `.github/workflows/` messages that lane with the scanned sha before it files or pushes.
5. **Every finding names the sha it scanned and the command that produced it.** Start from a fresh
   `origin/main` (`asimov-agent/llgenie` is upstream; a fork named `origin` is not) and write that sha into
   the first comment; bookend the work with a start comment (branch, main sha, what "done" means) and a
   finish comment (head sha, what changed, the command or run id that proves it, what is left open). A
   finding measured against a tree that moved is a false positive (wasted remediation) or a false negative
   (a fix assumed present); a scan that cannot name its sha is not a result.
6. **A security hold is the case where an untracked hold is itself the finding.** Name the exposure, the
   issue that closes it and the evidence that proves closure (a patch, a policy change, a scan showing
   absence), then remove the tag yourself with that evidence (#948).
7. **Never trust a write you did not read back.** `gh issue create --label` is dropped on the runner path
   (#724, #781-#784), so every write that matters is paired with a read-back that fails the step (#785).
8. **A scanner is untrusted code that holds nothing** — digest not tag, read-only mount, no write token in
   the job that ran it (#810).

## Procedure

1. **Audit** — `gh run list --workflow security-scan.yml`, then read the failing step list from
   `gh run view <id> --json jobs`. A red run whose FIRST failure is `security-verdict` means the reporting
   steps never ran: the gate is ahead of the report.
2. **Replay the run's own reports**, never infer from the summary:
   `gh run download <id> -n security-reports`, then `make security-issues-plan` and `make security-bumps-plan`.
3. **Relevance test before believing a finding** — is the named pin in a file the build installs
   (`tools/requirements*.in`/`txt`), or in a committed copy of a build-time input (#787)? A finding about a
   generated file can never clear.
4. **Prove a fix by running the scanner**: `make sbom && make security-scan TOOL=trivy`, then
   `python3 scripts/security_scan.py verdict --event schedule` -> `0 finding(s)` at a named sha.
5. **Gate before the PR**: `make check-security-scan check-security-issues check-security-bumps
   check-workflows check-docs check-wiring`; local `python3` has no pytest, so use the `llgenie/test` image.

## Never

- Never weaken a gate to make a run green (allowlist entry, widened severity set, emptied `fail_on`).
- Never put `secrets.BUMP_TOKEN` in a job that executes a pulled scanner image, and never mount the
  checkout read-write into a scanner (#810).
- Never add `push:`/`pull_request:` triggers to `security-scan.yml` — `make check-security-scan` refuses them.
- Never file a security finding without the run id and the scanner digests it was measured with (#787).
