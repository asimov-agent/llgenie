# Skill-surface gates: reference resolution & new-file newline

Two reds that ONLY bite when your change touches a skill's `references/` tree or any
newly-created file. Both run inside `linux / unit`, not the docs gate.

## `skill-reference-missing` — a `references/<file>` token must live in THIS skill's own dir

The `tests/test_agent_profiles.py` gate regexes every `references/<name>` token out of a
SKILL.md body and asserts `<this-skill-dir>/references/<name>.is_file()`. A pointer written
as a CROSS-LANE path — `skills/<other-lane>/references/<name>.md` — still yields the bare
token `references/<name>`, and that file lives in the OTHER lane's tree, so the check fails
for your skill. This is the exact red the failing unit step names.

- Do NOT widen or defeat the gate, and do NOT copy the whole canonical doc into your tree.
- Fix = add a SMALL LOCAL pointer file in YOUR `references/` (named for the rule it carries)
  whose body states the rule in one line and cites the canonical file by repo path, then
  point the SKILL.md references block at that LOCAL file. This local-pointer pattern is what
  every lane uses.
- Verify before pushing: run the gate locally in the container —
  `python3 -m pytest tests/test_agent_profiles.py -q` (or the
  `scripts/check_agent_profiles.py` reference-resolution pass) — and confirm `missing refs: []`.
- **Run the tree-internal half HERMETICALLY, the way CI does — no live profile — so the tree
  checks are not drowned by another lane's live drift.** `check_agent_profiles.py check` does a
  live↔tree comparison when the host has `~/.hermes/profiles/`, and that half prints
  `absent-from-tree` rows for OTHER lanes' uncommitted live files (noise CI never sees).
  `HOME=/tmp/emptyhome python3 scripts/check_agent_profiles.py check` skips it
  (`live-profile comparison SKIPPED … tree checks only` then `OK: N host-agent profile(s)`), which
  is the CI-equivalent verdict for YOUR edit; a `skill-reference-missing` red clears to
  `MISSING: []` here once the local pointer resolves.

## A newly-created file with no trailing newline reds `ci-lint` (part of `scope`)

The file-writing tool does not append a trailing newline. Beyond `docs/changes.d`
notes/fragments, this bites a NEW `references/*.md` pointer file too. Before pushing, check
`tail -c1 <file>` on EVERY hand-written file you created and append `\n` where missing, then
run `make lint` (it sees only TRACKED files — `git add` first).

## Verify these two gates directly, not via a full host `make ci-unit`

For a docs/skill-pointer-only diff, running the full host `make ci-unit` (~8-9 min) buys nothing
the two checks above don't already prove, and its `check-engine-launchers` step reds on stale
HOST launcher tags that a clean CI container never has — noise, not a blocker. Verify
`tests/test_agent_profiles.py` (hermetic, `missing refs: []`), `make lint` (newline red), and
`skills-validate` directly; let `ci-scope` decide the heavy rows. See `local-unit-run.md` →
'`make ci-unit` on the host carries host-state checks'.
