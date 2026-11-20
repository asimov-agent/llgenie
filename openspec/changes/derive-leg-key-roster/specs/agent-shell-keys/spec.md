## ADDED Requirements

### Requirement: The leg→job key coverage is derived from the tree
The gate suite SHALL derive the set of agent legs from the Makefile (every target whose recipe
starts `$(AGENT_IMAGE)`) and the set of leg calls from the workflow files (every step that runs
`make <target>` where `<target>` is an agent leg, directly or through a wrapper recipe that
transitively invokes one), with NO workflow, job, or leg named in the rule itself.

#### Scenario: every leg call is checked
- **WHEN** any workflow step runs `make <leg>` (or a wrapper that reaches a leg)
- **THEN** every credential the leg's recipe forwards with `-e` (minus the `NON_CREDENTIAL_ENV`
  knobs and the forced twins) MUST be set by that job's `env:` or that step's own `env:`,
  and a missing key SHALL fail `make test-unit` naming workflow, job, leg, and key.

#### Scenario: the walk is never vacuous
- **WHEN** the derived walk finds no leg call in the checkout
- **THEN** the test SHALL fail loudly rather than pass.

#### Scenario: the #364 shape is caught end-to-end
- **WHEN** a planted workflow runs a leg that forwards `-e GH_TOKEN` from a job that sets it
  only in a SIBLING step's `env:`
- **THEN** the derived walk reports the finding (red before, green after).

### Requirement: the hand-kept rosters are removed or narrowed
The four `(workflow, trigger, leg)` `entries` SHALL be removed and covered by the derived walk.
`BOT_JOBS` SHALL keep only the `agent-shell-keys-check` assertion (the key set each bot job
proves through the composite input), with a comment stating why that half stays hand-named.

#### Scenario: the four covered cases still assert
- **WHEN** the derived walk runs against the real tree
- **THEN** the calls the old `entries` pinned (fix-bot `fix-loop-image`, issue-bot
  `implement-issue`, issue-refiner `issue-refiner`, rebase-bot wrapper → `rebase-bot-agent`)
  are among the checked calls.

## MODIFIED Requirements

(None.)

## REMOVED Requirements

(None.)
