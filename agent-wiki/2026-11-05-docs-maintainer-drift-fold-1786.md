# Fold docs-maintainer skill references live→tree (#1786)

`make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` (byte-compares the
versioned `agents/llgenie-documentation-maintainer/` tree copy against the live profile
`~/.hermes/profiles/llgenie-documentation-maintainer/`) reded with "3 of 16 file(s) differ" and
"3 of them would SHRINK the live profile, so the tree copy is the truncated one". The live profile
(the copy that actually runs) had gained lines in two reference files and picked up four reference
files the tree did not carry at all, so the tree a reader and the drift gate trust was missing the
lane's own running guidance.

## The fix

Re-copied **live→tree byte-identically** (live is authoritative, tree follows) these six reference
files under `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/`:
`agents-soul-doc-changes.md` (8794→10343 b), `pr-merge-state-verification.md` (8124→11735 b), and
the live-only absent-from-tree refs `change-note-gate.md` (5438 b), `doc-claim-verification.md`
(2984 b), `own-domain-audit.md` (3574 b), `stale-reference-audit.md` (2306 b). Doc-only under
`agents/llgenie-documentation-maintainer/skills/...`; the lane's `SKILL.md` drift (+602 b) is the
implementer's #1771/#1785 vehicle, not this fold. Verified each of the 6 `cmp`s identical to live
at commit time, and `CHECK=1` at this head reds only on `SKILL.md` (owned by #1785).

## Verify

At the head sha: `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` —
all 6 reference files `cmp` identical to live; the single remaining `DIFFERS` is `SKILL.md`
(101247 vs 101849 b), the implementer's fold. `make lint` and `make check-docs` green at the head.
