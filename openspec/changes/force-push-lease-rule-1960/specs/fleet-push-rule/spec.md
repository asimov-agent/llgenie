## ADDED Requirements

### Requirement: the force-push rule names the post-rebase push explicitly

The fleet standing rule SHALL state that a rebase of your own branch pushes with plain
`--force-with-lease` after a fresh fetch, and SHALL reserve `--force-if-includes` for non-rebase
force pushes, in `agents/standing-rules.md` and in every lane `SOUL.md` copy.

#### Scenario: a lane rebases and pushes
- **Given** a lane that has just fetched remote+head and rebased its own branch
- **When** it pushes the rebased branch
- **Then** the rule it follows authorizes plain `--force-with-lease`
- **And** the rule never reads as banning that push

#### Scenario: one canonical sentence, not thirteen variants
- **Given** the rule text in `agents/standing-rules.md` and each lane's `SOUL.md`
- **When** the copies are compared
- **Then** they carry the same reworded sentence
- **And** no copy retains the pre-reword ambiguity
