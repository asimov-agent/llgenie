## ADDED Requirements

### Requirement: The architecture refresh ships its own note and row

The architecture-bot publish step SHALL, for every published doc refresh, author the
`agent-wiki/<date>-architecture-refresh-<issue>.md` note and the matching single-row
`docs/changes.d/<stem>.md` fragment (note link pointing at that exact stem) and rebuild
`CHANGES.md` from the fragments — in the SAME commit as the doc, under the bot identity.

#### Scenario: a published refresh carries four paths

- **WHEN** `publish` files a real doc change
- **THEN** the head commit touches exactly `docs/ARCHITECTURE.md`, the new note, the new
  fragment, and `CHANGES.md`
- **AND** the fragment row carries the date, a summary, the `[note](agent-wiki/<stem>.md)` link,
  and `#<issue>`

#### Scenario: the pair satisfies the change→note gate

- **WHEN** `make check-docs` inspects the published branch
- **THEN** the change→note rule finds the note and row for the doc change and stays green

#### Scenario: the model leg still writes only the doc

- **WHEN** the agent leg has written the doc and nothing else
- **THEN** `stray_changes` still guards against agent-written files, and the note/fragment/CHANGES
  trio is created by the deterministic publish step AFTER that guard has passed

#### Scenario: previews and no-drift runs write no pair

- **WHEN** `publish` runs with `--dry` or finds no drift (or an architecture PR is already open)
- **THEN** no note, no fragment, and no `CHANGES.md` rewrite happens on disk
