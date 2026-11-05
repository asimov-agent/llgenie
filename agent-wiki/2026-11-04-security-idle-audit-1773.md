# LLGenie Security Officer — emitting an empty-queue own-domain audit

Per the owner 2026-11-01 continuous-improvement contract (#1245, refined for this lane as
issue #1773), the security lane's live SOUL (authoritative, owner 2026-11-01) now encodes the
empty-queue → own-domain audit rule that was previously missing (measured: `grep`
`empty queue|own-domain|continuous|idle` over the SOUL → 0 hits at `0dcbda8a`).

## The rule now encoded (in `agents/llgenie-security/SOUL.md`)

When the reactive queue is empty (no dispatched work, no in-flight gate this lane owns), run
**one bounded own-domain audit** instead of idling — a quiet security lane that audits nothing
is indistinguishable from an idle one. Four named domains, mirroring the standing
`references/idle-audit.md` definition:

1. **scan-coverage** — which vulnerability classes the scanner misses; every reproducible result
   named by the sha it was measured at; scan stays its own pipeline (never a PR check).
2. **dependency-pin validity** — silently-unsatisfiable pins, the #1252/#1262 class; measured
   against the frozen reachable index, each pin `@ <sha>` of measurement.
3. **scan-rule-set freshness** — committed semgrep pack content-addressed and drift-free
   (`rules_sha` byte-matches the committed `default.yml`).
4. **admission-gate coverage** — which failures the pipeline cannot see; a finding is a gate
   that is not a gate, never a request to weaken one.

Findings are filed as **refined six-section tagged issues** (`agent:implement`) routed through
the normal queue — implementation belongs to the implement lane, never this auditing lane's own
pass, and never a deliberate weakening (no allowlist entry, no widened severity set, no
`require_fix: false`, no emptied `fail_on`, no inline `# nosemgrep:` carve). Use a subset check,
not equality, on any roster the tree extends. A clean audit is recorded
**`re-audited at <sha>, no findings`**. One-pass scope, no infinite loop; never overrides
reactive work.

The tree fold (`fold-live-profile.py --profile llgenie-security --copy`) also carries the lane's
live-ahead `security-scan-ops` skill gate lessons (check-pr-closing flag drift, the AGENTS/BASE
preflight body lines, staged-path hygiene) — the recurrent live→tree versioning duty (#791/#1010)
rides on the same vehicle per the owner-2026-11-01 "what you have in Hermes is the latest"
direction.

## Code / docs

Behavioural agent-profile change owed the #1123 scope gate: this note (agent-wiki),
`docs/changes.d/2026-11-04-security-idle-audit-1773.md` fragment, CHANGES.md regen, plus the
byte-identical live→tree fold of the profile files. Verified by the repo's own sync gate
(`agent_profile_sync.py --check`), `make check-docs`, `make lint` (per #1773 acceptance).
Vehicle: ready-for-review PR from `origin/main` tip `0dcbda8a`, closes #1773; #1088 sole
merge authority.