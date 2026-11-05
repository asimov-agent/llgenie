# Status-keeper acceptance-criteria form contract (#1796 #1) via #791

Issue [#1812](https://github.com/asimov-agent/llgenie/issues/1812) requires each affected fleet lane
to carry, via #791, a stated acceptance-criteria form contract in its own versioned skill. The
`llgenie-status-keeper` lane's skill on `origin/main` (v1.0.0, dde5c9ec) did not carry the contract,
leaving #1796 #1 un-tickable (reviewer #1804 verdict comment 6669030076 held #1796 at 5/6).

## What changed

`agents/llgenie-status-keeper/skills/llgenie-status-keeper/SKILL.md`:

- Folded the live lane skill (v1.1.0, 9416 b — ahead of the tree v1.0.0) live→tree byte-identical,
  preserving the delta-flow, nerve-check, and fan-out lessons accumulated since the tree copy.
- Added the `## Acceptance-criteria form contract (#1796 #1)` section stating the contract verbatim:
  every issue this lane files AND every PR body it opens carries a `## Acceptance criteria` section
  whose items are each a `- [ ]` markdown checkbox — one per provable outcome; a criterion a
  reviewer cannot tick is not one (#745).
- Version bumped 1.1.0 → 1.2.0.

The change is text-only under `agents/llgenie-status-keeper/`, versioned via #791 with the #1724
SYNC line; no edit to `issue_body.py`, `acceptance_writeback`, or `auto-merge.yml`.

## Proof

- `diff <(git show HEAD:agents/llgenie-status-keeper/skills/llgenie-status-keeper/SKILL.md) <live SKILL.md>`:
  the fold is byte-identical; only the added contract section (at version 1.2.0) differs by +248 b.
- `make check-docs` + `make lint` green; openspec change present for the `agents/` path (gate #1810).
- #1123 change-note pair ships in this PR per the fleet convention.
