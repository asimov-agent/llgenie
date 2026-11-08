# LLGenie Security Officer — own-domain audit re-audited at faa1af30, finding: #2241 still live

Empty-queue continuous-improvement audit (owner 2026-11-01 contract, #1245, refined #1773)
measured against **`faa1af30`** (origin/main at 2026-11-08T21:14Z) in a fresh worktree off
`origin/main`. This record accompanies the conclusion posted on the reopened audit tracker #2224.

## The finding: #2241 is NOT fixed at main faa1af30

The previous two security-lane audit records (PR #2284 @ `12276a3f` and the t_2e63b4f1 note @
`ee8679e6`) recorded #2241 (`run-shell-injection`, severity:high, component:code, in
`.github/workflows/engine-build-pr-trigger.yml:84`) as "fixed in-tree — awaits only its clearing
scan." That was **wrong at the merged tree**: the fix's acceptance rows were anchored to PR #2271's
**branch head** (`26179f46`), not to a merged main, and PR #2271 is `OPEN`/`BLOCKED`
(`reviewDecision=REVIEW_REQUIRED`, `reviewRequests=[]`), never merged.

Measured at `faa1af30` this cycle (fresh worktree, repo's own pinned scanner
`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`, rules pack `35377b8f`):

- `docker run … semgrep … scan --config …/rules/default.yml … .github/workflows/` → **1 finding**:
  `containers.scanners.semgrep.rules.yaml.github-actions.security.run-shell-injection.run-shell-injection`
  at `.github/workflows/engine-build-pr-trigger.yml:84`.
- `engine-build-pr-trigger.yml:88` verbatim at this sha:
  `make engine-build-pr-trigger BASE="${{ github.event.pull_request.base.sha }}" BRANCH="${{ github.head_ref }}"`
  (github-context interpolated directly into a `run:` shell command — the documented injection shape).
- `git merge-base --is-ancestor 26179f46 faa1af30` → NOT-ancestor (the env-hoist never reached main).

Correction posted on #2241 (`#issuecomment-6727358019`, 2026-11-08T21:27Z). The finding is
correctly `OPEN`; its fix is parked in unchanged PR #2271 (review is the affordable unblock; #2291
already re-scopes #2271's box-3 acceptance).

## The four domains, measured this cycle

1. **Scan-coverage** — #2229 re-measured: `grep -rlnE 'subprocess\.(run|check_output|Popen|check_call)\s*\('
   --include='*.py' agents/ tests/` → **137 files** (was 135 at the prior audit; the class is already
   tracked). The trivy misconfig IaC class remains shipped by #2234. **New this cycle: #2241's
   run-shell-injection was erroneously recorded fixed — it is live at main.**
2. **Dependency-pin validity** — clean: `python3 scripts/engine_pins.py inventory` → **7 pinned
   engine deps inventoried** @ `faa1af30`; `make check-security-scan` passes (3 scanner refs +
   gitleaks digest resolve). Pin-validity surface unchanged, no silently-unsatisfiable pin.
3. **Scan-rule-set freshness** — #2283/#1375 open (committed semgrep pack content-pinned `35377b8f`
   but no recency floor / no refresh path); rule-set surface unchanged this cycle.
4. **Admission-gate coverage** — #2227 open; the new #2261 surface (`registry-liveness.yml` dispatch
   step + `engine_image.py:collect`, both on `scripts/`/workflows) is covered by the existing semgrep
   github-actions rules (the full workflow subtree scan reported only the pre-existing #2241 finding).
   `make check-workflows` and `make check-gitleaks-pin` pass at this sha.

## Conclusion

A real finding this cycle: **#2241 is live at main `faa1af30`** (contradicting the prior two
records); the env-hoist fix is parked in unmerged, unreviewed PR #2271. The lane corrected the
record on #2241 and routes the fix to land; it does not implement the patch (owns
`engine-build-pr-trigger.yml`). The other three surfaces re-measured clean / unchanged.

`make check-security-scan` passes at `faa1af30`; policy sane (`fail_on: critical,high`,
`require_fix`, `enforce_events: schedule,workflow_dispatch`, no PR gate).
