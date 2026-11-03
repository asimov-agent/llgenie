# Folding the security lane's live skill into the tree — 2026-11-03

Per the orchestration contract's version-here clause and #791, the live
`security-scan-ops` skill (which owns the security lane's learned rules) must
be foldable back into `agents/<profile>/` byte-identical. This fold reconciles
`agents/llgenie-security/skills/security-scan-ops/` with the live profile.

**Drift closed (live → tree, byte-identical):**

- `SKILL.md` — the tree lacked the lane's this-window lessons: never create an
  issue in a parallel batch (create one, read it back, dedupe before retry);
  a non-scanner audit finding must not carry the `security-finding:` scanner
  marker (it would be adopted/cleared by the close-loop's MARKER_RE); a
  record PR must never carry `closes <finding>`; the audit record must land
  in the tree as a committed artifact.
- `references/security-issue-review.md` — updated rule drift.
- `references/ci-run-rollup.md`, `references/rule-set-freshness.md` —
  live-only references now in the tree (a SKILL linking them otherwise reds
  `skill-reference-missing`).

**Verification:** `fold-live-profile.py --profile llgenie-security` now reports
`8 same, 0 drifted, 0 live-missing, 0 live-only`; the four folded files are
byte-identical to the live profile. Docs-only behavioural versioning; no gate
weakened, no scanner/policy change.
