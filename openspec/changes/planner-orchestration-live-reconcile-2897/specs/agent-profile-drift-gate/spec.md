# Delta spec: agent-profile-drift-gate (planner-orchestration-live-reconcile-2897)

## ADDED Requirements

### Requirement: the reconciled live planner body stays patchable and drift-free

The planner lane's live orchestration `SKILL.md` (`~/.hermes/profiles/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`)
SHALL be brought back under the skill-writer cap (`SKILL_MAX_CHARS = 100_000` characters) by
landing the tree's split shape — the 95,033-b body plus `references/filters-and-classifiers.md`
(8,071 b), linked from SKILL.md:545 and :614 — onto the live profile with the documented deliberate
sync `make sync-agent-profile PROFILE=llgenie-planner FORCE=1`. No live content SHALL be lost: the
line-set diff's +52 live-only / −0 tree-only lines are carried by the reference file, whose 39
content lines match the live copy verbatim (measured 39/39). The tree body SHALL stay at or under
the cap by versioning large sections in `references/*.md`, never by raising the cap.

#### Scenario: the over-cap live copy is replaced from the tree

- **Given** a live planner `SKILL.md` at 102,764 b (over the 100,000-char cap) while the tree body
  is 95,033 b (94,626 chars) with its `references/filters-and-classifiers.md` linked at SKILL.md:545
  and :614
- **When** the owner/lane runs `make sync-agent-profile PROFILE=llgenie-planner FORCE=1`
- **Then** the live `SKILL.md` is byte-identical to the tree body and the reference file exists
  beside it, so the live body drops under the cap
- **And** no live content is lost: the +52 live-only inline lines remain carried by the reference
  file (39/39 content lines verbatim)
- **Test:** CI lane `ci-unit` -> `make test-unit` covers the sync/check round-trip against a fixture
  live home (`tests/test_agent_profiles.py`); the live proof is host-only
  (`make -s check-agent-profiles`), where a CI runner has no live profiles and skips audibly.

#### Scenario: the tree records the reconciliation release

- **Given** the planner orchestration `SKILL.md` frontmatter
- **When** its `version:` bumps `1.0.0 -> 1.0.1`
- **Then** the same commit carries the `agent-wiki/` note, the `docs/changes.d/` fragment and the
  `CHANGES.md` index row, and `make check-docs` exits 0
- **Test:** `make -s check-docs` reading the fragment + index with the note present and referenced
  (`docs/changes.d/2026-11-17-planner-orchestration-live-reconcile-2897.md`).

### Requirement: the drift gate reads zero fleet-wide after the reconciliation

Once the live planner skill is reconciled from the tree, `make -s check-agent-profiles` SHALL name
no llgenie-planner finding and SHALL read zero findings fleet-wide — the last finding of the
2026-11-08 measurement (586 findings) closes, so #2090's fleet-wide-zero acceptance item can tick.

#### Scenario: the fleet drift is measured at zero

- **Given** the host live profiles for every lane in `agents/manifest.json`
- **When** the owner/lane runs `make -s check-agent-profiles` after the planner sync lands
- **Then** it prints zero findings fleet-wide and exits 0 for the first time since the 2026-11-08
  baseline of 586
- **Test:** live host gate `make -s check-agent-profiles` (host-only; a CI/container checkout with
  no `~/.hermes/profiles` skips the live comparison with an audible note).
