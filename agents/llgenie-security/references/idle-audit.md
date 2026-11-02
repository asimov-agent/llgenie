# LLGenie Security Officer — standing idle-audit definition

Status: **concluded with the architect on issue #1245** (comment `6551420026`) and realized into the
tree as the reference home the contract names ("on #1245 **or** a reference under `agents/llgenie-security/`").
Lane: `llgenie-security`. Owns the orbit **only** — findings route through the normal implementer queue;
this lane does not implement the fixes it surfaces.

## When it runs (the trigger)

A bounded, own-domain audit runs when the lane's reactive queue is **empty for two consecutive passes**
(planner's continuous-improvement contract, #1245). "Empty" means the lane holds no actionable, non-gated
reactive work — an item parked on a real owner gate is *not* idle-capable. One-pass scope: a single bounded
run, no loop, and the audit never overrides real reactive work that arrives mid-run.

## The four measured dimensions

1. **Scan-coverage (with honesty-clamp).** Is every reproducible scan result named by the sha it was
   measured at (#787)? Is the scan still its own pipeline (schedule `04:05 UTC` + `workflow_dispatch` only),
   never a `push`/`pull_request` check (#738)? Does `data/security-policy.json` still keep `enforce_events`
   restricted and `pr_fail_on: []` so a pre-existing advisory can never red a PR? A finding in this dimension
   is a scan that cannot show its evidence, not a scoring preference.
2. **Dependency-pin validity.** Are the pinned engine install-strings (`scripts/engine_pins.py inventory` →
   `security-reports/engine-pins/`) still satisfiable against the **frozen reachable index**? Measured with
   `uv pip compile` against the pinned/frozen index, not a live-latest resolution; every pin reported as
   `@ <sha>` of the measurement, never `(local)`.
3. **Rule-set freshness.** Is the committed semgrep pack content-addressed and drift-free? `rules_sha`
   (sha256 in `containers/scanners/digests.json`) must byte-match the committed
   `containers/scanners/semgrep/rules/default.yml` at the same sha. Reading the pack from a live registry
   alias instead of the committed snapshot is a freshness finding.
4. **Admission-gate coverage.** Do the pipeline gates still do what the policy claims at the head? A red
   finding here is a gate that is not a gate (a weakened `fail_on`, a missing create→label→read-back pair,
   an un-verified `auto_merge.enabled_at`), never a request to weaken one. A deliberate weakening is never
   the fix.

## Output

A finding is filed as a **refined six-section tagged issue** (what is exposed, the measurement with command +
output + sha, who decides, the smallest fix, the route), routed through the normal implementer queue, never
implemented in the audit pass. A clean run is recorded **`re-audited at <sha>, no findings`**.

## Both clamps

- **Honesty-clamp:** no finding is asserted without its sha and run id; "not found" is only a *negative*
  measurement named by its command.
- **Coverage over cleverness:** a finding must name the exposure, the issue that closes it, and the evidence
  that proves closure — an untracked exposure is a finding in itself.
