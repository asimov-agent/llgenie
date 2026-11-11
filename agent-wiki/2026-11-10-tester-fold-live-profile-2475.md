# Tester lane: the live-only `scripts/fold-live-profile.py` is versioned (closes #2475)

The `absent-from-tree` finding for the `llgenie-tester` lane (quoted at every
`agents/**` head since 2026-11-10) named one file: the live profile's
`skills/llgenie-pr-testing/scripts/fold-live-profile.py` (6035 b, sha256
`05f829a78e0a047dd1cac9d53bce2c9c5a627fc78001f29dc9a40f6474ac564f`). This change
copies it verbatim into the tree at the checker's named target
`agents/llgenie-tester/skills/llgenie-pr-testing/scripts/fold-live-profile.py` so
the tester lane's own fold tooling is versioned, reviewable and rebuild-proof.

Verified against the spec: the copied file is byte-identical to the live copy
(sha256 above, measured in this worktree before commit);
`make check-agent-profiles` reports zero `absent-from-tree` findings for
`llgenie-tester` at this head; the wiring guard does not scan `agents/**/scripts/`
(it scans the top-level `scripts/` tree — proven by `make check-wiring` green at
this head, not by assumption). The historical wiring incident for an earlier copy
of the same script is #1316 (closed) and stays closed.

Status: fold PR open against `main`, closing #2475. The three live→tree fold
family PRs (#2338, #2388, #2391) can now prove their remaining
no-`absent-from-tree` acceptance items after rebasing onto a main that carries
this fold.
