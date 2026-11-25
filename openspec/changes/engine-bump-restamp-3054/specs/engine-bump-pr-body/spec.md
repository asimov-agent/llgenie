# Spec delta: engine-bump-pr-body (issue #3054)

## ADDED Requirements

### Requirement: an already-open bump PR body is re-rendered through the same composer and written only through the guarded seam

`scripts/engine_bump_restamp.py` (behind `make engine-bump-restamp`) MUST re-render the body of every OPEN
pull request whose head branch starts with `chore/engine-bump-` through
`scripts/engine_bump_pr_body.render_body` — the ONE composer introduced by issue #3050 — and MUST write the
result only through `scripts/pr_body_write.py` (the guarded `make bot-body-write` seam, issue #2131) after
stamping it through `scripts/bot_preflight.py --stamp` (the `make bot-stamp-body` authority, issue #2050). The
leg MUST NOT compose a body itself and MUST NOT issue a raw `gh pr edit --body-file`. Bump facts (engine,
`old -> new` pins, ref, full compare shas, the documentation-review section) MUST be read from the LIVE body,
never assumed, and the run id in the proven clause MUST come from that branch's own `engine-bump.yml` run.

#### Scenario: a glued `OPENSPEC:` line becomes a resolvable reference and an acceptance section

- **Given** the recorded body shape of PR #3030 (`- **Pin:** \`3a4d82f5\` -> \`0c57b419\` (\`v0.34.0\`)` …
  `OPENSPEC: publish-changed-pin-images## Documentation review`)
- **When** the leg renders its replacement body
- **Then** `scripts/check_pr_hygiene.OPENSPEC_REF` matches the `OPENSPEC:` line, the body carries a ticked
  `## Acceptance criteria` section, and the documentation-review text the live body carried is preserved
- **Test:** `pytest tests/test_engine_bump_restamp.py -q` (recorded body payload, no network)

#### Scenario: dry mode writes nothing and names every bump it read

- **Given** the recorded open-bump-PR payloads
- **When** `make engine-bump-restamp` runs without `APPLY=1`
- **Then** one line per bump prints its number, engine, classification, `old8 -> new8` and rendered body path,
  a tally line prints `restamp <kind>=<count>`, and no body write or close call is issued
- **Test:** `pytest tests/test_engine_bump_restamp.py -q`

#### Scenario: no write path uses a raw body edit

- **Given** the leg's source and its `APPLY=1` path
- **When** the tests inspect every command the leg issues
- **Then** the body write appears only as `scripts/pr_body_write.py` and the stamp only as
  `scripts/bot_preflight.py --stamp`
- **Test:** `pytest tests/test_engine_bump_restamp.py -q`

### Requirement: a bump whose pin main already passed is closed as superseded, not re-stamped

The leg MUST classify each bump against the pin `main` actually carries — read from
`skills/engines/<engine>/SKILL.md`'s frontmatter `pinned:` on `origin/main` — and MUST report `pending`
(main holds the bump's old pin), `landed` (main already holds the bump's new pin) or `superseded` (main holds a
different pin). Only `pending` bumps are re-stamped. With `CLOSE_SUPERSEDED=1` the leg closes a `superseded`
or `landed` bump through `gh pr close` with a comment naming main's live pin as the evidence, and MUST NOT
re-stamp it; it MUST NOT merge or arm anything itself.

#### Scenario: main already carries the new pin

- **Given** a recorded bump (`old=3a4d82f5`, `new=0c57b419`) and a recorded main pin `0c57b419`
- **When** the classification runs
- **Then** it reports `landed`, no body is proposed, and with `CLOSE_SUPERSEDED=1` the close comment names
  main's pin
- **Test:** `pytest tests/test_engine_bump_restamp.py -q`

#### Scenario: main moved to a third pin

- **Given** a recorded bump (`old=11111111`, `new=22222222`) and a recorded main pin `33333333`
- **When** the classification runs
- **Then** it reports `superseded` and no body is proposed for it
- **Test:** `pytest tests/test_engine_bump_restamp.py -q`
