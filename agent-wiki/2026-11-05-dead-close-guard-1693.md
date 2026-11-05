# Dead-close guard: a merged PR's `closes #N` never clears a scan-evidence box

**Issue:** #1693. The security pipeline's own loop (`scripts/security_issues.py`) is honest
(issue #1646): it only closes a finding when the next scan no longer reports it, and it comments
the run that cleared it. GitHub's merge-close-by-reference bypasses that loop entirely — a PR
merged with a bare `closes #N` closes the issue with zero scan evidence, so its acceptance box
(which reads "the next scan closes this issue with the run that cleared it") is treated as
satisfied on a run that never ran.

## The defect

`apply()` only reconciles OPEN security issues (`existing_issues` filters `--state open`). An issue
a merged PR's `closes #N` auto-closed disappears from the tracker, so on the next scan:

- the finding persists -> it is **re-filed as a duplicate** (a new issue for the same advisory),
  because the tracker no longer sees the existing key; or
- the finding has gone -> it closes silently, **without** the honest clearing comment (run id + sha)
  the #1646 round-trip requires.

Nothing re-opens or re-evidence-checks either case. A finding that is NOT fixed in source can be
silently closed this way.

## The fix

Add a `reconcile` pass (`scripts/security_issues.py`, wired as `make security-issues-reconcile` and
run in `security-scan.yml` right after `security-issues`). It reads the LIVE tracker for CLOSED
security issues carrying the scan-evidence acceptance line and **lacking** the pipeline's own
clearing comment (the signature of a merged-PR reference close, not a genuine clear). For each:

- the finding is STILL in this scan's reports -> **reopen** the issue and flag that a merged PR's
  `closes #N` does not satisfy the acceptance box (a live finding stays on the board, never
  re-filed as a duplicate);
- the finding has genuinely gone -> **post the honest clearing comment naming run id + sha**, the
  #1646 round-trip the merge-close skipped.

A closed issue that DOES carry the pipeline's clearing comment is a genuine pipeline clear and is
left untouched — no behaviour change to the honest loop, no gate weakened.

## Tests

`tests/test_security_issues.py` gains four tests over the real gh-stub seam: still-reported →
reopened+flagged; genuinely-gone → run id + sha clearing comment; genuine pipeline clear → untouched;
`--dry` → reads but rewrites nothing. 19 pass in `test_security_issues.py`.
